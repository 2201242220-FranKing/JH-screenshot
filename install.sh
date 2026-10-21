#!/usr/bin/env bash
# ─────────────────────────────────────────────
# 小金截图（自用）· 一键安装脚本
# 用法：chmod +x install.sh && ./install.sh
# 作用：检测 Python 环境并安装全部依赖
# ─────────────────────────────────────────────
set -e
cd "$(dirname "$0")"

echo "════════════════════════════════════"
echo " 小金截图（自用） 依赖安装"
echo "════════════════════════════════════"

# 1. 定位 Python
PY=""
for c in python3 /usr/bin/python3; do
  if command -v "$c" >/dev/null 2>&1; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "❌ 未找到 Python3，请先到 https://www.python.org/downloads/ 安装，然后重试。"
  exit 1
fi

VER=$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')
echo "✅ 使用 Python: $PY (版本 $VER)"

# 2. 优先尝试锁定版本（3.9~3.12 推荐）
echo "⏳ 安装依赖（首次可能需要 1~3 分钟）..."
if "$PY" -m pip install --user -r requirements.txt 2>/dev/null; then
  echo "✅ 依赖安装成功（锁定版本）"
else
  echo "⚠️  锁定版本安装失败，尝试自动匹配当前 Python 版本..."
  if "$PY" -m pip install --user pynput rumps pillow "pyobjc-framework-Quartz" "pyobjc-framework-ApplicationServices" "pyobjc-framework-Cocoa" "pyobjc-framework-CoreText"; then
    echo "✅ 依赖安装成功（自适应版本）"
  else
    echo "❌ 依赖安装失败。请检查网络后重试，或参见 README「常见问题 Q1」。"
    exit 1
  fi
fi

# 3. 提示授权
cat << 'EOF'

┌─────────────────────────────────────────────┐
│  下一步：授予权限（非常重要，否则不生效）      │
│                                             │
│  1) 系统设置 → 隐私与安全性 → 辅助功能        │
│     把 python3 / Python.app 加入并勾选       │
│  2) 系统设置 → 隐私与安全性 → 屏幕录制        │
│     同样加入并勾选                           │
│                                             │
│  然后运行 ./start.command 启动               │
└─────────────────────────────────────────────┘
EOF
echo ""
echo "✅ 安装完成！"
