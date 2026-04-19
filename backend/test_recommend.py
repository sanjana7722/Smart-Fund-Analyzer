import pandas as pd
from ml.recommendation import get_top_funds

df = pd.read_csv("data/final_scored_funds.csv")

top_funds = get_top_funds(df, "Aggressive", top_n=5)

print(top_funds[["Fund_Name", "AI_Score", "Risk_Category"]])