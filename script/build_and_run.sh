#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-run}"
APP_NAME="HippoJarvis"
BUNDLE_ID="com.hippodemo.HippoJarvis"
MIN_SYSTEM_VERSION="14.0"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
APP_BUNDLE="$DIST_DIR/$APP_NAME.app"
APP_CONTENTS="$APP_BUNDLE/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_RESOURCES="$APP_CONTENTS/Resources"
APP_BINARY="$APP_MACOS/$APP_NAME"
INFO_PLIST="$APP_CONTENTS/Info.plist"
APP_ICON_NAME="HippoJarvis"
APP_ICON_SOURCE="$ROOT_DIR/Sources/HippoJarvis/Resources/HippoJarvis.icns"
MENU_BAR_ICON_SOURCE="$ROOT_DIR/Sources/HippoJarvis/Resources/HippoJarvisIcon.png"

cd "$ROOT_DIR"
pkill -x "$APP_NAME" >/dev/null 2>&1 || true
pkill -f "uvicorn orchestrator.main:app --host 127.0.0.1 --port 8787" >/dev/null 2>&1 || true

verify_launch() {
  for _ in {1..40}; do
    if pgrep -x "$APP_NAME" >/dev/null; then
      break
    fi
    sleep 0.25
  done
  pgrep -x "$APP_NAME" >/dev/null

  for _ in {1..480}; do
    if curl -fsS http://127.0.0.1:8787/health >/dev/null 2>&1; then
      sleep 2
      pgrep -x "$APP_NAME" >/dev/null
      echo "$APP_NAME verified: app process and Orchestrator health are ready"
      exit 0
    fi
    sleep 0.25
  done

  echo "$APP_NAME launched, but Orchestrator health did not become ready" >&2
  exit 1
}

orchestrator_python() {
  for candidate in \
    "$ROOT_DIR/orchestrator-runtime/bin/python" \
    "/opt/anaconda3/bin/python" \
    "/opt/homebrew/bin/python3" \
    "/usr/bin/python3"; do
    if [[ -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

start_orchestrator_for_verify() {
  if curl -fsS http://127.0.0.1:8787/health >/dev/null 2>&1; then
    return 0
  fi

  local python
  python="$(orchestrator_python)"
  mkdir -p "$ROOT_DIR/.runtime"
  HIPPODEMO_ROOT="$ROOT_DIR" \
  HIPPODEMO_PYTHON="$python" \
  OWNSCRIBE_PYTHON="$python" \
  PYTHONPATH="$ROOT_DIR" \
  nohup "$python" -m uvicorn orchestrator.main:app --host 127.0.0.1 --port 8787 \
    >>"$ROOT_DIR/.runtime/orchestrator-app.log" 2>&1 &
  echo "$!" >"$ROOT_DIR/.runtime/orchestrator-app.pid"
}

case "$MODE" in
  --restart-no-build|restart-no-build)
    if [[ ! -x "$APP_BINARY" ]]; then
      echo "$APP_BINARY does not exist; run $0 --verify once to build the app bundle" >&2
      exit 2
    fi
    /usr/bin/open -n "$APP_BUNDLE"
    verify_launch
    ;;
esac

swift build --product "$APP_NAME"
BUILD_DIR="$(swift build --show-bin-path)"
BUILD_BINARY="$BUILD_DIR/$APP_NAME"

rm -rf "$APP_BUNDLE"
mkdir -p "$APP_MACOS" "$APP_RESOURCES"
cp "$BUILD_BINARY" "$APP_BINARY"
chmod +x "$APP_BINARY"
if [[ -f "$APP_ICON_SOURCE" ]]; then
  cp "$APP_ICON_SOURCE" "$APP_RESOURCES/$APP_ICON_NAME.icns"
fi
if [[ -f "$MENU_BAR_ICON_SOURCE" ]]; then
  cp "$MENU_BAR_ICON_SOURCE" "$APP_RESOURCES/HippoJarvisIcon.png"
fi

cat >"$INFO_PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>$APP_NAME</string>
  <key>CFBundleIdentifier</key>
  <string>$BUNDLE_ID</string>
  <key>CFBundleIconFile</key>
  <string>$APP_ICON_NAME</string>
  <key>CFBundleName</key>
  <string>$APP_NAME</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSMinimumSystemVersion</key>
  <string>$MIN_SYSTEM_VERSION</string>
  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
  <key>NSMicrophoneUsageDescription</key>
  <string>HippoJarvis records meeting audio from the microphone when Jarvis is enabled.</string>
  <key>NSAppTransportSecurity</key>
  <dict>
    <key>NSAllowsLocalNetworking</key>
    <true/>
  </dict>
</dict>
</plist>
PLIST

/usr/bin/codesign --force --sign - --identifier "$BUNDLE_ID" "$APP_BUNDLE" >/dev/null

open_app() {
  /usr/bin/open -n "$APP_BUNDLE"
}

case "$MODE" in
  run)
    open_app
    ;;
  --debug|debug)
    lldb -- "$APP_BINARY"
    ;;
  --logs|logs)
    open_app
    /usr/bin/log stream --info --style compact --predicate "process == \"$APP_NAME\""
    ;;
  --telemetry|telemetry)
    open_app
    /usr/bin/log stream --info --style compact --predicate "subsystem == \"$BUNDLE_ID\""
    ;;
  --verify|verify)
    start_orchestrator_for_verify
    open_app
    verify_launch
    ;;
  *)
    echo "usage: $0 [run|--debug|--logs|--telemetry|--verify|--restart-no-build]" >&2
    exit 2
    ;;
esac
