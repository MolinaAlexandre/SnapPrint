"""Client SAM 3.1 (Meta Model API) — segmentation d'images.

Produit deux masques binaires pleine image : l'objet cible et la pièce de
référence (1 €). SAM 3.1 est appelé via la Responses API (SDK `openai`) et sa
sortie est décodée avec `meta_sam_parser`.

En l'absence de clé API, un mode mock local (OpenCV : seuillage + Hough) génère
des masques plausibles pour garder le pipeline exécutable hors-ligne.
"""
from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from backend.config import settings


@dataclass
class SegmentationResult:
    """Deux masques binaires uint8 (0 ou 255), même résolution que l'image."""

    object_mask: np.ndarray
    coin_mask: np.ndarray


class SamClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        use_mock: Optional[bool] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.SAM_API_KEY
        self.api_base = api_base if api_base is not None else settings.SAM_API_BASE
        self.model = settings.SAM_MODEL
        # Mock si explicitement demandé, ou si pas de clé SAM.
        if use_mock is None:
            use_mock = settings.USE_MOCK_VISION or not self.api_key
        self.use_mock = use_mock

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------
    def segment(self, image_bgr: np.ndarray) -> SegmentationResult:
        """Retourne les masques de l'objet et de la pièce de référence."""
        if self.use_mock:
            return self._segment_mock(image_bgr)
        return self._segment_remote(image_bgr)

    # ------------------------------------------------------------------
    # Appel réel SAM 3.1 (Meta Model API)
    # ------------------------------------------------------------------
    def _segment_remote(self, image_bgr: np.ndarray) -> SegmentationResult:
        h, w = image_bgr.shape[:2]
        data_url = self._to_data_url(image_bgr)

        object_mask = self._segment_prompt(
            data_url, settings.SAM_OBJECT_PROMPT, (h, w)
        )
        coin_mask = self._segment_prompt(data_url, settings.SAM_COIN_PROMPT, (h, w))

        # Fiabilité : si la pièce chevauche l'objet (même masque capté),
        # on retire la pièce de l'objet pour un contour propre.
        if object_mask.any() and coin_mask.any():
            object_mask = cv2.bitwise_and(object_mask, cv2.bitwise_not(coin_mask))

        if not object_mask.any() or not coin_mask.any():
            missing = []
            if not object_mask.any():
                missing.append(f"objet ('{settings.SAM_OBJECT_PROMPT}')")
            if not coin_mask.any():
                missing.append(f"pièce ('{settings.SAM_COIN_PROMPT}')")
            raise ValueError(
                "SAM 3.1 n'a rien segmenté pour : "
                + ", ".join(missing)
                + ". Ajuste SAM_OBJECT_PROMPT / SAM_COIN_PROMPT."
            )

        return SegmentationResult(object_mask=object_mask, coin_mask=coin_mask)

    def _segment_prompt(
        self, data_url: str, prompt: str, shape_hw: tuple[int, int]
    ) -> np.ndarray:
        """Segmente une phrase nominale, renvoie un masque binaire pleine image.

        Si plusieurs objets correspondent, on fusionne tous les masques
        (union) — utile pour un objet unique, et robuste sinon on garde la
        plus grande composante via le calibrateur.
        """
        result = self._run_async(self._call_sam(data_url, prompt))
        h, w = shape_hw
        full = np.zeros((h, w), dtype=np.uint8)

        # On garde le masque le plus grand (objet principal) parmi les matches.
        best_area = 0
        best = None
        for rec in result.records:
            if type(rec).__name__ != "SegmentationMaskRecord":
                continue
            crop = self._decode_mask(rec)
            if crop is None:
                continue
            placed = self._place(crop, rec.bounds, (h, w))
            area = int((placed > 0).sum())
            if area > best_area:
                best_area, best = area, placed

        if best is not None:
            full = best
        return full

    @staticmethod
    def _run_async(coro):
        """Exécute une coroutine, même si un event loop tourne déjà (FastAPI).

        asyncio.run() échoue dans un loop actif ; on exécute donc la coroutine
        dans un thread dédié avec son propre loop.
        """
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()

    async def _call_sam(self, data_url: str, prompt: str):
        from openai import AsyncOpenAI
        import meta_sam_parser as msp

        client = AsyncOpenAI(base_url=self.api_base, api_key=self.api_key)
        stream = await client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": data_url},
                    ],
                }
            ],
            stream=True,
        )
        parsed = msp.parse_responses_stream(stream, msp.image_segmentation_format())
        async for _ in parsed:
            pass
        return await parsed.final_result()

    @staticmethod
    def _decode_mask(rec) -> Optional[np.ndarray]:
        """Décode le masque cropé (raster w*h d'octets {0,1}) en uint8 0/255."""
        import meta_sam_parser as msp

        try:
            raster = msp.decode_mask_to_raster(rec.mask)
        except Exception:  # noqa: BLE001 - masque invalide : on ignore ce record
            return None
        w, h = rec.mask.width, rec.mask.height
        arr = np.frombuffer(raster, dtype=np.uint8)
        if arr.size != w * h:
            return None
        return (arr.reshape(h, w) > 0).astype(np.uint8) * 255

    @staticmethod
    def _place(
        crop: np.ndarray, bounds, shape_hw: tuple[int, int]
    ) -> np.ndarray:
        """Replace un masque cropé dans une image pleine taille via ses bounds."""
        h, w = shape_hw
        full = np.zeros((h, w), dtype=np.uint8)
        left = max(0, int(round(bounds.left)))
        top = max(0, int(round(bounds.top)))
        ch, cw = crop.shape
        bottom = min(h, top + ch)
        right = min(w, left + cw)
        full[top:bottom, left:right] = crop[: bottom - top, : right - left]
        return full

    @staticmethod
    def _to_data_url(image_bgr: np.ndarray) -> str:
        ok, buf = cv2.imencode(".png", image_bgr)
        if not ok:
            raise ValueError("Encodage PNG de l'image échoué.")
        b64 = base64.b64encode(buf).decode()
        return f"data:image/png;base64,{b64}"

    # ------------------------------------------------------------------
    # Mode mock : heuristiques OpenCV
    # ------------------------------------------------------------------
    def _segment_mock(self, image_bgr: np.ndarray) -> SegmentationResult:
        """Approxime la segmentation sans modèle externe.

        - La pièce : détection de cercle (Hough) ; fallback = petit cercle.
        - L'objet : plus grande composante hors-fond (Otsu), pièce exclue.
        """
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        coin_mask = self._detect_coin(gray)

        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        kernel = np.ones((7, 7), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

        fg_without_coin = cv2.bitwise_and(thresh, cv2.bitwise_not(coin_mask))

        contours, _ = cv2.findContours(
            fg_without_coin, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        object_mask = np.zeros((h, w), dtype=np.uint8)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            cv2.drawContours(object_mask, [largest], -1, 255, thickness=cv2.FILLED)

        return SegmentationResult(object_mask=object_mask, coin_mask=coin_mask)

    @staticmethod
    def _detect_coin(gray: np.ndarray) -> np.ndarray:
        h, w = gray.shape
        coin_mask = np.zeros((h, w), dtype=np.uint8)
        blur = cv2.medianBlur(gray, 5)

        circles = cv2.HoughCircles(
            blur,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=min(h, w) // 4,
            param1=100,
            param2=40,
            minRadius=int(min(h, w) * 0.02),
            maxRadius=int(min(h, w) * 0.20),
        )

        if circles is not None:
            circles = np.round(circles[0, :]).astype(int)
            cx, cy, r = circles[0]
            cv2.circle(coin_mask, (cx, cy), r, 255, thickness=cv2.FILLED)
        else:
            r = int(min(h, w) * 0.05)
            cv2.circle(coin_mask, (w - 2 * r, h - 2 * r), r, 255, thickness=cv2.FILLED)

        return coin_mask
