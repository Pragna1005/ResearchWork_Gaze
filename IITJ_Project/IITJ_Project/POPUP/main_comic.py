import pyautogui
import datetime
import time
import keyboard
import cv2
import numpy as np
import os
import csv
import tkinter as tk
from tkinter import messagebox
import matplotlib.pyplot as plt
import threading
from collections import defaultdict
from PIL import Image,ImageTk

import openai
from pynput import mouse

import requests
from io import BytesIO
import easyocr
import re
import json


output_dir = "1Line_data_logs_3"
os.makedirs(output_dir, exist_ok=True)

gaze_log_file = os.path.join(output_dir, "gaze.csv")
# mouse_log_file = os.path.join(output_dir, "mouse.csv")
fixa_log_file = os.path.join(output_dir, "fixation.csv")
saccade_log_file = os.path.join(output_dir, "saccade.csv")

MIN_BUBBLE_AREA = 250
BUBBLE_RADIUS_RANGE = (10, 80)
HSV_LOWER = np.array([55, 180, 180])
HSV_UPPER = np.array([70, 255, 255])
DETECTION_INTERVAL = 0.025
GAZE_HOLD_RADIUS = 25
GAZE_HOLD_TIME = 0.25
MAX_BUBBLE_SPEED = 20
SACCADE_VELOCITY_THRESHOLD = 400

MAX_REGRESSIONS = 3
LINE_Y_THRESHOLD = 32
FIXATION_CLUSTER_RADIUS = 50
AREA_X_RADIUS = 40
AREA_FIXATION_THRESHOLD = 8


gaze_log = []
fixations = []
saccades = []
confusion_zones = []

last_bubble_pos = None
last_gaze_pos = None
last_gaze_time = None
last_logged_mouse_pos = None
gaze_hold_start = None
gaze_hold_pos = None
in_fixation = False
fixation_start_time = None
fixation_end_time = None
fixation_pos = None

regression_count = 0
regression_target_y = None

client = openai.OpenAI(api_key="enter you api key")  # 🔐 Replace with your actual key

reader = easyocr.Reader(['en'])


def save_prompt_response(prompt_type, prompt_text, response_text, output_file="prompt_log2.json"):
    data = []
    if os.path.exists(output_file):
        with open(output_file, "r") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []

    data.append({
        "type": prompt_type,
        "prompt": prompt_text,
        "response": response_text
    })

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)


def generate_comic_script(text):
    comic_prompt = (
        f"Format the following story into a 4-panel comic strip for kids. Include for each panel:\n"
        f"1.short Character Dialogue \n2. Visual Description\n\nStory:\n{text}"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": comic_prompt}],
            temperature=0.6
        )
        result = response.choices[0].message.content.strip()
        save_prompt_response("comic_script", comic_prompt, result)
        return result
    except Exception as e:
        print("[COMIC SCRIPT ERROR]", str(e))
        return "Comic script generation failed."

def generate_labeled_prompt(text):
    extraction_prompt = (
        f"""You are helping to generate an educational image for children based on the following story passage:\n\n{text}\n\n"""
        f"Return a short visual instruction like:\n"
        f"Label the characters: accordingly to the real character as it give clearing and realastic indication to that character,('just like example: a teacher is study in classroom,then provide imaeg like a teacher,is in classroom and there were many studuent studing').\"\n"
        f"Output only this kind of visual prompt that show each and every dialogue of the character and content that mention in the script i.e{text} in the final image."
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": extraction_prompt}],
            temperature=0.4
        )
        visual_prompt = response.choices[0].message.content.strip()
        final_prompt = (
            f"{visual_prompt} Use a soft cartoonish illustration style suitable for children. "
            
        )
        save_prompt_response("label_prompt", extraction_prompt, final_prompt)
        return final_prompt
    except Exception as e:
        print("[LABEL GEN ERROR]", str(e))
        return f"A cartoon-style illustration of the scene: {text}"

def generate_image_from_text(prompt):
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            n=1
        )
        image_url = response.data[0].url
        print("Generated image:", image_url)
        save_prompt_response("image_generation", prompt, image_url)
        return image_url
    except Exception as e:
        print("[IMAGE GEN ERROR]", str(e))
        return None

