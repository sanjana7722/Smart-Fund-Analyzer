import pandas as pd
from ml.decision_tree_model import train_decision_tree

df = pd.read_csv("data/final_scored_funds.csv")

model = train_decision_tree(df)