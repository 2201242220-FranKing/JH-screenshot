# 小金截图（自用）· XiaoJin Screenshot

一款轻量的 macOS 截图小工具：**三种截图模式 → 自动进剪贴板 → 空格钉图 / M 美化**。截图美化为 9 套背景 + 圆角阴影，发文档、推文直接能看。菜单栏常驻，开箱即用。

> 名字虽然写着"自用"，但代码完全开源、结构干净，任何人都可以 clone 下来自己安装使用或二次开发。

---

## ✨ 功能特性

| 功能 | 说明 |
| --- | --- |
| 📸 三种截图模式 | **区域框选** `⌘⇧A` · **整屏** `⌥⌘A` · **窗口** `⌥⌘W`，快捷键全部可改 |
| 🎨 截图美化 | 截图后按 **M**：9 套背景（瓷白/拍立得/纸雾/墨洗/柔瓣/苔静/暮紫/柑雾/夜墨）+ 圆角/阴影/边距，`←→` 切换，`⌘C` 复制 |
| 📋 剪贴板 + 焦点回切 | 截图自动复制到剪贴板，并自动把焦点还给截图前的应用，可直接粘贴 |
| 📌 按空格钉图 | 截图后按 `空格`，图片以无边框悬浮窗钉在屏幕上（可拖动、✕/Esc 关闭） |
| 🔐 权限自检 | 启动时检测「屏幕录制」「辅助功能」权限，缺失自动提示并引导打开系统设置 |
| 🍔 菜单栏常驻 | 菜单栏小狐狸图标：区域/窗口/全屏截图、美化、钉图、打开文件夹、改配置、退出 |
| ⚙️ 配置文件 | 快捷键、保存目录、美化开关与默认背景全可自定义 |
| 🖼️ 有趣图标 | 金冠小狐狸抱拍立得截图卡片，启动台/菜单栏均使用 |

## 🎯 设计理念

- **截图 ≠ 钉图 ≠ 美化**：截图后只进剪贴板；想"悬浮钉图"按空格；想"加背景美化"按 M。各取所需，绝不自动打扰。
- **零依赖系统服务**：截图内核直接调用 macOS 自带的 `screencapture`，美化与钉图用 Pillow + AppKit，全部本机处理，截图不上传。
- **极轻**：单个 Python 文件主程序 + 4 个运行依赖，macOS 12 就能跑。

## 🖥️ 系统要求

| 项目 | 要求 |
| --- | --- |
| 系统 | macOS 10.15 及以上（Intel / Apple Silicon 均可） |
| Python | Python 3.9+（macOS 自带 `/usr/bin/python3`，或官网安装） |
| 权限 | 「辅助功能」「屏幕录制」授权（首次启动工具会自动引导） |

## 🚀 快速开始（新电脑 3 步装好）

### 1. 克隆项目