def extract_text_from_image(image_path):
    results = reader.readtext(image_path, detail=0)
    raw_text = " ".join(results).strip()

    correction_prompt = (
        f"Correct the grammar, spelling, and sentence structure of the following text for clarity and conciseness. "
        f"If the text is already correct, just say so.\n\n{raw_text}"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": correction_prompt}],
            temperature=0.3
        )
        corrected_text = response.choices[0].message.content.strip()
        save_prompt_response("ocr_correction", correction_prompt, corrected_text)

        lower_reply = corrected_text.lower()
        if (
            "already grammatically correct" in lower_reply
            or "nothing to fix" in lower_reply
            or "no corrections are needed" in lower_reply
            or "already correct" in lower_reply
        ):
            return raw_text  

        return corrected_text

    except Exception as e:
        print("[TEXT CORRECTION ERROR]", str(e))
        return raw_text

def generate_meaningful_summary_and_image(text):
    if not text:
        return "No text detected.", [], ""

    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": f"Explain this simply:\n\n{text}"}],
            temperature=0.5
        )
        summary = response.choices[0].message.content.strip()
        save_prompt_response("summary_simplification", text, summary)

        comic_script = generate_comic_script(summary)

        character_prompt = (
            f"From this comic script, extract visual character descriptions to ensure consistency between panels. "
            f"Remember to maintain these character descriptions to ensure consistency between panels. The dialogue is important to display in the image as it guides the storyline and provides context to the characters' actions and emotions."
            f"point out all the dialogue as in the scipt and point as important to diaplay in the image."
            f"Give short bullet points describing appearance of each character (e.g. 'King: wears red robe and crown'):\n\n{comic_script}"
        )
        char_response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": character_prompt}],
            temperature=0.4
        )
        character_info = char_response.choices[0].message.content.strip()

        save_prompt_response("character_description", character_prompt, character_info)

        visual_prompt = (
            f"Create a 4-panel comic strip starting form 1 in soft cartoonish style for children. "
            f"Each panel must visually match the description and include **all exact character dialogues{character_info}, thoughts, and narration/captions** as given below. "
            f"Ensure every line of dialogue and narration appears clearly in the image, placed inside appropriate speech bubbles or caption boxes. "
            f"Use the following character appearance guide for consistency:\n{character_info}\n\n"
            f"Full Comic Script:\n{comic_script}"
        )

        image_url = generate_image_from_text(visual_prompt)

        return summary, [image_url], comic_script

    except Exception as e:
        return f"[LLM ERROR] {str(e)}", [], ""

def sanitize_filename(text):
    return re.sub(r'[\\/*?:"<>|]', "_", text)[:80]  # Safe filename

def show_image_popup(image_urls, comic_script, visual_prompt=""):
    def popup_thread():
        popup = tk.Toplevel()
        popup.title("Comic Strip")
        popup.geometry("1100x1000+400+100")
        popup.attributes("-topmost", True)

        frame = tk.Frame(popup)
        frame.pack()

        sanitized_prompt = sanitize_filename(visual_prompt[:80] or "comic_image")

        for i, url in enumerate(image_urls):
            try:
                img_data = requests.get(url).content
                pil_img = Image.open(BytesIO(img_data))
                pil_img = pil_img.resize((512, 512))
                tk_img = ImageTk.PhotoImage(pil_img)

                img_label = tk.Label(frame, image=tk_img)
                img_label.image = tk_img
                img_label.pack(side="left", padx=10, pady=10)

                def save_image(img=pil_img, index=i):
                    os.makedirs("saved_images", exist_ok=True)
                    filename = f"gpt-40-{sanitized_prompt}_{index + 22}.png"
                    filepath = os.path.join("saved_images", filename)
                    img.save(filepath)
                    print(f"[SAVED] Image saved to {filepath}")

                tk.Button(frame, text="Save Image", command=save_image).pack(side="left", padx=10)

            except Exception as e:
                print("[IMAGE ERROR]", e)
                tk.Label(frame, text="(Image failed)").pack(side="left", padx=10)

        tk.Label(popup, text="Comic Script", font=("Arial", 12, "bold")).pack(pady=5)
        text_widget = tk.Text(popup, height=15, width=120, wrap="word")
        text_widget.insert("1.0", comic_script)
        text_widget.config(state="disabled")
        text_widget.pack(pady=5)

        tk.Button(popup, text="Close", command=popup.destroy).pack(pady=10)
        popup.mainloop()

    threading.Thread(target=popup_thread).start()

