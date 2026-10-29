"""SnapPrint / VoiceCAD — API FastAPI.

Pipeline :
  photo (+ voix) -> SAM (masques) -> calibration mm -> Muse Spark (SCAD)
  -> compilation OpenSCAD auto-corrigée -> STL -> visualisation Three.js.
"""
from __future__ import annotations

import io
import uuid
import zipfile
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from backend.agent.orchestrator import AgentError, Orchestrator
from backend.agent.voice import VoiceTranscriber
from backend.cad.compiler import compile_scad_with_self_healing
from backend.cad.stl_parts import split_stl_into_parts
from backend.config import settings
from backend.vision.calibrator import extract_metric_polygon
from backend.vision.sam_client import SamClient

app = FastAPI(title="SnapPrint / VoiceCAD", version="0.1.0")

# CORS pour le frontend Next.js en dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sam_client = SamClient()
transcriber = VoiceTranscriber()
orchestrator = Orchestrator()


def _decode_image(raw: bytes) -> np.ndarray:
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Image illisible / format non supporté.")
    return img


def _compile_to_job(scad_code: str):
    """Compile un code SCAD en STL (avec auto-correction) sous un nouveau job_id.

    Chemin ABSOLU (le cwd change pendant la compilation pour résoudre l'include
    de la bibliothèque). Retourne (job_id, CompileResult).
    """
    job_id = uuid.uuid4().hex[:12]
    stl_path = (settings.OUTPUT_DIR / f"{job_id}.stl").resolve()
    result = compile_scad_with_self_healing(
        scad_code=scad_code,
        output_path=stl_path,
        agent_reflector_fn=orchestrator.reflector,
        max_retries=2,
    )
    return job_id, result


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "mock_vision": settings.USE_MOCK_VISION,
        "muse_configured": bool(settings.MUSE_API_KEY),
        "baseten_configured": bool(settings.BASETEN_API_KEY),
    }


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict:
    """Transcription seule (debug / usage frontend indépendant)."""
    data = await audio.read()
    text = transcriber.transcribe(data, filename=audio.filename or "audio.webm")
    return {"transcript": text}


