# import pyautogui
# import datetime
# import time
# import keyboard
# import cv2
# import numpy as np
# import os
# import csv
# import matplotlib.pyplot as plt

# output_dir = "data_logs"
# os.makedirs(output_dir, exist_ok=True)

# gaze_log_file = os.path.join(output_dir, "gaze_3.csv")
# fixa_log_file = os.path.join(output_dir, "fixation_3.csv")
# aoi_file_path = os.path.join(output_dir, "aoi_lines_3.csv")

# MIN_BUBBLE_AREA = 250
# BUBBLE_RADIUS_RANGE = (10, 80)
# DETECTION_INTERVAL = 0.025
# HSV_LOWER = np.array([55, 180, 180])
# HSV_UPPER = np.array([70, 255, 255])
# GAZE_HOLD_RADIUS = 25
# GAZE_HOLD_TIME = 0.25

# in_fixation = False
# fixation_start_time = None
# fixation_end_time = None
# fixation_pos = None
# gaze_hold_start = None
# gaze_hold_pos = None
# previous_fixation_end_time = None
# previous_fixation_pos = None

# last_logged_mouse_pos = None
# last_bubble_pos = None
# last_click_time = 0
# clicked = False
# last_gaze_time = None
# last_gaze_pos = None

# fixation_points = []
# gaze_log = []
# fixations = []

# aoi_regions = {}
# if os.path.exists(aoi_file_path):
#     with open(aoi_file_path, newline='') as f:
#         reader = csv.DictReader(f)
#         for row in reader:
#             aoi_id = row["AOI_ID"]
#             x1, y1, x2, y2 = map(int, [row["x1"], row["y1"], row["x2"], row["y2"]])
#             aoi_regions[aoi_id] = (x1, y1, x2, y2)
# else:
#     print(f"[ERROR] AOI file not found at {aoi_file_path}.")
#     exit(1)

# def open_csv_with_header(path, header):
#     file_exists = os.path.isfile(path) and os.path.getsize(path) > 0
#     f = open(path, 'a', newline='')
#     writer = csv.writer(f)
#     if not file_exists:
#         writer.writerow(header)
#     return f, writer

# gaze_writer, gaze_csv = open_csv_with_header(gaze_log_file, ["gaze_x", "gaze_y", "timestamp"])
# fixa_writer, fixa_csv = open_csv_with_header(
#     fixa_log_file,
#     ["fix_x", "fix_y", "start_time", "end_time", "duration", "dispersion", "distance", "fix_start_ts", *aoi_regions.keys()]
# )


# def detect_green_bubble(frame):
#     hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
#     mask = cv2.inRange(hsv, HSV_LOWER, HSV_UPPER)
#     mask = cv2.erode(mask, None, iterations=1)
#     mask = cv2.dilate(mask, None, iterations=1)
#     mask = cv2.GaussianBlur(mask, (7, 7), 0)
#     contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
#     for cnt in contours:
#         area = cv2.contourArea(cnt)
#         if area > MIN_BUBBLE_AREA:
#             (x, y), radius = cv2.minEnclosingCircle(cnt)
#             if BUBBLE_RADIUS_RANGE[0] < radius < BUBBLE_RADIUS_RANGE[1]:
#                 return int(x), int(y)
#     return None

# print("[INFO] Tracking green bubble (#CC10F61F)")
# print("[INFO] Press 'q' to quit")

# try:
#     while True:
#         screenshot = pyautogui.screenshot()
#         frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
#         bubble_pos = detect_green_bubble(frame)
#         bubble_detected = bubble_pos is not None

#         if bubble_detected:
#             screen_w, screen_h = pyautogui.size()
#             img_h, img_w = frame.shape[:2]

#             gaze_x = int(bubble_pos[0] * (screen_w / img_w))
#             gaze_y = int(bubble_pos[1] * (screen_h / img_h))
#             now = time.time()
#             timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

#             gaze_log.append((now, gaze_x, gaze_y))
#             gaze_csv.writerow([gaze_x, gaze_y, timestamp])

#             if gaze_hold_pos is None:
#                 gaze_hold_start = now
#                 gaze_hold_pos = (gaze_x, gaze_y)
#                 fixation_points = []
#             else:
#                 hold_dist = ((gaze_x - gaze_hold_pos[0])**2 + (gaze_y - gaze_hold_pos[1])**2)**0.5

