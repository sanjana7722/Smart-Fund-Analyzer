import pandas as pd
from sklearn.preprocessing import MinMaxScaler


def clean_metrics_columns(df):
    df = df.rename(columns={
        "Fund": "Fund_Name",
        "Category": "Fund_Type",
        "CAGR (%)": "CAGR",
        "Volatility (%)": "Volatility",
        "Sharpe": "Sharpe_Ratio"
    })
    return df


def calculate_ai_score(df):

    scaler = MinMaxScaler()

    cols = ['Forecast_Return', 'Sharpe_Ratio', 'CAGR', 'Volatility']

    df[cols] = df[cols].astype(float)

    normalized = scaler.fit_transform(df[cols])

    df_norm = pd.DataFrame(
        normalized,
        columns=[c + "_norm" for c in cols]
    )

    df = pd.concat([df.reset_index(drop=True), df_norm], axis=1)

    df["AI_Score"] = (
        0.40 * df["Forecast_Return_norm"] +
        0.25 * df["Sharpe_Ratio_norm"] +
        0.20 * df["CAGR_norm"] -
        0.15 * df["Volatility_norm"]
    )

    return df

def assign_risk_category(df):

    def categorize(vol):
        if vol < 10:
            return "Conservative"
        elif vol < 15:
            return "Moderate"
        else:
            return "Aggressive"

    df["Risk_Category"] = df["Volatility"].apply(categorize)

    return df