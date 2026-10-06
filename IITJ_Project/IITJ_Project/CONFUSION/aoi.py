# --------------------------------------------------------------------------------------

import cv2
import pytesseract
from pytesseract import Output
import os
import csv
import pyautogui
import numpy as np

screenshot = pyautogui.screenshot()
img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
screen_h, screen_w = gray.shape[:2]

data = pytesseract.image_to_data(gray, output_type=Output.DICT)

line_aois = {}
line_id = 1
group_lines = {}


for i in range(len(data['level'])):
    if int(data['conf'][i]) > 60 and data['text'][i].strip() != "":
        key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
        if key not in group_lines:
            group_lines[key] = []
        group_lines[key].append(i)

for (block, para, line), indices in group_lines.items():
    x1 = min(data['left'][i] for i in indices)
    y1 = min(data['top'][i] for i in indices)-5
    x2 = max(data['left'][i] + data['width'][i] for i in indices)
    y2 = max(data['top'][i] + data['height'][i] for i in indices)+2

    aoi_name = f"AOI_{line_id}"
    line_aois[aoi_name] = (x1, y1, x2, y2)

    
    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 1)
    cv2.putText(img, aoi_name, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)

    line_id += 1


os.makedirs("demo_debug", exist_ok=True)
cv2.imwrite("demo_debug/story_from_screenshot_with_aoistest2.png", img)


os.makedirs("demo_video_logs", exist_ok=True)
with open("demo_video_logs/aoi_lines_1.csv", "w", newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["AOI_ID", "x1", "y1", "x2", "y2"])
    for aoi_id, (x1, y1, x2, y2) in line_aois.items():
        writer.writerow([aoi_id, x1, y1, x2, y2])


print(f"[INFO] AOIs detected from screenshot and saved: {len(line_aois)}")
print("[INFO] Output: aoi_debug/story_from_screenshot_with_aois.png")