#                 if hold_dist <= GAZE_HOLD_RADIUS:
#                     hold_duration = now - gaze_hold_start
#                     if not in_fixation and hold_duration >= GAZE_HOLD_TIME:
#                         in_fixation = True
#                         fixation_start_time = gaze_hold_start
#                         fixation_pos = gaze_hold_pos
#                         fixation_points = [(gaze_x, gaze_y)]
#                         print(f"\n[FIXATION START] {fixation_pos}")
#                     elif in_fixation:
#                         fixation_end_time = now
#                         fixation_points.append((gaze_x, gaze_y))
#                 else:
#                     if in_fixation:
#                         fixation_end_time = now
#                         fixation_duration = fixation_end_time - fixation_start_time
#                         start_str = datetime.datetime.fromtimestamp(fixation_start_time).strftime("%Y-%m-%d %H:%M:%S.%f")
#                         end_str = datetime.datetime.fromtimestamp(fixation_end_time).strftime("%Y-%m-%d %H:%M:%S.%f")
#                         fix_start_ts = int(fixation_start_time * 1000)

#                         xs, ys = zip(*fixation_points) if fixation_points else ([fixation_pos[0]], [fixation_pos[1]])
#                         mean_x = sum(xs) / len(xs)
#                         mean_y = sum(ys) / len(ys)
#                         dispersion = max(((x - mean_x)**2 + (y - mean_y)**2)**0.5 for x, y in fixation_points) if fixation_points else 0.0

#                         distance = (fixation_pos[0]**2 + fixation_pos[1]**2)**0.5

#                         aoi_flags = {k: "True" if (x1 <= fixation_pos[0] <= x2 and y1 <= fixation_pos[1] <= y2) else "False"
#                                      for k, (x1, y1, x2, y2) in aoi_regions.items()}

#                         fixa_csv.writerow([
#                             fixation_pos[0], fixation_pos[1], start_str, end_str,
#                             f"{fixation_duration:.3f}", f"{dispersion:.2f}", f"{distance:.2f}", fix_start_ts,
#                             *[aoi_flags[k] for k in aoi_regions]
#                         ])
#                         fixations.append((fixation_start_time, fixation_pos))
#                         print(f"[FIXATION END] {fixation_pos} | Duration: {fixation_duration:.2f}s")

                   
#                     in_fixation = False
#                     gaze_hold_start = now
#                     gaze_hold_pos = (gaze_x, gaze_y)
#                     fixation_points = []

#             print(f"\r[GAZE] {timestamp} - Gaze at ({gaze_x}, {gaze_y})", end="", flush=True)
#             last_bubble_pos = bubble_pos
#         else:
#             last_bubble_pos = None
#             gaze_hold_start = None
#             gaze_hold_pos = None
#             in_fixation = False

#         if keyboard.is_pressed('q'):
#             print("\n[INFO] Exiting...")
#             break

#         time.sleep(DETECTION_INTERVAL)

# except KeyboardInterrupt:
#     print("\n[INFO] Stopped by user")

# finally:
#     cv2.destroyAllWindows()
#     gaze_writer.close()
#     fixa_writer.close()
#     print("\n[INFO] Logs saved to 'data_logs' folder.")


# ---------------------------------------------------------------------------------------------------


import pyautogui
import datetime
import time
import keyboard
import cv2
import numpy as np
import os
import csv
import matplotlib.pyplot as plt
import tkinter as tk

output_dir = "U_data_logs"
os.makedirs(output_dir, exist_ok=True)

popup_log_dir = os.path.join(output_dir, "popup_yes_clicks")
os.makedirs(popup_log_dir, exist_ok=True)

popup_log_file = os.path.join(popup_log_dir, "yes_click_log.csv")

gaze_log_file = os.path.join(output_dir, "gaze.csv")
fixa_log_file = os.path.join(output_dir, "fixation.csv")
aoi_file_path = os.path.join(output_dir, "aoi_lines2.csv")

MIN_BUBBLE_AREA = 250
BUBBLE_RADIUS_RANGE = (10, 80)
DETECTION_INTERVAL = 0.025
HSV_LOWER = np.array([55, 180, 180])
HSV_UPPER = np.array([70, 255, 255])
GAZE_HOLD_RADIUS = 25
GAZE_HOLD_TIME = 0.25

in_fixation = False
fixation_start_time = None
fixation_end_time = None
fixation_pos = None
gaze_hold_start = None
gaze_hold_pos = None
previous_fixation_end_time = None
previous_fixation_pos = None

last_logged_mouse_pos = None
last_bubble_pos = None
last_click_time = 0
clicked = False
last_gaze_time = None
last_gaze_pos = None

fixation_points = []
gaze_log = []
fixations = []
popup_gaze = (0, 0)
popup_aoi = "None"

aoi_regions = {}
if os.path.exists(aoi_file_path):
    with open(aoi_file_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            aoi_id = row["AOI_ID"]
            x1, y1, x2, y2 = map(int, [row["x1"], row["y1"], row["x2"], row["y2"]])
            aoi_regions[aoi_id] = (x1, y1, x2, y2)
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
    ["fix_x", "fix_y", "start_time", "end_time", "duration", "dispersion", "distance", "fix_start_ts", *aoi_regions.keys()]
)

