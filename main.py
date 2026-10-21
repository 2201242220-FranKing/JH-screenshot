#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小金截图（自用）v2 · macOS 本地截图小插件
----------------------
功能：
  1. 全局热键三种截图模式：区域框选（默认 ⌘⇧A）/ 整屏（默认 ⌥⌘A）/ 窗口（默认 ⌥⌘W），均可改
  2. 截图后自动保存到 save_dir（时间戳命名）
  3. 自动复制到剪贴板，复制后焦点自动回到截图前的应用，可直接粘贴
  4. 屏幕录制 / 辅助功能权限自检：缺失时提示并引导打开系统设置
  5. 截图美化：9 套背景（瓷白/拍立得/纸雾/墨洗/柔瓣/苔静/暮紫/柑雾/夜墨）+ 圆角阴影，截图后按 M 美化
  6. 按空格钉图（可拖动、✕/Esc 关闭）
  7. 菜单栏常驻小图标（区域/全屏/窗口/钉图/美化/打开文件夹/改配置/退出）
  8. 截图完成提示音 + 系统通知

配置文件：~/.localsnap/config.json（可改快捷键、保存目录、背景等，改完需重启生效）
运行方式：双击 start.command，或 /usr/bin/python3 main.py
"""

import json
import os
import queue
import subprocess
import sys
import threading
import time

# ─────────────────────────────────────────────
# 0. 依赖路径兜底（本环境禁用了 user site，主动补上）
# ─────────────────────────────────────────────
_USER_SITE = os.path.expanduser("~/Library/Python/3.9/lib/python/site-packages")
if _USER_SITE not in sys.path and os.path.isdir(_USER_SITE):
    sys.path.insert(0, _USER_SITE)

import rumps                                 # 菜单栏
import pynput.keyboard                        # 全局热键
import Quartz                                 # 权限检测 / 屏幕坐标
from PIL import Image, ImageDraw, ImageFilter # 图片处理（美化）
import objc                                   # PyObjC 运行时
from AppKit import (NSPasteboard, NSPasteboardTypePNG, NSApplication,
                    NSApplicationActivationPolicyAccessory,
                    NSApplicationActivateIgnoringOtherApps,
                    NSImage, NSImageView, NSButton, NSRoundedBezelStyle,
                    NSWindow, NSBorderlessWindowMask, NSBackingStoreBuffered,
                    NSFloatingWindowLevel, NSColor, NSView, NSImageScaleProportionallyDown,
                    NSScreen, NSTextField, NSCenterTextAlignment, NSFont,
                    NSBox, NSBoxCustom, NSNoTitle,
                    NSFontAttributeName, NSForegroundColorAttributeName,
                    NSWorkspace, NSCommandKeyMask)
from ApplicationServices import AXIsProcessTrusted
from Foundation import NSData, NSRect, NSPoint, NSSize, NSString

APP_NAME = "小金截图（自用）"
APP_VERSION = "2.0.0"
CONFIG_DIR = os.path.expanduser("~/.localsnap")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
LOG_PATH = os.path.join(CONFIG_DIR, "log.txt")
SCREENCAPTURE = "/usr/sbin/screencapture"
SOUND_PATH = "/System/Library/Sounds/Glass.aiff"
TMP_BEAUTIFY = os.path.join(CONFIG_DIR, "beautify_tmp.png")

DEFAULT_CONFIG = {
    "hotkey": "cmd+shift+A",       # 区域框选快捷键（空格切窗口模式，Esc 取消）
    "hotkey_full": "alt+cmd+A",    # 整屏截图快捷键
    "hotkey_window": "alt+cmd+W",  # 窗口截图快捷键
    "save_dir": "~/Desktop/截图",   # 截图保存目录
    "auto_copy": True,             # 截图后自动复制到剪贴板
    "pin_on_space": True,          # 截图后按空格键钉图
    "play_sound": True,            # 截图完成提示音
    "beautify": True,              # 是否启用截图美化（按 M 进入）
    "beautify_background": 0,      # 美化默认背景序号（0~8）
}

# 美化背景：名称 + 类型（solid=纯色 / grad=渐变 / paper=纸纹）+ 参数
BEAUTIFY_BACKGROUNDS = [
    ("瓷白",  "solid", "#FFFFFF"),
    ("拍立得", "solid", "#FFFFFF"),   # 特殊：底部加宽模拟相纸下沿
    ("纸雾",  "paper", "#F3EFE8"),
    ("墨洗",  "paper", "#E7EBF0"),
    ("柔瓣",  "solid", "#F7E9EC"),
    ("苔静",  "solid", "#E8EFE4"),
    ("暮紫",  "grad",  ("#EDE6F7", "#F6F1FB")),
    ("柑雾",  "grad",  ("#FBEADD", "#FDF4EA")),
    ("夜墨",  "solid", "#232A35"),
]


def log(msg):
    """写运行日志，便于排错。"""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + str(msg) + "\n")
    except Exception:
        pass


def load_config():
    """读取配置文件，缺失或损坏时用默认值并自动创建。"""
    cfg = dict(DEFAULT_CONFIG)
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update(data)
    except Exception as e:
        log("config load error: %s" % e)
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        if not os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log("config save error: %s" % e)
    return cfg


def expand_save_dir(path):
    """展开保存目录中的 ~ 等符号。"""
    return os.path.expanduser(os.path.expandvars(path))


_MODS = {"cmd", "ctrl", "control", "shift", "alt", "option", "meta"}


def normalize_hotkey(h):
    """把用户写法 'cmd+1' 转成 pynput 需要的 '<cmd>+1' 格式。"""
    h = h.strip()
    if not h:
        return DEFAULT_CONFIG["hotkey"]
    if h.startswith("<"):
        return h
    parts = [p.strip() for p in h.split("+") if p.strip()]
    out = []
    for p in parts:
        low = p.lower()
        if low in _MODS:
            name = {"control": "ctrl", "option": "alt"}.get(low, low)
            out.append("<%s>" % name)
        else:
            out.append(p)
    return "+".join(out)


def notify(title, message, subtitle=""):
    """系统通知。"""
    try:
        rumps.notification(title, subtitle, message, sound=False)
    except Exception as e:
        log("notify error: %s" % e)


def play_sound():
    try:
        subprocess.run(["afplay", SOUND_PATH], check=False)
    except Exception:
        pass


def copy_to_clipboard(path):
    """把图片文件写入剪贴板（AppKit 原生，最可靠）。"""
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    data = NSData.dataWithContentsOfFile_(path)
    if data is None:
        return False
    return pb.setData_forType_(data, NSPasteboardTypePNG)


# ─────────────────────────────────────────────
# 截图美化：9 套背景 + 圆角 + 阴影 + 边距（纯 Pillow 本地合成）
# ─────────────────────────────────────────────
def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _make_background(idx, w, h):
    """按背景序号生成 W×H 的背景画布（纯色 / 渐变 / 纸纹）。"""
    name, kind, param = BEAUTIFY_BACKGROUNDS[idx]
    if kind == "grad":
        c1, c2 = _hex_rgb(param[0]), _hex_rgb(param[1])
        img = Image.new("RGB", (1, h))
        for y in range(h):
            t = y / max(1, h - 1)
            img.putpixel((0, y), tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3)))
        img = img.resize((w, h))
    else:
        img = Image.new("RGB", (w, h), _hex_rgb(param) if isinstance(param, str) else param)
    if kind == "paper":
        # 轻噪点纸纹
        noise = Image.effect_noise((w, h), 14).convert("L")
        img = Image.composite(img, Image.new("RGB", (w, h), (255, 255, 255)),
                              noise.point(lambda p: p * 18))
    return img


# 阴影缓存：阴影只与截图尺寸/圆角有关，与背景无关；切换背景时直接复用
_SHADOW_CACHE = {}


def _get_shadow(w, h, round_r, dark):
    key = (w, h, round_r, dark)
    sh = _SHADOW_CACHE.get(key)
    if sh is None:
        sh = Image.new("RGBA", (w + 20, h + 20), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle(
            [10, 10, w + 9, h + 9], radius=round_r, fill=(0, 0, 0, dark))
        sh = sh.filter(ImageFilter.GaussianBlur(8))
        _SHADOW_CACHE[key] = sh
        if len(_SHADOW_CACHE) > 3:      # 只缓存最近 3 个尺寸
            _SHADOW_CACHE.clear()
    return sh


def make_beautified(src_path, idx, tmp_path=TMP_BEAUTIFY):
    """截图 + 背景 + 圆角 + 阴影 + 边距 → 合成图，保存到 tmp_path。"""
    img = Image.open(src_path).convert("RGB")
    w, h = img.size
    PAD = 64                       # 四周留白
    ROUND = 26                     # 圆角半径
    is_polaroid = BEAUTIFY_BACKGROUNDS[idx][0] == "拍立得"
    bottom_pad = PAD + 110 if is_polaroid else PAD   # 拍立得底部加宽

    W, H = w + PAD * 2, h + PAD + bottom_pad
    canvas = _make_background(idx, W, H).convert("RGBA")

    # 阴影：截图右下方偏移的半透明圆角块 + 高斯模糊（按尺寸缓存）
    dark = 130 if BEAUTIFY_BACKGROUNDS[idx][0] == "夜墨" else 90
    sh = _get_shadow(w, h, ROUND, dark)

    # 截图本体：圆角遮罩
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=ROUND, fill=255)
    rgba = img.convert("RGBA")
    rgba.putalpha(mask)

    canvas.paste(sh, (PAD - 10, PAD + 8), sh)
    canvas.paste(rgba, (PAD, PAD), rgba)
    # compress_level=1：牺牲少量文件体积换取秒级保存速度（剪贴板/预览场景更看重速度）
    canvas.convert("RGB").save(tmp_path, "PNG", compress_level=1)
    return tmp_path


class PassthroughImageView(NSImageView):
    """图片视图：鼠标事件全部转发给窗口，实现按住图片拖动窗口。"""

    def mouseDown_(self, event):
        nxt = self.nextResponder()
        if nxt is not None:
            nxt.mouseDown_(event)

    def mouseDragged_(self, event):
        nxt = self.nextResponder()
        if nxt is not None:
            nxt.mouseDragged_(event)

    def mouseUp_(self, event):
        nxt = self.nextResponder()
        if nxt is not None:
            nxt.mouseUp_(event)


def make_close_icon(size=32):
    """程序绘制一个白色 ✕ 图标（纯装饰，点击关闭由窗口热区处理）。"""
    img = NSImage.alloc().initWithSize_(NSSize(size, size))
    img.lockFocus()
    attrs = {
        NSFontAttributeName: NSFont.boldSystemFontOfSize_(15),
        NSForegroundColorAttributeName: NSColor.whiteColor(),
    }
    txt = NSString.stringWithString_("✕")
    txt.drawAtPoint_withAttributes_(NSPoint(size / 2.0 - 9, size / 2.0 - 11), attrs)
    img.unlockFocus()
    return img


class PinWindow(NSWindow):
    """无边框置顶悬浮窗：按住图片可拖动，点 ✕ 或按 Esc 关闭。"""

    def canBecomeKeyWindow(self):
        return True

    def canBecomeMainWindow(self):
        return True

    def keyDown_(self, event):
        code = event.keyCode()
        if code in (53, 12):  # Esc / Q
            self._safe_close()
        else:
            NSWindow.keyDown_(self, event)

    def _safe_close(self):
        """延迟到本次事件分发结束后再关闭，避免在事件处理中销毁窗口导致段错误。"""
        try:
            self.performSelector_withObject_afterDelay_("_finishClose:", None, 0.05)
        except Exception:
            self._hide_and_forget()

    def _finishClose_(self, sender):
        self._hide_and_forget()

    def _hide_and_forget(self):
        """关闭 = 隐藏窗口 + 移除引用。不销毁窗口对象，彻底避开 PyObjC dealloc 崩溃。"""
        try:
            if getattr(self, "_owner", None) is not None:
                try:
                    self._owner.pin_windows.remove(self)
                except ValueError:
                    pass
        except Exception:
            pass
        try:
            self.orderOut_(None)
        except Exception:
            pass

    # ── 拖动与关闭（窗口级处理，最可靠：不依赖按钮 target-action）──
    def mouseDown_(self, event):
        loc = event.locationInWindow()
        sz = self.frame().size
        # 右上角 46×46 热区 = ✕ 关闭按钮（点这里关闭）
        if loc.x >= sz.width - 46 and loc.y >= sz.height - 46:
            self._safe_close()
            return
        # 其余区域开始拖动（绝对定位，鼠标在哪窗口就瞬移到哪）
        f = self.frame()
        self._drag_origin = f.origin
        self._drag_start = NSPoint(f.origin.x + loc.x, f.origin.y + loc.y)

    def mouseDragged_(self, event):
        if getattr(self, "_drag_start", None) is None:
            return
        loc = event.locationInWindow()
        f = self.frame()
        cur = NSPoint(f.origin.x + loc.x, f.origin.y + loc.y)
        dx = cur.x - self._drag_start.x
        dy = cur.y - self._drag_start.y
        self.setFrameOrigin_(NSPoint(self._drag_origin.x + dx, self._drag_origin.y + dy))

    def mouseUp_(self, event):
        self._drag_start = None


class BeautifyWindow(NSWindow):
    """截图美化预览窗：← → 切换背景，⌘C / 回车 复制并关闭，Esc 关闭。"""

    def canBecomeKeyWindow(self):
        return True

    def canBecomeMainWindow(self):
        return True

    def keyDown_(self, event):
        code = event.keyCode()
        mods = event.modifierFlags()
        owner = getattr(self, "_owner", None)
        if owner is None:
            NSWindow.keyDown_(self, event)
            return
        if code == 53:                       # Esc
            owner._close_beautify()
        elif code == 123:                    # ←
            owner._beautify_switch(-1)
        elif code == 124:                    # →
            owner._beautify_switch(1)
        elif code == 36:                     # 回车
            owner._beautify_copy()
        elif code == 8 and (mods & NSCommandKeyMask):  # ⌘C
            owner._beautify_copy()
        else:
            NSWindow.keyDown_(self, event)


class SnapApp:
    def __init__(self):
        self.cfg = load_config()
        self.q = queue.Queue()          # 跨线程消息队列
        self.last_path = None           # 最近一次截图路径
        self.pin_windows = []           # 保持钉图窗口引用，防止被回收
        self.listener = None            # pynput 全局键盘监听
        self._startup_notified = False
        self._toast_window = None       # 截图完成提示浮层
        self._toast = None              # 复用的浮层组件（强引用，避免反复创建/销毁崩溃）
        self._toast_path = None         # 待钉图路径
        self._toast_shown_at = 0        # 浮层出现时间
        self._prev_app = None           # 截图前活跃应用（用于复制后焦点回切）
        self._beautify_win = None       # 美化预览窗口（复用，不销毁）
        self._beautify_views = None     # 美化窗口子视图强引用
        self._beautify_path = None      # 当前美化的截图
        self._beautify_bg = 0           # 当前背景序号
        self._beautify_busy = False     # 合成进行中防并发
        self._beautify_ready = False    # 当前合成结果是否可用
        self._perm_notified = False     # 权限提示只提示一次

        self.app = rumps.App(
            "小金截图（自用）",
            title=APP_NAME,
            icon=self._ensure_menu_icon(),
            menu=[
                rumps.MenuItem("区域截图"),
                rumps.MenuItem("窗口截图"),
                rumps.MenuItem("全屏截图"),
                None,
                rumps.MenuItem("美化最近一张"),
                rumps.MenuItem("钉图最近一张"),
                rumps.MenuItem("打开截图文件夹"),
                rumps.MenuItem("更改配置…"),
                None,
                rumps.MenuItem("关于"),
                rumps.MenuItem("退出"),
            ],
            quit_button=None,
        )
        self._bind_menu()
        self.timer = rumps.Timer(self._on_tick, 0.5)

    # ── 菜单绑定 ──────────────────────────────
    # 注意：rumps 回调只接收 1 个参数（被点击的菜单项对象），这里统一用 _sender。
    def _bind_menu(self):
        @rumps.clicked("区域截图")
        def _area(_sender):
            self._request_capture("area")

        @rumps.clicked("窗口截图")
        def _window(_sender):
            self._request_capture("window")

        @rumps.clicked("全屏截图")
        def _full(_sender):
            self._request_capture("full")

        @rumps.clicked("美化最近一张")
        def _beautify(_sender):
            if self.last_path and os.path.exists(self.last_path):
                self._open_beautify(self.last_path)
            else:
                notify(APP_NAME, "还没有截图，先截一张再美化吧")

        @rumps.clicked("钉图最近一张")
        def _pin(_sender):
            self.q.put(("menu_pin", None))

        @rumps.clicked("打开截图文件夹")
        def _open_dir(_sender):
            d = expand_save_dir(self.cfg["save_dir"])
            os.makedirs(d, exist_ok=True)
            subprocess.Popen(["open", d])

        @rumps.clicked("更改配置…")
        def _edit_cfg(_sender):
            subprocess.Popen(["open", "-t", CONFIG_PATH])

        @rumps.clicked("关于")
        def _about(_sender):
            rumps.alert(title="小金截图（自用） v%s" % APP_VERSION,
                        message="macOS 本地截图小插件\n\n区域：%s    全屏：%s    窗口：%s\n截图后：空格=钉图  M=美化  Esc=关闭浮层\n美化窗内：←→切背景  ⌘C/回车=复制  Esc=关闭\n\n截图保存：%s\n配置文件：%s\n（修改后退出并重新启动生效）"
                                % (self.cfg.get("hotkey", "cmd+shift+A"),
                                   self.cfg.get("hotkey_full", "alt+cmd+A"),
                                   self.cfg.get("hotkey_window", "alt+cmd+W"),
                                   expand_save_dir(self.cfg["save_dir"]), CONFIG_PATH))

        @rumps.clicked("退出")
        def _quit(_sender):
            self._shutdown()

    def _ensure_menu_icon(self):
        """生成一个彩色小狐狸菜单栏图标（44px，适配 Retina）。"""
        p = os.path.join(CONFIG_DIR, "menu_icon.png")
        try:
            if not os.path.exists(p):
                base = os.path.dirname(os.path.abspath(__file__))
                for cand in (os.path.join(base, ".creative-design", "icon-task", "icon_source.png"),
                             os.path.join(base, "assets", "icon.png"),
                             os.path.join(base, "Resources", "menu_icon.png")):
                    if os.path.exists(cand):
                        img = Image.open(cand).convert("RGB")
                        img.resize((44, 44), Image.LANCZOS).save(p)
                        break
        except Exception as e:
            log("menu icon error: %s" % e)
        return p if os.path.exists(p) else None

    # ── 热键（单个全局监听器，手动识别所有键，最可靠）──
    def start_hotkey(self):
        try:
            self._pressed = set()                 # 当前按住的键
            self._hotkey_fired = {}               # 各热键防重复触发
            self._hotkeys = {}                    # mode -> 按键集合
            for mode, key in (("area", self.cfg.get("hotkey", "cmd+shift+a")),
                              ("full", self.cfg.get("hotkey_full", "alt+cmd+a")),
                              ("window", self.cfg.get("hotkey_window", "alt+cmd+w"))):
                self._hotkeys[mode] = self._parse_hotkey(key)
                self._hotkey_fired[mode] = False
            self.listener = pynput.keyboard.Listener(
                on_press=self._on_key, on_release=self._on_key_release)
            self.listener.daemon = True
            self.listener.start()
            log("hotkey started: area=%s full=%s window=%s" %
                (self.cfg.get("hotkey", "cmd+shift+a"),
                 self.cfg.get("hotkey_full", "alt+cmd+a"),
                 self.cfg.get("hotkey_window", "alt+cmd+w")))
        except Exception as e:
            log("hotkey start error: %s" % e)
            notify(APP_NAME, "全局热键启动失败，请在「系统设置 → 隐私与安全性 → 辅助功能」中允许本应用。")

    def _parse_hotkey(self, h):
        """把 'cmd+shift+A' 解析成按键集合。"""
        s = set()
        parts = normalize_hotkey(h).replace("<", "").replace(">", "").split("+")
        for p in parts:
            low = p.lower().strip()
            if low in ("cmd", "meta"):
                s.add(pynput.keyboard.Key.cmd)
            elif low == "shift":
                s.add(pynput.keyboard.Key.shift)
            elif low in ("ctrl", "control"):
                s.add(pynput.keyboard.Key.ctrl)
            elif low in ("alt", "option"):
                s.add(pynput.keyboard.Key.alt)
            elif len(low) == 1:
                s.add(pynput.keyboard.KeyCode.from_char(low))
            else:
                try:
                    s.add(pynput.keyboard.Key[low])
                except Exception:
                    s.add(pynput.keyboard.KeyCode.from_char(low))
        return s

    def _canon_key(self, key):
        """统一键表示：字母小写、空格归一为 Key.space。"""
        if isinstance(key, pynput.keyboard.KeyCode):
            if key.char is not None:
                if key.char == " ":
                    return pynput.keyboard.Key.space
                return pynput.keyboard.KeyCode.from_char(key.char.lower())
            return key
        return key

    def _on_key(self, key):
        try:
            k = self._canon_key(key)
            self._pressed.add(k)

            # 1) 组合热键 → 三种截图模式
            for mode, keyset in self._hotkeys.items():
                if keyset and keyset.issubset(self._pressed):
                    if not self._hotkey_fired.get(mode):
                        self._hotkey_fired[mode] = True
                        self._request_capture(mode)

            # 2) 空格 → 钉图（仅浮层显示时）
            if k == pynput.keyboard.Key.space and self._toast_window is not None:
                self.q.put(("pin_requested", self._toast_path))

            # 3) M → 美化（仅浮层显示时）
            if k == pynput.keyboard.KeyCode.from_char("m") and self._toast_window is not None:
                if self.cfg.get("beautify", True) and self._toast_path:
                    self.q.put(("beautify", self._toast_path))

            # 4) Esc → 关闭浮层（仅浮层显示时）
            if k == pynput.keyboard.Key.esc and self._toast_window is not None:
                self.q.put(("toast_dismiss", None))
        except Exception as e:
            log("key press error: %s" % e)

    def _on_key_release(self, key):
        try:
            k = self._canon_key(key)
            self._pressed.discard(k)
            # 松开任一热键中的一键，允许下次再触发
            for mode, keyset in self._hotkeys.items():
                if keyset and k in keyset:
                    self._hotkey_fired[mode] = False
        except Exception:
            pass

    def _request_capture(self, mode):
        """任意线程可调用：记录当前应用（用于焦点回切），放入队列调度。"""
        try:
            self._prev_app = NSWorkspace.sharedWorkspace().frontmostApplication()
        except Exception:
            self._prev_app = None
        self.q.put(("capture", mode))

    # ── 截图（子线程执行，避免阻塞菜单栏）──────
    def _capture_worker(self, mode):
        try:
            save_dir = expand_save_dir(self.cfg["save_dir"])
            os.makedirs(save_dir, exist_ok=True)
            name = time.strftime("%Y-%m-%d_%H-%M-%S") + ".png"
            path = os.path.join(save_dir, name)

            if mode == "full":
                cmd = [SCREENCAPTURE, "-x", path]
            elif mode == "window":
                cmd = [SCREENCAPTURE, "-w", "-x", path]  # -w 点击选择窗口
            else:
                cmd = [SCREENCAPTURE, "-i", "-x", path]  # -i 框选；空格切窗口；Esc 取消

            log("capture: %s" % " ".join(cmd))
            subprocess.run(cmd, timeout=180, check=False)

            if os.path.exists(path) and os.path.getsize(path) > 1000:
                self.last_path = path
                self.q.put(("done", path))
            else:
                log("capture cancelled or failed: %s" % path)
        except Exception as e:
            log("capture error: %s" % e)

    # ── 主线程定时器：处理队列 ────────────────
    def _on_tick(self, _timer):
        try:
            if not self._startup_notified:
                self._startup_notified = True
                notify(APP_NAME, "已启动 ✓ 区域 %s · 全屏 %s · 窗口 %s\n截图后：空格=钉图 M=美化"
                       % (self.cfg.get("hotkey", "cmd+shift+A"),
                          self.cfg.get("hotkey_full", "alt+cmd+A"),
                          self.cfg.get("hotkey_window", "alt+cmd+W")))
            if not self._perm_notified:
                self._perm_notified = True
                self._check_permissions()
            if self._toast_shown_at and time.time() - self._toast_shown_at > 8:
                self._close_toast()
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "capture":
                    threading.Thread(target=self._capture_worker, args=(payload,), daemon=True).start()
                elif kind == "done":
                    self._on_capture_done(payload)
                elif kind == "menu_pin":
                    if self.last_path and os.path.exists(self.last_path):
                        self.pin_image(self.last_path)
                    else:
                        notify(APP_NAME, "还没有截图，先按热键截一张吧")
                elif kind == "pin_requested":
                    self._close_toast()
                    if payload and os.path.exists(payload):
                        self.pin_image(payload)
                elif kind == "beautify":
                    self._close_toast()
                    if payload and os.path.exists(payload):
                        self._open_beautify(payload)
                elif kind == "beautify_ready":
                    self._beautify_show_result(payload)
                elif kind == "toast_dismiss":
                    self._close_toast()
        except queue.Empty:
            pass
        except Exception as e:
            log("tick error: %s" % e)

    def _check_permissions(self):
        """启动后检查屏幕录制 / 辅助功能权限，缺失时提示并引导打开系统设置。"""
        try:
            screen_ok = bool(Quartz.CGPreflightScreenCaptureAccess())
        except Exception:
            screen_ok = True
        try:
            ax_ok = bool(AXIsProcessTrusted())
        except Exception:
            ax_ok = True
        if not screen_ok or not ax_ok:
            missing = []
            if not screen_ok:
                missing.append("屏幕录制")
            if not ax_ok:
                missing.append("辅助功能")
            log("permission missing: %s" % ", ".join(missing))
            rumps.alert(
                title="小金截图（自用）需要权限",
                message="缺少权限：%s\n\n请在弹出的系统设置中勾选本应用（Python 或「小金截图（自用）」），"
                        "然后重新启动本工具。" % "、".join(missing))
            try:
                if not screen_ok:
                    subprocess.Popen(["open",
                                      "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"])
                else:
                    subprocess.Popen(["open",
                                      "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
            except Exception as e:
                log("open settings error: %s" % e)

    def _on_capture_done(self, path):
        name = os.path.basename(path)
        auto_copy = self.cfg.get("auto_copy", True)

        if auto_copy:
            try:
                copy_to_clipboard(path)
            except Exception as e:
                log("clipboard error: %s" % e)

        if self.cfg.get("play_sound", True):
            threading.Thread(target=play_sound, daemon=True).start()

        msg = "已保存：%s" % name
        if auto_copy:
            msg += "\n已复制到剪贴板"
        notify(APP_NAME, msg)
        log("done: %s" % path)

        # 截图后默认只进剪贴板；按空格钉图 / M 美化（浮层提示，Esc 关闭，8 秒自动消失）
        self._arm_space_to_pin(path)

        # 复制完成后焦点回到截图前的应用，可直接粘贴
        self._restore_frontmost()

    def _restore_frontmost(self):
        """把焦点还给截图前用户正在用的应用。"""
        app = getattr(self, "_prev_app", None)
        if app is None:
            return
        try:
            app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
        except Exception as e:
            log("restore frontmost error: %s" % e)
        finally:
            self._prev_app = None

    def _arm_space_to_pin(self, path):
        """截图完成后：弹出小提示浮层，按空格钉图、Esc 关闭、8 秒自动消失。"""
        if not self.cfg.get("pin_on_space", True):
            return
        self._toast_path = path
        self._show_toast(path)

    def _close_toast(self):
        """隐藏浮层（窗口复用，不销毁，避免 PyObjC 反复创建/关闭窗口导致崩溃）。"""
        try:
            if self._toast_window is not None:
                self._toast_window.orderOut_(None)
        except Exception as e:
            log("toast close error: %s" % e)
        self._toast_window = None
        self._toast_shown_at = 0

    def _show_toast(self, path):
        """屏幕下方的小提示浮层：缩略图 + 「按空格钉图 / Esc 关闭」。窗口只创建一次，之后复用。"""
        try:
            img = NSImage.alloc().initWithContentsOfFile_(path)
            if img is None or img.size().width < 1:
                return

            t = self._toast
            if t is None:
                tw, th = 330, 150
                win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                    NSRect(NSPoint(0, 0), NSSize(tw, th)),
                    NSBorderlessWindowMask, NSBackingStoreBuffered, False,
                )
                win.setLevel_(NSFloatingWindowLevel)
                win.setOpaque_(False)
                win.setBackgroundColor_(NSColor.clearColor())
                win.setHasShadow_(True)

                imgview = NSImageView.alloc().initWithFrame_(NSRect(NSPoint(0, 0), NSSize(tw, th)))
                imgview.setImageScaling_(NSImageScaleProportionallyDown)

                label = NSTextField.alloc().initWithFrame_(NSRect(NSPoint(10, 12), NSSize(tw - 20, 22)))
                label.setStringValue_("✓ 已复制 · 空格 钉图 · M 美化 · Esc 关闭")
                label.setBezeled_(False)
                label.setDrawsBackground_(False)
                label.setEditable_(False)
                label.setSelectable_(False)
                label.setAlignment_(NSCenterTextAlignment)
                label.setFont_(NSFont.systemFontOfSize_(12))
                label.setTextColor_(NSColor.whiteColor())

                box = NSBox.alloc().initWithFrame_(NSRect(NSPoint(0, 0), NSSize(tw, th)))
                box.setBoxType_(NSBoxCustom)
                box.setFillColor_(NSColor.colorWithCalibratedWhite_alpha_(0.12, 0.92))
                box.setBorderColor_(NSColor.colorWithCalibratedWhite_alpha_(1.0, 0.35))
                box.setBorderWidth_(1)
                box.setCornerRadius_(14)
                box.setTitlePosition_(NSNoTitle)

                container = NSView.alloc().initWithFrame_(NSRect(NSPoint(0, 0), NSSize(tw, th)))
                container.addSubview_(box)
                container.addSubview_(imgview)
                container.addSubview_(label)
                win.setContentView_(container)

                t = self._toast = {
                    "win": win, "imgview": imgview, "label": label,
                    "box": box, "container": container, "img": None,
                    "w": tw, "h": th,
                }

            win = t["win"]
            tw, th = t["w"], t["h"]
            isize = img.size()
            scale = min(1.0, 150.0 / isize.width, 90.0 / isize.height)
            iw = max(60, int(isize.width * scale))
            ih = max(40, int(isize.height * scale))
            iw = min(iw, tw - 16)
            ih = min(ih, th - 42)
            t["imgview"].setFrame_(NSRect(NSPoint((tw - iw) / 2, th - ih - 8), NSSize(iw, ih)))
            t["imgview"].setImage_(img)
            t["img"] = img              # 强引用，防止被提前释放

            screen = NSScreen.mainScreen().frame()
            x = screen.origin.x + (screen.size.width - tw) / 2
            y = screen.origin.y + 90
            win.setFrameOrigin_(NSPoint(x, y))
            win.orderFront_(None)
            self._toast_window = win
            self._toast_shown_at = time.time()
            log("toast shown: %s" % path)
        except Exception as e:
            log("toast error: %s" % e)

    # ── 钉图到屏幕 ───────────────────────────
    def pin_image(self, path):
        try:
            img = NSImage.alloc().initWithContentsOfFile_(path)
            if img is None or img.size().width < 1:
                return
            isize = img.size()
            screen = NSScreen.mainScreen().frame()

            max_w = screen.size.width * 0.75
            max_h = screen.size.height * 0.8
            scale = min(1.0, max_w / isize.width, max_h / isize.height)
            w = max(200, int(isize.width * scale))
            h = max(120, int(isize.height * scale))

            win = PinWindow.alloc().initWithContentRect_styleMask_backing_defer_(
                NSRect(NSPoint(0, 0), NSSize(w, h)),
                NSBorderlessWindowMask, NSBackingStoreBuffered, False,
            )
            win.setLevel_(NSFloatingWindowLevel)
            win.setMovableByWindowBackground_(True)
            win.setOpaque_(False)
            win.setBackgroundColor_(NSColor.clearColor())
            win.setHasShadow_(True)

            imgview = PassthroughImageView.alloc().initWithFrame_(NSRect(NSPoint(0, 0), NSSize(w, h)))
            imgview.setImage_(img)
            imgview.setImageScaling_(NSImageScaleProportionallyDown)

            # ✕ 关闭图标（纯装饰；点击关闭由 PinWindow 右上角热区处理）
            xview = PassthroughImageView.alloc().initWithFrame_(
                NSRect(NSPoint(w - 40, h - 40), NSSize(32, 32)))
            xview.setImage_(make_close_icon())
            xview.setToolTip_("关闭钉图")

            container = NSView.alloc().initWithFrame_(NSRect(NSPoint(0, 0), NSSize(w, h)))
            container.addSubview_(imgview)
            container.addSubview_(xview)
            win.setContentView_(container)

            offset = len(self.pin_windows) * 28
            x = screen.origin.x + (screen.size.width - w) / 2 + offset
            y = screen.origin.y + (screen.size.height - h) / 2 + offset
            win.setFrameOrigin_(NSPoint(x, y))
            win.makeKeyAndOrderFront_(None)

            self.pin_windows.append(win)
            win._owner = self             # 供关闭时移除引用
            if len(self.pin_windows) > 12:
                self.pin_windows = self.pin_windows[-12:]
            log("pin: %s" % path)
        except Exception as e:
            log("pin error: %s" % e)

    # ── 截图美化（9 套背景 + 圆角阴影，←→ 切换，⌘C/回车 复制）──
    def _open_beautify(self, path):
        try:
            self._beautify_path = path
            self._beautify_bg = int(self.cfg.get("beautify_background", 0))
            self._beautify_busy = False
            self._beautify_ready = False
            self._build_beautify_window()
            self._beautify_start_render()
        except Exception as e:
            log("beautify open error: %s" % e)

    def _build_beautify_window(self):
        """创建或复用美化预览窗口（窗口对象常驻，不销毁，避免 PyObjC 崩溃）。"""
        if self._beautify_views is not None:
            return
        imgview = NSImageView.alloc().initWithFrame_(NSRect(NSPoint(0, 0), NSSize(600, 400)))
        imgview.setImageScaling_(NSImageScaleProportionallyDown)
        label = NSTextField.alloc().initWithFrame_(NSRect(NSPoint(0, 10), NSSize(600, 20)))
        label.setStringValue_("")
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        label.setAlignment_(NSCenterTextAlignment)
        label.setFont_(NSFont.systemFontOfSize_(12))
        label.setTextColor_(NSColor.whiteColor())
        busy = NSTextField.alloc().initWithFrame_(NSRect(NSPoint(0, 34), NSSize(600, 20)))
        busy.setStringValue_("")
        busy.setBezeled_(False)
        busy.setDrawsBackground_(False)
        busy.setEditable_(False)
        busy.setSelectable_(False)
        busy.setAlignment_(NSCenterTextAlignment)
        busy.setFont_(NSFont.systemFontOfSize_(11))
        busy.setTextColor_(NSColor.whiteColor())

        container = NSView.alloc().initWithFrame_(NSRect(NSPoint(0, 0), NSSize(600, 400)))
        container.addSubview_(imgview)
        container.addSubview_(label)
        container.addSubview_(busy)

        win = BeautifyWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSRect(NSPoint(0, 0), NSSize(600, 400)),
            NSBorderlessWindowMask, NSBackingStoreBuffered, False,
        )
        win.setLevel_(NSFloatingWindowLevel)
        win.setOpaque_(False)
        win.setBackgroundColor_(NSColor.clearColor())
        win.setHasShadow_(True)
        win.setContentView_(container)
        win._owner = self
        self._beautify_win = win
        self._beautify_views = {"imgview": imgview, "label": label, "busy": busy,
                                "container": container, "win": win}

    def _beautify_start_render(self):
        """后台线程合成当前背景，完成后通知主线程显示。"""
        if self._beautify_busy or self._beautify_path is None:
            return
        self._beautify_busy = True
        self._beautify_ready = False
        try:
            self._beautify_views["busy"].setStringValue_("处理中…")
        except Exception:
            pass
        path, idx = self._beautify_path, self._beautify_bg
        threading.Thread(target=self._beautify_render, args=(path, idx), daemon=True).start()

    def _beautify_render(self, path, idx):
        try:
            make_beautified(path, idx)
            self.q.put(("beautify_ready", idx))
        except Exception as e:
            log("beautify render error: %s" % e)
            self.q.put(("beautify_ready", None))

    def _beautify_show_result(self, idx):
        """主线程：加载合成图并更新预览窗口。"""
        try:
            self._beautify_busy = False
            if idx is None or not os.path.exists(TMP_BEAUTIFY):
                self._beautify_ready = False
                return
            img = NSImage.alloc().initWithContentsOfFile_(TMP_BEAUTIFY)
            if img is None or img.size().width < 1:
                return
            self._beautify_ready = True
            v = self._beautify_views
            isize = img.size()
            max_w, max_h = 760.0, 560.0
            scale = min(1.0, max_w / isize.width, max_h / isize.height)
            w = max(260, int(isize.width * scale))
            h = max(180, int(isize.height * scale))
            v["win"].setFrame_(NSRect(NSPoint(0, 0), NSSize(w, h + 64)))
            v["imgview"].setFrame_(NSRect(NSPoint(0, 64), NSSize(w, h)))
            v["imgview"].setImage_(img)
            name = BEAUTIFY_BACKGROUNDS[idx][0]
            v["label"].setStringValue_("背景：%s   ← → 切换 · ⌘C/回车 复制 · Esc 关闭" % name)
            v["busy"].setStringValue_("")
            screen = NSScreen.mainScreen().frame()
            x = screen.origin.x + (screen.size.width - w) / 2
            y = screen.origin.y + (screen.size.height - (h + 64)) / 2
            v["win"].setFrameOrigin_(NSPoint(x, y))
            v["win"].makeKeyAndOrderFront_(None)
            log("beautify preview: bg=%s" % name)
        except Exception as e:
            log("beautify show error: %s" % e)
            self._beautify_busy = False

    def _beautify_switch(self, step):
        if self._beautify_path is None or self._beautify_busy:
            return
        total = len(BEAUTIFY_BACKGROUNDS)
        self._beautify_bg = (self._beautify_bg + step) % total
        self._beautify_start_render()

    def _beautify_copy(self):
        if not self._beautify_ready or not os.path.exists(TMP_BEAUTIFY):
            notify(APP_NAME, "还在处理中，稍等一下再复制")
            return
        try:
            copy_to_clipboard(TMP_BEAUTIFY)
            threading.Thread(target=play_sound, daemon=True).start()
            notify(APP_NAME, "美化图已复制 ✓（背景：%s）"
                   % BEAUTIFY_BACKGROUNDS[self._beautify_bg][0])
            self._close_beautify()
            self._restore_frontmost()
        except Exception as e:
            log("beautify copy error: %s" % e)

    def _close_beautify(self):
        try:
            if self._beautify_win is not None:
                self._beautify_win.orderOut_(None)
        except Exception:
            pass
        self._beautify_path = None
        self._beautify_ready = False
        self._beautify_busy = False

    # ── 启动与退出 ───────────────────────────
    def run(self):
        # 隐藏 Dock 图标，只留菜单栏
        try:
            NSApplication.sharedApplication().setActivationPolicy_(
                NSApplicationActivationPolicyAccessory
            )
        except Exception as e:
            log("activation policy error: %s" % e)

        self.start_hotkey()
        self.timer.start()
        log("=== %s started ===" % APP_NAME)
        self.app.run()

    def _shutdown(self):
        try:
            if self.listener is not None:
                self.listener.stop()
        except Exception:
            pass
        log("=== %s exited ===" % APP_NAME)
        rumps.quit_application()


if __name__ == "__main__":
    SnapApp().run()
