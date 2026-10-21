#!/bin/bash
# ─────────────────────────────────────────────
# 小金截图（自用）· 启动器
# 双击本文件即可启动（首次如提示无法打开，请右键 → 打开）
# 依赖未安装时请先运行 ./install.sh
# ─────────────────────────────────────────────
cd "$(dirname "$0")"

PY=""
for c in /usr/bin/python3 python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "未找到 Python3，请先安装 Python 后重试。"
  read -n 1 -s -r -p "按任意键退出..."
  exit 1
fi

# 注入用户 site-packages（部分环境 ENABLE_USER_SITE=False，必需）
SITE=$("$PY" -c "import site; print(site.getusersitepackages())" 2>/dev/null)
export PYTHONPATH="$SITE"

mkdir -p "$HOME/.localsnap"
echo "启动中...（菜单栏出现小狐狸图标即成功，按 ⌘⇧A 截图）"
exec "$PY" main.py >> "$HOME/.localsnap/log.txt" 2>&1
