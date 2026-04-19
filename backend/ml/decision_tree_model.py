import joblib
import os
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report


def train_decision_tree(df):

    X = df[[
        "AI_Score",
        "Forecast_Return",
        "Volatility",
        "Sharpe_Ratio"
    ]]

    y = df["Risk_Category"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )

    model = DecisionTreeClassifier(max_depth=4, random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    print("\nDecision Tree Model Report:\n")
    print(classification_report(y_test, y_pred))
    print(f"Decision Tree model accuracy: {accuracy:.2%}\n")

    # Create models directory if not exists
    os.makedirs("models", exist_ok=True)

    # Save model
    joblib.dump(model, "models/decision_tree.pkl")

    print("Decision Tree model saved successfully.")

    return model