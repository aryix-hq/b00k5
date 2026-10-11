"""
b00k5 - Product & Service Cost-Plus Margin & GST Tax Calculator Engine
Compliant with Indian Goods and Services Tax (GST) Act, 2017 & ICAI Costing Standards.

Formulas:
- Total Cost Base = Direct Cost + Overhead Cost
- Markup on Cost: Taxable Base = Total Cost * (1 + Markup% / 100)
- Gross Margin on Price: Taxable Base = Total Cost / (1 - Margin% / 100)
- Dual GST: Intra-State (CGST 50% + SGST 50%) vs Inter-State (IGST 100%)
- Banker's Rounding: ROUND_HALF_EVEN to 2 decimal places (exact paise)
"""

from decimal import Decimal, ROUND_HALF_EVEN
from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, field_validator


def quantize_paise(val: Decimal) -> Decimal:
    """Quantize to 2 decimal places using Banker's rounding (ROUND_HALF_EVEN)."""
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)


class PricingCalculationRequest(BaseModel):
    direct_cost: Decimal = Field(default=Decimal("0.00"), ge=0, description="Direct materials/labor/hosting cost")
    overhead_cost: Decimal = Field(default=Decimal("0.00"), ge=0, description="Indirect overheads, platform fees, utilities")
    pricing_mode: Literal["markup", "margin"] = Field(
        default="markup",
        description="'markup' on total cost base vs 'margin' on selling price"
    )
    margin_percentage: Decimal = Field(default=Decimal("20.00"), ge=0, description="Profit margin or markup percentage")
    gst_rate: Decimal = Field(default=Decimal("18.00"), ge=0, description="GST slab (0, 5, 12, 18, 28)")
    transaction_type: Literal["intra_state", "inter_state"] = Field(
        default="intra_state",
        description="'intra_state' (CGST+SGST) vs 'inter_state' (IGST)"
    )
    hsn_sac_code: Optional[str] = Field(default="998314", description="HSN/SAC code (default 998314 for IT software)")
    item_description: Optional[str] = Field(default="Software Consulting & Development Services", description="Description for invoice line item")
    currency: str = Field(default="INR", description="Currency symbol")

    @field_validator("margin_percentage")
    @classmethod
    def validate_margin(cls, v: Decimal, info) -> Decimal:
        pricing_mode = info.data.get("pricing_mode", "markup")
        if pricing_mode == "margin" and v >= Decimal("100.00"):
            raise ValueError("Gross margin percentage cannot be 100% or greater (division by zero / infinite price).")
        return v


class ReversePricingRequest(BaseModel):
    desired_mrp: Decimal = Field(gt=0, description="Target Gross MRP inclusive of GST")
    gst_rate: Decimal = Field(default=Decimal("18.00"), ge=0, description="Applicable GST rate %")
    pricing_mode: Literal["markup", "margin"] = Field(default="margin")
    target_margin_percentage: Decimal = Field(default=Decimal("25.00"), ge=0, description="Target margin/markup %")
    transaction_type: Literal["intra_state", "inter_state"] = Field(default="intra_state")


class PricingCalculationResponse(BaseModel):
    direct_cost: Decimal
    overhead_cost: Decimal
    total_cost_base: Decimal
    pricing_mode: str
    margin_percentage: Decimal
    taxable_base_price: Decimal
    net_profit: Decimal
    effective_margin_percentage: Decimal
    gst_rate: Decimal
    transaction_type: str
    cgst_rate: Decimal
    cgst_amount: Decimal
    sgst_rate: Decimal
    sgst_amount: Decimal
    igst_rate: Decimal
    igst_amount: Decimal
    total_gst_amount: Decimal
    final_invoiced_price: Decimal
    hsn_sac_code: str
    item_description: str
    currency: str
    invoice_item_payload: Dict[str, Any]


class ReversePricingResponse(BaseModel):
    desired_mrp: Decimal
    taxable_base_price: Decimal
    total_gst_amount: Decimal
    gst_rate: Decimal
    pricing_mode: str
    target_margin_percentage: Decimal
    allowable_cost_base: Decimal
    expected_net_profit: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal


