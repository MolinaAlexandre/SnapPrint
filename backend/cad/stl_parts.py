"""Découpe un STL en pièces séparées par composantes connexes.

Un STL ne contient aucune notion de "pièce" : juste des triangles. On regroupe
les triangles qui partagent des sommets (union-find) pour isoler les îlots
géométriques distincts (ex. base + couvercle posés côte à côte), et on écrit un
STL binaire par îlot. Si tout est connecté, on obtient une seule pièce.
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np


def _read_stl(path: Path) -> np.ndarray:
    """Lit un STL (binaire ou ASCII) -> tableau (N, 3, 3) de triangles."""
    data = path.read_bytes()

    # ASCII si ça commence par "solid" ET contient "facet" en texte.
    is_ascii = data[:5].lower() == b"solid" and b"facet" in data[:1024].lower()
    if is_ascii:
        return _read_ascii(data.decode("utf-8", "replace"))
    return _read_binary(data)


def _read_binary(data: bytes) -> np.ndarray:
    n = struct.unpack_from("<I", data, 80)[0]
    tris = np.empty((n, 3, 3), dtype=np.float64)
    off = 84
    for i in range(n):
        # 12 floats après la normale (3 floats) ; on saute la normale.
        vals = struct.unpack_from("<12f", data, off)
        tris[i, 0] = vals[3:6]
        tris[i, 1] = vals[6:9]
        tris[i, 2] = vals[9:12]
        off += 50
    return tris


def _read_ascii(text: str) -> np.ndarray:
    verts = []
    cur = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("vertex"):
            _, x, y, z = s.split()
            cur.append((float(x), float(y), float(z)))
            if len(cur) == 3:
                verts.append(cur)
                cur = []
    return np.asarray(verts, dtype=np.float64)


class _UnionFind:
    def __init__(self, n: int) -> None:
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def _write_binary_stl(path: Path, tris: np.ndarray) -> None:
    n = len(tris)
    with path.open("wb") as f:
        f.write(b"SnapPrint part" + b"\0" * (80 - 14))
        f.write(struct.pack("<I", n))
        for t in tris:
            v0, v1, v2 = t[0], t[1], t[2]
            normal = np.cross(v1 - v0, v2 - v0)
            norm = np.linalg.norm(normal)
            normal = normal / norm if norm > 0 else np.zeros(3)
            f.write(struct.pack("<3f", *normal))
            for v in (v0, v1, v2):
                f.write(struct.pack("<3f", *v))
            f.write(struct.pack("<H", 0))


def split_stl_into_parts(
    stl_path: str | Path, out_dir: str | Path, quantize: int = 4
) -> list[Path]:
    """Découpe le STL en composantes connexes -> liste de fichiers STL écrits.

    `quantize` : nombre de décimales pour considérer deux sommets identiques
    (soude les sommets quasi-coïncidents issus de facettes adjacentes).
    """
    stl_path = Path(stl_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tris = _read_stl(stl_path)
    n = len(tris)
    if n == 0:
        return []

    # Index de sommets soudés (quantifiés) -> union-find triangle par triangle.
    vert_id: dict[tuple, int] = {}

    def vid(p) -> int:
        key = (round(float(p[0]), quantize),
               round(float(p[1]), quantize),
               round(float(p[2]), quantize))
        idx = vert_id.get(key)
        if idx is None:
            idx = len(vert_id)
            vert_id[key] = idx
        return idx

    tri_verts = np.empty((n, 3), dtype=np.int64)
    for i in range(n):
        tri_verts[i] = (vid(tris[i, 0]), vid(tris[i, 1]), vid(tris[i, 2]))

    # Union des triangles partageant un sommet : on relie via le 1er triangle
    # qui a touché chaque sommet.
    uf = _UnionFind(n)
    first_tri_of_vert: dict[int, int] = {}
    for i in range(n):
        for v in tri_verts[i]:
            v = int(v)
            if v in first_tri_of_vert:
                uf.union(i, first_tri_of_vert[v])
            else:
                first_tri_of_vert[v] = i

    # Regroupe les triangles par composante.
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(uf.find(i), []).append(i)

    # Trie les composantes par taille décroissante pour nommer part_1 = la plus grande.
    comps = sorted(groups.values(), key=len, reverse=True)

    paths: list[Path] = []
    stem = stl_path.stem
    for k, idxs in enumerate(comps, start=1):
        part = tris[idxs]
        out = out_dir / f"{stem}_part{k}.stl"
        _write_binary_stl(out, part)
        paths.append(out)
    return paths
