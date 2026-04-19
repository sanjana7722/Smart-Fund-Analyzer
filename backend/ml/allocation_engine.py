import numpy as np


ALLOCATION_RULES = {
    "Conservative": {"Debt": 70, "Hybrid": 20, "Equity": 10},
    "Moderate": {"Hybrid": 40, "Equity": 40, "Debt": 20},
    "Aggressive": {"Equity": 70, "Hybrid": 20, "Debt": 10}
}


def generate_portfolio(df, risk_appetite, top_per_category=2):

    # Clean column names (important for Excel exports)
    df.columns = df.columns.str.strip()

    required_columns = [
        "Fund_Name",
        "Fund_Type",
        "AI_Score",
        "Forecast_Return",
        "Volatility"
    ]

    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    if risk_appetite not in ALLOCATION_RULES:
        raise ValueError("Invalid risk appetite")

    rules = ALLOCATION_RULES[risk_appetite]

    portfolio = []
    total_expected_return = 0
    total_volatility = 0

    for fund_type, percent in rules.items():

        # Use Fund_Type (correct column)
        category_funds = df[df["Fund_Type"].str.strip() == fund_type]
        category_funds = category_funds.sort_values("AI_Score", ascending=False)

        selected = category_funds.head(top_per_category)

        if selected.empty:
            continue

        allocation_per_fund = percent / len(selected)

        for _, row in selected.iterrows():

            weight = allocation_per_fund / 100

            total_expected_return += weight * row["Forecast_Return"]
            total_volatility += weight * row["Volatility"]

            portfolio.append({
                "Fund_Name": row["Fund_Name"],
                "Fund_Type": fund_type,
                "Allocation_percent": weight * 100,
                "Forecast_Return": round(row["Forecast_Return"], 4),
                "Volatility": round(row["Volatility"], 4)
            })

    total_expected_return = round(total_expected_return, 4)
    total_volatility = round(total_volatility, 4)

    return portfolio, total_expected_return, total_volatility