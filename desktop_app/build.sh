#!/bin/bash
# Build script for creating the desktop app executable

cd "$(dirname "$0")"

# Copy utils.py from parent for bundling
cp ../utils.py ./utils.py

# Build the app using uv run (no venv needed). Use -y to overwrite existing build.
# Use --onedir (not --onefile) so the app launches fast — no temp extraction on each run.
# With --windowed --onedir on macOS, PyInstaller creates a proper .app bundle automatically.
echo "Building executable..."
uv run --with pyinstaller --with selenium --with webdriver-manager --with dearpygui --with imap-tools --with python-dotenv \
    pyinstaller --onedir --windowed -y \
    --name "AcademyAutomation" \
    --hidden-import=selenium \
    --hidden-import=webdriver_manager \
    --hidden-import=dearpygui \
    main.py

# Clean up copied utils.py
rm ./utils.py

# Copy config.json into the .app bundle (next to the executable)
APP_DIR="dist/AcademyAutomation.app"
cp config.json "$APP_DIR/Contents/MacOS/"

echo ""
echo "========================================"
echo "Build complete!"
echo "========================================"
echo ""
echo "Output: dist/AcademyAutomation.app"
echo ""
echo "Double-click to run, or:"
echo "  open dist/AcademyAutomation.app"
