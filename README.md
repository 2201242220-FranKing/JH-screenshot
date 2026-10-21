# 小金截图（自用）· XiaoJin Screenshot

一款轻量的 macOS 截图小工具：**全局快捷键截图 → 自动进剪贴板 → 按空格钉图**。钉图窗口可随意拖动、点 ✕ 或按 Esc 关闭。菜单栏常驻，开箱即用。

> 名字虽然写着"自用"，但代码完全开源、结构干净，任何人都可以 clone 下来自己安装使用或二次开发。

---

## ✨ 功能特性

| 功能 | 说明 |
| --- | --- |
| 📸 全局热键截图 | 默认 `⌘⇧A`（Cmd + Shift + A），在任意应用上方都生效 |
| 📋 截图进剪贴板 | 截图完成后图片自动复制到剪贴板，可随手粘贴到任何地方 |
| 📌 按空格钉图 | 截图后按一次 `空格`，图片会以无边框悬浮窗"钉"在屏幕上置顶显示 |
| 🖱️ 钉图可拖动 | 按住图片任意位置拖动，窗口实时跟随鼠标（绝对定位，不抖不漂） |
| ❌ 钉图可关闭 | 点右上角 `✕`，或按 `Esc` 关闭钉图窗口 |
| 🍔 菜单栏常驻 | 菜单栏显示小狐狸图标，可随时退出 |
| ⚙️ 配置文件 | 快捷键、保存目录、开关项全部可在 `~/.localsnap/config.json` 中自定义 |
| 🖼️ 有趣图标 | 金冠小狐狸抱拍立得截图卡片，启动台/菜单栏均使用 |

## 🎯 设计理念

- **截图 ≠ 钉图**：截图后只进剪贴板，绝不自动弹窗打扰；想要"悬浮钉图"才按空格。
- **零依赖系统服务**：截图内核直接调用 macOS 自带的 `screencapture`，钉图用系统 `AppKit`，不引入任何第三方截图库。
- **极轻**：单个 Python 文件主程序 + 4 个运行依赖。

## 🖥️ 系统要求

| 项目 | 要求 |
| --- | --- |
| 系统 | macOS 10.15 及以上（Intel / Apple Silicon 均可） |
| Python | Python 3.9+（macOS 自带 `/usr/bin/python3`，或官网安装） |
| 权限 | 「辅助功能」「屏幕录制」授权（见下方） |

## 🚀 快速开始（新电脑 3 步装好）

### 1. 克隆项目

```bash
git clone <你的仓库地址> 小金截图
cd 小金截图
```

> 如果是在豆包等 AI 助手里，直接把整个仓库文件夹发给 agent，让它执行下面的安装步骤即可。

### 2. 一键安装依赖

```bash
chmod +x install.sh
./install.sh
```

脚本会自动检测 Python 版本并安装全部依赖（`pynput` / `rumps` / `pillow` / `pyobjc`）。

### 3. 授权 + 启动

1. 打开 `系统设置 → 隐私与安全性 → 辅助功能`，把 **Python**（或打包后的 App）加入并勾选；
2. 打开 `系统设置 → 隐私与安全性 → 屏幕录制`，同样加入并勾选；
3. 启动：**方式一** 双击 `start.command`（命令行运行）；**方式二** 运行 `./build_app.sh` 打包成启动台 App，然后从启动台打开。

看到菜单栏出现小狐狸图标即成功。按 `⌘⇧A` 试试截图吧！

## ⌨️ 使用说明

| 操作 | 效果 |
| --- | --- |
| `⌘⇧A` | 全屏截图，图片自动进剪贴板，屏幕底部出现提示浮层 |
| `空格`（截图后 8 秒内） | 将刚才的截图钉到屏幕（置顶悬浮） |
| `Esc`（提示浮层期间） | 关闭提示浮层 |
| 按住钉图窗口拖动 | 移动钉图位置（实时跟随） |
| 点击钉图右上角 `✕` / 按 `Esc` | 关闭钉图窗口 |
| 菜单栏小狐狸图标 → 退出 | 完全退出工具 |

