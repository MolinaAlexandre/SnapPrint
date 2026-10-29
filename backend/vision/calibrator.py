"""Vision métrique : masques SAM -> polygone 2D calibré en millimètres.

La pièce de 1 € (diamètre légal 23,25 mm) sert d'étalon pixel -> mm. On peut
aussi RECALER l'échelle sur une dimension réelle connue de l'objet (mesurée au
réglet), ce qui donne une taille exacte indépendamment de la photo.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

REFERENCE_COIN_DIAMETER_MM = 23.25  # 1 euro standard

# Axes de recalage possibles pour real_dim.
AXIS_WIDTH = "width"      # étendue X (bbox)
AXIS_DEPTH = "depth"      # étendue Y (bbox)
AXIS_LENGTH = "length"    # plus grande dimension (longueur réelle de l'objet)


@dataclass
class MetricPolygon:
    scad_polygon: str          # "[[x1, y1], [x2, y2], ...]" prêt pour OpenSCAD
    points_mm: list[list[float]]
    width_mm: float
    depth_mm: float
    length_mm: float           # plus grande dimension (min-area-rect)
    px_to_mm: float
    calibration: str           # "coin" ou "real_dim:<axis>"


def extract_metric_polygon(
    object_mask: np.ndarray,
    coin_mask: Optional[np.ndarray] = None,
    simplify_epsilon_ratio: float = 0.008,
    real_dim_mm: Optional[float] = None,
    real_dim_axis: str = AXIS_LENGTH,
) -> MetricPolygon:
    """Convertit le masque objet en polygone 2D calibré en mm.

    Échelle px->mm :
      - par défaut, via la pièce de référence (`coin_mask`) ;
      - si `real_dim_mm` est fourni, on RECALE l'échelle pour que la dimension
        choisie (`real_dim_axis`: width/depth/length) vaille exactement cette
        valeur. La pièce devient alors facultative.
    """
    # 1. Contour de l'objet en pixels + simplification Douglas-Peucker.
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

    pts_px = approx_contour.reshape(-1, 2).astype(np.float32)

    # Dimensions en PIXELS.
    bbox_w_px = float(np.max(pts_px[:, 0]) - np.min(pts_px[:, 0]))
    bbox_h_px = float(np.max(pts_px[:, 1]) - np.min(pts_px[:, 1]))
    # Plus grande dimension réelle (rectangle d'aire minimale orienté).
    (_, (rw, rh), _) = cv2.minAreaRect(approx_contour)
    length_px = float(max(rw, rh))

    # 2. Échelle px -> mm.
    calibration = "coin"
    px_to_mm: Optional[float] = None

    if real_dim_mm and real_dim_mm > 0:
        # Recalage sur une dimension réelle connue.
        ref_px = {
            AXIS_WIDTH: bbox_w_px,
            AXIS_DEPTH: bbox_h_px,
            AXIS_LENGTH: length_px,
        }.get(real_dim_axis, length_px)
        if ref_px <= 0:
            raise ValueError("Dimension de référence nulle en pixels.")
        px_to_mm = real_dim_mm / ref_px
        calibration = f"real_dim:{real_dim_axis}"
    else:
        # Étalonnage par la pièce.
        if coin_mask is None:
            raise ValueError(
                "Fournir une pièce de référence OU une dimension réelle connue."
            )
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

    # 3. Recentrage au barycentre + conversion mm (+ inversion Y OpenSCAD).
    center = np.mean(pts_px, axis=0)
    centered = (pts_px - center) * px_to_mm
    centered[:, 1] = -centered[:, 1]

    points_mm = [[round(float(p[0]), 2), round(float(p[1]), 2)] for p in centered]
    scad_points_str = "[" + ", ".join(f"[{x}, {y}]" for x, y in points_mm) + "]"

    width_mm = round(bbox_w_px * px_to_mm, 2)
    depth_mm = round(bbox_h_px * px_to_mm, 2)
    length_mm = round(length_px * px_to_mm, 2)

    return MetricPolygon(
        scad_polygon=scad_points_str,
        points_mm=points_mm,
        width_mm=width_mm,
        depth_mm=depth_mm,
        length_mm=length_mm,
        px_to_mm=px_to_mm,
        calibration=calibration,
    )
