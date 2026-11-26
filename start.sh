#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import fastapi' 2>/dev/null; then
  .venv/bin/pip install -e '.[dev]'
fi
if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install)
fi
if [ ! -f frontend/dist/index.html ]; then
  (cd frontend && npm run build)
fi
exec .venv/bin/openace-server "$@"