def show_confusion_popup(cropped_image=None):
    def popup_thread():
        root = tk.Tk()
        root.withdraw()

        popup = tk.Toplevel()
        popup.title("Confusion Alert")
        popup.geometry("700x700+600+100")
        popup.attributes("-topmost", True)

        label = tk.Label(popup, text="Are you confused?", font=("Arial", 14, "bold"))
        label.pack(pady=10)

        summary_text = tk.StringVar(value="(Click 'Yes' to get a summary)")
        extracted_text_str = ""

        if cropped_image is not None:
            temp_path = "temp_crop.png"
            cv2.imwrite(temp_path, cropped_image)

            try:
                pil_img = Image.open(temp_path)
                tk_img = ImageTk.PhotoImage(pil_img)
                img_label = tk.Label(popup, image=tk_img)
                img_label.image = tk_img
                img_label.pack(pady=10)
            except Exception as e:
                print("[ERROR] Failed to load image:", e)

            extracted_text_str = extract_text_from_image(temp_path)
            print("[EXTRACTED TEXT]:", extracted_text_str)

        tk.Label(popup, text="Extracted Text:", font=("Arial", 11, "bold")).pack()
        extracted_text_box = tk.Label(popup, text=extracted_text_str or "(No text found)", wraplength=600,
                                      justify="left", font=("Arial", 10), fg="black", relief="groove", padx=10, pady=5)
        extracted_text_box.pack(pady=5)

        tk.Label(popup, text="Summary:", font=("Arial", 11, "bold")).pack()
        summary_box = tk.Label(popup, textvariable=summary_text, wraplength=600,
                               justify="left", font=("Arial", 10), fg="darkgreen", relief="sunken", padx=10, pady=5)
        summary_box.pack(pady=5)

        def close_popup(is_confused):
            print("[USER RESPONSE]", "YES" if is_confused else "NO")
            summary_text.set("")
            popup.destroy()
            if os.path.exists("temp_crop.png"):
                os.remove("temp_crop.png")

        def generate_summary():
            def worker():
                summary_text.set("Generating summary, image & comic...")
                summary, image_urls, comic_script= generate_meaningful_summary_and_image(extracted_text_str)
                
                summary_text.set(summary)
                if image_urls:
                    show_image_popup(image_urls, comic_script)


            threading.Thread(target=worker).start()

        button_frame = tk.Frame(popup)
        button_frame.pack(pady=10)
        tk.Button(button_frame, text="Yes", command=generate_summary).pack(side="left", padx=10)
        tk.Button(button_frame, text="No", command=lambda: close_popup(False)).pack(side="right", padx=10)

        popup.mainloop()

    threading.Thread(target=popup_thread).start()


scroll_flag = False
last_scroll_time = 0
SCROLL_RESET_INTERVAL = 1.5  

def on_scroll(x, y, dx, dy):
    global scroll_flag, last_scroll_time
    scroll_flag = True
    last_scroll_time = time.time()
    print(f"[SCROLL DETECTED] at ({x}, {y}) - dy={dy}")


scroll_listener = mouse.Listener(on_scroll=on_scroll)
scroll_listener.start()


#
def open_csv_with_header(path, header):
    file_exists = os.path.isfile(path) and os.path.getsize(path) > 0
    f = open(path, 'a', newline='')
    writer = csv.writer(f)
    if not file_exists:
        writer.writerow(header)
    return f, writer

gaze_writer, gaze_csv = open_csv_with_header(gaze_log_file, ["gaze_x", "gaze_y", "timestamp"])
# mouse_writer, mouse_csv = open_csv_with_header(mouse_log_file, ["mouse_x", "mouse_y", "timestamp"])
fixa_writer, fixa_csv = open_csv_with_header(fixa_log_file, ["fix_x", "fix_y", "start_time", "end_time", "duration"])
saccade_writer, saccade_csv = open_csv_with_header(saccade_log_file, ["from", "to", "velocity", "timestamp", "duration"])

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

def calculate_velocity(pos1, time1, pos2, time2):
    if None in (pos1, time1, pos2, time2):
        return 0
    dx, dy = pos2[0] - pos1[0], pos2[1] - pos1[1]
    dt = time2 - time1
    return 0 if dt == 0 else ((dx**2 + dy**2) ** 0.5) / dt

# Main loop
print("[INFO] Tracking green bubble")
print("[INFO] Press 'q' to quit")

