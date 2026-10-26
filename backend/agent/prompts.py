"""System prompt & templates pour l'agent Muse Spark."""
from __future__ import annotations

SYSTEM_PROMPT = """
Tu es SnapCAD Agent, un ingénieur mécanique expert en modélisation 3D paramétrique pour impression 3D.
Tu disposes d'une bibliothèque OpenSCAD native incluse via 'include <lib_primitives.scad>'.

TON OBJECTIF :
Générer un script OpenSCAD complet, solide, manifold et imprimable en 3D, basé sur :
1. Les dimensions métriques et le polygone 2D de l'objet scanné (fournis en variables).
2. L'instruction vocale de l'utilisateur.

RÈGLES D'ASSEMBLAGE :
1. NE RÉINVENTE PAS LES FORMES : Utilise les modules existants de lib_primitives.scad :
   - negative_cavity(points_2d, depth, tolerance)
   - angled_dock_body(width, depth, height, angle)
   - cable_channel(width, height, depth)
   - f1_chassis(width, height, thickness)
   - f1_grip(length, radius, angle)
   - button_cutouts([[x, y, d], ...])
   - wheel_hub_mount_70mm()

2. TOLÉRANCES D'IMPRESSION 3D :
   - Ajustement serré (support mural/dock) : tolerance = 0.5 mm
   - Encastrement écran (F1) : tolerance = 0.4 mm

3. STRUCTURE DU CODE RENDU :
   - Commence TOUJOURS par : include <lib_primitives.scad>;
   - Renvoie UNIQUEMENT le bloc de code OpenSCAD propre, sans texte d'introduction ni bavardage.
""".strip()


def build_generation_prompt(
    *,
    transcript: str,
    scad_polygon: str,
    width_mm: float,
    depth_mm: float,
) -> str:
    """Construit le message utilisateur pour la génération initiale."""
    return f"""
DONNÉES DE L'OBJET SCANNÉ :
- polygone 2D (mm, repère OpenSCAD) : {scad_polygon}
- largeur (bbox) : {width_mm} mm
- profondeur (bbox) : {depth_mm} mm

INSTRUCTION VOCALE DE L'UTILISATEUR :
"{transcript}"

Génère le script OpenSCAD complet. Déclare le polygone dans une variable
`obj_points = {scad_polygon};` puis assemble les modules de lib_primitives.scad.
Rappel : renvoie UNIQUEMENT le code OpenSCAD.
""".strip()


def build_reflection_prompt(current_code: str, error_msg: str) -> str:
    """Construit le message de correction après un échec de compilation."""
    return f"""
Le code OpenSCAD suivant a échoué à la compilation.

--- CODE ACTUEL ---
{current_code}

--- ERREUR OPENSCAD ---
{error_msg}

Corrige le code pour qu'il compile et produise une géométrie manifold imprimable.
Renvoie UNIQUEMENT le code OpenSCAD corrigé, sans explication.
""".strip()
