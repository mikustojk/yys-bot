import ctypes
import datetime
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
TEMPLATE_DIR = os.path.join(SCRIPT_DIR, "images", "templates")
BASE_W = 1280
BASE_H = 720


TASKS = {
    "stage": {
        "template": "k28_stage.png",
        "roi": (0.0, 0.0, 1.0, 1.0),
        "threshold": 0.78,
        "required": True,
    },
    "explore": {
        "template": "k28_explore.png",
        "roi": (0.0, 0.0, 1.0, 1.0),
        "threshold": 0.78,
        "required": True,
    },
    "battle": {
        "template": "k28_battle.png",
        "roi": (0.0, 0.0, 1.0, 1.0),
        "threshold": 0.76,
        "required": True,
    },
    "boss": {
        "template": "k28_boss.png",
        "roi": (0.0, 0.0, 1.0, 1.0),
        "threshold": 0.76,
        "required": True,
    },
    "settlement": {
        "template": "k28_settlement.png",
        "fallback": "settlement.png",
        "roi": (0.0, 0.0, 1.0, 1.0),
        "threshold": 0.72,
        "required": True,
    },
    "paper": {
        "template": "k28_paper.png",
        "roi": (0.0, 0.0, 1.0, 1.0),
        "threshold": 0.76,
        "required": True,
    },
    "treasure": {
        "template": "k28_treasure.png",
        "roi": (0.0, 0.0, 1.0, 1.0),
        "threshold": 0.76,
        "scales": [1.0, 0.67],
        "required": True,
    },
    "team_prompt": {
        "template": "k28_team_prompt.png",
        "roi": (0.0, 0.0, 1.0, 1.0),
        "threshold": 0.76,
        "scales": [1.0, 0.67],
        "required": True,
    },
    "team_confirm": {
        "template": "k28_team_confirm.png",
        "roi": (0.0, 0.0, 1.0, 1.0),
        "threshold": 0.76,
        "scales": [1.0, 0.67],
        "required": True,
    },
}


class ScriptStuck(Exception):
    pass


def log(message: str):
    print(message, flush=True)


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


