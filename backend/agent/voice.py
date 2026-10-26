"""Muse Voice Transcribe — transcription audio -> texte.

En l'absence de clé Muse, renvoie une transcription mock pour garder le
pipeline exécutable en démo.
"""
from __future__ import annotations

import httpx

from backend.config import settings

_MOCK_TRANSCRIPT = (
    "Fais-moi un dock incliné pour poser ma souris avec un passage de câble."
)


class VoiceTranscriber:
    def __init__(self, api_key: str | None = None, api_base: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.MUSE_API_KEY
        self.api_base = api_base if api_base is not None else settings.MUSE_API_BASE
        self.model = settings.MUSE_VOICE_MODEL

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        """Transcrit l'audio. Mock si pas de clé Muse configurée."""
        if not self.api_key:
            return _MOCK_TRANSCRIPT

        url = f"{self.api_base.rstrip('/')}/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        files = {"file": (filename, audio_bytes, "application/octet-stream")}
        data = {"model": self.model}

        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, headers=headers, files=files, data=data)
                resp.raise_for_status()
                payload = resp.json()
                # Format type OpenAI/Whisper : {"text": "..."}
                return payload.get("text", "").strip() or _MOCK_TRANSCRIPT
        except (httpx.HTTPError, ValueError) as exc:  # pragma: no cover
            print(f"[voice] Transcription Muse échouée, fallback mock : {exc}")
            return _MOCK_TRANSCRIPT
