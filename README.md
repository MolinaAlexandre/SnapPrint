# SnapPrint / VoiceCAD

Transforme une **photo d'objet** (calibrée par une pièce de 1 €) et une **consigne vocale**
en un **fichier STL imprimable en 3D**.

```
Photo + pièce 1€        Voix
      │                   │
   SAM 3.1          Muse Voice Transcribe
      │                   │
 Masques (objet/pièce)  Texte
      │                   │
 OpenCV calibration mm   │
      └────────┬─────────┘
               ▼
     Muse Spark (Baseten fallback) + lib_primitives.scad
               │
         code .scad
               ▼
   Compilation OpenSCAD + auto-correction
               ▼
            .STL  ──► Three.js (navigateur)
```

## Structure

```
backend/
  main.py                 API FastAPI (pipeline complet)
  config.py               Chargement .env
  vision/
    sam_client.py         SAM 3.1 (+ mock OpenCV)
    calibrator.py         Calibration mm + polygone 2D
  agent/
    orchestrator.py       Muse Spark + fallback Baseten
    prompts.py            System prompt & templates
    voice.py              Muse Voice Transcribe (+ mock)
  cad/
    compiler.py           OpenSCAD CLI + boucle d'auto-correction
    lib_primitives.scad   Bibliothèque de briques paramétriques
  outputs/                STL/SCAD générés
frontend/                 Next.js (upload, micro, viewer Three.js)
```

## Backend

Prérequis : Python 3.11+, et [OpenSCAD](https://openscad.org/downloads.html) dans le PATH.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # renseigner MUSE_API_KEY, etc.
# Lancer depuis la racine du repo (imports `backend.*`) :
cd ..
uvicorn backend.main:app --reload --port 8000
```

Sans clés API, le backend tourne en mode démo : vision mockée (OpenCV) et
gabarit SCAD local. Renseigne `MUSE_API_KEY` pour activer la voix + Muse Spark,
et/ou `BASETEN_API_KEY` pour le fallback `meta-models/muse-spark-open-1026`.

Endpoints : `GET /health`, `POST /api/transcribe`, `POST /api/generate`,
`GET /api/stl/{job_id}`.

## Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # BACKEND_URL=http://localhost:8000
npm run dev                  # http://localhost:3000
```

Les requêtes `/api/*` sont proxifiées vers le backend via `next.config.js`.

## Bibliothèque SCAD (`lib_primitives.scad`)

L'agent assemble ces modules, il ne manipule jamais de polygones bruts :
`negative_cavity`, `angled_dock_body`, `cable_channel`, `f1_chassis`,
`f1_grip`, `button_cutouts`, `wheel_hub_mount_70mm`.

## Notes

- `sam_client._segment_remote` est un stub : brancher l'API SAM 3.1 réelle quand
  les credentials sont disponibles (garder `USE_MOCK_VISION=true` sinon).
- Muse Spark / Baseten sont appelés via le schéma OpenAI `/chat/completions` ;
  ajuster si l'API réelle diffère.
