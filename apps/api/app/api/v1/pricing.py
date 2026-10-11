"""
b00k5 - Pricing Calculator API Router
Endpoints:
- POST /api/v1/pricing/calculate: Cost-Plus Margin & GST Calculator
- POST /api/v1/pricing/reverse-calculate: Reverse Target Price & Max Cost Calculator
"""

from fastapi import APIRouter, HTTPException, status
from app.services.pricing_calculator import (
    PricingCalculatorEngine,
    PricingCalculationRequest,
    PricingCalculationResponse,
    ReversePricingRequest,
    ReversePricingResponse
)

router = APIRouter()


@router.post("/calculate", response_model=PricingCalculationResponse)
async def calculate_pricing(payload: PricingCalculationRequest):
    """
    Computes cost-plus markup or gross margin pricing with dual GST liability.
    Enforces banker's rounding to exact paise.
    """
    try:
        return PricingCalculatorEngine.calculate(payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/reverse-calculate", response_model=ReversePricingResponse)
async def reverse_calculate_pricing(payload: ReversePricingRequest):
    """
    Backward pricing from desired gross MRP to extract base price and allowable cost ceiling.
    """
    try:
        return PricingCalculatorEngine.reverse_calculate(payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