try:
    while True:
        screenshot = pyautogui.screenshot()
        frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        bubble_pos = detect_green_bubble(frame)
        

        if bubble_pos:
            if last_bubble_pos is not None:
                dist = np.hypot(bubble_pos[0] - last_bubble_pos[0], bubble_pos[1] - last_bubble_pos[1])
            else:
                dist = 0

            if dist < MAX_BUBBLE_SPEED:
                screen_w, screen_h = pyautogui.size()
                img_h, img_w = frame.shape[:2]
                gaze_x = int(bubble_pos[0] * (screen_w / img_w))
                gaze_y = int(bubble_pos[1] * (screen_h / img_h))
                now = time.time()
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

                gaze_log.append((now, gaze_x, gaze_y))
                gaze_csv.writerow([gaze_x, gaze_y, timestamp])

                SCROLL_DETECTION_Y_JUMP = 50 # If gaze jumps by >400 pixels, assume user scrolled
        

                velocity = calculate_velocity(last_gaze_pos, last_gaze_time, (gaze_x, gaze_y), now)
                if velocity > SACCADE_VELOCITY_THRESHOLD and last_gaze_pos:
                    s_from = last_gaze_pos
                    s_to = (gaze_x, gaze_y)
                    saccade_csv.writerow([s_from, s_to, velocity, timestamp, now - last_gaze_time])
                    saccades.append({'from': s_from, 'to': s_to, 'velocity': velocity, 'duration': now - last_gaze_time})

                    LINE_Y_TOLERANCE = 32
                    LINE_X_THRESHOLD = 40

                    same_line = abs(s_to[1] - s_from[1]) < LINE_Y_TOLERANCE
                    is_regression = s_to[0] < s_from[0]
                    same_horizontal_zone = abs(s_from[0] - s_to[0]) > LINE_X_THRESHOLD

                    print("\n", s_from[0], s_from[1], s_to[0], s_to[1])
                    print("\nsame line:", same_line, ":", abs(s_to[1] - s_from[1]), ":", is_regression)

                    if same_line and is_regression and same_horizontal_zone:
                        if regression_target_y is None:
                            regression_target_y = s_to[1]
                            regression_count = 1
                        elif abs(s_to[1] - regression_target_y) <= LINE_Y_TOLERANCE:
                            regression_count += 1
                        else:
                            regression_target_y = s_to[1]
                            regression_count = 1
                        print("regression_y:", regression_target_y, ":", abs(s_to[1] - regression_target_y), "  :  ", LINE_Y_TOLERANCE)
                    else:
                        regression_count = 0
                        regression_target_y = None

                    print("regression count:", regression_count, "\n")

                    if regression_count >= MAX_REGRESSIONS:
                        print("\n[CONFUSION DETECTED] Regressions on same line.")

                        # Take screenshot
                        screenshot_pil = pyautogui.screenshot()
                        screen_img = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)

                        reg_y = int(regression_target_y)
                        top = max(0, reg_y - LINE_Y_THRESHOLD)
                        bottom = min(screen_img.shape[0], reg_y + LINE_Y_THRESHOLD)
                        cropped = screen_img[top:bottom, :, :]

                        show_confusion_popup(cropped)
                        regression_count = 0


                last_gaze_pos = (gaze_x, gaze_y)
                last_gaze_time = now

                if gaze_hold_pos is None:
                    gaze_hold_start = now
                    gaze_hold_pos = (gaze_x, gaze_y)
                else:
                    hold_dist = np.hypot(gaze_x - gaze_hold_pos[0], gaze_y - gaze_hold_pos[1])
                    if hold_dist <= GAZE_HOLD_RADIUS:
                        hold_duration = now - gaze_hold_start
                        if not in_fixation and hold_duration >= GAZE_HOLD_TIME:
                            in_fixation = True
                            fixation_start_time = gaze_hold_start
                            fixation_pos = gaze_hold_pos
                        elif in_fixation:
                            fixation_end_time = now
                    else:
                        if in_fixation:
                            fixation_end_time = now
                            fixation_duration = fixation_end_time - fixation_start_time

                           
                            start_str = datetime.datetime.fromtimestamp(fixation_start_time).strftime("%Y-%m-%d %H:%M:%S.%f")
                            end_str = datetime.datetime.fromtimestamp(fixation_end_time).strftime("%Y-%m-%d %H:%M:%S.%f")
                            fixa_csv.writerow([fixation_pos[0], fixation_pos[1], start_str, end_str, f"{fixation_duration:.3f}"])
                            fixations.append((fixation_start_time, fixation_pos))

                            if scroll_flag and (time.time() - last_scroll_time < SCROLL_RESET_INTERVAL):
                                print("[INFO] Resetting fixations due to scroll event")
                                fixations.clear()
                                scroll_flag = False

                    # ----------------------------------------------------------------------------------------------------------------
                            current_y = fixation_pos[1]
                            same_line_fixations = [pos for _, pos in fixations if abs(pos[1] - current_y) <= LINE_Y_THRESHOLD]

                            # Group fixations by horizontal area buckets
                            buckets = defaultdict(list)
                            for fx, fy in same_line_fixations:
                                bucket_key = fx // AREA_X_RADIUS
                                buckets[bucket_key].append((fx, fy))

                            for bkey, bucket_points in buckets.items():
                                if len(bucket_points) >= AREA_FIXATION_THRESHOLD:
                                    avg_x = int(sum(p[0] for p in bucket_points) / len(bucket_points))
                                    avg_y = int(sum(p[1] for p in bucket_points) / len(bucket_points))
                                    if (avg_x, avg_y) not in confusion_zones:
                                        confusion_zones.append((avg_x, avg_y, len(bucket_points)))
                                        print("[CONFUSION DETECTED] Fixation cluster in horizontal zone")
                                        screenshot_pil = pyautogui.screenshot()
                                        screen_img = cv2.cvtColor(np.array(screenshot_pil), cv2.COLOR_RGB2BGR)

                                        reg_y = int(avg_y)
                                        top = max(0, reg_y - LINE_Y_THRESHOLD)
                                        bottom = min(screen_img.shape[0], reg_y + LINE_Y_THRESHOLD)
                                        cropped = screen_img[top:bottom, :, :]

                                        show_confusion_popup(cropped)
                        # -------------------------------------------------------------------------

                        in_fixation = False
                        gaze_hold_start = now
                        gaze_hold_pos = (gaze_x, gaze_y)

                print(f"\r[GAZE] {timestamp} - Gaze at ({gaze_x}, {gaze_y})", end="", flush=True)

            last_bubble_pos = bubble_pos
        else:
            last_bubble_pos = None
            gaze_hold_pos = None
            regression_count = 0
            regression_target_y = None

        if keyboard.is_pressed('q'):
            print("\n[INFO] Exiting...")
            break

        time.sleep(DETECTION_INTERVAL)
        

