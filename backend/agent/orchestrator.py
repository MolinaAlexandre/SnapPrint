"""Orchestrateur agentique : génération de code OpenSCAD via Muse Spark.

Appelle Muse Spark en priorité, et bascule sur Muse Spark Open (Baseten)
en cas d'indisponibilité. Expose aussi un `reflector` branché sur la boucle
d'auto-correction du compilateur.

Les deux endpoints sont supposés compatibles avec le schéma OpenAI
`/chat/completions`. Ajustez si l'API réelle diffère.
"""
from __future__ import annotations

import re

import httpx

from backend.agent.prompts import (
    SYSTEM_PROMPT,
    build_generation_prompt,
    build_reflection_prompt,
)
from backend.config import settings

# Gabarit de secours si aucune API n'est configurée (démo hors-ligne).
_FALLBACK_SCAD_TEMPLATE = """include <lib_primitives.scad>;

obj_points = {polygon};
obj_depth = 12;

difference() {{
    angled_dock_body(width = {width}, depth = {depth}, height = 25, angle = 20);
    translate([0, 0, 6])
        negative_cavity(obj_points, obj_depth, tolerance = 0.5);
    translate([0, {depth_half}, 0])
        cable_channel(width = 6, height = 35, depth = 10);
}}
"""


class AgentError(RuntimeError):
    pass


def _extract_scad(text: str) -> str:
    """Extrait le code OpenSCAD d'une réponse LLM (retire les ```fences)."""
    fenced = re.search(r"```(?:scad|openscad)?\s*(.*?)```", text, re.DOTALL)
    code = fenced.group(1) if fenced else text
    return code.strip()


class Orchestrator:
    def __init__(self) -> None:
        self.muse_key = settings.MUSE_API_KEY
        self.muse_base = settings.MUSE_API_BASE
        self.muse_model = settings.MUSE_SPARK_MODEL
        self.baseten_key = settings.BASETEN_API_KEY
        self.baseten_base = settings.BASETEN_API_BASE
        self.baseten_model = settings.BASETEN_MODEL

    # ------------------------------------------------------------------
    # Appels LLM
    # ------------------------------------------------------------------
    def _chat(self, base: str, key: str, model: str, user_msg: str) -> str:
        url = f"{base.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.2,
        }
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            payload = resp.json()
            return payload["choices"][0]["message"]["content"]

    def _complete(self, user_msg: str) -> str:
        """Muse Spark en priorité, fallback Baseten, puis gabarit local."""
        if self.muse_key:
            try:
                return self._chat(
                    self.muse_base, self.muse_key, self.muse_model, user_msg
                )
            except httpx.HTTPError as exc:
                print(f"[agent] Muse Spark indisponible, fallback Baseten : {exc}")

        if self.baseten_key:
            try:
                return self._chat(
                    self.baseten_base,
                    self.baseten_key,
                    self.baseten_model,
                    user_msg,
                )
            except httpx.HTTPError as exc:
                print(f"[agent] Baseten indisponible : {exc}")

        raise AgentError("no_llm_available")

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------
    def generate_scad(
        self,
        *,
        transcript: str,
        scad_polygon: str,
        width_mm: float,
        depth_mm: float,
    ) -> str:
        """Génère le code OpenSCAD initial depuis la transcription + le polygone."""
        user_msg = build_generation_prompt(
            transcript=transcript,
            scad_polygon=scad_polygon,
            width_mm=width_mm,
            depth_mm=depth_mm,
        )
        try:
            raw = self._complete(user_msg)
            return _extract_scad(raw)
        except AgentError:
            # Démo hors-ligne : gabarit déterministe assemblant la bibliothèque.
            print("[agent] Aucun LLM configuré, usage du gabarit SCAD local.")
            return _FALLBACK_SCAD_TEMPLATE.format(
                polygon=scad_polygon,
                width=max(width_mm + 20, 60),
                depth=max(depth_mm + 20, 60),
                depth_half=round((depth_mm + 20) / 2, 2),
            )

    def reflector(self, current_code: str, error_msg: str) -> str:
        """Callback d'auto-correction pour le compilateur."""
        user_msg = build_reflection_prompt(current_code, error_msg)
        try:
            raw = self._complete(user_msg)
            return _extract_scad(raw)
        except AgentError:
            # Sans LLM, on ne peut pas corriger : on renvoie le code tel quel.
            print("[agent] Pas de LLM pour l'auto-correction, code inchangé.")
            return current_code