popup_root = tk.Tk()
popup_root.title("Gaze Capture")
popup_root.geometry("220x120+1680+880")
popup_root.configure(bg="white")
popup_root.attributes('-topmost', True)

def start_move(event):
    popup_root.x = event.x
    popup_root.y = event.y

def do_move(event):
    x = popup_root.winfo_pointerx() - popup_root.x
    y = popup_root.winfo_pointery() - popup_root.y
    popup_root.geometry(f"+{x}+{y}")

popup_root.bind("<Button-1>", start_move)
popup_root.bind("<B1-Motion>", do_move)

label = tk.Label(popup_root, text="Log current gaze?", bg="white")
label.pack(pady=10)

def log_yes_click():
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    with open(popup_log_file, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([timestamp, popup_gaze[0], popup_gaze[1], popup_aoi])
    print(f"[POPUP LOG] YES at ({popup_gaze[0]}, {popup_gaze[1]}) in {popup_aoi}")

yes_btn = tk.Button(popup_root, text="Yes", width=10, command=log_yes_click)
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

                        aoi_flags = {k: "True" if (x1 <= fixation_pos[0] <= x2 and y1 <= fixation_pos[1] <= y2) else "False"
                                     for k, (x1, y1, x2, y2) in aoi_regions.items()}

                        fixa_csv.writerow([
                            fixation_pos[0], fixation_pos[1], start_str, end_str,
                            f"{fixation_duration:.3f}", f"{dispersion:.2f}", f"{distance:.2f}", fix_start_ts,
                            *[aoi_flags[k] for k in aoi_regions]
                        ])
                        fixa_writer.flush()
                        fixations.append((fixation_start_time, fixation_pos))
                        print(f"[FIXATION END] {fixation_pos} | Duration: {fixation_duration:.2f}s")

                    in_fixation = False
                    gaze_hold_start = now
                    gaze_hold_pos = (gaze_x, gaze_y)
                    fixation_points = []

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
    if in_fixation and fixation_start_time and fixation_points:
        fixation_end_time = time.time()
        fixation_duration = fixation_end_time - fixation_start_time
        start_str = datetime.datetime.fromtimestamp(fixation_start_time).strftime("%Y-%m-%d %H:%M:%S.%f")
        end_str = datetime.datetime.fromtimestamp(fixation_end_time).strftime("%Y-%m-%d %H:%M:%S.%f")
        fix_start_ts = int(fixation_start_time * 1000)

        xs, ys = zip(*fixation_points)
        mean_x = sum(xs) / len(xs)
        mean_y = sum(ys) / len(ys)
        dispersion = max(((x - mean_x)**2 + (y - mean_y)**2)**0.5 for x, y in fixation_points)
        distance = (fixation_pos[0]**2 + fixation_pos[1]**2)**0.5

        aoi_flags = {k: "True" if (x1 <= fixation_pos[0] <= x2 and y1 <= fixation_pos[1] <= y2) else "False"
                     for k, (x1, y1, x2, y2) in aoi_regions.items()}

        fixa_csv.writerow([
            fixation_pos[0], fixation_pos[1], start_str, end_str,
            f"{fixation_duration:.3f}", f"{dispersion:.2f}", f"{distance:.2f}", fix_start_ts,
            *[aoi_flags[k] for k in aoi_regions]
        ])
        fixa_writer.flush()
        print(f"[FIXATION END-FORCED] {fixation_pos} | Duration: {fixation_duration:.2f}s")

    gaze_writer.close()
    fixa_writer.close()
    print("\n[INFO] Logs saved to 'data_logs' folder.")

    def plot_scanpath(gaze_log, fixations, save_dir="scanpath_output", filename="scanpath3.png"):
        if not fixations and not gaze_log:
            print("[SCANPATH] No data to plot.")
            return

        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)

        fig, ax = plt.subplots(figsize=(14, 7))
        ax.set_title("Scanpath: Gaze and Fixations")
        ax.set_xlim(0, pyautogui.size().width)
        ax.set_ylim(pyautogui.size().height, 0)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")

        x_vals = [x for _, x, _ in gaze_log]
        y_vals = [y for _, _, y in gaze_log]
        ax.plot(x_vals, y_vals, color='blue', linestyle='-', linewidth=1, label='Gaze Path')
        ax.scatter(x_vals, y_vals, c='blue', s=15, label='Gaze Points', alpha=0.6)

        # === Fixations ===
        # for i, (t, (x, y)) in enumerate(fixations):
        #     ax.scatter(x, y, c='red', s=60, label='Fixation' if i == 0 else "", zorder=3)
        #     ax.text(x + 10, y - 10, f"Fix {i+1}", color='red', fontsize=8)

        plt.tight_layout()
        ax.legend()
        plt.savefig(save_path)
        plt.close()
        print(f"[SCANPATH] Saved to: {save_path}")


    plot_scanpath(gaze_log, fixations)



