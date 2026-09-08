#!/usr/bin/env bash
# Wulfpack Forge source launcher for macOS and Linux.
# Creates a private Python environment beside this script, installs the pinned
# dependencies when requirements.txt changes, and starts the application.
set -u

cd "$(dirname "$0")" || { echo "Could not enter the Wulfpack Forge folder."; exit 1; }

if [ ! -f requirements.txt ] || [ ! -f main.py ]; then
    echo "This folder is missing requirements.txt or main.py. Extract the complete source ZIP and try again."
    exit 1
fi

VENV_DIR=".wulfpack-forge-venv"
VENV_PYTHON="$VENV_DIR/bin/python"
REQUIREMENTS_STAMP="$VENV_DIR/wulfpack-forge-requirements.txt"

find_python() {
    for candidate in python3.12 python3.13 python3.14 python3.11 python3.10 python3; do
        if command -v "$candidate" >/dev/null 2>&1 &&
           "$candidate" -c "import sys; raise SystemExit(sys.version_info[:2] not in [(3,10),(3,11),(3,12),(3,13),(3,14)])" >/dev/null 2>&1; then
            PYTHON_COMMAND="$candidate"
            return 0
        fi
    done
    return 1
}

if [ ! -x "$VENV_PYTHON" ]; then
    if ! find_python; then
        echo "Python 3.10 to 3.14 was not found. Install Python 3.12 from https://www.python.org/downloads/ and run this script again."
        exit 1
    fi
    echo "Creating Wulfpack Forge's private Python environment..."
    "$PYTHON_COMMAND" -m venv "$VENV_DIR" || { echo "Could not create the Python environment."; exit 1; }
fi

if [ ! -f "$REQUIREMENTS_STAMP" ] || ! cmp -s requirements.txt "$REQUIREMENTS_STAMP"; then
    echo "Installing Wulfpack Forge dependencies..."
    echo "The first run may take several minutes and requires an internet connection."
    "$VENV_PYTHON" -m pip install --disable-pip-version-check -r requirements.txt || { echo "Dependency installation failed."; exit 1; }
    cp requirements.txt "$REQUIREMENTS_STAMP" || { echo "Could not record the installed requirements."; exit 1; }
fi

echo "Starting Wulfpack Forge..."
"$VENV_PYTHON" main.py "$@"
APP_EXIT_CODE=$?
if [ "$APP_EXIT_CODE" -ne 0 ]; then
    echo "Wulfpack Forge exited with code $APP_EXIT_CODE. The log file is under the Wulfpack Forge workspace (logs/wulfpack-forge.log)."
fi
exit "$APP_EXIT_CODE"
