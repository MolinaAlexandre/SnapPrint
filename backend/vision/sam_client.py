"""Client SAM 3.1 (Meta) — segmentation d'images.

Produit deux masques binaires : l'objet cible et la pièce de référence (1 €).
En l'absence de clé API / de endpoint SAM, un mode mock local génère des masques
plausibles à partir de l'image (seuillage + détection de cercle) afin que le
pipeline complet reste exécutable hors-ligne.
"""
from __future__ import annotations

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
        # Mock si explicitement demandé, ou si pas de credentials SAM.
        if use_mock is None:
            use_mock = settings.USE_MOCK_VISION or not (self.api_key and self.api_base)
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
    # Appel réel SAM 3.1 (à brancher sur l'endpoint Meta)
    # ------------------------------------------------------------------
    def _segment_remote(self, image_bgr: np.ndarray) -> SegmentationResult:
        # TODO: implémenter l'appel HTTP réel vers SAM 3.1.
        # Le format d'entrée/sortie exact dépend de l'API Meta finale.
        # On encode l'image en PNG, on envoie, on décode les masques retournés.
        raise NotImplementedError(
            "Appel SAM 3.1 distant non implémenté. "
            "Renseignez SAM_API_KEY / SAM_API_BASE et implémentez _segment_remote, "
            "ou gardez USE_MOCK_VISION=true."
        )

    # ------------------------------------------------------------------
    # Mode mock : heuristiques OpenCV
    # ------------------------------------------------------------------
    def _segment_mock(self, image_bgr: np.ndarray) -> SegmentationResult:
        """Approxime la segmentation sans modèle externe.

        - La pièce : détection de cercle (Hough) ; fallback = petit cercle au centre.
        - L'objet : plus grande composante hors-fond (seuillage Otsu), pièce exclue.
        """
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        coin_mask = self._detect_coin(gray)

        # Seuillage Otsu pour séparer l'avant-plan du fond.
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # Nettoyage morphologique.
        kernel = np.ones((7, 7), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

        # On retire la zone de la pièce de l'avant-plan.
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
            # On prend le cercle le plus "net" (premier retourné par Hough).
            cx, cy, r = circles[0]
            cv2.circle(coin_mask, (cx, cy), r, 255, thickness=cv2.FILLED)
        else:
            # Fallback : petit cercle en bas à droite pour garder le pipeline vivant.
            r = int(min(h, w) * 0.05)
            cv2.circle(coin_mask, (w - 2 * r, h - 2 * r), r, 255, thickness=cv2.FILLED)

        return coin_mask