except KeyboardInterrupt:
    print("\n[INFO] Stopped by user")

finally:
    # cv2.destroyAllWindows()
    gaze_writer.close()
    # mouse_writer.close()
    fixa_writer.close()
    saccade_writer.close()

    def plot_scanpath(gaze_log, fixations, saccades,confusion_zones):
        fig, ax = plt.subplots(figsize=(14, 7))
        ax.set_title("Scanpath: Fixations, Saccades, and Gaze Path")
        screen_w, screen_h = pyautogui.size()
        ax.set_xlim(0, screen_w)
        ax.set_ylim(screen_h, 0)
        ax.set_xlabel("X")
        ax.set_ylabel("Y")

        x_vals = [x for _, x, _ in gaze_log]
        y_vals = [y for _, _, y in gaze_log]
        ax.plot(x_vals, y_vals, color='blue', label='Raw Gaze Path', alpha=0.4)

        for i, (t, (x, y)) in enumerate(fixations):
            ax.scatter(x, y, c='red', s=60, label='Fixation' if i == 0 else "", zorder=3)
            ax.text(x + 10, y - 10, f"F{i+1}", color='red', fontsize=8)

        for saccade in saccades:
            (x1, y1) = saccade['from']
            (x2, y2) = saccade['to']
            ax.arrow(x1, y1, x2 - x1, y2 - y1,
                     head_width=15, head_length=15,
                     length_includes_head=True, linestyle='--',
                     color='black', alpha=0.5, zorder=2)
            ax.plot([x1, x2], [y1, y2], 'k:', lw=1, zorder=1)

        for (cx, cy, count) in confusion_zones:
            ax.add_patch(plt.Circle((cx, cy), AREA_X_RADIUS, color='orange', alpha=0.4))
            ax.text(cx, cy - 10, f"Confused({count})", fontsize=9, color='darkorange')

        plt.tight_layout()
        ax.legend()
        plt.show()

    plot_scanpath(gaze_log, fixations, saccades,confusion_zones)
    print("[INFO] All data saved.")