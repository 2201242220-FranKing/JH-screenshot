#!/usr/bin/env bash
# ─────────────────────────────────────────────
# 小金截图（自用）· 打包启动台 App
# 用法：chmod +x build_app.sh && ./build_app.sh
# 产物：~/Applications/小金截图（自用）.app
# ─────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

APP_NAME="小金截图（自用）"
APP_DIR="$HOME/Applications/${APP_NAME}.app"
BUNDLE_ID="com.xiaojin.screenshot"
ICON="assets/AppIcon.icns"

echo "════════════════════════════════════"
echo " 打包启动台 App: ${APP_NAME}"
echo "════════════════════════════════════"

if [ ! -f "$ICON" ]; then
  echo "❌ 缺少图标文件 $ICON"
  exit 1
fi

# 1. 创建 .app 骨架
rm -rf "$APP_DIR"
mkdir -p "$APP_DIR/Contents/MacOS"
mkdir -p "$APP_DIR/Contents/Resources"

# 2. Info.plist（LSUIElement=true = 菜单栏常驻，无 Dock 图标）
cat > "$APP_DIR/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>launcher</string>
  <key>CFBundleIdentifier</key>
  <string>$BUNDLE_ID</string>
  <key>CFBundleName</key>
  <string>${APP_NAME}</string>
  <key>CFBundleDisplayName</key>
  <string>${APP_NAME}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>2.0.0</string>
  <key>CFBundleVersion</key>
  <string>2</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>LSUIElement</key>
  <true/>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

# 3. 复制程序与图标
cp main.py "$APP_DIR/Contents/Resources/main.py"
cp config.example.json "$APP_DIR/Contents/Resources/config.example.json"
cp "$ICON" "$APP_DIR/Contents/Resources/AppIcon.icns"
# 菜单栏小图标源图（首次运行生成 44px 菜单图标用）
if [ -f assets/icon.png ]; then
  cp assets/icon.png "$APP_DIR/Contents/Resources/menu_icon.png"
fi

# 4. 启动器（自动定位 Python 的 site-packages 并注入 PYTHONPATH）
cat > "$APP_DIR/Contents/MacOS/launcher" <<'LAUNCHER'
#!/bin/bash
# 定位 python3
PY=""
for c in /usr/bin/python3 python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  osascript -e 'display alert "小金截图" message "未找到 Python3，请先安装 Python。"'
  exit 1
fi
# 注入用户 site-packages（本环境 ENABLE_USER_SITE=False 时必需）
SITE=$("$PY" -c "import site; print(site.getusersitepackages())" 2>/dev/null)
export PYTHONPATH="$SITE"
RES="$(cd "$(dirname "$0")/../Resources" && pwd)"
mkdir -p "$HOME/.localsnap"
exec "$PY" "$RES/main.py" >> "$HOME/.localsnap/log.txt" 2>&1
LAUNCHER
chmod +x "$APP_DIR/Contents/MacOS/launcher"

# 5. 注册到启动台
if command -v /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister >/dev/null 2>&1; then
  /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$APP_DIR" 2>/dev/null || true
fi

echo "✅ 打包完成：$APP_DIR"
echo "   打开「启动台」即可看到「${APP_NAME}」图标。"
echo "   首次打开如提示无法验证开发者，请右键图标 → 打开。"