```bash
git clone git@github.com:2201242220-FranKing/JH-screenshot.git 小金截图
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

1. 启动工具后，它会自动检测权限：缺「屏幕录制」或「辅助功能」会弹窗并打开系统设置，按提示勾选即可；
2. 启动：**方式一** 双击 `start.command`（命令行运行）；**方式二** 运行 `./build_app.sh` 打包成启动台 App，然后从启动台打开。

看到菜单栏出现小狐狸图标即成功。按 `⌘⇧A` 试试区域截图吧！

## ⌨️ 使用说明

### 截图

| 操作 | 效果 |
| --- | --- |
| `⌘⇧A` | 区域框选截图（拖动框选，空格切窗口模式，Esc 取消） |
| `⌥⌘A` | 整屏截图 |
| `⌥⌘W` | 窗口截图（点击目标窗口） |
| 任意模式截图完成 | 自动保存 + 复制到剪贴板 + 焦点回到原应用 |

### 截图后（8 秒提示浮层）

| 操作 | 效果 |
| --- | --- |
| `空格` | 钉图：把截图钉在屏幕（可拖动，✕/Esc 关闭） |
| `M` | 美化：打开美化预览窗 |
| `Esc` | 关闭提示浮层 |

### 美化窗内

| 操作 | 效果 |
| --- | --- |
| `←` / `→` | 切换 9 套背景 |
| `⌘C` / `回车` | 复制美化图到剪贴板并关闭（焦点回原应用） |
| `Esc` | 关闭，不复制 |

### 菜单栏

小狐狸图标 → 区域截图 / 窗口截图 / 全屏截图 / 美化最近一张 / 钉图最近一张 / 打开截图文件夹 / 更改配置 / 关于 / 退出。

## ⚙️ 配置

配置文件位于 `~/.localsnap/config.json`（首次启动自动创建，字段见 `config.example.json`）：

```json
{
  "hotkey": "cmd+shift+A",
  "hotkey_full": "alt+cmd+A",
  "hotkey_window": "alt+cmd+W",
  "save_dir": "~/Desktop/截图",
  "auto_copy": true,
  "pin_on_space": true,
  "play_sound": true,
  "beautify": true,
  "beautify_background": 0
}
```

| 字段 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `hotkey` | string | `cmd+shift+A` | 区域框选快捷键，格式 `ctrl/cmd/alt/shift` 用 `+` 组合 |
| `hotkey_full` | string | `alt+cmd+A` | 整屏截图快捷键 |
| `hotkey_window` | string | `alt+cmd+W` | 窗口截图快捷键 |
| `save_dir` | string | `~/Desktop/截图` | 截图文件保存目录（同时保留一份原图） |
| `auto_copy` | bool | `true` | 截图后是否自动复制到剪贴板 |
| `pin_on_space` | bool | `true` | 截图后按空格是否钉图 |
| `play_sound` | bool | `true` | 截图时是否播放快门提示音 |
| `beautify` | bool | `true` | 是否启用截图美化（M 键进入） |
| `beautify_background` | int | `0` | 美化默认背景序号（0~8，见下方背景表） |

### 美化背景一览

| 序号 | 背景 | 效果 |
| --- | --- | --- |
| 0 | 瓷白 | 纯白底，干净百搭 |
| 1 | 拍立得 | 白底 + 底部加宽相纸下沿 |
| 2 | 纸雾 | 米白纸纹质感 |
| 3 | 墨洗 | 浅灰蓝纸纹 |
| 4 | 柔瓣 | 浅粉 |
| 5 | 苔静 | 浅绿 |
| 6 | 暮紫 | 浅紫渐变 |
| 7 | 柑雾 | 浅橙渐变 |
| 8 | 夜墨 | 深色底，截图更醒目 |

修改配置后重启工具生效。

## 🧩 目录结构

```
小金截图/
├── main.py            # 主程序（热键 / 截图 / 美化 / 钉图 / 菜单栏）
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
A：先确认「辅助功能」是否已把 Python/App 加入并勾选；再看 `~/.localsnap/log.txt` 末尾有无报错。若与系统快捷键冲突，修改 `config.json` 里的快捷键换一个组合。

**Q3：截图黑屏 / 没有画面内容？**
A：是「屏幕录制」权限未授予。启动工具会自动检测并引导打开系统设置；也可手动去「系统设置 › 隐私与安全性 › 录屏与系统录音」勾选后重启。

**Q4：区域框选时按 Esc 没反应 / 截图取消？**
A：区域框选是系统原生 UI，Esc 会取消本次截图（这是正常行为）。取消后不会保存和复制。

**Q5：美化时切换背景有点慢？**
A：美化为纯本地 Pillow 合成，1~2 秒属正常（阴影按尺寸缓存，切换只换背景）。超大屏截图会更慢一点点，可把截图区域选小一些。

**Q6：找不到 `/usr/bin/python3`？**
A：到 [python.org](https://www.python.org/downloads/) 安装 Python 3，然后在「辅助功能」里授权 `Python.app`（路径可用 `which python3` 查看）。

## ⚙️ 打包成启动台 App（可选）

```bash
./build_app.sh
```

会生成 `~/Applications/小金截图（自用）.app` 并注册到启动台，带金冠小狐狸图标，双击图标即可启动（菜单栏常驻，无 Dock 图标）。

## 🛠️ 技术原理

- **截图**：调用 macOS 系统命令 `/usr/sbin/screencapture`（`-i` 框选 / `-w` 窗口 / `-x` 整屏）；
- **全局热键 / 空格 / M**：`pynput` 全局键盘监听，单监听器统一识别全部组合键；
- **美化**：Pillow 本地合成（9 套背景 + 圆角遮罩 + 阴影高斯模糊缓存 + 低压缩 PNG 秒级保存）；
- **权限自检**：`CGPreflightScreenCaptureAccess` + `AXIsProcessTrusted`，缺失弹窗并打开系统设置；
- **焦点回切**：截图前记录 `frontmostApplication`，完成后 `activate` 还给原应用；
- **钉图窗口**：`AppKit` 无边框置顶悬浮窗，窗口级处理拖动与关闭，稳定不崩溃；
- **菜单栏**：`rumps` 菜单栏常驻组件。

## 📜 License

[MIT](LICENSE) © 2026 小金截图项目贡献者

## 🙏 参考与致谢

灵感与交互参考了以下开源项目：
- [MacShot](https://github.com/sw33tLie/macshot) — 轻量截图
- [Capso](https://github.com/lzhgus/Capso) — 截图增强
- [Flameshot](https://github.com/flameshot-org/flameshot) — 钉图/标注交互范式
- [PrettyShot](https://github.com/KinGao294/prettyshot) — 截图美化背景 / 多截图模式启发
