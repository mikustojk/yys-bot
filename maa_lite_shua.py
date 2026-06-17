import ctypes
import datetime
import json
import os
import random
import re
import subprocess
import sys
import time

import cv2
import numpy as np
import win32gui
import win32ui


ctypes.windll.user32.SetProcessDPIAware()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(SCRIPT_DIR, "images", "maa")
BASE_W = 1280
BASE_H = 720


TASKS = {
    "challenge": {
        "template": "challenge.png",
        "roi": (0.72, 0.60, 0.28, 0.40),
        "threshold": 0.78,
        "method": "dark_mask",
        "pick": "right_bottom",
        "required": True,
    },
    "settlement": {
        "template": "settlement.png",
        "roi": (0.0, 0.0, 1.0, 1.0),
        "threshold": 0.70,
        "method": "normal",
        "scales": [0.55, 0.60, 0.65, 0.67, 0.70, 0.75, 0.80, 0.90, 1.00],
        "required": True,
    },
    "bounty": {
        "template": "bounty.png",
        "roi": (0.15, 0.10, 0.70, 0.80),
        "threshold": 0.78,
        "method": "normal",
        "required": False,
    },
    "bounty_decline": {
        "template": "bounty_decline.png",
        "roi": (0.15, 0.45, 0.70, 0.45),
        "threshold": 0.78,
        "method": "normal",
        "required": False,
    },
    "disconnect": {
        "template": "disconnect.png",
        "roi": (0.15, 0.15, 0.70, 0.70),
        "threshold": 0.78,
        "method": "normal",
        "required": False,
    },
    "disconnect_ok": {
        "template": "disconnect_ok.png",
        "roi": (0.20, 0.45, 0.60, 0.45),
        "threshold": 0.78,
        "method": "normal",
        "required": False,
    },
}


def log(message: str):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"{now} {message}", flush=True)


def get_run_count(prompt: str) -> int:
    value = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("YYS_BOT_TIMES")
    if value is not None:
        return int(value)
    return int(input(prompt))


def read_image(path: str):
    if not os.path.exists(path):
        return None
    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def maa_scale_size(width: int, height: int) -> tuple:
    if width <= 0 or height <= 0:
        return BASE_W, BASE_H

    default_ratio = BASE_W / BASE_H
    cur_ratio = width / height
    if cur_ratio >= default_ratio:
        return int(cur_ratio * BASE_H), BASE_H
    return BASE_W, int(BASE_W / cur_ratio)


