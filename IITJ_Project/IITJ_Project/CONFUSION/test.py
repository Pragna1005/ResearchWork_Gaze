# import pyautogui
# import datetime
# import time
# import keyboard
# import cv2
# import numpy as np
# import os
# import csv

# import matplotlib
# matplotlib.use('Agg')
# import matplotlib.pyplot as plt

# import tkinter as tk
# import random
# import threading

# import joblib
# import pandas as pd
# import numpy as np

# # Load the saved model
# model = joblib.load("confusion_model_rf4.pkl")
# feature_order = joblib.load("feature_names_order.pkl")

# output_dir = "test_data_logs"
# os.makedirs(output_dir, exist_ok=True)

# aoi_file_path = os.path.join(output_dir, "aoi_lines_test.csv")

# MIN_BUBBLE_AREA = 250
# BUBBLE_RADIUS_RANGE = (10, 80)
# DETECTION_INTERVAL = 0.020
# SCANPATH_SAVE_INTERVAL = 1.0  # seconds
# SCANPATH_SEGMENT_DURATION = 15.0  # seconds
# HSV_LOWER = np.array([55, 180, 180])
# HSV_UPPER = np.array([70, 255, 255])
# GAZE_HOLD_RADIUS = 25
# GAZE_HOLD_TIME = 0.25

# latest_scanpath_filename = None
# last_saved_end_time = 0

# in_fixation = False
# fixation_start_time = None
# fixation_end_time = None
# fixation_pos = None
# gaze_hold_start = None
# gaze_hold_pos = None
# previous_fixation_end_time = None
# previous_fixation_pos = None

# last_bubble_pos = None

# confused_segments = [] 
# fixation_points = []
# gaze_log = []
# fixations = []
# popup_gaze = (0, 0)
# popup_aoi = "None"

# prev_fixation_time = None
# prev_fixation_y = None

# aoi_regions = {}
# aoi_fixation_counter = {}
# if os.path.exists(aoi_file_path):
#     with open(aoi_file_path, newline='') as f:
#         reader = csv.DictReader(f)
#         for row in reader:
#             aoi_id = row["AOI_ID"]
#             x1, y1, x2, y2 = map(int, [row["x1"], row["y1"], row["x2"], row["y2"]])
#             aoi_regions[aoi_id] = (x1, y1, x2, y2)
#             aoi_fixation_counter[aoi_id] = 0
# else:
#     print(f"[ERROR] AOI file not found at {aoi_file_path}.")
#     exit(1)

# root = tk.Tk()
# root.withdraw()

# prediction_popup = tk.Toplevel(root)
# prediction_popup.title("Confusion Prediction")
# prediction_popup.geometry("300x100+100+100")
# prediction_popup.configure(bg="white")
# prediction_popup.attributes('-topmost', True)
# prediction_label = tk.Label(prediction_popup, text="Waiting for prediction...", font=("Arial", 12), bg="white")
# prediction_label.pack(pady=20)

# def start_move(event):
#     prediction_popup.x = event.x
#     prediction_popup.y = event.y

# def do_move(event):
#     x = event.x_root - prediction_popup.x
#     y = event.y_root - prediction_popup.y
#     prediction_popup.geometry(f"+{x}+{y}")

# prediction_popup.bind("<Button-1>", start_move)
# prediction_popup.bind("<B1-Motion>", do_move)


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

# recording_started = False
# print("[INFO] Tracking green bubble (#CC10F61F)")
# print("[INFO] Press 'q' to quit")

# try:
#     # scanpath_thread = threading.Thread(target=continuously_save_nonconfused_scanpaths, daemon=True)
#     # scanpath_thread.start()

#     while not recording_started:
#         # popup_root.update_idletasks()
#         # popup_root.update()
#         if keyboard.is_pressed('esc'):
#             prediction_popup.update_idletasks()
#             prediction_popup.update()
#             print("[STARTED] Gaze and fixation recording started...")
#             recording_started = True
#             break
#         elif keyboard.is_pressed('q'):
#             break

#     while True and recording_started:
#         screenshot = pyautogui.screenshot()
#         frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
#         bubble_pos = detect_green_bubble(frame)
#         bubble_detected = bubble_pos is not None

#         if bubble_detected:
#             screen_w, screen_h = pyautogui.size()
#             img_h, img_w = frame.shape[:2]

