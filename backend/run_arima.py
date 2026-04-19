import pandas as pd
from ml.data_loader import load_all_funds
from ml.arima_model import process_fund

filepath = "data/mutual_fund.xlsx"

funds_dict = load_all_funds(filepath)

results = []

for fund_name, df in funds_dict.items():
    print(f"Processing: {fund_name}")
    output = process_fund(fund_name, df)

    if output:
        results.append(output)

results_df = pd.DataFrame(results)

results_df.to_csv("data/arima_results.csv", index=False)

if not results_df.empty:
    avg_rmse = results_df["RMSE"].mean()
    print(f"Average ARIMA RMSE across {len(results_df)} funds: {avg_rmse:.6f}")

print("ARIMA forecasting completed successfully!")