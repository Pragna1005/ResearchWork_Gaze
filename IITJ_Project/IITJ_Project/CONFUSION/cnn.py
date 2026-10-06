import pyautogui
import datetime
import time
import keyboard
import cv2
import numpy as np
import os
import csv

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import tkinter as tk
import random
import threading


output_dir = "demo_video_logs"
os.makedirs(output_dir, exist_ok=True)

popup_log_dir = os.path.join(output_dir, "popup_yes_clicks")
os.makedirs(popup_log_dir, exist_ok=True)

popup_log_file = os.path.join(popup_log_dir, "yes_click_log1.csv")

scanpath_output_dir = os.path.join(output_dir, "scanpath_segments")
os.makedirs(scanpath_output_dir, exist_ok=True)

gaze_log_file = os.path.join(output_dir, "gaze.csv")
fixa_log_file = os.path.join(output_dir, "fixation.csv")
aoi_file_path = os.path.join(output_dir, "aoi_lines_1.csv")

MIN_BUBBLE_AREA = 250
BUBBLE_RADIUS_RANGE = (10, 80)
DETECTION_INTERVAL = 0.020
SCANPATH_SAVE_INTERVAL = 1.0  # seconds
SCANPATH_SEGMENT_DURATION = 15.0  # seconds
HSV_LOWER = np.array([55, 180, 180])
HSV_UPPER = np.array([70, 255, 255])
GAZE_HOLD_RADIUS = 25
GAZE_HOLD_TIME = 0.25

latest_scanpath_filename = None
last_saved_end_time = 0

in_fixation = False
fixation_start_time = None
fixation_end_time = None
fixation_pos = None
gaze_hold_start = None
gaze_hold_pos = None
previous_fixation_end_time = None
previous_fixation_pos = None

last_bubble_pos = None

confused_segments = [] 
fixation_points = []
gaze_log = []
fixations = []
popup_gaze = (0, 0)
popup_aoi = "None"

prev_fixation_time = None
prev_fixation_y = None

aoi_regions = {}
aoi_fixation_counter = {}
if os.path.exists(aoi_file_path):
    with open(aoi_file_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            aoi_id = row["AOI_ID"]
            x1, y1, x2, y2 = map(int, [row["x1"], row["y1"], row["x2"], row["y2"]])
            aoi_regions[aoi_id] = (x1, y1, x2, y2)
            aoi_fixation_counter[aoi_id] = 0
else:
    print(f"[ERROR] AOI file not found at {aoi_file_path}.")
    exit(1)

with open(popup_log_file, 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["timestamp", "gaze_x", "gaze_y", "AOI_ID"])

def open_csv_with_header(path, header):
    file_exists = os.path.isfile(path) and os.path.getsize(path) > 0
    f = open(path, 'a', newline='')
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(header)
    return f, writer

gaze_writer, gaze_csv = open_csv_with_header(gaze_log_file, ["gaze_x", "gaze_y", "timestamp"])
fixa_writer, fixa_csv = open_csv_with_header(
    fixa_log_file,
    ["fix_x", "fix_y", "start_time", "end_time", "duration", "dispersion", "distance", "fix_start_ts",
     "saccade_before_duration", "regression_flag", "fixation_count_in_AOI", *aoi_regions.keys()]
)

def save_scanpath_image(segment, label, output_dir=scanpath_output_dir):
    global latest_scanpath_filename
    os.makedirs(output_dir, exist_ok=True)

    if not segment:
        print("[SCANPATH] No gaze data provided.")
        return

    screen_width, screen_height = pyautogui.size()

    x_vals = [x for _, x, y in segment]
    y_vals = [y for _, x, y in segment]

    fig, ax = plt.subplots(figsize=(14, 7))
    ax.set_title("Scanpath: Gaze and Fixations")
    ax.set_xlim(0, screen_width)
    ax.set_ylim(screen_height, 0)  # inverted Y axis for screen coordinates
    ax.set_xlabel("X")
    ax.set_ylabel("Y")

    ax.plot(x_vals, y_vals, color='blue', linewidth=1, label='Gaze Path')
    ax.scatter(x_vals, y_vals, c='blue', s=15, alpha=0.6, label='Gaze Points')

    ax.legend()
    plt.tight_layout()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{label}_{timestamp}.png"
    save_path = os.path.join(output_dir, filename)

    plt.savefig(save_path)
    plt.close()
    latest_scanpath_filename = save_path if label == 0 else latest_scanpath_filename
    print(f"[SAVED] Scanpath image (matplotlib): {save_path}")

def overlaps_confused(start, end):
    for c_start, c_end in confused_segments:
        if not (end < c_start or start > c_end):
            return True
    return False


def continuously_save_nonconfused_scanpaths():
    global last_saved_end_time
    while True:
        time.sleep(SCANPATH_SAVE_INTERVAL)
        end_time = time.time()
        start_time = end_time - SCANPATH_SEGMENT_DURATION
        if end_time - last_saved_end_time >= SCANPATH_SEGMENT_DURATION:
            segment = [row for row in gaze_log if start_time <= row[0] <= end_time]
            if len(segment) >= 80 and not overlaps_confused(start_time, end_time):
                save_scanpath_image(segment, 0)
                last_saved_end_time = end_time
            else:
                print("[SKIP] Overlap or not enough gaze samples for scanpath.")

def log_yes_click():
    global latest_scanpath_filename
    timestamp = time.time()
    end_time = timestamp - 1
    start_time = end_time - 15.0
    segment = [row for row in gaze_log if start_time <= row[0] <= end_time]
    if len(segment) >= 80:
        confused_segments.append((start_time, end_time))  # store this interval
        if latest_scanpath_filename and os.path.exists(latest_scanpath_filename):
            new_path = latest_scanpath_filename.replace("0_", "1_")
            os.rename(latest_scanpath_filename, new_path)
            print(f"[UPDATED] Relabeled scanpath image: {new_path}")
        else:
            save_scanpath_image(segment, 1)
    else:
        print("[WARNING] Not enough gaze samples for scanpath.")
    with open(popup_log_file, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S.%f"),
            popup_gaze[0], popup_gaze[1], popup_aoi
        ])
    print(f"[POPUP LOG] YES at ({popup_gaze[0]}, {popup_gaze[1]}) in {popup_aoi}")

