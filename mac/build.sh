#!/bin/bash
# Builds VibeCut.app and VibeCut-mac.zip on an Apple silicon Mac (GitHub's
# macOS runner, see .github/workflows/mac-app.yml, or a developer's Mac).
#
# Needs: Xcode (swiftc), Python 3.12+, Node 20+, network for the downloads.
# Nothing is installed outside mac/build. No key goes in: the app reads none
# from inside itself, so AI stays off until a person adds their own.
#
#   VERSION=0.1.0 mac/build.sh

set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT=$ROOT/mac/build
VERSION=${VERSION:-0.1.0}
PY=${PYTHON:-python3}
FFMPEG_URL=${FFMPEG_URL:-https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffmpeg.zip}
FFPROBE_URL=${FFPROBE_URL:-https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffprobe.zip}
YTDLP_URL=${YTDLP_URL:-https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos}

[ "$(uname -s)-$(uname -m)" = "Darwin-arm64" ] || { echo "Build on an Apple silicon Mac." >&2; exit 1; }

rm -rf "$OUT"
APP=$OUT/VibeCut.app
C=$APP/Contents
R=$C/Resources
mkdir -p "$C/MacOS" "$R/bin" "$R/helpers" "$OUT/dl"

echo "== the page"
(cd "$ROOT/web/frontend" && npm ci --no-audit --no-fund && npm run build)

echo "== the server"
"$PY" -m venv "$OUT/venv"
"$OUT/venv/bin/pip" install -q -r "$ROOT/requirements.txt" -r "$ROOT/web/requirements.txt" pyinstaller
(cd "$ROOT" && "$OUT/venv/bin/pyinstaller" --noconfirm --log-level WARN --onedir --name vibecut-server \
    --distpath "$OUT/dist" --workpath "$OUT/work" --specpath "$OUT" --paths "$ROOT" \
    --collect-submodules uvicorn --collect-submodules web --collect-submodules cutgrammar \
    --collect-submodules polish \
    --add-data "$ROOT/web/frontend/dist:web/frontend/dist" \
    --add-data "$ROOT/web/backend/looks:web/backend/looks" \
    "$ROOT/mac/server.py")
cp -R "$OUT/dist/vibecut-server" "$R/server"

echo "== the Apple helpers (built here, so the person needs no Xcode)"
# Each at the oldest macOS it compiles for; on an older Mac that one helper
# is missing and VibeCut does without it, as it does on Linux.
"$OUT/venv/bin/python" -c "import sys; sys.path.insert(0, '$ROOT'); from web.backend.remix import SWIFT; print(SWIFT, end='')" \
    > "$OUT/vibetext.swift"
helper() {   # name source [extra swiftc flags]
    local name=$1 src=$2; shift 2
    for os in 13.0 14.0 15.0 26.0; do
        if swiftc -O -target "arm64-apple-macos$os" "$@" "$src" -o "$R/helpers/$name" 2>"$OUT/$name.err"; then
            echo "$name macOS $os+" | tee -a "$R/helpers/MINIMUM.txt"
            return
        fi
    done
    echo "!! $name did not build:" >&2; tail -20 "$OUT/$name.err" >&2; exit 1
}
helper vibevision "$ROOT/web/backend/vision/vibevision.swift"
helper vibesound  "$ROOT/web/backend/sound/vibesound.swift"
helper vibeplace  "$ROOT/web/backend/place/vibeplace.swift"
helper vibespeech "$ROOT/web/backend/speech/vibespeech.swift" -parse-as-library
helper vibetext   "$OUT/vibetext.swift"

echo "== ffmpeg, ffprobe, yt-dlp"
for t in ffmpeg ffprobe; do
    url=FFMPEG_URL; [ $t = ffprobe ] && url=FFPROBE_URL
    curl -fsSL "${!url}" -o "$OUT/dl/$t.zip"
    mkdir -p "$OUT/dl/$t" && ditto -x -k "$OUT/dl/$t.zip" "$OUT/dl/$t"
    find "$OUT/dl/$t" -type f -name "$t" -exec cp {} "$R/bin/$t" \;
    chmod +x "$R/bin/$t"
    # must stand alone: nothing but the system's own libraries
    if otool -L "$R/bin/$t" | tail -n +2 | grep -v -e '/usr/lib/' -e '/System/Library/'; then
        echo "!! $t links libraries a person won't have" >&2; exit 1
    fi
