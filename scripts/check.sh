#!/usr/bin/env bash
# Every check CI runs, in one command: lint, format, types, card syntax, tests with coverage.
set -euo pipefail
cd "$(dirname "$0")/.."

# The integration depends on the frontend and camera components: install the
# packages they pin for the installed Home Assistant version (no-op when present).
python - <<'PY'
import importlib, importlib.util, json, pathlib, subprocess, sys
for component, module in (("frontend", "hass_frontend"), ("camera", "turbojpeg")):
    if importlib.util.find_spec(module) is None:
        package = importlib.import_module("homeassistant.components").__path__[0]
        manifest = json.loads((pathlib.Path(package) / component / "manifest.json").read_text())
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *manifest["requirements"]])
PY

ruff check .
ruff format --check .
mypy
# The card is an ES module: check its syntax as one.
cp custom_components/meter_vision/frontend/meter-vision-card.js "${TMPDIR:-/tmp}/meter-vision-card.mjs"
node --check "${TMPDIR:-/tmp}/meter-vision-card.mjs"
pytest -q --cov --cov-report=term "$@"
