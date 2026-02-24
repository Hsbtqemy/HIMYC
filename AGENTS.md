# AGENTS.md

## Cursor Cloud specific instructions

### Overview

HowIMetYourCorpus (HIMYC) is a PySide6 desktop application for building, normalizing, and exploring multilingual TV transcript corpora. It is a single-process desktop app with an embedded SQLite database — no external services or Docker needed.

### Running the application

```bash
source .venv/bin/activate
DISPLAY=:1 PYTHONPATH=src python -m howimetyourcorpus.app.main
```

For headless/offscreen mode (no GUI rendering):

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m howimetyourcorpus.app.main
```

### Running tests

```bash
source .venv/bin/activate
QT_QPA_PLATFORM=offscreen PYTHONPATH=src python -m pytest tests/ -v
```

All 184 tests run with `QT_QPA_PLATFORM=offscreen` to avoid requiring a real display. The UI tests use PySide6 widgets in offscreen mode and work correctly.

### System dependencies for PySide6

The following system packages are required for PySide6 to load the xcb platform plugin (needed for GUI display on X11):

- `libegl1`, `libopengl0`, `libxcb-cursor0`, `libxcb-xinerama0`, `libxcb-xkb1`, `libxkbcommon-x11-0`, `libxcb-icccm4`, `libxcb-keysyms1`, `libxcb-image0`, `libxcb-render-util0`

These are already installed in the Cloud VM snapshot.

### Gotchas

- **No linter configured**: The project has no ruff/flake8/pylint/mypy configuration. Syntax checking is done via `python -m py_compile` or import verification.
- **Example project database**: If `example/corpus.db` has migration issues, reset it with `PYTHONPATH=src python example/reset_example.py`.
- **Package install mode**: Always install in editable mode with dev and align extras: `pip install -e ".[dev,align]"`.
- **`python3.12-venv`**: The system `python3.12-venv` apt package must be installed before creating a virtualenv.

### Project structure

See `README.md` for full project structure, usage instructions, and workflow documentation.
