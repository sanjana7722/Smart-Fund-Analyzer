import pandas as pd
from ml.allocation_engine import generate_portfolio

# Load final scored dataset
df = pd.read_csv("data/final_scored_funds.csv")

portfolio, exp_return, volatility = generate_portfolio(df, "Aggressive")

print("\nRecommended Portfolio:\n")

for fund in portfolio:
    print(fund)

print("\nExpected Portfolio Return:", exp_return)
print("Estimated Portfolio Volatility:", volatility)