#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地截图小插件（macOS）
----------------------
功能：
  1. 全局热键（默认 ⌘1）一键框选截图（系统级框选 UI，空格切窗口模式，Esc 取消）
  2. 截图后自动保存到 ~/Desktop/截图/（时间戳命名）
  3. 自动复制到剪贴板
  4. 菜单栏常驻小图标（截图/全屏/钉图/打开文件夹/改快捷键/退出）
  5. 截图完成提示音 + 系统通知
  6. 钉图到屏幕：截图后自动弹出可拖动、可关闭的置顶悬浮窗（也可从菜单栏钉最近一张）

配置文件：~/.localsnap/config.json（可改快捷键、保存目录等，改完需重启生效）
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
from PIL import Image                         # 图片尺寸读取（备用）
import objc                                   # PyObjC 运行时
from AppKit import (NSPasteboard, NSPasteboardTypePNG, NSApplication,
                    NSApplicationActivationPolicyAccessory,
                    NSImage, NSImageView, NSButton, NSRoundedBezelStyle,
                    NSWindow, NSBorderlessWindowMask, NSBackingStoreBuffered,
                    NSFloatingWindowLevel, NSColor, NSView, NSImageScaleProportionallyDown,
                    NSScreen, NSTextField, NSCenterTextAlignment, NSFont,
                    NSBox, NSBoxCustom, NSNoTitle,
                    NSFontAttributeName, NSForegroundColorAttributeName)
from Foundation import NSData, NSRect, NSPoint, NSSize, NSString

APP_NAME = "本地截图工具"
CONFIG_DIR = os.path.expanduser("~/.localsnap")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
LOG_PATH = os.path.join(CONFIG_DIR, "log.txt")
SCREENCAPTURE = "/usr/sbin/screencapture"
SOUND_PATH = "/System/Library/Sounds/Glass.aiff"

DEFAULT_CONFIG = {
    "hotkey": "cmd+1",          # 全局快捷键，格式：cmd / ctrl / shift / alt 任意组合 + 按键，如 "cmd+shift+3"
    "save_dir": "~/Desktop/截图",  # 截图保存目录
    "auto_copy": True,          # 截图后自动复制到剪贴板
    "pin_on_space": True,       # 截图后按空格键钉图（Esc 关闭提示浮层）
    "play_sound": True,         # 截图完成提示音
}


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

        self.app = rumps.App(
            "小金截图（自用）",
            title=APP_NAME,
            icon=self._ensure_menu_icon(),
            menu=[
                rumps.MenuItem("立即截图（区域）"),
                rumps.MenuItem("全屏截图"),
                None,
                rumps.MenuItem("钉图最近一张"),
                rumps.MenuItem("打开截图文件夹"),
                rumps.MenuItem("更改快捷键…"),
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
        @rumps.clicked("立即截图（区域）")
        def _area(_sender):
            self._request_capture("area")

        @rumps.clicked("全屏截图")
        def _full(_sender):
            self._request_capture("full")

        @rumps.clicked("钉图最近一张")
        def _pin(_sender):
            self.q.put(("menu_pin", None))

        @rumps.clicked("打开截图文件夹")
        def _open_dir(_sender):
            d = expand_save_dir(self.cfg["save_dir"])
            os.makedirs(d, exist_ok=True)
            subprocess.Popen(["open", d])

        @rumps.clicked("更改快捷键…")
        def _edit_cfg(_sender):
            subprocess.Popen(["open", "-t", CONFIG_PATH])

        @rumps.clicked("关于")
        def _about(_sender):
            rumps.alert(title="小金截图（自用）",
                        message="macOS 本地截图小插件\n热键：%s\n截图保存：%s\n\n配置文件：%s\n（修改后退出并重新启动生效）"
                                % (self.cfg["hotkey"], expand_save_dir(self.cfg["save_dir"]), CONFIG_PATH))

        @rumps.clicked("退出")
        def _quit(_sender):
            self._shutdown()

    def _ensure_menu_icon(self):
        """生成一个彩色小狐狸菜单栏图标（44px，适配 Retina）。"""
        p = os.path.join(CONFIG_DIR, "menu_icon.png")
        try:
            if not os.path.exists(p):
                src = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   ".creative-design", "icon-task", "icon_source.png")
                if os.path.exists(src):
                    img = Image.open(src).convert("RGB")
                    img.resize((44, 44), Image.LANCZOS).save(p)
        except Exception as e:
            log("menu icon error: %s" % e)
        return p if os.path.exists(p) else None

    # ── 热键（单个全局监听器，手动识别所有键，最可靠）──
    def start_hotkey(self):
        try:
            self._pressed = set()                 # 当前按住的键
            self._hotkey_fired = False            # 防止按住不放连续触发截图
            self._hotkey_set = self._parse_hotkey(self.cfg.get("hotkey", "cmd+shift+a"))
            self.listener = pynput.keyboard.Listener(
                on_press=self._on_key, on_release=self._on_key_release)
            self.listener.daemon = True
            self.listener.start()
            log("hotkey started: %s (single listener)" % self.cfg.get("hotkey", "cmd+shift+a"))
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

            # 1) 组合热键 → 截图
            if self._hotkey_set and self._hotkey_set.issubset(self._pressed):
                if not self._hotkey_fired:
                    self._hotkey_fired = True
                    self._request_capture("area")

            # 2) 空格 → 钉图（仅浮层显示时）
            if k == pynput.keyboard.Key.space and self._toast_window is not None:
                self.q.put(("pin_requested", self._toast_path))

            # 3) Esc → 关闭浮层（仅浮层显示时）
            if k == pynput.keyboard.Key.esc and self._toast_window is not None:
                self.q.put(("toast_dismiss", None))
        except Exception as e:
            log("key press error: %s" % e)

    def _on_key_release(self, key):
        try:
            k = self._canon_key(key)
            self._pressed.discard(k)
            # 松开热键中的任意一键，允许下次再触发截图
            if self._hotkey_set and k in self._hotkey_set:
                self._hotkey_fired = False
        except Exception:
            pass

    def _request_capture(self, mode):
        """任意线程可调用：放入队列，由主线程调度执行。"""
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
                notify(APP_NAME, "已启动 ✓ 菜单栏找到小狐狸图标，按 %s 即可截图"
                       % self.cfg.get("hotkey", "cmd+shift+A"))
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
                elif kind == "toast_dismiss":
                    self._close_toast()
        except queue.Empty:
            pass
        except Exception as e:
            log("tick error: %s" % e)

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

        # 截图后默认只进剪贴板；按空格才钉图（浮层提示，Esc 关闭，8 秒自动消失）
        self._arm_space_to_pin(path)

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
                tw, th = 280, 150
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
                label.setStringValue_("✓ 已复制到剪贴板 · 按 空格 钉图 · Esc 关闭")
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
