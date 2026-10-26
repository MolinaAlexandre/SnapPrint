"""Vision métrique : masques SAM -> polygone 2D calibré en millimètres.

La pièce de 1 € (diamètre légal 23,25 mm) sert d'étalon pixel -> mm.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

REFERENCE_COIN_DIAMETER_MM = 23.25  # 1 euro standard


@dataclass
class MetricPolygon:
    scad_polygon: str          # "[[x1, y1], [x2, y2], ...]" prêt pour OpenSCAD
    points_mm: list[list[float]]
    width_mm: float
    depth_mm: float
    px_to_mm: float


def extract_metric_polygon(
    object_mask: np.ndarray,
    coin_mask: np.ndarray,
    simplify_epsilon_ratio: float = 0.008,
) -> MetricPolygon:
    """Convertit le masque de segmentation en polygone 2D calibré en mm."""
    # 1. Ratio pixel -> mm via la pièce de référence.
    coin_contours, _ = cv2.findContours(
        coin_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not coin_contours:
        raise ValueError("Pièce de référence non détectée.")

    coin_contour = max(coin_contours, key=cv2.contourArea)
    (_, _), radius_px = cv2.minEnclosingCircle(coin_contour)
    diameter_px = radius_px * 2.0
    if diameter_px <= 0:
        raise ValueError("Diamètre de la pièce invalide (0 px).")
    px_to_mm = REFERENCE_COIN_DIAMETER_MM / diameter_px

    # 2. Contour de l'objet + simplification Douglas-Peucker.
    obj_contours, _ = cv2.findContours(
        object_mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )
    if not obj_contours:
        raise ValueError("Objet cible non détecté.")

    main_contour = max(obj_contours, key=cv2.contourArea)
    epsilon = simplify_epsilon_ratio * cv2.arcLength(main_contour, True)
    approx_contour = cv2.approxPolyDP(main_contour, epsilon, True)

    if len(approx_contour) < 3:
        raise ValueError("Contour objet trop simple (< 3 points).")

    # 3. Recentrage au barycentre + conversion mm.
    pts = approx_contour.reshape(-1, 2).astype(np.float32)
    center = np.mean(pts, axis=0)
    centered_pts = (pts - center) * px_to_mm

    # Inversion Y (repère image -> repère cartésien OpenSCAD).
    centered_pts[:, 1] = -centered_pts[:, 1]

    points_mm = [[round(float(p[0]), 2), round(float(p[1]), 2)] for p in centered_pts]
    scad_points_str = "[" + ", ".join(f"[{x}, {y}]" for x, y in points_mm) + "]"

    bbox_width = float(np.max(centered_pts[:, 0]) - np.min(centered_pts[:, 0]))
    bbox_depth = float(np.max(centered_pts[:, 1]) - np.min(centered_pts[:, 1]))

    return MetricPolygon(
        scad_polygon=scad_points_str,
        points_mm=points_mm,
        width_mm=round(bbox_width, 2),
        depth_mm=round(bbox_depth, 2),
        px_to_mm=px_to_mm,
    )
