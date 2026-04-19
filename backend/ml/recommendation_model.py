import joblib
import os
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report


def train_recommendation_model(df):

    df.columns = df.columns.str.strip()

    # -----------------------------
    # Create Recommendation Label
    # -----------------------------
    threshold = df["AI_Score"].quantile(0.7)

    df["Recommended_Flag"] = df["AI_Score"].apply(
        lambda x: 1 if x >= threshold else 0
    )

    # -----------------------------
    # Feature Matrix
    # -----------------------------
    X = df[[
        
        "Forecast_Return",
        "Sharpe_Ratio",
        "CAGR",
        "Volatility"
    ]]

    y = df["Recommended_Flag"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )

    model = DecisionTreeClassifier(
        max_depth=4,
        min_samples_leaf=5,
        random_state=42
    )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    print("\nRecommendation Model Report:\n")
    print(classification_report(y_test, y_pred))
    print(f"Recommendation model accuracy: {accuracy:.2%}\n")

    joblib.dump(model, "models/recommendation_model.pkl")
    print("Recommendation model saved successfully.")
    return model