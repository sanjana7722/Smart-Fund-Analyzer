import pandas as pd

def load_all_funds(filepath):

    # Read all sheets
    all_sheets = pd.read_excel(filepath, sheet_name=None)

    fund_data = {}

    for sheet_name, df in all_sheets.items():

        df.columns = df.columns.str.strip()

        # Check required columns
        if "Date" not in df.columns or "Adj Close" not in df.columns:
            print(f"Skipping {sheet_name} - Required columns missing")
            continue

        # Convert date properly
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

        # Remove invalid rows
        df = df.dropna(subset=["Date", "Adj Close"])

        # Sort chronologically
        df = df.sort_values("Date")

        # Keep only necessary columns
        df = df[["Date", "Adj Close"]]

        fund_data[sheet_name] = df

    return fund_data