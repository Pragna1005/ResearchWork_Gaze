"""AOI extraction: OCR a screenshot of the reading page into one box per text line.

Used on its own (below) or imported by collect.py, which captures the AOIs at
the start of every recording so they always belong to that session.

    python aoi.py                       # 5 s countdown - switch to the page meanwhile
    python aoi.py --delay 8 --out test_data_logs/aoi_lines_test2.csv

Tip: show the page full screen (F11) so tabs, address bar and taskbar are not
OCR'd as text lines (README §10.9).
"""
import argparse
import csv
import os
import time

import cv2
import numpy as np
import pyautogui
import pytesseract
from pytesseract import Output

MIN_OCR_CONFIDENCE = 60


def extract_line_aois(img_bgr):
    """Return ({'AOI_1': (x1, y1, x2, y2), ...}, annotated copy of the image)."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    data = pytesseract.image_to_data(gray, output_type=Output.DICT)

    group_lines = {}
    for i in range(len(data["level"])):
        if int(data["conf"][i]) > MIN_OCR_CONFIDENCE and data["text"][i].strip() != "":
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            group_lines.setdefault(key, []).append(i)

    annotated = img_bgr.copy()
    line_aois = {}
    for line_id, indices in enumerate(group_lines.values(), start=1):
        x1 = min(data["left"][i] for i in indices)
        y1 = min(data["top"][i] for i in indices) - 5
        x2 = max(data["left"][i] + data["width"][i] for i in indices)
        y2 = max(data["top"][i] + data["height"][i] for i in indices) + 2
        aoi_name = f"AOI_{line_id}"
        line_aois[aoi_name] = (x1, y1, x2, y2)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 1)
        cv2.putText(annotated, aoi_name, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
    return line_aois, annotated


def capture_aois(delay, csv_path, debug_png_path):
    """Count down, screenshot the screen, OCR it, write the AOI csv + debug image."""
    for remaining in range(int(delay), 0, -1):
        print(f"[AOI] screenshot in {remaining} s - switch to the reading page", flush=True)
        time.sleep(1)
    img = cv2.cvtColor(np.array(pyautogui.screenshot()), cv2.COLOR_RGB2BGR)
    line_aois, annotated = extract_line_aois(img)

    for path in (csv_path, debug_png_path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    cv2.imwrite(debug_png_path, annotated)
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["AOI_ID", "x1", "y1", "x2", "y2"])
        for aoi_id, box in line_aois.items():
            writer.writerow([aoi_id, *box])
    print(f"[AOI] {len(line_aois)} lines -> {csv_path}")
    print(f"[AOI] check every line has its own box: {debug_png_path}")
    return line_aois


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--delay", type=float, default=5, help="seconds before the screenshot")
    ap.add_argument("--out", default="demo_video_logs/aoi_lines_1.csv")
    ap.add_argument("--debug", default="demo_debug/story_from_screenshot_with_aoistest2.png")
    args = ap.parse_args()
    capture_aois(args.delay, args.out, args.debug)
