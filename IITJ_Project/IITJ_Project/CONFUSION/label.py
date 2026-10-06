import pandas as pd

fixation_df = pd.read_csv("demo_video_logs/fixation.csv")
yes_click_df = pd.read_csv("demo_video_logs/popup_yes_clicks/yes_click_log1.csv")

fixation_df['label'] = 0

for _, click_row in yes_click_df.iterrows():
    target_aoi = click_row['AOI_ID']

    if target_aoi in fixation_df.columns:
        for i in fixation_df.index:
            if str(fixation_df.at[i, target_aoi]) == "True":
                fixation_df.at[i, 'label'] = 1
    else:
        print(f"[WARNING] AOI column '{target_aoi}' not found in fixation.csv")

fixation_df.to_csv("fixation_label.csv", index=False)
print("[✅] fixation_labeled.csv saved with updated labels.")
