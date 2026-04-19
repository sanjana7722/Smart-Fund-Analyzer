from pydantic import BaseModel
from typing import List, Dict


class RecommendRequest(BaseModel):
    risk_appetite: str
    investment_horizon: int
    goal: str


class FundAllocation(BaseModel):
    Fund_Name: str
    Fund_Type: str
    Allocation_percent: float
    Forecast_Return: float
    Volatility: float


class RecommendResponse(BaseModel):
    recommended_funds: List[Dict]
    allocation: List[FundAllocation]
    expected_return: float
    volatility_estimate: float
    risk_level: str