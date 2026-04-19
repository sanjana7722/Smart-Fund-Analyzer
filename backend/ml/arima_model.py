import numpy as np
from statsmodels.tsa.arima.model import ARIMA
from sklearn.metrics import mean_squared_error


def convert_to_monthly_returns(df):

    df = df.set_index("Date")

    # Take last NAV of each month
    monthly_nav = df["Adj Close"].resample("M").last()

    # Calculate monthly returns
    monthly_returns = monthly_nav.pct_change().dropna()

    return monthly_returns


def process_fund(fund_name, df):

    try:
        returns = convert_to_monthly_returns(df)

        # Minimum 3 years monthly data
        if len(returns) < 36:
            print(f"Skipping {fund_name} - insufficient data")
            return None

        model = ARIMA(returns, order=(1, 0, 1))
        model_fit = model.fit()

        forecast = model_fit.forecast(steps=12)

        # Annualize expected return
        annual_return = (1 + forecast.mean())**12 - 1

        predictions = model_fit.fittedvalues
        rmse = np.sqrt(mean_squared_error(returns, predictions))
        aic = model_fit.aic

        return {
            "Fund_Name": fund_name,
            "Forecast_Return": float(annual_return),
            "RMSE": float(rmse),
            "AIC": float(aic)
        }

    except Exception as e:
        print(f"Error in {fund_name}: {e}")
        return None