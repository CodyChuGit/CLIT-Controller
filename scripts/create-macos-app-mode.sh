#!/usr/bin/env bash
# Generate a thin macOS app wrapper: dist/CLIT Controller IDE.app whose only job
# is to run scripts/app-mode.sh (which owns all real logic). This is convenience
# packaging only — NOT a native desktop app: no Electron, Tauri, notarization,
# updater, or separate app state. See docs/pwa-chrome-app-mode.md.
#
#   ./scripts/create-macos-app-mode.sh            # build into ./dist
#   ./scripts/create-macos-app-mode.sh /Applications
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

APP_NAME="CLIT Controller IDE"
DEST_DIR="${1:-$REPO/dist}"
APP="$DEST_DIR/$APP_NAME.app"

echo "==> Building $APP_NAME.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$APP_NAME</string>
  <key>CFBundleDisplayName</key><string>$APP_NAME</string>
  <key>CFBundleIdentifier</key><string>com.clitcontroller.appmode</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>launch</string>
  <key>CFBundleIconFile</key><string>icon</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

# Thin launcher — delegate everything to the shell script in this repo.
cat > "$APP/Contents/MacOS/launch" <<LAUNCH
#!/usr/bin/env bash
exec "$REPO/scripts/app-mode.sh"
LAUNCH
chmod +x "$APP/Contents/MacOS/launch"

# Use the promoted bean SVG source to refresh PNGs before building the .icns.
ICON_PNG="$REPO/frontend/public/icons/bean-512.png"
if command -v "$REPO/.venv/bin/python" >/dev/null 2>&1 && [ -f "$REPO/scripts/make-icons.py" ]; then
  "$REPO/.venv/bin/python" "$REPO/scripts/make-icons.py" >/dev/null 2>&1 || true
fi

if [ -f "$ICON_PNG" ] && command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
  TMP="$(mktemp -d)"; ICONSET="$TMP/icon.iconset"; mkdir -p "$ICONSET"
  for size in 16 32 128 256 512; do
    sips -z "$size" "$size" "$ICON_PNG" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null 2>&1 || true
    dbl=$(( size * 2 ))
    sips -z "$dbl" "$dbl" "$ICON_PNG" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null 2>&1 || true
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/icon.icns" >/dev/null 2>&1 && echo "==> Icon built" \
    || echo "==> warn: icon build failed; bundle uses a generic icon." >&2
else
  echo "==> warn: bean-512.png / sips / iconutil unavailable; bundle uses a generic icon." >&2
fi

touch "$APP"  # nudge Finder/Launchpad to pick up the bundle + icon
echo ""
echo "✓ Built: $APP"
echo "  Double-click it (or move to /Applications) to launch CLITC in app mode."
