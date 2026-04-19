from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from services.recommendation_service import recommend_portfolio

app = FastAPI()

# ✅ Proper CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Request Schema
# ----------------------------
class RecommendationRequest(BaseModel):
    risk_appetite: str


# ----------------------------
# API Endpoint
# ----------------------------
@app.post("/recommend")
def recommend(request: RecommendationRequest):
    funds, allocation, exp_return, volatility = recommend_portfolio(
        request.risk_appetite
    )

    return {
        "funds": funds,
        "allocation": allocation,
        "expected_return": exp_return,
        "volatility": volatility,
    }


@app.get("/")
def root():
    return {"message": "API Running"}