## ⚙️ 配置

配置文件位于 `~/.localsnap/config.json`（首次启动自动创建，字段见 `config.example.json`）：

```json
{
  "hotkey": "cmd+shift+A",
  "save_dir": "~/Desktop/截图",
  "auto_copy": true,
  "pin_on_space": true,
  "play_sound": true
}
```

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `hotkey` | string | `cmd+shift+A` | 全局截图快捷键，格式 `ctrl/cmd/alt/shift` 用 `+` 组合 |
| `save_dir` | string | `~/Desktop/截图` | 截图文件保存目录（同时保留一份原图） |
| `auto_copy` | bool | `true` | 截图后是否自动复制到剪贴板 |
| `pin_on_space` | bool | `true` | 截图后按空格是否钉图 |
| `play_sound` | bool | `true` | 截图时是否播放快门提示音 |

修改后重启工具生效。

## 🧩 目录结构

```
小金截图/
├── main.py            # 主程序（热键 / 截图 / 钉图 / 菜单栏）
├── install.sh         # 一键安装脚本（检测环境并安装依赖）
├── build_app.sh       # 打包启动台 .app 脚本
├── start.command      # 命令行启动器（双击运行）
├── requirements.txt   # 依赖清单（精确版本）
├── config.example.json# 配置示例
├── assets/
│   ├── icon.png       # 应用图标源图（2048×2048）
│   └── AppIcon.icns   # 打包 .app 用的图标
└── CHANGELOG.md       # 版本变更记录
```

## 🔧 常见问题（FAQ）

**Q1：安装依赖失败（pyobjc 报编译错误）？**
A：`install.sh` 已做兼容处理。若仍失败，说明本机 Python 版本过新，请执行：
```bash
pip3 install --user pynput rumps pillow "pyobjc-framework-Quartz"
```
让 pip 自动挑选适配当前 Python 的 pyobjc 版本。

**Q2：按快捷键没反应？**
A：先检查「辅助功能」是否已把 Python/App 加入并勾选；再看 `~/.localsnap/log.txt` 末尾有无报错。若与系统快捷键冲突，修改 `config.json` 的 `hotkey` 换一个组合。

**Q3：截图黑屏 / 没有画面内容？**
A：是「屏幕录制」权限未授予，按快速开始第 3 步授权后重启工具。

**Q4：找不到 `/usr/bin/python3`？**
A：到 [python.org](https://www.python.org/downloads/) 安装 Python 3，然后在「辅助功能」里授权 `Python.app`（路径可用 `which python3` 查看）。

**Q5：想让截图不自动保存，只进剪贴板？**
A：把 `save_dir` 留空字符串即可。

## ⚙️ 打包成启动台 App（可选）

```bash
./build_app.sh
```

会生成 `~/Applications/小金截图（自用）.app` 并注册到启动台，带金冠小狐狸图标，双击图标即可启动（菜单栏常驻，无 Dock 图标）。

## 🛠️ 技术原理

- **截图**：调用 macOS 系统命令 `/usr/sbin/screencapture`（无需额外截图框架）；
- **全局热键 / 空格监听**：`pynput` 全局键盘监听，单监听器统一识别快捷键与空格/Esc；
- **钉图窗口**：`AppKit` 无边框置顶悬浮窗，窗口级处理拖动与关闭，稳定不崩溃；
- **菜单栏**：`rumps` 菜单栏常驻组件；
- **提示浮层**：屏幕底部 toast，复用单窗口避免内存反复创建/销毁。

## 📜 License

[MIT](LICENSE) © 2026 小金截图项目贡献者

## 🙏 参考与致谢

灵感与交互参考了以下开源项目：
- [MacShot](https://github.com/sw33tLie/macshot) — 轻量截图
- [Capso](https://github.com/lzhgus/Capso) — 截图增强
- [Flameshot](https://github.com/flameshot-org/flameshot) — 钉图/标注交互范式
