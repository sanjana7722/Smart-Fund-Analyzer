import pandas as pd

def get_top_funds(df, risk_appetite, top_n=5):

    filtered = df[df["Risk_Category"] == risk_appetite]

    ranked = filtered.sort_values("AI_Score", ascending=False)

    return ranked.head(top_n)