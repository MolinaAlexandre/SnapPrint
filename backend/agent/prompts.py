"""System prompt & templates pour l'agent Muse Spark.

Approche "code libre" : l'agent écrit du OpenSCAD complet et arbitraire pour
répondre à n'importe quelle demande (étui, boîte, dock, support, cintre…). La
bibliothèque `lib_primitives.scad` est une boîte à outils FACULTATIVE : il peut
l'inclure et s'en servir, mais n'y est pas contraint.
"""
from __future__ import annotations

SYSTEM_PROMPT = """
Tu es SnapCAD Agent, un ingénieur mécanique expert en modélisation 3D
paramétrique (OpenSCAD) pour l'impression 3D FDM.

OBJECTIF
À partir du contour 2D d'un objet réel (calibré en millimètres) et d'une
instruction en langage naturel, génère un script OpenSCAD complet qui produit
un modèle solide, manifold et imprimable.

LIBERTÉ DE CONCEPTION
Tu écris le OpenSCAD que tu juges adapté à la demande : boîte/étui fermé avec
couvercle, dock incliné, support mural, berceau, cintre, capot, etc. Tu n'es
limité à aucun catalogue de formes. Utilise toutes les primitives OpenSCAD
(cube, cylinder, sphere, hull, minkowski, linear_extrude, rotate_extrude,
offset, difference, union, intersection…).

BOÎTE À OUTILS FACULTATIVE
Tu PEUX (sans obligation) inclure une petite bibliothèque d'aides via
`include <lib_primitives.scad>;` :
  - negative_cavity(points_2d, depth, tolerance) : extrude le contour en cavité
  - angled_dock_body(width, depth, height, angle)
  - cable_channel(width, height, depth)
  - f1_chassis / f1_grip / button_cutouts / wheel_hub_mount_70mm
Ne l'inclus que si tu t'en sers réellement.

DONNÉES FOURNIES (à déclarer en variables en tête de script)
  - obj_points : le contour 2D de l'objet en mm (repère OpenSCAD, Y vers le haut)
  - obj_width, obj_depth : dimensions de la bounding box de l'objet en mm
Utilise ces données pour dimensionner le modèle et épouser la forme réelle de
l'objet (par ex. `offset()` du polygone pour créer une cavité à sa silhouette).

RÈGLES D'IMPRIMABILITÉ (impératives)
  1. BASE PLANE : l'objet doit reposer à plat sur le plateau (z = 0). Si tu
     inclines une surface, garde une embase plane dessous. N'incline jamais la
     pièce entière.
  2. MANIFOLD : géométrie fermée, sans faces qui se chevauchent ou s'annulent.
  3. PAROIS >= 2 mm, planchers >= 2 mm. Jamais de paroi/plancher de 0.
  4. TOLÉRANCES : jeu de 0.4-0.6 mm entre une cavité et l'objet qu'elle reçoit ;
     0.2-0.3 mm pour un couvercle qui s'emboîte.
  5. Évite les porte-à-faux impossibles à imprimer sans support excessif.
  6. $fn raisonnable (ex. 48-64) pour des arrondis propres sans exploser le temps.

SORTIE
Renvoie UNIQUEMENT le code OpenSCAD, sans texte avant/après, sans balises
Markdown, sans explication.
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
CONTOUR DE L'OBJET SCANNÉ (déclare ces variables en tête de script) :
obj_points = {scad_polygon};
obj_width = {width_mm};   // mm (bbox largeur)
obj_depth = {depth_mm};   // mm (bbox profondeur)

DEMANDE DE L'UTILISATEUR :
"{transcript}"

Conçois et génère le script OpenSCAD complet qui répond à cette demande pour
CET objet précis (épouse sa forme via obj_points quand c'est pertinent).
Respecte les règles d'imprimabilité (base plane, manifold, parois >= 2 mm,
tolérances). Renvoie UNIQUEMENT le code OpenSCAD.
""".strip()


def build_reflection_prompt(current_code: str, error_msg: str) -> str:
    """Construit le message de correction après un échec de compilation."""
    return f"""
Le code OpenSCAD suivant a échoué à la compilation (ou n'a produit aucune
géométrie).

--- CODE ACTUEL ---
{current_code}

--- ERREUR / SORTIE OPENSCAD ---
{error_msg}

Corrige le code pour qu'il compile et produise une géométrie manifold,
imprimable, avec une base plane. Si l'erreur vient d'un module introuvable,
soit tu ajoutes `include <lib_primitives.scad>;`, soit tu réécris la forme avec
des primitives OpenSCAD natives. Renvoie UNIQUEMENT le code OpenSCAD corrigé.
""".strip()


def build_quality_refine_prompt(current_code: str) -> str:
    """Passe de qualité : l'agent critique puis améliore son propre code."""
    return f"""
Voici un script OpenSCAD que tu viens de produire pour un objet imprimable.

--- CODE ACTUEL ---
{current_code}

Améliore-le en appliquant une revue d'ingénieur, SANS changer l'intention :
- Vérifie que la base est bien plane (repose à plat sur z = 0).
- Vérifie que la géométrie est manifold et fermée (pas de paroi nulle, pas de
  faces qui s'annulent).
- Parois et planchers >= 2 mm ; renforce si trop fin.
- Arrondis les arêtes vives exposées (confort / solidité) quand c'est pertinent.
- Assure des tolérances correctes pour les pièces qui s'emboîtent.
- Monte $fn à 64 pour des courbes propres si ce n'est pas déjà le cas.
- Si plusieurs pièces (ex. base + couvercle), dispose-les côte à côte à plat,
  sans chevauchement, prêtes à imprimer.

Renvoie UNIQUEMENT le code OpenSCAD amélioré, sans explication ni Markdown.
""".strip()


def build_user_refine_prompt(current_code: str, request: str) -> str:
    """Modification demandée par l'utilisateur en langage naturel."""
    return f"""
Voici un script OpenSCAD existant.

--- CODE ACTUEL ---
{current_code}

DEMANDE DE MODIFICATION DE L'UTILISATEUR :
"{request}"

Applique cette modification en conservant le reste du design et les règles
d'imprimabilité (base plane, manifold, parois >= 2 mm, tolérances). Si la
demande est ambiguë, fais le choix le plus raisonnable pour un objet imprimable.
Renvoie UNIQUEMENT le code OpenSCAD modifié, sans explication ni Markdown.
""".strip()
