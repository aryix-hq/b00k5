from decimal import Decimal, ROUND_HALF_EVEN
from datetime import date, datetime
from typing import Dict, Any, List, Optional, Tuple
import hashlib
import json
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload

from app.models.invoice import Invoice, InvoiceItem, Contact
from app.models.tenant import Tenant


def round_flt(val: Any) -> float:
    """Rounds to 2 decimal places using Banker's Rounding and returns float."""
    d = Decimal(str(val or 0.0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    return float(d)


class GSTR1ExportService:
    """
    Official GSTN (Goods and Services Tax Network) GSTR-1 Offline Tool JSON Generator.
    Produces schema-compliant JSON payloads for direct upload to the gst.gov.in portal.
    Covers Tables:
    - 4A, 4B, 4C, 6B, 6C: B2B Invoices
    - 5A, 5B: B2C (Large) Invoices
    - 7: B2C (Others / Small) Invoices
    - 9B: Credit / Debit Notes (Registered)
    - 6A: Exports (EXP)
    - 12: HSN/SAC Summary of Outward Supplies
    - 13: Documents Issued During the Tax Period
    """

    @classmethod
    async def generate_gstr1_json(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        year: int,
        month: int
    ) -> Dict[str, Any]:
        """
        Compiles all outward invoices for the specified calendar month and year
        and returns the official GST offline tool format JSON.
        """
        # Fetch Tenant Profile
        t_stmt = select(Tenant).where(Tenant.id == tenant_id)
        t_res = await session.execute(t_stmt)
        tenant = t_res.scalar_one_or_none()
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found.")

        gstin = (tenant.gstin or "29AABCV1234F1Z5").strip().upper()
        filing_period = f"{month:02d}{year}"

        # Determine start and end dates of the target month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        # Query all invoices issued in the month
        stmt = (
            select(Invoice)
            .options(selectinload(Invoice.contact), selectinload(Invoice.items))
            .where(
                and_(
                    Invoice.tenant_id == tenant_id,
                    Invoice.issue_date >= start_date,
                    Invoice.issue_date < end_date
                )
            )
            .order_by(Invoice.issue_date.asc(), Invoice.invoice_number.asc())
        )
        res = await session.execute(stmt)
        invoices = res.scalars().all()

        b2b_map: Dict[str, List[Dict[str, Any]]] = {}
        b2cl_map: Dict[str, List[Dict[str, Any]]] = {}
        b2cs_map: Dict[Tuple[str, str, float], Dict[str, float]] = {}
        cdnr_list: List[Dict[str, Any]] = []
        exp_list: List[Dict[str, Any]] = []
        hsn_map: Dict[str, Dict[str, Any]] = {}

        total_invoices_count = 0
        cancelled_invoices_count = 0
        min_doc_no = None
        max_doc_no = None

        for inv in invoices:
            doc_no = inv.invoice_number
            if min_doc_no is None or doc_no < min_doc_no:
                min_doc_no = doc_no
            if max_doc_no is None or doc_no > max_doc_no:
                max_doc_no = doc_no

            total_invoices_count += 1
            if inv.status == "cancelled":
                cancelled_invoices_count += 1
                continue

            contact = inv.contact
            cust_gstin = (contact.gstin or "").strip().upper() if contact else ""
            pos = str(inv.place_of_supply or (contact.state_code if contact else "29")).zfill(2)
            inv_date_str = inv.issue_date.strftime("%d-%m-%Y") if isinstance(inv.issue_date, (date, datetime)) else str(inv.issue_date)

            is_registered = bool(cust_gstin and len(cust_gstin) == 15 and cust_gstin != "URP")

            # Group items by GST rate
            rate_groups: Dict[float, Dict[str, Decimal]] = {}
            for item in inv.items:
                r = float(item.gst_rate_percent)
                if r not in rate_groups:
                    rate_groups[r] = {
                        "txval": Decimal("0.00"),
                        "iamt": Decimal("0.00"),
                        "camt": Decimal("0.00"),
                        "samt": Decimal("0.00"),
                        "csamt": Decimal("0.00"),
                    }
                rate_groups[r]["txval"] += Decimal(str(item.taxable_value))
                rate_groups[r]["iamt"] += Decimal(str(item.igst_amount))
                rate_groups[r]["camt"] += Decimal(str(item.cgst_amount))
                rate_groups[r]["samt"] += Decimal(str(item.sgst_amount))

                # HSN Summary aggregation
                hsn_code = (item.hsn_sac_code or "998313").strip()
                if hsn_code not in hsn_map:
                    hsn_map[hsn_code] = {
                        "desc": item.item_description or "Software/Consulting",
                        "uqc": "OTH",
                        "qty": Decimal("0.00"),
                        "val": Decimal("0.00"),
                        "txval": Decimal("0.00"),
                        "iamt": Decimal("0.00"),
                        "camt": Decimal("0.00"),
                        "samt": Decimal("0.00"),
                        "csamt": Decimal("0.00"),
                    }
                hsn_map[hsn_code]["qty"] += Decimal(str(item.quantity or 1.0))
                hsn_map[hsn_code]["val"] += Decimal(str(item.total_amount))
                hsn_map[hsn_code]["txval"] += Decimal(str(item.taxable_value))
                hsn_map[hsn_code]["iamt"] += Decimal(str(item.igst_amount))
                hsn_map[hsn_code]["camt"] += Decimal(str(item.cgst_amount))
                hsn_map[hsn_code]["samt"] += Decimal(str(item.sgst_amount))

            # Table 9B: Credit / Debit Notes
            if inv.type in ("credit_note", "debit_note"):
                cdn_entry = {
                    "ctin": cust_gstin if is_registered else "URP",
                    "cflag": "N",
                    "nt": [
                        {
                            "ntty": "C" if inv.type == "credit_note" else "D",
                            "nt_num": inv.invoice_number,
                            "nt_dt": inv_date_str,
                            "val": round_flt(inv.grand_total),
                            "pos": pos,
                            "rchrg": "N",
                            "inv_typ": "R",
                            "itms": [
                                {
                                    "num": idx,
                                    "itm_det": {
                                        "rt": r,
                                        "txval": round_flt(vals["txval"]),
                                        "iamt": round_flt(vals["iamt"]),
                                        "camt": round_flt(vals["camt"]),
                                        "samt": round_flt(vals["samt"]),
                                        "csamt": round_flt(vals["csamt"]),
                                    }
                                }
                                for idx, (r, vals) in enumerate(rate_groups.items(), start=1)
                            ]
                        }
                    ]
                }
                cdnr_list.append(cdn_entry)
                continue

            # Table 6A: Exports
            if pos == "96" or (contact and getattr(contact, "is_export", False)):
                exp_entry = {
                    "exp_typ": "WOPAY", # Without Payment of Tax
                    "inv": [
                        {
                            "inum": inv.invoice_number,
                            "idt": inv_date_str,
                            "val": round_flt(inv.grand_total),
                            "sbnum": "",
                            "sbdt": "",
                            "itms": [
                                {
                                    "num": idx,
                                    "itm_det": {
                                        "txval": round_flt(vals["txval"]),
                                        "rt": r,
                                        "iamt": round_flt(vals["iamt"]),
                                        "csamt": round_flt(vals["csamt"])
                                    }
                                }
                                for idx, (r, vals) in enumerate(rate_groups.items(), start=1)
                            ]
                        }
                    ]
                }
                exp_list.append(exp_entry)
                continue

            # Table 4: B2B Invoices
            if is_registered:
                inv_obj = {
                    "inum": inv.invoice_number,
                    "idt": inv_date_str,
                    "val": round_flt(inv.grand_total),
                    "pos": pos,
                    "rchrg": "N",
                    "inv_typ": "R",
                    "itms": [
                        {
                            "num": idx,
                            "itm_det": {
                                "rt": r,
                                "txval": round_flt(vals["txval"]),
                                "iamt": round_flt(vals["iamt"]),
                                "camt": round_flt(vals["camt"]),
                                "samt": round_flt(vals["samt"]),
                                "csamt": round_flt(vals["csamt"]),
                            }
                        }
                        for idx, (r, vals) in enumerate(rate_groups.items(), start=1)
                    ]
                }
                if cust_gstin not in b2b_map:
                    b2b_map[cust_gstin] = []
                b2b_map[cust_gstin].append(inv_obj)

            # Table 5: B2C Large (Unregistered + Interstate + Invoice Value > 2.5 Lakhs)
            elif inv.is_interstate and inv.grand_total > Decimal("250000.00"):
                inv_obj = {
                    "inum": inv.invoice_number,
                    "idt": inv_date_str,
                    "val": round_flt(inv.grand_total),
                    "pos": pos,
                    "itms": [
                        {
                            "num": idx,
                            "itm_det": {
                                "rt": r,
                                "txval": round_flt(vals["txval"]),
                                "iamt": round_flt(vals["iamt"]),
                                "csamt": round_flt(vals["csamt"]),
                            }
                        }
                        for idx, (r, vals) in enumerate(rate_groups.items(), start=1)
                    ]
                }
                if pos not in b2cl_map:
                    b2cl_map[pos] = []
                b2cl_map[pos].append(inv_obj)

            # Table 7: B2C Small (Other Unregistered)
            else:
                sply_ty = "INTER" if inv.is_interstate else "INTRA"
                for r, vals in rate_groups.items():
                    k = (sply_ty, pos, r)
                    if k not in b2cs_map:
                        b2cs_map[k] = {
                            "txval": Decimal("0.00"),
                            "iamt": Decimal("0.00"),
                            "camt": Decimal("0.00"),
                            "samt": Decimal("0.00"),
                            "csamt": Decimal("0.00"),
                        }
                    b2cs_map[k]["txval"] += vals["txval"]
                    b2cs_map[k]["iamt"] += vals["iamt"]
                    b2cs_map[k]["camt"] += vals["camt"]
                    b2cs_map[k]["samt"] += vals["samt"]
                    b2cs_map[k]["csamt"] += vals["csamt"]

        # Compile b2b array
        b2b_list = [
            {"ctin": ctin, "cflag": "N", "inv": inv_list}
            for ctin, inv_list in b2b_map.items()
        ]

        # Compile b2cl array
        b2cl_list = [
            {"pos": pos, "inv": inv_list}
            for pos, inv_list in b2cl_map.items()
        ]

        # Compile b2cs array
        b2cs_list = [
            {
                "sply_ty": k[0],
                "pos": k[1],
                "typ": "OE",
                "rt": k[2],
                "txval": round_flt(v["txval"]),
                "iamt": round_flt(v["iamt"]),
                "camt": round_flt(v["camt"]),
                "samt": round_flt(v["samt"]),
                "csamt": round_flt(v["csamt"]),
            }
            for k, v in b2cs_map.items()
        ]

        # Compile HSN Summary Table 12
        hsn_list = [
            {
                "num": idx,
                "hsn_sc": hsn,
                "desc": data["desc"],
                "uqc": data["uqc"],
                "qty": round_flt(data["qty"]),
                "val": round_flt(data["val"]),
                "txval": round_flt(data["txval"]),
                "iamt": round_flt(data["iamt"]),
                "camt": round_flt(data["camt"]),
                "samt": round_flt(data["samt"]),
                "csamt": round_flt(data["csamt"]),
            }
            for idx, (hsn, data) in enumerate(hsn_map.items(), start=1)
        ]

        # Compile Document Issue Table 13
        net_issued = total_invoices_count - cancelled_invoices_count
        doc_details = []
        if total_invoices_count > 0:
            doc_details.append(
                {
                    "doc_num": 1,
                    "doc_typ": "Invoices for outward supply",
                    "docs": [
                        {
                            "num": 1,
                            "from": min_doc_no or "INV-001",
                            "to": max_doc_no or "INV-001",
                            "totnum": total_invoices_count,
                            "canc": cancelled_invoices_count,
                            "net_issue": net_issued
                        }
                    ]
                }
            )

        payload = {
            "gstin": gstin,
            "fp": filing_period,
            "gt": 0.0,
            "cur_gt": 0.0,
            "version": "GSTR1_1.0",
            "hash": hashlib.sha256(f"{gstin}{filing_period}{total_invoices_count}".encode("utf-8")).hexdigest(),
            "b2b": b2b_list,
            "b2cl": b2cl_list,
            "b2cs": b2cs_list,
            "cdnr": cdnr_list,
            "exp": exp_list,
            "hsn": {"data": hsn_list},
            "doc_issue": {"doc_det": doc_details}
        }
        return payload
