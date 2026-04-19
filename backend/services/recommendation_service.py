import pandas as pd
import joblib
import os

from backend.ml.allocation_engine import generate_portfolio

# -----------------------------
# Base Directory
# -----------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# -----------------------------
# Load Fund Mapping (Excel)
# -----------------------------
mapping_path = os.path.join(BASE_DIR, "data", "fund_name_with_Id.xlsx")

fund_df = pd.read_excel(mapping_path, engine="openpyxl")

# Clean column names (very important)
fund_df.columns = fund_df.columns.str.strip()

# Keep only required columns
fund_df = fund_df[["Fund Name", "Type", "SubType", "Risk", "Fund"]]

# Create dictionary: ID -> Actual Fund Name
fund_name_mapping = dict(zip(
    fund_df["Fund"],
    fund_df["Fund Name"]
))

# -----------------------------
# Load Model & Data
# -----------------------------
DATA_PATH = os.path.join(BASE_DIR, "data", "final_scored_funds.csv")
MODEL_PATH = os.path.join(BASE_DIR, "models", "recommendation_model.pkl")

df = pd.read_csv(DATA_PATH)
recommend_model = joblib.load(MODEL_PATH)


# -----------------------------
# Recommendation Function
# -----------------------------
def recommend_portfolio(risk_appetite: str):

    # 1️⃣ Filter by Risk Category
    filtered = df[df["Risk_Category"] == risk_appetite].copy()

    if len(filtered) == 0:
        return [], [], 0.0, 0.0

    # 2️⃣ Ensure feature order matches trained model
    feature_order = recommend_model.feature_names_in_
    features = filtered[feature_order]

    # 3️⃣ Predict Recommendation Flag
    filtered["Predicted_Recommend"] = recommend_model.predict(features)

    # 4️⃣ Keep Only Recommended Funds
    recommended = filtered[filtered["Predicted_Recommend"] == 1]

    # Fallback if model rejects everything
    if len(recommended) == 0:
        recommended = filtered.sort_values("AI_Score", ascending=False).head(6)
    else:
        recommended = recommended.sort_values("AI_Score", ascending=False)

    # 5️⃣ Select Top 6
    top_funds = recommended.head(6).copy()

    # 6️⃣ Replace Fund IDs with Actual Names (IMPORTANT: AFTER top_funds defined)
    top_funds["Fund_Name"] = top_funds["Fund_Name"].apply(
        lambda x: fund_name_mapping.get(x, x)
    )

    # 7️⃣ Generate Portfolio Allocation
    portfolio, exp_return, volatility = generate_portfolio(top_funds, risk_appetite)

    # 8️⃣ Replace IDs in allocation also
    for alloc in portfolio:
        fund_id = alloc["Fund_Name"]
        alloc["Fund_Name"] = fund_name_mapping.get(fund_id, fund_id)

    return (
        top_funds.to_dict(orient="records"),
        portfolio,
        float(exp_return),
        float(volatility),
    )