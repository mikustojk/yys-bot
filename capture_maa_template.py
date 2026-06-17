import base64
import ctypes
import json
import os
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog

import cv2
import numpy as np
import win32gui
import win32ui


ctypes.windll.user32.SetProcessDPIAware()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(SCRIPT_DIR, "images", "maa")
BASE_W = 1280
BASE_H = 720


def maa_scale_size(width: int, height: int) -> tuple:
    if width <= 0 or height <= 0:
        return BASE_W, BASE_H
    default_ratio = BASE_W / BASE_H
    cur_ratio = width / height
    if cur_ratio >= default_ratio:
        return int(cur_ratio * BASE_H), BASE_H
    return BASE_W, int(BASE_W / cur_ratio)


class BgEmulatorWindow:
    def __init__(self, window_title="MuMu安卓设备"):
        self.hwnd = win32gui.FindWindow(None, window_title)
        if not self.hwnd:
            raise RuntimeError(f"未找到窗口：{window_title}")
        self.render_hwnd = self._get_mumu_render_child(self.hwnd)

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

    def screenshot_raw(self):
        left, top, right, bottom = win32gui.GetClientRect(self.render_hwnd)
        width = right - left
        height = bottom - top

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
        if raw_w == base_w and raw_h == base_h:
            return raw
        interpolation = cv2.INTER_AREA if base_w <= raw_w and base_h <= raw_h else cv2.INTER_LINEAR
        return cv2.resize(raw, (base_w, base_h), interpolation=interpolation)


class CropWindow:
    def __init__(self, image, template_name):
        self.image = image
        self.template_name = template_name
        self.root = tk.Tk()
        self.root.title(f"截取 MAA 模板：{template_name}")
        self.root.configure(bg="#111111")

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        img_h, img_w = image.shape[:2]
        self.scale = min((screen_w * 0.92) / img_w, (screen_h * 0.82) / img_h, 1.0)
        self.display_w = int(img_w * self.scale)
        self.display_h = int(img_h * self.scale)

        display = cv2.resize(image, (self.display_w, self.display_h), interpolation=cv2.INTER_AREA)
        ok, preview_png = cv2.imencode(".png", display)
        if not ok:
            raise RuntimeError("无法生成预览图。")

        label = tk.Label(
            self.root,
            text=f"拖动框选模板：{template_name}。只截关键文字/图标，松开鼠标自动保存，Esc 取消。",
            bg="#111111",
            fg="#ffffff",
            font=("Microsoft YaHei UI", 12, "bold"),
        )
        label.pack(fill="x", padx=10, pady=(10, 6))

        self.photo = tk.PhotoImage(data=base64.b64encode(preview_png.tobytes()).decode("ascii"), format="PNG")
        self.canvas = tk.Canvas(self.root, width=self.display_w, height=self.display_h, highlightthickness=0, cursor="crosshair")
        self.canvas.pack(padx=10, pady=(0, 10))
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw")

        self.start_x = 0
        self.start_y = 0
        self.rect_id = None
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.root.bind("<Escape>", lambda event: self.root.destroy())

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        if self.rect_id is not None:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="#ffcc33", width=3)

    def on_drag(self, event):
        if self.rect_id is not None:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)

    def on_release(self, event):
        x1, x2 = sorted((self.start_x, event.x))
        y1, y2 = sorted((self.start_y, event.y))
        if x2 - x1 < 8 or y2 - y1 < 8:
            messagebox.showwarning("区域太小", "框选区域太小，请重新框选。")
            return

        ox1 = max(0, int(x1 / self.scale))
        oy1 = max(0, int(y1 / self.scale))
        ox2 = min(self.image.shape[1], int(x2 / self.scale))
        oy2 = min(self.image.shape[0], int(y2 / self.scale))
        crop = self.image[oy1:oy2, ox1:ox2]

        os.makedirs(TEMPLATE_DIR, exist_ok=True)
        output_path = os.path.join(TEMPLATE_DIR, f"{self.template_name}.png")
        ok, png = cv2.imencode(".png", crop)
        if not ok:
            messagebox.showerror("保存失败", "无法编码模板图片，请重新框选。")
            return
        png.tofile(output_path)

        meta_path = os.path.join(TEMPLATE_DIR, f"{self.template_name}.json")
        meta = {
            "template": f"{self.template_name}.png",
            "base_size": [self.image.shape[1], self.image.shape[0]],
            "rect": [ox1, oy1, ox2 - ox1, oy2 - oy1],
        }
        with open(meta_path, "w", encoding="utf-8") as file:
            json.dump(meta, file, ensure_ascii=False, indent=2)

        messagebox.showinfo("保存成功", f"已保存：{output_path}")
        print(f"Saved template: {output_path}", flush=True)
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def get_template_name():
    if len(sys.argv) > 1:
        return sys.argv[1].strip()

    root = tk.Tk()
    root.withdraw()
    name = simpledialog.askstring("模板名", "输入模板名，例如 challenge / settlement：")
    root.destroy()
    return (name or "").strip()


def main():
    os.chdir(SCRIPT_DIR)
    name = get_template_name()
    if not name:
        print("未输入模板名。")
        return

    image = BgEmulatorWindow().screenshot_base()
    CropWindow(image, name).run()


if __name__ == "__main__":
    main()