@app.post("/api/generate")
async def generate(
    photo: UploadFile = File(...),
    audio: UploadFile | None = File(None),
    instruction: str | None = Form(None),
    object_prompt: str | None = Form(None),
    quality: bool = Form(True),
    real_dim_mm: float | None = Form(None),
    real_dim_axis: str = Form("length"),
) -> JSONResponse:
    """Pipeline complet : photo (+ voix ou texte) -> STL.

    - `audio` (transcrit via Muse Voice) ou `instruction` (texte) : la consigne.
    - `object_prompt` : phrase nominale décrivant l'objet à détourer pour SAM.
    - `real_dim_mm` + `real_dim_axis` (width/depth/length) : dimension réelle
      connue de l'objet pour recaler l'échelle (la pièce devient facultative).
    """
    # 1. Image.
    image_bgr = _decode_image(await photo.read())

    use_real_dim = real_dim_mm is not None and real_dim_mm > 0

    # 2. Instruction : audio prioritaire, sinon texte.
    if audio is not None:
        transcript = transcriber.transcribe(
            await audio.read(), filename=audio.filename or "audio.webm"
        )
    elif instruction:
        transcript = instruction
    else:
        raise HTTPException(
            status_code=400, detail="Fournir un audio ou une instruction texte."
        )

    # 3. Segmentation SAM. Si une dimension réelle est donnée, la pièce n'est
    #    pas nécessaire (on saute sa segmentation).
    try:
        seg = sam_client.segment(
            image_bgr, object_prompt=object_prompt, need_coin=not use_real_dim
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Segmentation échouée : {exc}")

    # 4. Calibration mm + polygone.
    try:
        metric = extract_metric_polygon(
            seg.object_mask,
            seg.coin_mask if not use_real_dim else None,
            real_dim_mm=real_dim_mm if use_real_dim else None,
            real_dim_axis=real_dim_axis,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Calibration échouée : {exc}")

    # 5. Génération du code SCAD.
    scad_code = orchestrator.generate_scad(
        transcript=transcript,
        scad_polygon=metric.scad_polygon,
        width_mm=metric.width_mm,
        depth_mm=metric.depth_mm,
    )

    # 5b. Passe de qualité (optionnelle) : l'agent critique et améliore son
    #     propre code (base plane, manifold, parois, arrondis, pièces côte à
    #     côte). Désactivable pour une génération plus rapide.
    if quality:
        scad_code = orchestrator.refine_quality(scad_code)

    # 6. Compilation OpenSCAD avec auto-correction.
    job_id, result = _compile_to_job(scad_code)

    response = {
        "job_id": job_id,
        "transcript": transcript,
        "metric": {
            "width_mm": metric.width_mm,
            "depth_mm": metric.depth_mm,
            "length_mm": metric.length_mm,
            "px_to_mm": round(metric.px_to_mm, 5),
            "calibration": metric.calibration,
        },
        "success": result.success,
        "attempts": result.attempts,
        "scad_code": result.final_code,
        "errors": result.errors,
        "stl_url": f"/api/stl/{job_id}" if result.success else None,
        "parts_url": f"/api/parts/{job_id}" if result.success else None,
    }
    status = 200 if result.success else 500
    return JSONResponse(content=response, status_code=status)


@app.get("/api/stl/{job_id}")
def get_stl(job_id: str) -> FileResponse:
    """Sert le fichier STL généré."""
    # Garde-fou contre le path traversal.
    if not job_id.isalnum():
        raise HTTPException(status_code=400, detail="job_id invalide.")
    stl_path = (settings.OUTPUT_DIR / f"{job_id}.stl").resolve()
    if not stl_path.exists() or settings.OUTPUT_DIR.resolve() not in stl_path.parents:
        raise HTTPException(status_code=404, detail="STL introuvable.")
    return FileResponse(
        stl_path, media_type="model/stl", filename=f"snapprint_{job_id}.stl"
    )


@app.get("/api/parts/{job_id}")
def get_parts(job_id: str):
    """Découpe le STL en pièces (composantes connexes) et renvoie un ZIP.

    S'il n'y a qu'une pièce, le ZIP contient un seul STL.
    """
    if not job_id.isalnum():
        raise HTTPException(status_code=400, detail="job_id invalide.")
    stl_path = (settings.OUTPUT_DIR / f"{job_id}.stl").resolve()
    if not stl_path.exists() or settings.OUTPUT_DIR.resolve() not in stl_path.parents:
        raise HTTPException(status_code=404, detail="STL introuvable.")

    parts_dir = (settings.OUTPUT_DIR / f"{job_id}_parts").resolve()
    try:
        part_paths = split_stl_into_parts(stl_path, parts_dir)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Découpe STL échouée : {exc}")

    if not part_paths:
        raise HTTPException(status_code=422, detail="Aucune géométrie à découper.")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in part_paths:
            zf.write(p, arcname=p.name)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="snapprint_{job_id}_parts.zip"'
        },
    )


class RecompileBody(BaseModel):
    scad_code: str


class RefineBody(BaseModel):
    scad_code: str
    request: str


@app.post("/api/recompile")
def recompile(body: RecompileBody) -> JSONResponse:
    """Recompile un code OpenSCAD fourni (édité à la main) en STL."""
    if not body.scad_code.strip():
        raise HTTPException(status_code=400, detail="Code OpenSCAD vide.")
    job_id, result = _compile_to_job(body.scad_code)
    return JSONResponse(
        content={
            "job_id": job_id,
            "success": result.success,
            "attempts": result.attempts,
            "scad_code": result.final_code,
            "errors": result.errors,
            "stl_url": f"/api/stl/{job_id}" if result.success else None,
        "parts_url": f"/api/parts/{job_id}" if result.success else None,
        },
        status_code=200 if result.success else 500,
    )


@app.post("/api/refine")
def refine(body: RefineBody) -> JSONResponse:
    """Modifie le code via l'IA (demande en langage naturel), puis recompile."""
    if not body.scad_code.strip():
        raise HTTPException(status_code=400, detail="Code OpenSCAD vide.")
    if not body.request.strip():
        raise HTTPException(status_code=400, detail="Demande de modification vide.")
    try:
        new_code = orchestrator.refine_request(body.scad_code, body.request)
    except AgentError:
        raise HTTPException(
            status_code=503,
            detail="Modification par IA indisponible (aucun LLM configuré).",
        )
    if not new_code.strip():
        raise HTTPException(status_code=502, detail="L'IA n'a renvoyé aucun code.")
    job_id, result = _compile_to_job(new_code)
    return JSONResponse(
        content={
            "job_id": job_id,
            "success": result.success,
            "attempts": result.attempts,
            "scad_code": result.final_code,
            "errors": result.errors,
            "stl_url": f"/api/stl/{job_id}" if result.success else None,
        "parts_url": f"/api/parts/{job_id}" if result.success else None,
        },
        status_code=200 if result.success else 500,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
