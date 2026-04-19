import pandas as pd
from ml.recommendation_model import train_recommendation_model

df = pd.read_csv("data/final_scored_funds.csv")

model = train_recommendation_model(df)