class BgEmulatorWindow:
    def __init__(self, window_title="MuMu安卓设备", adb_port=16384):
        self.adb_exe = os.path.join(SCRIPT_DIR, "adb.exe")
        if not os.path.exists(self.adb_exe):
            self.adb_exe = "adb.exe"

        self.hwnd = win32gui.FindWindow(None, window_title)
        if not self.hwnd:
            raise RuntimeError(f"未找到窗口：{window_title}，请先打开 MuMu。")

        self.render_hwnd = self._get_mumu_render_child(self.hwnd)
        self.adb_address = f"127.0.0.1:{adb_port}"
        self.android_w = 0
        self.android_h = 0
        self.last_raw_size = None
        self.last_base_size = None

        log(f"[+] 主窗口: {hex(self.hwnd)}, 渲染窗口: {hex(self.render_hwnd)}")
        self._connect_adb()

    def _connect_adb(self):
        subprocess.run(
            [self.adb_exe, "connect", self.adb_address],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        try:
            out = subprocess.check_output(
                [self.adb_exe, "-s", self.adb_address, "shell", "wm", "size"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            ).decode("utf-8", errors="ignore")
            match = re.search(r"(\d+)x(\d+)", out)
            if match:
                self.android_w = int(match.group(1))
                self.android_h = int(match.group(2))
                log(f"[*] Android 分辨率: {self.android_w}x{self.android_h}")
        except Exception as exc:
            log(f"[!] 获取 Android 分辨率失败: {exc}")

    def _get_mumu_render_child(self, parent_hwnd):
        child_hwnds = []
        win32gui.EnumChildWindows(parent_hwnd, lambda hwnd, param: param.append(hwnd), child_hwnds)
        if not child_hwnds:
            return parent_hwnd

        target_hwnd = parent_hwnd
        max_area = 0
        for hwnd in child_hwnds:
            left, top, right, bottom = win32gui.GetClientRect(hwnd)
            area = (right - left) * (bottom - top)
            if area > max_area:
                max_area = area
                target_hwnd = hwnd
        return target_hwnd

    def _client_size(self) -> tuple:
        left, top, right, bottom = win32gui.GetClientRect(self.render_hwnd)
        return right - left, bottom - top

    def screenshot_raw(self):
        width, height = self._client_size()

        hwnd_dc = win32gui.GetWindowDC(self.render_hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()

        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(bitmap)

        ctypes.windll.user32.PrintWindow(self.render_hwnd, save_dc.GetSafeHdc(), 3)

        bmpinfo = bitmap.GetInfo()
        bmpstr = bitmap.GetBitmapBits(True)
        image = np.frombuffer(bmpstr, dtype="uint8")
        image.shape = (bmpinfo["bmHeight"], bmpinfo["bmWidth"], 4)

        win32gui.DeleteObject(bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(self.render_hwnd, hwnd_dc)

        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    def screenshot_base(self):
        raw = self.screenshot_raw()
        raw_h, raw_w = raw.shape[:2]
        base_w, base_h = maa_scale_size(raw_w, raw_h)

        self.last_raw_size = (raw_w, raw_h)
        self.last_base_size = (base_w, base_h)

        if raw_w == base_w and raw_h == base_h:
            return raw

        interpolation = cv2.INTER_AREA if base_w <= raw_w and base_h <= raw_h else cv2.INTER_LINEAR
        return cv2.resize(raw, (base_w, base_h), interpolation=interpolation)

    def _map_raw_to_adb(self, x: int, y: int, raw_w: int, raw_h: int) -> tuple:
        if self.android_w <= 0 or self.android_h <= 0 or raw_w <= 0 or raw_h <= 0:
            return x, y

        adb_w = self.android_w
        adb_h = self.android_h
        if raw_w > raw_h and self.android_w < self.android_h:
            adb_w, adb_h = self.android_h, self.android_w
        elif raw_w < raw_h and self.android_w > self.android_h:
            adb_w, adb_h = self.android_h, self.android_w

        return int(x / raw_w * adb_w), int(y / raw_h * adb_h)

    def click_base(self, x: int, y: int):
        raw_w, raw_h = self.last_raw_size or self._client_size()
        base_w, base_h = self.last_base_size or maa_scale_size(raw_w, raw_h)
        raw_x = int(x / base_w * raw_w)
        raw_y = int(y / base_h * raw_h)
        adb_x, adb_y = self._map_raw_to_adb(raw_x, raw_y, raw_w, raw_h)

        subprocess.run(
            [self.adb_exe, "-s", self.adb_address, "shell", "input", "tap", str(adb_x), str(adb_y)],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        log(f"[debug] click base=({x},{y}) raw=({raw_x},{raw_y}) adb=({adb_x},{adb_y})")


class MaaLiteMatcher:
    def __init__(self, emu: BgEmulatorWindow):
        self.emu = emu
        self.last_screen = None
        self.debug_times = {}

    def template_path(self, task_name: str) -> str:
        return os.path.join(TEMPLATE_DIR, TASKS[task_name]["template"])

    def has_template(self, task_name: str) -> bool:
        return os.path.exists(self.template_path(task_name))

    def check_required_templates(self) -> bool:
        missing = []
        for name, task in TASKS.items():
            if task["required"] and not self.has_template(name):
                missing.append(task["template"])
        if missing:
            log("[ERROR] 缺少必要模板：" + ", ".join(missing))
            log("[ERROR] 请先运行 capture_maa_template.py 截图，具体截法见我给你的说明。")
            return False
        return True

    def _rect_from_ratio(self, ratio_rect, width: int, height: int):
        x = int(width * ratio_rect[0])
        y = int(height * ratio_rect[1])
        w = int(width * ratio_rect[2])
        h = int(height * ratio_rect[3])
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        w = max(1, min(w, width - x))
        h = max(1, min(h, height - y))
        return x, y, w, h

    def _dark_mask(self, templ_gray):
        mask = cv2.inRange(templ_gray, 0, 130)
        if cv2.countNonZero(mask) < 20:
            return None
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        return cv2.dilate(mask, kernel, iterations=1)

    def _debug_miss(self, task_name: str, score: float, scale: float):
        now = time.time()
        last = self.debug_times.get(task_name, 0)
        if now - last >= 5:
            log(f"[debug] {task_name} miss best={score:.3f} scale={scale:.2f}")
            self.debug_times[task_name] = now

    def find(self, task_name: str):
        if not self.has_template(task_name):
            return None

        task = TASKS[task_name]
        screen = self.emu.screenshot_base()
        self.last_screen = screen

        templ = read_image(self.template_path(task_name))
        if templ is None:
            log(f"[WARN] 模板读取失败: {self.template_path(task_name)}")
            return None

        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        templ_gray = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
        screen_h, screen_w = screen_gray.shape[:2]
        roi_x, roi_y, roi_w, roi_h = self._rect_from_ratio(task["roi"], screen_w, screen_h)
        search = screen_gray[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]

        threshold = task["threshold"]
        best_score = -1.0
        best_loc = None
        best_size = None
        best_scale = 1.0

        for scale in task.get("scales", [1.0]):
            if scale == 1.0:
                scaled_templ = templ_gray
            else:
                scaled_w = max(8, int(templ_gray.shape[1] * scale))
                scaled_h = max(8, int(templ_gray.shape[0] * scale))
                interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
                scaled_templ = cv2.resize(templ_gray, (scaled_w, scaled_h), interpolation=interpolation)

            if scaled_templ.shape[0] > search.shape[0] or scaled_templ.shape[1] > search.shape[1]:
                continue

            if task["method"] == "dark_mask":
                mask = self._dark_mask(scaled_templ)
                if mask is None:
                    continue
                res = cv2.matchTemplate(search, scaled_templ, cv2.TM_CCORR_NORMED, mask=mask)
            else:
                res = cv2.matchTemplate(search, scaled_templ, cv2.TM_CCOEFF_NORMED)

            if task.get("pick") == "right_bottom":
                ys, xs = np.where(res >= threshold)
                if len(xs) == 0:
                    _, score, _, loc = cv2.minMaxLoc(res)
                else:
                    best_index = max(
                        range(len(xs)),
                        key=lambda i: (
                            ys[i],
                            xs[i],
                            float(res[ys[i], xs[i]]),
                        ),
                    )
                    loc = (int(xs[best_index]), int(ys[best_index]))
                    score = float(res[loc[1], loc[0]])
            else:
                _, score, _, loc = cv2.minMaxLoc(res)

            if np.isfinite(score) and score > best_score:
                best_score = float(score)
                best_loc = loc
                best_size = (scaled_templ.shape[1], scaled_templ.shape[0])
                best_scale = scale

        if best_loc is None or not np.isfinite(best_score) or best_score < threshold:
            self._debug_miss(task_name, best_score, best_scale)
            return None

        x = best_loc[0] + roi_x
        y = best_loc[1] + roi_y
        w, h = best_size
        log(f"[debug] {task_name} score={best_score:.3f} scale={best_scale:.2f} rect=({x},{y},{w},{h})")
        return x, y, w, h, best_score, task_name

    def click_match(self, match, wait=0.5):
        x, y, w, h, _ = match[:5]
        if len(match) >= 6 and match[5] == "settlement":
            self.emu.click_base(x + int(w * 0.50), y + int(h * 0.55))
            time.sleep(wait)
            return

        if len(match) >= 6 and match[5] == "challenge":
            click_x = x + int(w * 0.52)
            click_y = y + int(h * 0.78)
            self.emu.click_base(click_x, click_y)
            time.sleep(wait)
            return

        margin_x = max(2, int(w * 0.18))
        margin_y = max(2, int(h * 0.18))
        click_x = random.randint(x + margin_x, x + w - margin_x)
        click_y = random.randint(y + margin_y, y + h - margin_y)
        self.emu.click_base(click_x, click_y)
        time.sleep(wait)


def handle_optional_dialogs(bot: MaaLiteMatcher):
    disconnect = bot.find("disconnect")
    if disconnect:
        log("[操作] 检测到掉线弹窗")
        ok = bot.find("disconnect_ok")
        if ok:
            bot.click_match(ok, wait=random.uniform(1.0, 2.0))
        return True

    bounty = bot.find("bounty")
    if bounty:
        log("[操作] 检测到悬赏/邀请弹窗")
        decline = bot.find("bounty_decline")
        if decline:
            bot.click_match(decline, wait=random.uniform(1.0, 2.0))
        return True

    return False


def run_loop(bot: MaaLiteMatcher, times: int):
    completed = 0
    while completed < times:
        log(f"--- 已完成 {completed}/{times}，寻找挑战按钮 ---")
        handle_optional_dialogs(bot)

        challenge = bot.find("challenge")
        if not challenge:
            log("[等待] 未找到挑战按钮")
            time.sleep(1.5)
            continue

        bot.click_match(challenge, wait=random.uniform(1.2, 2.0))
        log("[操作] 点击挑战按钮")

        start = time.time()
        while time.time() - start < 240:
            handle_optional_dialogs(bot)
            settlement = bot.find("settlement")
            if settlement:
                closed = False
                for attempt in range(3):
                    bot.click_match(settlement, wait=random.uniform(1.0, 1.5))
                    time.sleep(0.8)
                    settlement = bot.find("settlement")
                    if not settlement:
                        closed = True
                        break
                    log(f"[debug] settlement still visible, click retry {attempt + 1}/3")

                if not closed:
                    log("[WARN] 检测到结算，但点击后仍未关闭，继续等待。")
                    continue
                completed += 1
                log(f"--- 第 {completed}/{times} 次挑战完成 ---")
                break
            time.sleep(1.0)
        else:
            log("[WARN] 240 秒内没有检测到结算模板，回到寻找挑战按钮。")


def main():
    os.chdir(SCRIPT_DIR)
    log("正在启动 MAA-lite 挑战脚本...")
    emu = BgEmulatorWindow()
    bot = MaaLiteMatcher(emu)
    if not bot.check_required_templates():
        return

    try:
        times = get_run_count("请输入刷取次数：")
    except ValueError:
        log("[ERROR] 请输入有效数字。")
        return

    run_loop(bot, times)
    log("任务结束。")


if __name__ == "__main__":
    main()