#             gaze_x = int(bubble_pos[0] * (screen_w / img_w))
#             gaze_y = int(bubble_pos[1] * (screen_h / img_h))
#             popup_gaze = (gaze_x, gaze_y)

#             matched = False
#             for k, (x1, y1, x2, y2) in aoi_regions.items():
#                 if x1 <= gaze_x <= x2 and y1 <= gaze_y <= y2:
#                     popup_aoi = k
#                     matched = True
#                     break
#             if not matched:
#                 popup_aoi = "None"

#             now = time.time()
#             timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

#             gaze_log.append((now, gaze_x, gaze_y))
#             # gaze_csv.writerow([gaze_x, gaze_y, timestamp])

#             # -------------------------------------------------------------
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

#                         saccade_before_duration = fixation_start_time - prev_fixation_time if prev_fixation_time else 0
#                         regression_flag = 1 if prev_fixation_y and fixation_pos[1] < prev_fixation_y else 0

#                         current_aoi = next((k for k, (x1, y1, x2, y2) in aoi_regions.items()
#                                             if x1 <= fixation_pos[0] <= x2 and y1 <= fixation_pos[1] <= y2), None)
#                         if current_aoi:
#                             aoi_fixation_counter[current_aoi] += 1
#                         fixation_count_in_AOI = aoi_fixation_counter.get(current_aoi, 0)

#                         aoi_flags = {k: "True" if (x1 <= fixation_pos[0] <= x2 and y1 <= fixation_pos[1] <= y2) else "False"
#                                      for k, (x1, y1, x2, y2) in aoi_regions.items()}

#                         # fixa_csv.writerow([
#                         #     fixation_pos[0], fixation_pos[1], start_str, end_str,
#                         #     f"{fixation_duration:.3f}", f"{dispersion:.2f}", f"{distance:.2f}", fix_start_ts,
#                         #     f"{saccade_before_duration:.3f}", regression_flag, fixation_count_in_AOI,
#                         #     *[aoi_flags[k] for k in aoi_regions]
#                         # ])
#                         # fixa_writer.flush()
#                         prev_fixation_time = fixation_start_time
#                         prev_fixation_y = fixation_pos[1]

#                         fixations.append((fixation_start_time, fixation_pos))
#                         print(f"[FIXATION END] {fixation_pos} | Duration: {fixation_duration:.2f}s")

#                         # === Construct features ===
#                         features = [
#                             fixation_pos[0],
#                             fixation_pos[1],
#                             float(fixation_duration),
#                             float(dispersion),
#                             float(distance),
#                             float(saccade_before_duration),
#                             regression_flag,
#                             fixation_count_in_AOI,
#                             *[1 if aoi_flags[k] == "True" else 0 for k in aoi_regions]  # this must match order of AOI columns
#                         ]

#                         # Create dataframe with correct order and column names
#                         input_df = pd.DataFrame([features], columns=feature_order)

#                         # Predict
#                         pred = model.predict(input_df)[0]


#                        # Predict
#                         pred = model.predict(input_df)[0]  # pred is now 0 or 1 (int)

#                         # Use directly without [0] again
#                         predicted_aoi = current_aoi or "None"
#                         confused_text = "😕 Confused" if pred == 1 else "waiting"
#                         print("\n",confused_text,"  :  ",predicted_aoi,"\n")
#                         prediction_msg = f"AOI: {predicted_aoi}\n{confused_text}"
#                         prediction_label.config(text=prediction_msg)


#                     in_fixation = False
#                     gaze_hold_start = now
#                     gaze_hold_pos = (gaze_x, gaze_y)
#                     fixation_points = []
#             # -------------------------------------------------------------------

#             print(f"\r[GAZE] {timestamp} - Gaze at ({gaze_x}, {gaze_y})", end="", flush=True)
#             last_bubble_pos = bubble_pos
#             prediction_popup.update_idletasks()
#             prediction_popup.update()
            
#         else:
#             last_bubble_pos = None
#             gaze_hold_start = None
#             gaze_hold_pos = None
#             in_fixation = False

#         # popup_root.update_idletasks()
#         # popup_root.update()

#         if keyboard.is_pressed('q'):
#             print("\n[INFO] Exiting...")
#             break

#         time.sleep(DETECTION_INTERVAL)

