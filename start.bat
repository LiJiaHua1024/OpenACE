@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
)
.venv\Scripts\python.exe -c "import fastapi" 2>NUL || .venv\Scripts\pip install -e ".[dev]"
if not exist frontend\node_modules (
  pushd frontend
  npm install
  popd
)
if not exist frontend\dist\index.html (
  pushd frontend
  npm run build
  popd
)
.venv\Scripts\openace-server.exe %*
