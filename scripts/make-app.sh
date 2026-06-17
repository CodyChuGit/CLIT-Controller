#!/usr/bin/env bash
# Build a macOS "CLIT Controller.app" bundle so the app launches from the Dock,
# Launchpad, or Spotlight with its own icon — like vjbooth. The bundle is a thin
# launcher: double-clicking it runs ./scripts/app.sh from this repo, which serves
# the backend and opens the Chrome app window.
#
#   ./scripts/make-app.sh                  # build into ./dist-app/CLIT Controller.app
#   ./scripts/make-app.sh /Applications    # build and install into /Applications
#
# Re-run after moving the repo (the launcher hard-codes this repo's path).
set -euo pipefail
cd "$(dirname "$0")/.."

REPO="$(pwd)"
APP_NAME="CLIT Controller"
DEST_DIR="${1:-$REPO/dist-app}"
APP="$DEST_DIR/$APP_NAME.app"

echo "==> Building $APP_NAME.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

# --- Info.plist -------------------------------------------------------------
cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$APP_NAME</string>
  <key>CFBundleDisplayName</key><string>$APP_NAME</string>
  <key>CFBundleIdentifier</key><string>com.clitcontroller.app</string>
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

# --- launcher executable ----------------------------------------------------
# Open Terminal so the user can see startup/quit and Ctrl+C if needed; the
# backend + Chrome window are managed by scripts/app.sh.
cat > "$APP/Contents/MacOS/launch" <<LAUNCH
#!/usr/bin/env bash
exec "$REPO/scripts/app.sh"
LAUNCH
chmod +x "$APP/Contents/MacOS/launch"

# --- icon (SVG -> PNG via Quick Look -> .icns) ------------------------------
ICON_SRC="$(mktemp -d)/icon.svg"
cat > "$ICON_SRC" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
  <rect width="1024" height="1024" rx="220" fill="#2563eb"/>
  <g fill="none" stroke="white" stroke-width="64" stroke-linecap="round" stroke-linejoin="round" transform="translate(176 176) scale(28.4)">
    <path d="M16.9 3.7c-2.7-1.1-6.2.2-7.9 3.1-.7 1.2-1.7 2.1-3 2.7-2.8 1.3-3.7 4.8-2 7.4 2.2 3.4 7.4 4.4 11.6 2.2 4.6-2.4 6.5-8.3 4.4-12.1-.7-1.4-1.8-2.5-3.1-3.3z"/>
    <path d="M13.9 7.2c1.5.3 2.7 1.3 3.4 2.7"/>
  </g>
</svg>
SVG

if command -v qlmanage >/dev/null 2>&1 && command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
  TMP="$(mktemp -d)"
  QL_OUT="$TMP/ql"; mkdir -p "$QL_OUT"
  qlmanage -t -s 1024 -o "$QL_OUT" "$ICON_SRC" >/dev/null 2>&1 || true
  BASE="$QL_OUT/icon.svg.png"
  if [ -f "$BASE" ]; then
    ICONSET="$TMP/icon.iconset"; mkdir -p "$ICONSET"
    for size in 16 32 64 128 256 512 1024; do
      sips -z "$size" "$size" "$BASE" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null 2>&1
    done
    # @2x retina variants (a size's 2x is the next size up)
    cp "$ICONSET/icon_32x32.png"   "$ICONSET/icon_16x16@2x.png"
    cp "$ICONSET/icon_64x64.png"   "$ICONSET/icon_32x32@2x.png"
    cp "$ICONSET/icon_256x256.png" "$ICONSET/icon_128x128@2x.png"
    cp "$ICONSET/icon_512x512.png" "$ICONSET/icon_256x256@2x.png"
    cp "$ICONSET/icon_1024x1024.png" "$ICONSET/icon_512x512@2x.png"
    rm -f "$ICONSET/icon_64x64.png" "$ICONSET/icon_1024x1024.png"  # not standard iconset names
    iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/icon.icns" && echo "==> Icon built"
  else
    echo "==> warn: Quick Look could not render the icon; bundle will use a generic icon." >&2
  fi
else
  echo "==> warn: qlmanage/sips/iconutil unavailable; bundle will use a generic icon." >&2
fi

# Nudge Finder/Launchpad to pick up the new bundle + icon.
touch "$APP"

echo ""
echo "✓ Built: $APP"
if [ "$DEST_DIR" != "/Applications" ]; then
  echo "  Drag it to /Applications (or run: ./scripts/make-app.sh /Applications),"
  echo "  then launch it from Launchpad/Spotlight."
else
  echo "  Launch \"$APP_NAME\" from Launchpad or Spotlight."
fi
