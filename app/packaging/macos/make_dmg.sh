#!/usr/bin/env bash
# AstroForge macOS dmg 打包脚本（Phase 8 / Phase 10.4，方案补丁 8）
# 前置：flutter build macos --release；可选 create-dmg（brew install create-dmg）
# 产物：dist/AstroForge_x.y.z.dmg（内含 ad-hoc 签名的 .app）
set -e
cd "$(dirname "$0")/../../.."   # -> app/
APP_NAME="AstroForge"
VERSION=$(grep -o 'version: [0-9.]*' pubspec.yaml | head -1 | grep -o '[0-9.]*')
BUILD_DIR="build/macos/Build/Products/Release"
APP_PATH="$BUILD_DIR/$APP_NAME.app"

[ -d "$APP_PATH" ] || { echo "[MISS] 请先执行 flutter build macos --release"; exit 1; }

# ad-hoc 签名（无 Developer ID 时的标准做法；Gatekeeper 指引见 README）
codesign --deep --force -s - "$APP_PATH"
echo "[OK] ad-hoc 签名完成"

mkdir -p dist
DMG="dist/${APP_NAME}_${VERSION}.dmg"
rm -f "$DMG"
if command -v create-dmg >/dev/null 2>&1; then
    create-dmg --volname "$APP_NAME" --volicon "$APP_PATH/Contents/Resources/AppIcon.icns" \
        --window-size 640 420 --icon-size 128 \
        --icon "$APP_NAME.app" 175 190 \
        --app-drop-link 465 190 \
        "$DMG" "$APP_PATH" || true
fi
# create-dmg 失败时回退 hdiutil
[ -f "$DMG" ] || hdiutil create -volname "$APP_NAME" -srcfolder "$APP_PATH" -ov -format UDZO "$DMG"
echo "[OK] 产物: $DMG"
echo "提示：用户首次打开需右键打开或 xattr -cr /Applications/$APP_NAME.app（Gatekeeper）"
