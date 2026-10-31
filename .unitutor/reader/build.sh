#!/bin/bash
# Builds "Lecture Reader.app" into ~/Applications so Spotlight finds it.
set -euo pipefail
cd "$(dirname "$0")"
APP="${1:-$HOME/Applications/Lecture Reader.app}"
swift build -c release
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp .build/release/LectureReader "$APP/Contents/MacOS/LectureReader"
cp Info.plist "$APP/Contents/Info.plist"
ICONSET="$(mktemp -d)/AppIcon.iconset"
mkdir -p "$ICONSET"
for s in 16 32 128 256 512; do
  sips -z $s $s lecture.png --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) lecture.png --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns"
codesign --force --sign - "$APP"
echo "Built: $APP"
