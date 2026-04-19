import os
import pandas as pd
from ml.scoring import clean_metrics_columns, calculate_ai_score, assign_risk_category

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

arima_path = os.path.join(BASE_DIR, "data", "arima_results.csv")
metrics_path = os.path.join(BASE_DIR, "data", "metrics.xlsx")

# Load files
arima_df = pd.read_csv(arima_path)
metrics_df = pd.read_excel(metrics_path)

# Clean metrics column names
metrics_df = clean_metrics_columns(metrics_df)

# Merge on Fund_Name
merged_df = pd.merge(arima_df, metrics_df, on="Fund_Name")

# Calculate AI Score
final_df = calculate_ai_score(merged_df)

# Assign Risk Category
final_df = assign_risk_category(final_df)

# Sort by AI Score
final_df = final_df.sort_values("AI_Score", ascending=False)

# Save final output
output_path = os.path.join(BASE_DIR, "data", "final_scored_funds.csv")
final_df.to_csv(output_path, index=False)

print("AI scoring completed successfully!")