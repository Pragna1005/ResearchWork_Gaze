
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Load dataset
with open("dataset_demo2.json", "r") as f:
    data = json.load(f)

# Flatten into dataframe
records = []
for block in data:
    h = block.get("helpfulness")
    stats = block.get("behavioral_statistics", {})
    dynamics = block.get("dynamic_behavior", {})
    fix_pos = stats.get("fixation_avg_position", [None, None])
    saccades = dynamics.get("saccade_velocities", [])

    records.append({
        "helpfulness": h,
        "fixation_count": stats.get("fixation_count"),
        "fixation_duration": stats.get("fixation_duration"),
        "hover_time": stats.get("hover_time"),
        "saccades_average_speed": stats.get("saccade_avg_speed"),
        "mouse_average_speed": stats.get("mouse_avg_speed"),
        "average_fixation_position_X": fix_pos[0],
        "average_fixation_position_Y": fix_pos[1],
        "saccades_mean_velocity": sum(saccades) / len(saccades) if saccades else None
    })

df = pd.DataFrame(records)
sns.set(style="whitegrid")

metrics = [
    "fixation_count", "fixation_duration", "hover_time",
    "saccades_average_speed", "mouse_average_speed",
    "average_fixation_position_X", "average_fixation_position_Y",
    "saccades_mean_velocity"
]

flier_props = dict(marker='o', markerfacecolor='black', markersize=3, linestyle='none')

# Plot with correct annotation
for metric in metrics:
    plt.figure(figsize=(8, 5))
    ax = sns.boxplot(data=df, x="helpfulness", y=metric, flierprops=flier_props)
    plt.title(f"{metric.replace('_', ' ').capitalize()} vs Helpfulness Level")
    plt.xlabel("Helpfulness Level (0 = Not Helpful to 3 = Very Helpful)")
    plt.ylabel(metric.replace('_', ' ').capitalize())

    # Iterate over each help level (category)
    help_levels = sorted(df["helpfulness"].dropna().unique())
    for idx, val in enumerate(help_levels):
        y_vals = df[df["helpfulness"] == val][metric].dropna()
        if y_vals.empty:
            continue

        q1 = y_vals.quantile(0.25)
        q3 = y_vals.quantile(0.75)
        median = y_vals.median()
        iqr = q3 - q1

        # Use the actual x location of the box from ax.patches
        # Each box is a patch; every category has 1 box (so patch[0] = first box, patch[1] = second box, etc.)
        x = idx  # since x is numeric here

        # Annotations
        ax.annotate(f"Median: {median:.2f}", xy=(x, median), xytext=(x - 0.3, median + 0.05 * iqr),
                    arrowprops=dict(arrowstyle="->", color='black'), fontsize=8, color='black')

        ax.annotate(f"Q1: {q1:.2f}", xy=(x, q1), xytext=(x + 0.2, q1),
                    arrowprops=dict(arrowstyle="->", color='blue'), fontsize=8, color='blue')

        ax.annotate(f"Q3: {q3:.2f}", xy=(x, q3), xytext=(x + 0.2, q3),
                    arrowprops=dict(arrowstyle="->", color='green'), fontsize=8, color='green')

    plt.tight_layout()
    plt.show()