# except KeyboardInterrupt:
#     print("\n[INFO] Stopped by user")

# finally:
#     # gaze_writer.close()
#     # fixa_writer.close()
#     print("\n[INFO] Logs saved to 'data_logs3' folder.")



# === Imports and Setup ===
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
import threading
import joblib
import pandas as pd

# === Load Model and Features ===
model = joblib.load("confusion_model_xgb_new.pkl")
feature_order = joblib.load("feature_names_order_xgb_new.pkl")

# import pickle

# with open("confusion_model_xgb_new.pkl", "rb") as f:
#     model = pickle.load(f)

output_dir = "test_data_logs"
os.makedirs(output_dir, exist_ok=True)
aoi_file_path = os.path.join(output_dir, "aoi_lines_test2.csv")

# === Constants ===
MIN_BUBBLE_AREA = 250
BUBBLE_RADIUS_RANGE = (10, 80)
DETECTION_INTERVAL = 0.020
HSV_LOWER = np.array([55, 180, 180])
HSV_UPPER = np.array([70, 255, 255])
GAZE_HOLD_RADIUS = 25
GAZE_HOLD_TIME = 0.25

# === Global States ===
in_fixation = False
fixation_start_time = None
fixation_pos = None
gaze_hold_start = None
gaze_hold_pos = None
previous_fixation_time = None
previous_fixation_y = None

aoi_regions = {}
aoi_fixation_counter = {}
popup_gaze = (0, 0)
popup_aoi = "None"
fixation_points = []

