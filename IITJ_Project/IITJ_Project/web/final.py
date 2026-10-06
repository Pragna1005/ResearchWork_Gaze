import pandas as pd
import json
from datetime import datetime, timedelta
import math
import numpy as np
from scipy.stats import pearsonr
from fastdtw import fastdtw

# Configuration
ANNOTATION_FILE = "demodata_logs2/annotations.csv"
FIXATION_FILE = "demodata_logs2/fixation.csv"
SACCADE_FILE = "demodata_logs2/saccade.csv"
MOUSE_LOG_FILE = "demodata_logs2/mouse_log.csv"
OUTPUT_JSON = "dataset_demo2.json"

# --- Helpers ---
def parse_datetime(dt_str):
    try:
        return datetime.strptime(dt_str.strip(), "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        return datetime.strptime(dt_str.strip(), "%Y-%m-%d %H:%M:%S")

def inside_block(x, y, block):
    return (
        block["x"] <= x <= block["x"] + block["width"] and
        block["y"] <= y <= block["y"] + block["height"]
    )

def fixation_inside_block(fix_x, fix_y, block):
    block_left = float(block["x"])
    block_top = float(block["y"])
    block_right = block_left + float(block["width"])
    block_bottom = block_top + float(block["height"])

    if((block_top-fix_y)>0):
        return block_left <= fix_x <= block_right and block_top <= (fix_y+10) <= block_bottom
    
    elif((fix_y-block_bottom)>0):
        return block_left <= fix_x <= block_right and block_top <= (fix_y-45) <= block_bottom
    
    else:
        return block_left <= fix_x <= block_right and block_top <= fix_y<= block_bottom

def build_scroll_timeline(scroll_log):
    scroll_log = scroll_log.copy()
    scroll_log['ts'] = scroll_log['timestamp'].apply(parse_datetime)
    scroll_log = scroll_log.sort_values('ts')
    return [(row['ts'], float(row['y'])) for _, row in scroll_log.iterrows()]

def get_scroll_offset(timestamp, scroll_timeline):
    ts = parse_datetime(timestamp)
    last_offset = 0.0
    for scroll_ts, offset in scroll_timeline:
        if ts >= scroll_ts:
            last_offset = offset
        else:
            break
    return last_offset

def calculate_pcc(eye_seq, mouse_seq):
    if len(eye_seq) < 2 or len(mouse_seq) < 2:
        return 0.0, 0.0
    eye_x, eye_y = zip(*eye_seq)
    mouse_x, mouse_y = zip(*mouse_seq)
    try:
        pcc_x = pearsonr(eye_x, mouse_x)[0]
        pcc_y = pearsonr(eye_y, mouse_y)[0]
    except:
        pcc_x, pcc_y = 0.0, 0.0
    return pcc_x, pcc_y


def calculate_dtw(eye_seq, mouse_seq):
    if len(eye_seq) < 2 or len(mouse_seq) < 2:
        return 0.0, 0.0
    eye_diff = np.diff(eye_seq, axis=0)
    mouse_diff = np.diff(mouse_seq, axis=0)
    dist_x, _ = fastdtw(eye_diff[:, 0], mouse_diff[:, 0])
    dist_y, _ = fastdtw(eye_diff[:, 1], mouse_diff[:, 1])
    return dist_x, dist_y

# --- Load Data ---
annotations = pd.read_csv(ANNOTATION_FILE)
fixations = pd.read_csv(FIXATION_FILE)
saccades = pd.read_csv(SACCADE_FILE)
mouse_log = pd.read_csv(MOUSE_LOG_FILE)

# --- Scroll Timeline ---
mouse_log = mouse_log.sort_values('timestamp')
scroll_df = mouse_log[mouse_log['type'] == 'scroll'][['timestamp', 'y']]
scroll_timeline = build_scroll_timeline(scroll_df)

# --- Adjust Mouse Moves ---
def adjust_mouse_records(df):
    records = []
    for _, row in df.iterrows():
        timestamp = row["timestamp"]
        offset = get_scroll_offset(timestamp, scroll_timeline)
        records.append({
            "x": float(row["x"]),
            "y": float(row["y"]) + offset,
            "timestamp": timestamp
        })
    return pd.DataFrame(records)

adjusted_mouse = adjust_mouse_records(mouse_log[mouse_log['type'] == 'move'])

# --- Adjust Fixations with fix_y / 1.65 + 2*offset ---
adjusted_fixations = []
for _, row in fixations.iterrows():
    offset = get_scroll_offset(row["start_time"], scroll_timeline)
    adjusted_fixations.append({
        "x": float(row["fix_x"]),
        "y": (float(row["fix_y"]) / 1.65) + (2 * offset),
        "duration": float(row["duration"]),
        "timestamp": row["start_time"]
    })
adjusted_fixations = pd.DataFrame(adjusted_fixations)

# --- Build Final JSON ---
final_data = []
for _, blk in annotations.iterrows():
    block_rect = {
        'x': float(blk['x']),
        'y': float(blk['y']),
        'width': float(blk['width']),
        'height': float(blk['height'])
    }
    ann_time = parse_datetime(blk['timestamp'])
    time_start = ann_time - timedelta(seconds=15)
    time_end = ann_time + timedelta(seconds=15)

    # Filter events in time window
    fix_window = adjusted_fixations[
        adjusted_fixations['timestamp'].apply(parse_datetime).between(time_start, time_end)
    ]
    mouse_window = adjusted_mouse[
        adjusted_mouse['timestamp'].apply(parse_datetime).between(time_start, time_end)
    ]

    block_data = {
        'blockId': str(blk['blockId']),
        'helpfulness': int(blk['helpfulness']),
        'content': blk['content'],
        'structural_metrics': {
            'area': block_rect['width'] * block_rect['height'],
            'text_density': len(blk['content'].split()) / max(1, block_rect['width']*block_rect['height']),
            'vertical_position': block_rect['y'],
            'has_image': 'IMG' in blk['tag'],
            'hyperlink_count': blk['content'].count('http'),
            'width': block_rect['width'],
            'height': block_rect['height']
        },
        'eye_data': [],
        'mouse_data': [],
        'behavioral_statistics': {},
        'dynamic_behavior': {}
    }

    # Fixations inside block
    fix_list = []
    total_fix_duration = 0
    fx_positions = []
    for _, fx in fix_window.iterrows():
        if fixation_inside_block(fx['x'], fx['y'], block_rect):
            fix_list.append({
                'x': fx['x'],
                'y': fx['y'],
                'duration': fx['duration'],
                'timestamp': fx['timestamp']
            })
            total_fix_duration += fx['duration']
            fx_positions.append((fx['x'], fx['y']))

    block_data['eye_data'] = fix_list

    fixation_count = len(fix_list)
    avg_fix_x = np.mean([pos[0] for pos in fx_positions]) if fx_positions else 0
    avg_fix_y = np.mean([pos[1] for pos in fx_positions]) if fx_positions else 0


    # Mouse moves inside block
    prev = None
    speeds = []
    mouse_list = []
    hover_time = 0
    dx_list = []
    dy_list = []
    vx_list = []
    vy_list = []

    for _, mv in mouse_window.iterrows():
        if inside_block(mv['x'], mv['y'], block_rect):
            mouse_list.append({'x': mv['x'], 'y': mv['y'], 'timestamp': mv['timestamp']})
            if prev is not None:
                t1 = parse_datetime(prev['timestamp'])
                t2 = parse_datetime(mv['timestamp'])
                dt = (t2 - t1).total_seconds()
                if dt > 0:
                    dx = mv['x'] - prev['x']
                    dy = mv['y'] - prev['y']
                    dist = math.hypot(dx, dy)

                    dx_list.append(dx)
                    dy_list.append(dy)
                    vx_list.append(dx / dt)
                    vy_list.append(dy / dt)
                    speeds.append(dist / dt)
                    hover_time += dt * 1000
            prev = mv

    block_data['mouse_data'] = mouse_list

    # Saccades
    # Saccades
    sac_dists = []
    sac_vels = []

    for _, sc in saccades.iterrows():
        sc_ts = parse_datetime(sc['timestamp'])
        if time_start <= sc_ts <= time_end:
            offset = get_scroll_offset(sc['timestamp'], scroll_timeline)

            to_x = float(sc['to_x'])
            to_y = (float(sc['to_y']) / 1.65) + (2 * offset)

            from_x = float(sc['from_x'])
            from_y = (float(sc['from_y']) / 1.65) + (2 * offset)

            if fixation_inside_block(to_x, to_y, block_rect):
                dist = math.hypot(to_x - from_x, to_y - from_y)
                sac_dists.append(dist)
                sac_vels.append(float(sc['velocity']))

    block_data['dynamic_behavior']['saccade_distances'] = sac_dists
    block_data['dynamic_behavior']['saccade_velocities'] = sac_vels


    # eye_seq = np.array([[fx['x'], fx['y']] for fx in fix_list])
    # mouse_seq = np.array([[mv['x'], mv['y']] for mv in mouse_list])
    # dtw_x, dtw_y = calculate_dtw(eye_seq, mouse_seq)
    # block_data['dynamic_behavior']['dtw_eye_mouse_x'] = dtw_x
    # block_data['dynamic_behavior']['dtw_eye_mouse_y'] = dtw_y

    # pcc_x, pcc_y = calculate_pcc(eye_seq, mouse_seq)
    # block_data['dynamic_behavior']['eye_mouse_pcc_x'] = pcc_x
    # block_data['dynamic_behavior']['eye_mouse_pcc_y'] = pcc_y

    block_data['dynamic_behavior']['mouse_dx'] = dx_list
    block_data['dynamic_behavior']['mouse_dy'] = dy_list
    block_data['dynamic_behavior']['mouse_vx'] = vx_list
    block_data['dynamic_behavior']['mouse_vy'] = vy_list



    # Behavioral Statistics
    block_data['behavioral_statistics'] = {
        'fixation_count': fixation_count,
        'fixation_duration': total_fix_duration,
        'fixation_avg_position': [avg_fix_x, avg_fix_y],
        'eye_review_count': 0,
        'saccade_avg_speed': np.mean(sac_vels) if sac_vels else 0,
        'hover_time': hover_time,
        'mouse_avg_speed': np.mean(speeds) if speeds else 0,
        'block_exposure_count': 0,
        'block_exposure_time': 0
    }

    final_data.append(block_data)

# Save to JSON
with open(OUTPUT_JSON, 'w') as f:
    json.dump(final_data, f, indent=2)

print(f"✅ Dataset saved to {OUTPUT_JSON}")
