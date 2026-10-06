import pyautogui
import datetime
import time
import keyboard
import cv2
import numpy as np
# from pywinauto import mouse
import matplotlib.pyplot as plt
import os
import csv

output_dir = "demodata_logs2"
os.makedirs(output_dir, exist_ok=True)


gaze_log_file = os.path.join(output_dir, "gaze.csv")
# mouse_log_file = os.path.join(output_dir, "mouse.csv")
fixa_log_file = os.path.join(output_dir, "fixation.csv")
saccade_log_file = os.path.join(output_dir, "saccade.csv")


MIN_BUBBLE_AREA = 250
BUBBLE_RADIUS_RANGE = (10, 80)
DETECTION_INTERVAL = 0.025
#CC10F61F
HSV_LOWER = np.array([55, 180, 180])
HSV_UPPER = np.array([70, 255, 255])
GAZE_HOLD_RADIUS = 25
GAZE_HOLD_TIME = 0.25
DOUBLE_CLICK_HOLD_TIME = 0.6
CLICK_COOLDOWN = 3
# MAX_BUBBLE_SPEED = 20
SACCADE_VELOCITY_THRESHOLD = 450

in_fixation = False
fixation_start_time = None
fixation_end_time = None
fixation_pos = None
gaze_hold_start = None
gaze_hold_pos = None

previous_fixation_end_time = None
previous_fixation_pos = None



gaze_log = []
fixations = []
saccades_list = []

last_logged_mouse_pos = None
last_bubble_pos = None
gaze_hold_start = None
gaze_hold_pos = None
last_click_time = 0
clicked = False
last_gaze_time = None
last_gaze_pos = None

def open_csv_with_header(path, header):
    file_exists = os.path.isfile(path) and os.path.getsize(path) > 0
    f = open(path, 'a', newline='')
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(header)
    return f, writer

gaze_writer, gaze_csv = open_csv_with_header(gaze_log_file, ["gaze_x", "gaze_y", "timestamp"])
# mouse_writer, mouse_csv = open_csv_with_header(mouse_log_file, ["mouse_x", "mouse_y", "timestamp"])
# fixa_writer, fixa_csv = open_csv_with_header(fixa_log_file, ["fix_x", "fix_y", "timestamp"])
fixa_writer, fixa_csv = open_csv_with_header(fixa_log_file, ["fix_x", "fix_y", "start_time", "end_time", "duration"])
# saccade_writer, saccade_csv = open_csv_with_header(saccade_log_file, ["from", "to", "velocity", "timestamp", "duration"])
saccade_writer, saccade_csv = open_csv_with_header(
    saccade_log_file,
    ["from_x", "from_y", "to_x", "to_y", "velocity", "distance", "timestamp", "duration"]
)

#CC10F61F
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

def is_on_desktop(gaze_x, gaze_y):
    screen_width, screen_height = pyautogui.size()
    TASKBAR_HEIGHT = 40
    return gaze_y < (screen_height - TASKBAR_HEIGHT)

def calculate_velocity(pos1, time1, pos2, time2):
    if pos1 is None or pos2 is None or time1 is None or time2 is None:
        return 0
    dx = pos2[0] - pos1[0]
    dy = pos2[1] - pos1[1]
    dt = time2 - time1
    if dt == 0:
        return 0
    return ((dx**2 + dy**2) ** 0.5) / dt

recording_started = False

print("[INFO] Tracking green bubble (#CC10F61F)")
print("[INFO] Double-click gaze to open folder/file on desktop only")
print("[INFO] Press 'q' to quit")