if os.path.exists(aoi_file_path):
    with open(aoi_file_path, newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            aoi_id = row["AOI_ID"]
            x1, y1, x2, y2 = map(int, [row["x1"], row["y1"], row["x2"], row["y2"]])
            aoi_regions[aoi_id] = (x1, y1, x2, y2)
            aoi_fixation_counter[aoi_id] = 0
else:
    print(f"[ERROR] AOI file not found at {aoi_file_path}")
    exit(1)

# === GUI Setup ===
root = tk.Tk()
root.withdraw()
prediction_popup = tk.Toplevel(root)
prediction_popup.title("Confusion Prediction")
prediction_popup.geometry("300x100+100+100")
prediction_popup.configure(bg="white")
prediction_popup.attributes('-topmost', True)
prediction_label = tk.Label(prediction_popup, text="Waiting for prediction...", font=("Arial", 12), bg="white")
prediction_label.pack(pady=20)

def start_move(event):
    prediction_popup.x = event.x
def do_move(event):
    x = event.x_root - prediction_popup.x
    y = event.y_root - prediction_popup.y
    prediction_popup.geometry(f"+{x}+{y}")

prediction_popup.bind("<Button-1>", start_move)
prediction_popup.bind("<B1-Motion>", do_move)

# === Green Bubble Detection ===
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

# === Main Loop ===
recording_started = False
print("[INFO] Tracking green bubble (#CC10F61F)")
print("[INFO] Press 'esc' to start recording, 'q' to quit")

try:
    while not recording_started:
        if keyboard.is_pressed('esc'):
            prediction_popup.update_idletasks()
            prediction_popup.update()
            print("[STARTED] Gaze and fixation recording started...")
            recording_started = True
            break
        elif keyboard.is_pressed('q'):
            break

    while recording_started:
        screenshot = pyautogui.screenshot()
        frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        bubble_pos = detect_green_bubble(frame)

        if bubble_pos:
            screen_w, screen_h = pyautogui.size()
            img_h, img_w = frame.shape[:2]
            gaze_x = int(bubble_pos[0] * (screen_w / img_w))
            gaze_y = int(bubble_pos[1] * (screen_h / img_h))
            popup_gaze = (gaze_x, gaze_y)

            now = time.time()
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

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

                        # === Early Prediction ===
                        current_aoi = next((k for k, (x1, y1, x2, y2) in aoi_regions.items()
                                            if x1 <= fixation_pos[0] <= x2 and y1 <= fixation_pos[1] <= y2), None)
                        fixation_count_in_AOI = aoi_fixation_counter.get(current_aoi, 0)
                        distance = (fixation_pos[0]**2 + fixation_pos[1]**2)**0.5
                        saccade_before_duration = fixation_start_time - previous_fixation_time if previous_fixation_time else 0
                        regression_flag = 1 if previous_fixation_y and fixation_pos[1] < previous_fixation_y else 0
                        aoi_flags = {k: "True" if (x1 <= fixation_pos[0] <= x2 and y1 <= fixation_pos[1] <= y2) else "False"
                                     for k, (x1, y1, x2, y2) in aoi_regions.items()}

                        early_features = [
                            fixation_pos[0], fixation_pos[1],
                            0.25, 0.0, float(distance),
                            float(saccade_before_duration),
                            regression_flag,
                            fixation_count_in_AOI,
                            *[1 if aoi_flags[k] == "True" else 0 for k in aoi_regions]
                        ]

                        input_df = pd.DataFrame([early_features], columns=feature_order)
                        pred = model.predict(input_df)[0]
                        predicted_aoi = current_aoi or "None"
                        confused_text = "😕 Confused" if pred == 1 else "waiting"
                        prediction_label.config(text=f"AOI: {predicted_aoi}\n{confused_text}")
                        print("\n",confused_text,"  :  ",predicted_aoi,"\n")
                        prediction_popup.update_idletasks()
                        prediction_popup.update()

                    elif in_fixation:
                        fixation_points.append((gaze_x, gaze_y))

                else:
                    if in_fixation:
                        fixation_end_time = now
                        fixation_duration = fixation_end_time - fixation_start_time
                        xs, ys = zip(*fixation_points) if fixation_points else ([fixation_pos[0]], [fixation_pos[1]])
                        mean_x = sum(xs) / len(xs)
                        mean_y = sum(ys) / len(ys)
                        dispersion = max(((x - mean_x)**2 + (y - mean_y)**2)**0.5 for x, y in fixation_points) if fixation_points else 0.0

                        distance = (fixation_pos[0]**2 + fixation_pos[1]**2)**0.5
                        saccade_before_duration = fixation_start_time - previous_fixation_time if previous_fixation_time else 0
                        regression_flag = 1 if previous_fixation_y and fixation_pos[1] < previous_fixation_y else 0

                        current_aoi = next((k for k, (x1, y1, x2, y2) in aoi_regions.items()
                                            if x1 <= fixation_pos[0] <= x2 and y1 <= fixation_pos[1] <= y2), None)
                        if current_aoi:
                            aoi_fixation_counter[current_aoi] += 1
                        fixation_count_in_AOI = aoi_fixation_counter.get(current_aoi, 0)

                        aoi_flags = {k: "True" if (x1 <= fixation_pos[0] <= x2 and y1 <= fixation_pos[1] <= y2) else "False"
                                     for k, (x1, y1, x2, y2) in aoi_regions.items()}

                        features = [
                            fixation_pos[0], fixation_pos[1],
                            float(fixation_duration),
                            float(dispersion),
                            float(distance),
                            float(saccade_before_duration),
                            regression_flag,
                            fixation_count_in_AOI,
                            *[1 if aoi_flags[k] == "True" else 0 for k in aoi_regions]
                        ]

                        input_df = pd.DataFrame([features], columns=feature_order)
                        pred = model.predict(input_df)[0]
                        confused_text = "😕 Confused" if pred == 1 else "waiting"
                        predicted_aoi = current_aoi or "None"
                        prediction_label.config(text=f"AOI: {predicted_aoi}\n{confused_text}")
                        print("\n",confused_text,"  :  ",predicted_aoi,"\n")
                        prediction_popup.update_idletasks()
                        prediction_popup.update()

                        previous_fixation_time = fixation_start_time
                        previous_fixation_y = fixation_pos[1]

                    in_fixation = False
                    gaze_hold_start = now
                    gaze_hold_pos = (gaze_x, gaze_y)
                    fixation_points = []

            print(f"\r[GAZE] {timestamp} - Gaze at ({gaze_x}, {gaze_y})", end="", flush=True)
            prediction_popup.update_idletasks()
            prediction_popup.update()

        else:
            gaze_hold_start = None
            gaze_hold_pos = None
            in_fixation = False

        if keyboard.is_pressed('q'):
            print("\n[INFO] Exiting...")
            break

        time.sleep(DETECTION_INTERVAL)

except KeyboardInterrupt:
    print("\n[INFO] Stopped by user")
finally:
    print("\n[INFO] Session finished and logs closed.")
