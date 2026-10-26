"""Compilation OpenSCAD avec boucle d'auto-correction (reflection loop).

En cas d'erreur de compilation, l'agent est rappelé avec le message d'erreur
OpenSCAD pour corriger le code, jusqu'à `max_retries` fois.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from backend.config import settings

# Signature du callback de correction : (code_actuel, message_erreur) -> code_corrigé
ReflectorFn = Callable[[str, str], str]


@dataclass
class CompileResult:
    success: bool
    stl_path: str | None
    final_code: str
    attempts: int
    errors: list[str] = field(default_factory=list)


def _ensure_openscad_available() -> str:
    """Retourne le chemin de l'exécutable OpenSCAD ou lève une erreur claire."""
    bin_path = settings.OPENSCAD_BIN
    resolved = shutil.which(bin_path) or (bin_path if Path(bin_path).exists() else None)
    if not resolved:
        raise FileNotFoundError(
            f"OpenSCAD introuvable (OPENSCAD_BIN='{bin_path}'). "
            "Installez OpenSCAD et/ou ajustez OPENSCAD_BIN dans .env."
        )
    return resolved


def compile_scad_with_self_healing(
    scad_code: str,
    output_path: str | Path,
    agent_reflector_fn: ReflectorFn,
    max_retries: int = 2,
) -> CompileResult:
    """Compile le code OpenSCAD en STL, avec auto-correction en cas d'échec."""
    openscad_bin = _ensure_openscad_available()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    current_code = scad_code
    errors: list[str] = []

    for attempt in range(max_retries + 1):
        temp_scad_file = output_path.with_suffix(".scad")
        temp_scad_file.write_text(current_code, encoding="utf-8")

        # -o sortie STL, et include-dir pour résoudre lib_primitives.scad.
        cmd = [
            openscad_bin,
            "-o",
            str(output_path),
            temp_scad_file.as_posix(),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(settings.CAD_LIB_DIR),  # résout include <lib_primitives.scad>
        )

        if result.returncode == 0 and output_path.exists():
            return CompileResult(
                success=True,
                stl_path=str(output_path),
                final_code=current_code,
                attempts=attempt + 1,
                errors=errors,
            )

        error_msg = result.stderr.strip() or result.stdout.strip() or "Erreur inconnue"
        errors.append(error_msg)
        print(f"[compile] Tentative {attempt + 1} échouée : {error_msg}")

        if attempt < max_retries:
            current_code = agent_reflector_fn(current_code, error_msg)

    return CompileResult(
        success=False,
        stl_path=None,
        final_code=current_code,
        attempts=max_retries + 1,
        errors=errors,
    )
