#!/usr/bin/env bash
# ==========================================
# SnapPrint / VoiceCAD - lanceur dev
# Démarre le backend FastAPI + le frontend Next.js, et les arrête
# proprement ensemble (Ctrl+C).
# ==========================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

VENV_PY="$ROOT/backend/.venv/bin/python"

# --- Vérifications préalables -------------------------------------------
if [ ! -x "$VENV_PY" ]; then
  echo "❌ venv backend introuvable ($VENV_PY)."
  echo "   Crée-le : python3.12 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt"
  exit 1
fi

if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "❌ node_modules du frontend absents."
  echo "   Installe-les : (cd frontend && npm install)"
  exit 1
fi

if [ ! -f "$ROOT/backend/.env" ]; then
  echo "⚠️  backend/.env absent, copie depuis .env.example."
  cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"
fi

if ! command -v openscad >/dev/null 2>&1 && ! grep -q "^OPENSCAD_BIN=/" "$ROOT/backend/.env" 2>/dev/null; then
  echo "⚠️  OpenSCAD introuvable dans le PATH. La compilation STL échouera."
  echo "   Installe-le ou renseigne OPENSCAD_BIN dans backend/.env."
fi

# --- Arrêt propre des deux process --------------------------------------
PIDS=()
cleanup() {
  echo ""
  echo "⏹  Arrêt des serveurs…"
  for pid in "${PIDS[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  # Filet de sécurité : les process enfants (reloader uvicorn, next-server).
  pkill -f "uvicorn backend.main:app" 2>/dev/null || true
  pkill -f "next dev" 2>/dev/null || true
  pkill -f "next-server" 2>/dev/null || true
  wait 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

# --- Backend ------------------------------------------------------------
echo "🚀 Backend  : http://localhost:$BACKEND_PORT  (uvicorn)"
cd "$ROOT"
"$VENV_PY" -m uvicorn backend.main:app --reload --port "$BACKEND_PORT" &
BACKEND_PID=$!
PIDS+=("$BACKEND_PID")

# --- Frontend -----------------------------------------------------------
echo "🎨 Frontend : http://localhost:$FRONTEND_PORT  (next dev)"
cd "$ROOT/frontend"
npm run dev -- --port "$FRONTEND_PORT" &
FRONTEND_PID=$!
PIDS+=("$FRONTEND_PID")
cd "$ROOT"

echo ""
echo "✅ Démarrage en cours. Ouvre http://localhost:$FRONTEND_PORT dès que c'est prêt."
echo "   Ctrl+C pour tout arrêter."
echo ""

# Surveille les deux process : si l'un meurt, on arrête l'autre.
while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

echo "⚠️  Un des serveurs s'est arrêté."
cleanup
