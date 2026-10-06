import json
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

def plot_saccade_distributions(json_path):
    # Load JSON data
    with open(json_path, "r") as f:
        data = json.load(f)

    # Collect saccade and mouse movement features with helpfulness labels
    records = []
    for block in data:
        h = block.get("helpfulness")
        dyn = block.get("dynamic_behavior", {})

        for d in dyn.get("saccade_distances", []):
            records.append({"type": "Saccade Distance", "value": d, "helpfulness": h})
        for v in dyn.get("saccade_velocities", []):
            records.append({"type": "Saccade Velocity", "value": v, "helpfulness": h})

        for dx in dyn.get("mouse_dx", []):
            records.append({"type": "Mouse Movement X", "value": dx, "helpfulness": h})
        for dy in dyn.get("mouse_dy", []):
            records.append({"type": "Mouse Movement Y", "value": dy, "helpfulness": h})
        for vx in dyn.get("mouse_vx", []):
            records.append({"type": "Mouse Velocity X", "value": vx, "helpfulness": h})
        for vy in dyn.get("mouse_vy", []):
            records.append({"type": "Mouse Velocity Y", "value": vy, "helpfulness": h})

    # Create DataFrame
    df = pd.DataFrame(records)
    sns.set(style="whitegrid")

    # Line and color settings per helpfulness level
    linestyle_map = {0: "dotted", 1: "dashdot", 2: "dashed", 3: "solid"}
    color_map = {0: "blue", 1: "orange", 2: "green", 3: "red"}

    # All metrics to plot
    metrics = [
        "Saccade Distance", "Saccade Velocity",
        "Mouse Movement X", "Mouse Movement Y",
        "Mouse Velocity X", "Mouse Velocity Y"
    ]

    # Plot in 2 rows
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    for ax, metric in zip(axes, metrics):
        subset = df[df["type"] == metric]
        levels = sorted(subset["helpfulness"].dropna().unique())

        for h in levels:
            level_data = subset[subset["helpfulness"] == h]
            if not level_data.empty:
                sns.kdeplot(
                    data=level_data,
                    x="value",
                    ax=ax,
                    label=f"level={h}",
                    linewidth=2,
                    linestyle=linestyle_map.get(h, "solid"),
                    color=color_map.get(h, "black")
                )

        ax.set_title(f"Distribution of {metric}")
        ax.set_xlabel(f"{metric} (px or px/s)")
        ax.set_ylabel("Content Block Density")
        ax.legend(title="Helpfulness Level")

    plt.tight_layout()
    plt.show()

# Call the function
plot_saccade_distributions("dataset_demo2.json")