def normalize_screen_size(width: int, height: int) -> tuple:
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
            raise RuntimeError(f"Window not found: {window_title}")

        self.render_hwnd = self._get_mumu_render_child(self.hwnd)
        self.adb_address = f"127.0.0.1:{adb_port}"
        self.android_w = 0
        self.android_h = 0
        self.last_raw_size = None
        self.last_base_size = None
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
        except Exception as exc:
            log(f"[WARN] failed to read Android size: {exc}")

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
        base_w, base_h = normalize_screen_size(raw_w, raw_h)
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

    def _base_to_raw(self, x: int, y: int):
        raw_w, raw_h = self.last_raw_size or self._client_size()
        base_w, base_h = self.last_base_size or normalize_screen_size(raw_w, raw_h)
        return int(x / base_w * raw_w), int(y / base_h * raw_h), raw_w, raw_h

    def _human_tap_adb(self, adb_x: int, adb_y: int, jitter=3, extra_tap_chance=0.06):
        x = adb_x + random.randint(-jitter, jitter)
        y = adb_y + random.randint(-jitter, jitter)
        drift_x = random.randint(-1, 1)
        drift_y = random.randint(-1, 1)
        press_ms = random.randint(45, 135)
        time.sleep(random.uniform(0.035, 0.16))
        subprocess.run(
            [
                self.adb_exe,
                "-s",
                self.adb_address,
                "shell",
                "input",
                "swipe",
                str(x),
                str(y),
                str(x + drift_x),
                str(y + drift_y),
                str(press_ms),
            ],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if random.random() < extra_tap_chance:
            time.sleep(random.uniform(0.055, 0.14))
            x2 = adb_x + random.randint(-jitter, jitter)
            y2 = adb_y + random.randint(-jitter, jitter)
            subprocess.run(
                [
                    self.adb_exe,
                    "-s",
                    self.adb_address,
                    "shell",
                    "input",
                    "swipe",
                    str(x2),
                    str(y2),
                    str(x2 + random.randint(-1, 1)),
                    str(y2 + random.randint(-1, 1)),
                    str(random.randint(40, 110)),
                ],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        time.sleep(random.uniform(0.025, 0.11))

    def click_base(self, x: int, y: int):
        raw_x, raw_y, raw_w, raw_h = self._base_to_raw(x, y)
        adb_x, adb_y = self._map_raw_to_adb(raw_x, raw_y, raw_w, raw_h)
        self._human_tap_adb(adb_x, adb_y)

    def swipe_base(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.8):
        rx1, ry1, raw_w, raw_h = self._base_to_raw(x1, y1)
        rx2, ry2, _, _ = self._base_to_raw(x2, y2)
        ax1, ay1 = self._map_raw_to_adb(rx1, ry1, raw_w, raw_h)
        ax2, ay2 = self._map_raw_to_adb(rx2, ry2, raw_w, raw_h)
        subprocess.run(
            [
                self.adb_exe,
                "-s",
                self.adb_address,
                "shell",
                "input",
                "swipe",
                str(ax1),
                str(ay1),
                str(ax2),
                str(ay2),
                str(int(duration * 1000)),
            ],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )


class TemplateMatcher:
    def __init__(self, emu: BgEmulatorWindow):
        self.emu = emu
        self.debug_times = {}

    def template_path(self, task_name: str) -> str:
        task = TASKS[task_name]
        path = os.path.join(TEMPLATE_DIR, task["template"])
        if not os.path.exists(path) and task.get("fallback"):
            fallback = os.path.join(TEMPLATE_DIR, task["fallback"])
            if os.path.exists(fallback):
                return fallback
        return path

    def has_template(self, task_name: str) -> bool:
        return os.path.exists(self.template_path(task_name))

    def check_required_templates(self) -> bool:
        missing = []
        for name, task in TASKS.items():
            if task["required"] and not self.has_template(name):
                missing.append(task["template"])
        if missing:
            log("[ERROR] missing templates: " + ", ".join(missing))
            log("[ERROR] use capture_template.py to capture the k28_* templates.")
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

    def _debug_miss(self, task_name: str, score: float):
        return

    def find(self, task_name: str):
        if not self.has_template(task_name):
            return None

        task = TASKS[task_name]
        screen = self.emu.screenshot_base()
        templ = read_image(self.template_path(task_name))
        if templ is None:
            return None

        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        templ_gray = cv2.cvtColor(templ, cv2.COLOR_BGR2GRAY)
        screen_h, screen_w = screen_gray.shape[:2]
        roi_x, roi_y, roi_w, roi_h = self._rect_from_ratio(task["roi"], screen_w, screen_h)
        search = screen_gray[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]
        best_score = -1.0
        best_loc = None
        best_templ = None
        best_scale = 1.0
        for scale in task.get("scales", [1.0]):
            if scale <= 0:
                continue
            scaled = templ_gray
            if scale != 1.0:
                scaled_w = max(1, int(templ_gray.shape[1] * scale))
                scaled_h = max(1, int(templ_gray.shape[0] * scale))
                scaled = cv2.resize(templ_gray, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)
            if scaled.shape[0] > search.shape[0] or scaled.shape[1] > search.shape[1]:
                continue
            res = cv2.matchTemplate(search, scaled, cv2.TM_CCOEFF_NORMED)
            _, score, _, loc = cv2.minMaxLoc(res)
            if np.isfinite(score) and score > best_score:
                best_score = float(score)
                best_loc = loc
                best_templ = scaled
                best_scale = scale

        if best_loc is None or best_templ is None or best_score < task["threshold"]:
            self._debug_miss(task_name, best_score)
            return None

        x = best_loc[0] + roi_x
        y = best_loc[1] + roi_y
        w = best_templ.shape[1]
        h = best_templ.shape[0]
        return x, y, w, h, best_score, task_name

    def random_point(self, match):
        x, y, w, h, _ = match[:5]
        safe_x1 = x + int(w * 0.1)
        safe_x2 = x + max(int(w * 0.9), int(w * 0.1))
        safe_y1 = y + int(h * 0.1)
        safe_y2 = y + max(int(h * 0.9), int(h * 0.1))
        return random.randint(safe_x1, safe_x2), random.randint(safe_y1, safe_y2)

    def click_base_point(self, x: int, y: int, wait=0.5):
        self.emu.click_base(x, y)
        time.sleep(wait)

    def click_match(self, match, wait=0.5):
        click_x, click_y = self.random_point(match)
        self.emu.click_base(click_x, click_y)
        time.sleep(wait)


def wait_until_gone(bot: TemplateMatcher, task_name: str, timeout=3.0):
    start = time.time()
    while time.time() - start < timeout:
        if not bot.find(task_name):
            return True
        time.sleep(0.3)
    return False


def wait_and_click(bot: TemplateMatcher, task_name: str, timeout=120, retries=3):
    start = time.time()
    while time.time() - start < timeout:
        match = bot.find(task_name)
        if match:
            for attempt in range(retries):
                bot.click_match(match, wait=random.uniform(0.8, 1.2))
                if wait_until_gone(bot, task_name, timeout=2.0):
                    return True
                match = bot.find(task_name) or match
            return False
        time.sleep(1.0)
    return False


def enter_k28(bot: TemplateMatcher):
    start = time.time()
    while time.time() - start < 120:
        explore = bot.find("explore")
        if explore:
            bot.click_match(explore, wait=0.2)
            verify_start = time.time()
            while time.time() - verify_start < 2.5:
                if not bot.find("explore"):
                    time.sleep(0.5)
                    return True
                time.sleep(0.3)
            continue

        stage = bot.find("stage")
        if stage:
            bot.click_match(stage, wait=0.5)
        time.sleep(0.5)
    return False


def click_settlement_once(bot: TemplateMatcher, wait=1.0) -> bool:
    settlement = bot.find("settlement")
    if not settlement:
        return False
    bot.click_match(settlement, wait=wait)
    return True


def wait_for_settlement_and_click(bot: TemplateMatcher, timeout=120, wait=1.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        if click_settlement_once(bot, wait=wait):
            return True
        time.sleep(1)
    return False


def swipe_map(emu: BgEmulatorWindow):
    base_w, base_h = emu.last_base_size or (BASE_W, BASE_H)
    cx = base_w // 2 + random.randint(-50, 50)
    cy = base_h // 2 + random.randint(-50, 50)
    dx = int(random.randint(-1400, -1000) * base_w / 1920)
    emu.swipe_base(cx, cy, cx + dx, cy, duration=random.uniform(1.0, 1.5))


def finish_k28_rewards(bot: TemplateMatcher):
    log("处理奖励")
    base_w, base_h = bot.emu.last_base_size or (BASE_W, BASE_H)
    for _ in range(1, 4):
        start = time.time()
        while time.time() - start < 2:
            paper = bot.find("paper")
            if paper:
                x, y = bot.random_point(paper)
                bot.click_base_point(x, y, wait=random.uniform(0.4, 0.6))
                offset_x = int(random.randint(-20, 20) * base_w / 1920)
                offset_y = int(random.randint(280, 320) * base_h / 1080)
                bot.click_base_point(x + offset_x, y + offset_y, wait=1)
                break
            time.sleep(0.2)

    treasure = bot.find("treasure")
    if treasure:
        bot.click_match(treasure, wait=0.2)
        time.sleep(3)
        if not wait_for_settlement_and_click(bot, timeout=120, wait=1.0):
            raise ScriptStuck("treasure settlement not found")

    time.sleep(random.uniform(1, 4))

    if bot.find("team_prompt"):
        confirm = bot.find("team_confirm")
        if confirm:
            bot.click_match(confirm, wait=random.uniform(0.8, 1.2))
    log("奖励处理完成")


def run_k28(bot: TemplateMatcher, emu: BgEmulatorWindow, times: int):
    for index in range(times):
        current = index + 1
        log(f"第 {current}/{times} 次困难28开始")
        if not enter_k28(bot):
            raise ScriptStuck("could not enter K28 map")
        log("进入探索地图")

        boss_found = False
        step_start = time.time()
        re_search = 0
        while not boss_found:
            if time.time() - step_start > 120:
                raise ScriptStuck("no target advanced within 120 seconds")
            if re_search > 5:
                raise ScriptStuck("map search repeated more than 5 times")

            boss = bot.find("boss")
            if boss:
                bot.click_match(boss, wait=0.2)
                log(f"第 {current}/{times} 次：开始 Boss 战斗")
                boss_found = True
                continue

            battle = bot.find("battle")
            if battle:
                bot.click_match(battle, wait=0.2)
                log(f"第 {current}/{times} 次：开始小怪战斗")
                step_start = time.time()
                time.sleep(12)
                end_found = False
                wait_count = 0
                while wait_count < 5:
                    if click_settlement_once(bot, wait=1.0):
                        end_found = True
                        break
                    time.sleep(1)
                    wait_count += 1
                if end_found:
                    log(f"第 {current}/{times} 次：结束小怪战斗")
                re_search = 0 if end_found else re_search + 1
                time.sleep(0.5)
                continue

            re_search += 1
            swipe_map(emu)
            time.sleep(1.5)

        time.sleep(12)
        if not wait_for_settlement_and_click(bot, timeout=120, wait=random.uniform(1.5, 2.5)):
            raise ScriptStuck("boss settlement not found")
        log(f"第 {current}/{times} 次：结束 Boss 战斗")
        time.sleep(2)

        finish_k28_rewards(bot)

        log(f"第 {current}/{times} 次困难28完成")


def main():
    os.chdir(SCRIPT_DIR)
    log("困难28脚本启动")
    emu = BgEmulatorWindow()
    bot = TemplateMatcher(emu)
    if not bot.check_required_templates():
        return

    try:
        times = get_run_count("K28 run count: ")
    except ValueError:
        log("[ERROR] invalid count")
        return

    try:
        run_k28(bot, emu, times)
    except ScriptStuck as exc:
        log(f"[WARN] script stuck: {exc}")
        ctypes.windll.user32.MessageBoxW(None, "脚本卡死，请人工介入", "YYS Bot", 0x30)

    log("困难28任务结束")


if __name__ == "__main__":
    main()