try:
    while not recording_started:
        print("NOt Started gaze recording:")
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

        # now1 = time.time()
        # timestamp1 = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        # mouse_x, mouse_y = pyautogui.position()
        # if last_logged_mouse_pos != (mouse_x, mouse_y):
        #     mouse_csv.writerow([mouse_x, mouse_y, timestamp1])
        #     last_logged_mouse_pos = (mouse_x, mouse_y)



        if bubble_detected:
            if last_bubble_pos is not None:
                dist = ((bubble_pos[0] - last_bubble_pos[0]) ** 2 + (bubble_pos[1] - last_bubble_pos[1]) ** 2) ** 0.5
            else:
                dist = 0

            # if dist < MAX_BUBBLE_SPEED:
            screen_w, screen_h = pyautogui.size()
            img_h, img_w = frame.shape[:2]

            gaze_x = int(bubble_pos[0] * (screen_w / img_w))
            gaze_y = int(bubble_pos[1] * (screen_h / img_h))
            now = time.time()
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

            gaze_log.append((now, gaze_x, gaze_y))
            gaze_csv.writerow([gaze_x, gaze_y, timestamp])

            # Fixation detection
            if gaze_hold_pos is None:
                gaze_hold_start = now
                gaze_hold_pos = (gaze_x, gaze_y)
            else:
                hold_dist = ((gaze_x - gaze_hold_pos[0]) ** 2 + (gaze_y - gaze_hold_pos[1]) ** 2) ** 0.5
                if hold_dist <= GAZE_HOLD_RADIUS:
                    hold_duration = now - gaze_hold_start

                    if not in_fixation and hold_duration >= GAZE_HOLD_TIME:
                        in_fixation = True
                        fixation_start_time = gaze_hold_start
                        fixation_pos = gaze_hold_pos
                        print(f"\n[FIXATION START] {fixation_pos}")

                    elif in_fixation:
                        fixation_end_time = now

                else:
                    if in_fixation:
                        fixation_end_time = now
                        fixation_duration = fixation_end_time - fixation_start_time
                        start_str = datetime.datetime.fromtimestamp(fixation_start_time).strftime("%Y-%m-%d %H:%M:%S.%f")
                        end_str = datetime.datetime.fromtimestamp(fixation_end_time).strftime("%Y-%m-%d %H:%M:%S.%f")
                        fixa_csv.writerow([
                            fixation_pos[0], fixation_pos[1],
                            start_str, end_str, f"{fixation_duration:.3f}"
                        ])
                        fixations.append((fixation_start_time, fixation_pos))
                        print(f"[FIXATION END] {fixation_pos} | Duration: {fixation_duration:.2f}s")

                        # --- Saccade Detection: between previous and current fixation
                        if previous_fixation_pos is not None:
                            dx = fixation_pos[0] - previous_fixation_pos[0]
                            dy = fixation_pos[1] - previous_fixation_pos[1]
                            distance = (dx**2 + dy**2) ** 0.5
                            saccade_duration = fixation_start_time - previous_fixation_end_time
                            velocity = distance / saccade_duration if saccade_duration > 0 else 0
                            saccade_csv.writerow([
                                previous_fixation_pos[0], previous_fixation_pos[1],
                                fixation_pos[0], fixation_pos[1],
                                f"{velocity:.2f}", f"{distance:.2f}",
                                end_str, f"{saccade_duration:.3f}"
                            ])

                            saccades_list.append((previous_fixation_pos, fixation_pos))
                            print(f"[SACCADE] From {previous_fixation_pos} to {fixation_pos} | Distance: {distance:.1f}px | Velocity: {velocity:.1f}px/s")

                        # Update last fixation
                        previous_fixation_pos = fixation_pos
                        previous_fixation_end_time = fixation_end_time

                    # Reset for next fixation
                    in_fixation = False
                    gaze_hold_start = now
                    gaze_hold_pos = (gaze_x, gaze_y)
    
            print(f"\r[GAZE] {timestamp} - Gaze at ({gaze_x}, {gaze_y})", end="", flush=True)
            # else:
            #     print(f"\r[GAZE] Skipping fast movement (speed={dist:.1f})      ", end="", flush=True)
            #     gaze_hold_start = None
            #     gaze_hold_pos = None
            #     in_fixation = False

            last_bubble_pos = bubble_pos
        else:
            last_bubble_pos = None
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
    cv2.destroyAllWindows()
    gaze_writer.close()
    # mouse_writer.close()
    fixa_writer.close()
    saccade_writer.close()
    print("\n[INFO] Logs saved to 'data_logs' folder.")

    def plot_scanpath(gaze_log, fixations, saccades):
        if not fixations and not saccades:
            print("[SCANPATH] No data to plot.")
            return

        fig, ax = plt.subplots(figsize=(14, 7))
        ax.set_title("Scanpath: Fixations and Saccades")
        ax.set_xlim(0, pyautogui.size().width)
        ax.set_ylim(pyautogui.size().height, 0)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")

        x_vals = [x for _, x, _ in gaze_log]
        y_vals = [y for _, _, y in gaze_log]
        ax.plot(x_vals, y_vals, color='blue', label='Raw Gaze Path', alpha=0.5)

        for i, (t, (x, y)) in enumerate(fixations):
            ax.scatter(x, y, c='red', s=60, label='Fixation' if i == 0 else "", zorder=3)
            ax.text(x + 10, y - 10, f"Fix {i+1}", color='red', fontsize=8)

        
        for (x1, y1), (x2, y2) in saccades:
            ax.arrow(x1, y1, x2 - x1, y2 - y1,
                    head_width=15, head_length=15,
                    length_includes_head=True, linestyle='--',
                    color='black', alpha=0.5, zorder=2)
            ax.plot([x1, x2], [y1, y2], 'k:', lw=1, zorder=1)

        plt.tight_layout()
        plt.legend()
        plt.show()

    plot_scanpath(gaze_log, fixations, saccades_list)