class PricingCalculatorEngine:
    @staticmethod
    def calculate(req: PricingCalculationRequest) -> PricingCalculationResponse:
        c_direct = Decimal(str(req.direct_cost))
        c_overhead = Decimal(str(req.overhead_cost))
        c_total = c_direct + c_overhead

        margin_pct = Decimal(str(req.margin_percentage))
        mode = req.pricing_mode

        if mode == "markup":
            # Taxable Base = Cost * (1 + Markup / 100)
            multiplier = Decimal("1.00") + (margin_pct / Decimal("100.00"))
            p_taxable = c_total * multiplier
        else:
            # Taxable Base = Cost / (1 - Margin / 100)
            if margin_pct >= Decimal("100.00"):
                raise ValueError("Gross margin cannot equal or exceed 100%.")
            divisor = Decimal("1.00") - (margin_pct / Decimal("100.00"))
            p_taxable = c_total / divisor

        p_taxable = quantize_paise(p_taxable)
        c_total = quantize_paise(c_total)
        net_profit = quantize_paise(p_taxable - c_total)

        effective_margin = Decimal("0.00")
        if p_taxable > Decimal("0.00"):
            effective_margin = quantize_paise((net_profit / p_taxable) * Decimal("100.00"))

        gst_rate = Decimal(str(req.gst_rate))
        is_intra = req.transaction_type == "intra_state"

        if is_intra:
            cgst_rate = gst_rate / Decimal("2.00")
            sgst_rate = cgst_rate
            igst_rate = Decimal("0.00")
            cgst_amount = quantize_paise((p_taxable * cgst_rate) / Decimal("100.00"))
            sgst_amount = quantize_paise((p_taxable * sgst_rate) / Decimal("100.00"))
            igst_amount = Decimal("0.00")
            total_gst = cgst_amount + sgst_amount
        else:
            cgst_rate = Decimal("0.00")
            sgst_rate = Decimal("0.00")
            igst_rate = gst_rate
            cgst_amount = Decimal("0.00")
            sgst_amount = Decimal("0.00")
            igst_amount = quantize_paise((p_taxable * igst_rate) / Decimal("100.00"))
            total_gst = igst_amount

        final_invoiced_price = quantize_paise(p_taxable + total_gst)

        # Structure standard line item for invoice conversion
        hsn_sac = req.hsn_sac_code or "998314"
        desc = req.item_description or "Services / Goods"
        invoice_item = {
            "description": desc,
            "hsn_sac": hsn_sac,
            "quantity": 1,
            "unit_price": float(p_taxable),
            "gst_rate": float(gst_rate),
            "taxable_amount": float(p_taxable),
            "cgst_amount": float(cgst_amount),
            "sgst_amount": float(sgst_amount),
            "igst_amount": float(igst_amount),
            "total_amount": float(final_invoiced_price)
        }

        return PricingCalculationResponse(
            direct_cost=quantize_paise(c_direct),
            overhead_cost=quantize_paise(c_overhead),
            total_cost_base=c_total,
            pricing_mode=mode,
            margin_percentage=quantize_paise(margin_pct),
            taxable_base_price=p_taxable,
            net_profit=net_profit,
            effective_margin_percentage=effective_margin,
            gst_rate=quantize_paise(gst_rate),
            transaction_type=req.transaction_type,
            cgst_rate=quantize_paise(cgst_rate),
            cgst_amount=cgst_amount,
            sgst_rate=quantize_paise(sgst_rate),
            sgst_amount=sgst_amount,
            igst_rate=quantize_paise(igst_rate),
            igst_amount=igst_amount,
            total_gst_amount=total_gst,
            final_invoiced_price=final_invoiced_price,
            hsn_sac_code=hsn_sac,
            item_description=desc,
            currency=req.currency,
            invoice_item_payload=invoice_item
        )

    @staticmethod
    def reverse_calculate(req: ReversePricingRequest) -> ReversePricingResponse:
        mrp = Decimal(str(req.desired_mrp))
        gst_rate = Decimal(str(req.gst_rate))
        target_margin = Decimal(str(req.target_margin_percentage))

        # Base Price = MRP / (1 + GST Rate / 100)
        taxable_base = quantize_paise(mrp / (Decimal("1.00") + (gst_rate / Decimal("100.00"))))
        total_gst = quantize_paise(mrp - taxable_base)

        if req.pricing_mode == "markup":
            # Allowable Cost = Base / (1 + Markup / 100)
            allowable_cost = quantize_paise(taxable_base / (Decimal("1.00") + (target_margin / Decimal("100.00"))))
        else:
            # Allowable Cost = Base * (1 - Margin / 100)
            if target_margin >= Decimal("100.00"):
                raise ValueError("Gross margin cannot equal or exceed 100%.")
            allowable_cost = quantize_paise(taxable_base * (Decimal("1.00") - (target_margin / Decimal("100.00"))))

        net_profit = quantize_paise(taxable_base - allowable_cost)

        is_intra = req.transaction_type == "intra_state"
        if is_intra:
            cgst = quantize_paise(total_gst / Decimal("2.00"))
            sgst = total_gst - cgst
            igst = Decimal("0.00")
        else:
            cgst = Decimal("0.00")
            sgst = Decimal("0.00")
            igst = total_gst

        return ReversePricingResponse(
            desired_mrp=quantize_paise(mrp),
            taxable_base_price=taxable_base,
            total_gst_amount=total_gst,
            gst_rate=quantize_paise(gst_rate),
            pricing_mode=req.pricing_mode,
            target_margin_percentage=quantize_paise(target_margin),
            allowable_cost_base=allowable_cost,
            expected_net_profit=net_profit,
            cgst_amount=cgst,
            sgst_amount=sgst,
            igst_amount=igst
        )
