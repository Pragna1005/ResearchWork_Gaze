import pandas as pd

# Load your dataset
df = pd.read_csv("fixation_labeled20.csv")

aoi_cols = [col for col in df.columns if col.startswith("AOI_")]

df[aoi_cols] = df[aoi_cols].applymap(lambda x: 1 if str(x).strip().lower() == "true" else 0)

df.to_csv("fixation_label_final.csv", index=False)
print("✅ AOI columns converted to binary and saved.")
