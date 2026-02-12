#!/bin/bash
# Build script for creating the desktop app executable

cd "$(dirname "$0")"

# Copy utils.py from parent for bundling
cp ../utils.py ./utils.py

# Build the app using uv run (no venv needed)
echo "Building executable..."
uv run --with pyinstaller --with selenium --with webdriver-manager --with dearpygui --with imap-tools --with python-dotenv \
    pyinstaller --onefile --windowed \
    --name "AcademyAutomation" \
    --hidden-import=selenium \
    --hidden-import=webdriver_manager \
    --hidden-import=dearpygui \
    main.py

# Clean up copied utils.py
rm ./utils.py

# Create .app bundle for macOS
echo "Creating .app bundle..."
APP_DIR="dist/AcademyAutomation.app"
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# Move executable into .app
mv dist/AcademyAutomation "$APP_DIR/Contents/MacOS/"

# Copy config.json into .app (next to executable)
cp config.json "$APP_DIR/Contents/MacOS/"

# Create Info.plist
cat > "$APP_DIR/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>AcademyAutomation</string>
    <key>CFBundleIdentifier</key>
    <string>com.academy.automation</string>
    <key>CFBundleName</key>
    <string>Academy Automation</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

echo ""
echo "========================================"
echo "Build complete!"
echo "========================================"
echo ""
echo "Output: dist/AcademyAutomation.app"
echo ""
echo "Double-click to run, or:"
echo "  open dist/AcademyAutomation.app"