popup_root = tk.Tk()
popup_root.title("Gaze Capture")
popup_root.geometry("220x120+1680+880")
popup_root.configure(bg="white")
popup_root.attributes('-topmost', True)

label = tk.Label(popup_root, text="Log current gaze?", bg="white")
label.pack(pady=10)

yes_btn = tk.Button(popup_root, text="Yes (Confused)", width=18, command=log_yes_click)
yes_btn.pack(pady=5)

def detect_green_bubble(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, HSV_LOWER, HSV_UPPER)
    mask = cv2.erode(mask, None, iterations=1)
    mask = cv2.dilate(mask, None, iterations=1)
    mask = cv2.GaussianBlur(mask, (7, 7), 0)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area > MIN_BUBBLE_AREA:
            (x, y), radius = cv2.minEnclosingCircle(cnt)
            if BUBBLE_RADIUS_RANGE[0] < radius < BUBBLE_RADIUS_RANGE[1]:
                return int(x), int(y)
    return None

recording_started = False
print("[INFO] Tracking green bubble (#CC10F61F)")
print("[INFO] Press 'q' to quit")

try:
    scanpath_thread = threading.Thread(target=continuously_save_nonconfused_scanpaths, daemon=True)
    scanpath_thread.start()

    while not recording_started:
        popup_root.update_idletasks()
        popup_root.update()
        if keyboard.is_pressed('esc'):
            print("[STARTED] Gaze and fixation recording started...")
            recording_started = True
            break
        elif keyboard.is_pressed('q'):
            break

    while True and recording_started:
        screenshot = pyautogui.screenshot()
        frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        bubble_pos = detect_green_bubble(frame)
        bubble_detected = bubble_pos is not None

        if bubble_detected:
            screen_w, screen_h = pyautogui.size()
            img_h, img_w = frame.shape[:2]

            gaze_x = int(bubble_pos[0] * (screen_w / img_w))
            gaze_y = int(bubble_pos[1] * (screen_h / img_h))
            popup_gaze = (gaze_x, gaze_y)

            matched = False
            for k, (x1, y1, x2, y2) in aoi_regions.items():
                if x1 <= gaze_x <= x2 and y1 <= gaze_y <= y2:
                    popup_aoi = k
                    matched = True
                    break
            if not matched:
                popup_aoi = "None"

            now = time.time()
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

            gaze_log.append((now, gaze_x, gaze_y))
            gaze_csv.writerow([gaze_x, gaze_y, timestamp])

            # -------------------------------------------------------------
            if gaze_hold_pos is None:
                gaze_hold_start = now
                gaze_hold_pos = (gaze_x, gaze_y)
                fixation_points = []
            else:
                hold_dist = ((gaze_x - gaze_hold_pos[0])**2 + (gaze_y - gaze_hold_pos[1])**2)**0.5

                if hold_dist <= GAZE_HOLD_RADIUS:
                    hold_duration = now - gaze_hold_start
                    if not in_fixation and hold_duration >= GAZE_HOLD_TIME:
                        in_fixation = True
                        fixation_start_time = gaze_hold_start
                        fixation_pos = gaze_hold_pos
                        fixation_points = [(gaze_x, gaze_y)]
                        print(f"\n[FIXATION START] {fixation_pos}")
                    elif in_fixation:
                        fixation_end_time = now
                        fixation_points.append((gaze_x, gaze_y))
                else:
                    if in_fixation:
                        fixation_end_time = now
                        fixation_duration = fixation_end_time - fixation_start_time
                        start_str = datetime.datetime.fromtimestamp(fixation_start_time).strftime("%Y-%m-%d %H:%M:%S.%f")
                        end_str = datetime.datetime.fromtimestamp(fixation_end_time).strftime("%Y-%m-%d %H:%M:%S.%f")
                        fix_start_ts = int(fixation_start_time * 1000)

                        xs, ys = zip(*fixation_points) if fixation_points else ([fixation_pos[0]], [fixation_pos[1]])
                        mean_x = sum(xs) / len(xs)
                        mean_y = sum(ys) / len(ys)
                        dispersion = max(((x - mean_x)**2 + (y - mean_y)**2)**0.5 for x, y in fixation_points) if fixation_points else 0.0

                        distance = (fixation_pos[0]**2 + fixation_pos[1]**2)**0.5

                        saccade_before_duration = fixation_start_time - prev_fixation_time if prev_fixation_time else 0
                        regression_flag = 1 if prev_fixation_y and fixation_pos[1] < prev_fixation_y else 0

                        current_aoi = next((k for k, (x1, y1, x2, y2) in aoi_regions.items()
                                            if x1 <= fixation_pos[0] <= x2 and y1 <= fixation_pos[1] <= y2), None)
                        if current_aoi:
                            aoi_fixation_counter[current_aoi] += 1
                        fixation_count_in_AOI = aoi_fixation_counter.get(current_aoi, 0)

                        aoi_flags = {k: "True" if (x1 <= fixation_pos[0] <= x2 and y1 <= fixation_pos[1] <= y2) else "False"
                                     for k, (x1, y1, x2, y2) in aoi_regions.items()}

                        fixa_csv.writerow([
                            fixation_pos[0], fixation_pos[1], start_str, end_str,
                            f"{fixation_duration:.3f}", f"{dispersion:.2f}", f"{distance:.2f}", fix_start_ts,
                            f"{saccade_before_duration:.3f}", regression_flag, fixation_count_in_AOI,
                            *[aoi_flags[k] for k in aoi_regions]
                        ])
                        fixa_writer.flush()
                        prev_fixation_time = fixation_start_time
                        prev_fixation_y = fixation_pos[1]

                        fixations.append((fixation_start_time, fixation_pos))
                        print(f"[FIXATION END] {fixation_pos} | Duration: {fixation_duration:.2f}s")

                    in_fixation = False
                    gaze_hold_start = now
                    gaze_hold_pos = (gaze_x, gaze_y)
                    fixation_points = []
            # -------------------------------------------------------------------

            print(f"\r[GAZE] {timestamp} - Gaze at ({gaze_x}, {gaze_y})", end="", flush=True)
            last_bubble_pos = bubble_pos
            
        else:
            last_bubble_pos = None
            gaze_hold_start = None
            gaze_hold_pos = None
            in_fixation = False

        popup_root.update_idletasks()
        popup_root.update()

        if keyboard.is_pressed('q'):
            print("\n[INFO] Exiting...")
            break

        time.sleep(DETECTION_INTERVAL)

except KeyboardInterrupt:
    print("\n[INFO] Stopped by user")

finally:
    gaze_writer.close()
    fixa_writer.close()
    print("\n[INFO] Logs saved to 'data_logs3' folder.")