done
curl -fsSL "$YTDLP_URL" -o "$R/bin/yt-dlp" && chmod +x "$R/bin/yt-dlp"
"$R/bin/ffmpeg" -hide_banner -version | head -1
"$R/bin/ffmpeg" -hide_banner -version > "$R/bin/FFMPEG-VERSION.txt"
"$R/bin/ffmpeg" -hide_banner -encoders | grep -q -e libx264 -e h264_videotoolbox ||
    { echo "!! this ffmpeg can't write H.264" >&2; exit 1; }

echo "== the window"
swiftc -O -target arm64-apple-macos14.0 "$ROOT/mac/VibeCut.swift" -o "$C/MacOS/VibeCut"
cat > "$C/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>VibeCut</string>
  <key>CFBundleDisplayName</key><string>VibeCut</string>
  <key>CFBundleIdentifier</key><string>app.vibecut.VibeCut</string>
  <key>CFBundleExecutable</key><string>VibeCut</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>LSMinimumSystemVersion</key><string>14.0</string>
  <key>LSArchitecturePriority</key><array><string>arm64</string></array>
  <key>NSHighResolutionCapable</key><true/>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
  <key>NSHumanReadableCopyright</key><string>VibeCut. Bundles ffmpeg (GPL) and yt-dlp; see Resources/NOTICE.</string>
</dict>
</plist>
EOF
cp "$ROOT/NOTICE" "$R/NOTICE"

echo "== sign (ad hoc until there is an Apple developer account)"
find "$R" -type f \( -perm -u+x -o -name '*.so' -o -name '*.dylib' \) -print0 |
    while IFS= read -r -d '' f; do
        file -b "$f" | grep -q Mach-O && codesign --force --sign - "$f" 2>/dev/null || true
    done
codesign --force --sign - "$APP"
codesign --verify --deep --strict "$APP"

echo "== smoke test: the server answers and finds its tools"
SMOKE=$OUT/smoke; mkdir -p "$SMOKE"
VIBECUT_CACHE=$SMOKE VIBECUT_EXPORTS=$SMOKE/exports VIBECUT_PORT=8799 VIBECUT_BED=0 \
    VIBECUT_HELPERS="$R/helpers" PATH="$R/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
    "$R/server/vibecut-server" > "$OUT/smoke.log" 2>&1 &
pid=$!
for _ in $(seq 120); do curl -fs http://127.0.0.1:8799/api/projects -o "$OUT/smoke.json" && break; sleep 0.5; done
cat "$OUT/smoke.json" || { cat "$OUT/smoke.log"; exit 1; }
echo
grep -q '"links": *true' "$OUT/smoke.json" || { echo "!! yt-dlp not found by the server" >&2; exit 1; }
grep -q '"speech": *true' "$OUT/smoke.json" || { echo "!! speech helper not found by the server" >&2; exit 1; }
curl -fs http://127.0.0.1:8799/ | grep -q 'id="root"' || { echo "!! the page isn't served" >&2; exit 1; }
kill $pid 2>/dev/null || true
echo "== smoke test: read a clip like an import does"
"$R/bin/ffmpeg" -v error -f lavfi -i testsrc2=size=1280x720:rate=30:duration=4 \
    -f lavfi -i sine=frequency=440:duration=4 -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest "$SMOKE/clip.mp4"
VIBECUT_CACHE=$SMOKE VIBECUT_HELPERS="$R/helpers" PATH="$R/bin:/usr/bin:/bin:/usr/sbin:/sbin" \
    "$R/server/vibecut-server" --selftest "$SMOKE/clip.mp4"

echo "== zip"
ditto -c -k --keepParent "$APP" "$OUT/VibeCut-mac.zip"
du -sh "$APP" "$OUT/VibeCut-mac.zip"
