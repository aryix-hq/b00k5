import uuid
from typing import Optional, List, Any, Dict
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.iam import require_any_employee, require_ca_or_owner, IAMContext
from app.schemas.mca_registers import (
    MemberCreate,
    MemberResponse,
    LoanGuaranteeCreate,
    LoanGuaranteeResponse,
    ContractInterestedDirectorCreate,
    ContractInterestedDirectorResponse,
    DirectorDisclosureCreate,
    DirectorDisclosureResponse,
    ShareCertificateCreate,
    ShareCertificateResponse
)
from app.services.mca_registers_service import MCARegistersService

router = APIRouter()


# --- 1. Form MGT-1: Register of Members (Sec 88) ---
@router.post("/members", response_model=MemberResponse)
async def register_member(
    payload: MemberCreate,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Registers a member / shareholder in the statutory Form MGT-1 Register of Members u/s 88.
    """
    try:
        member = await MCARegistersService.register_member(
            session=db,
            tenant_id=ctx.tenant.id,
            folio_number=payload.folio_number,
            member_name=payload.member_name,
            number_of_shares=payload.number_of_shares,
            distinctive_from=payload.distinctive_from,
            distinctive_to=payload.distinctive_to,
            nominal_value_per_share=payload.nominal_value_per_share,
            amount_paid_per_share=payload.amount_paid_per_share,
            date_of_becoming_member=payload.date_of_becoming_member,
            father_or_spouse_name=payload.father_or_spouse_name,
            pan=payload.pan,
            email=payload.email,
            address=payload.address,
            certificate_number=payload.certificate_number
        )
        await db.commit()
        return MemberResponse.model_validate(member)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/members", response_model=List[MemberResponse])
async def list_members(
    ctx: IAMContext = Depends(require_any_employee),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists all shareholders registered in Form MGT-1.
    """
    members = await MCARegistersService.list_members(session=db, tenant_id=ctx.tenant.id)
    return [MemberResponse.model_validate(m) for m in members]


# --- 2. Form MBP-2: Register of Loans & Guarantees (Sec 186) ---
@router.post("/loans", response_model=LoanGuaranteeResponse)
async def record_loan_guarantee(
    payload: LoanGuaranteeCreate,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Records an entry in Form MBP-2 Register of Loans, Guarantees and Securities u/s 186.
    """
    try:
        entry = await MCARegistersService.record_loan_guarantee(
            session=db,
            tenant_id=ctx.tenant.id,
            transaction_type=payload.transaction_type,
            body_corporate_name=payload.body_corporate_name,
            amount=payload.amount,
            board_resolution_date=payload.board_resolution_date,
            interest_rate_pct=payload.interest_rate_pct,
            tenure_months=payload.tenure_months,
            cin_or_pan=payload.cin_or_pan,
            special_resolution_date=payload.special_resolution_date,
            notes=payload.notes
        )
        await db.commit()
        return LoanGuaranteeResponse.model_validate(entry)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/loans", response_model=List[LoanGuaranteeResponse])
async def list_loans_guarantees(
    ctx: IAMContext = Depends(require_any_employee),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists entries in Form MBP-2 Register of Loans & Guarantees.
    """
    loans = await MCARegistersService.list_loans_guarantees(session=db, tenant_id=ctx.tenant.id)
    return [LoanGuaranteeResponse.model_validate(l) for l in loans]


# --- 3. Form MBP-4: Register of Contracts with Interested Directors (Sec 189) ---
@router.post("/contracts", response_model=ContractInterestedDirectorResponse)
async def record_contract(
    payload: ContractInterestedDirectorCreate,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Records a contract or arrangement in Form MBP-4 Register of Contracts with Interested Directors u/s 189.
    """
    try:
        entry = await MCARegistersService.record_contract(
            session=db,
            tenant_id=ctx.tenant.id,
            contract_date=payload.contract_date,
            party_name=payload.party_name,
            nature_of_contract=payload.nature_of_contract,
            director_name=payload.director_name,
            nature_of_interest=payload.nature_of_interest,
            board_meeting_date=payload.board_meeting_date,
            contract_value=payload.contract_value,
            director_din=payload.director_din,
            voting_status=payload.voting_status
        )
        await db.commit()
        return ContractInterestedDirectorResponse.model_validate(entry)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/contracts", response_model=List[ContractInterestedDirectorResponse])
async def list_contracts(
    ctx: IAMContext = Depends(require_any_employee),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists entries in Form MBP-4 Register of Contracts.
    """
    contracts = await MCARegistersService.list_contracts(session=db, tenant_id=ctx.tenant.id)
    return [ContractInterestedDirectorResponse.model_validate(c) for c in contracts]


# --- 4. Director Annual Disclosures (Form MBP-1 & Form DIR-8) ---
@router.post("/disclosures", response_model=DirectorDisclosureResponse)
async def record_director_disclosure(
    payload: DirectorDisclosureCreate,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Records annual statutory director disclosure: Form MBP-1 (Interest u/s 184) or Form DIR-8 (Non-Disqualification u/s 164).
    """
    try:
        entry = await MCARegistersService.record_director_disclosure(
            session=db,
            tenant_id=ctx.tenant.id,
            fiscal_year=payload.fiscal_year,
            form_type=payload.form_type,
            director_name=payload.director_name,
            director_din=payload.director_din,
            disclosure_payload=payload.disclosure_payload,
            filing_date=payload.filing_date,
            is_digitally_signed=payload.is_digitally_signed,
            signed_hash=payload.signed_hash
        )
        await db.commit()
        return DirectorDisclosureResponse.model_validate(entry)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/disclosures", response_model=List[DirectorDisclosureResponse])
async def list_director_disclosures(
    fiscal_year: Optional[str] = Query(None),
    form_type: Optional[str] = Query(None, description="MBP_1 or DIR_8"),
    ctx: IAMContext = Depends(require_any_employee),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists director disclosures (Form MBP-1 and Form DIR-8).
    """
    disclosures = await MCARegistersService.list_director_disclosures(
        session=db,
        tenant_id=ctx.tenant.id,
        fiscal_year=fiscal_year,
        form_type=form_type
    )
    return [DirectorDisclosureResponse.model_validate(d) for d in disclosures]


# --- 5. Form SH-1: Share Certificate Generation ---
@router.post("/share-certificates", response_model=ShareCertificateResponse)
async def issue_share_certificate(
    payload: ShareCertificateCreate,
    ctx: IAMContext = Depends(require_ca_or_owner),
    db: AsyncSession = Depends(get_db)
):
    """
    Issues a Form SH-1 Share Certificate pursuant to Section 46 of Companies Act, 2013 and Rule 5.
    """
    try:
        cert = await MCARegistersService.issue_share_certificate(
            session=db,
            tenant_id=ctx.tenant.id,
            member_id=payload.member_id,
            certificate_number=payload.certificate_number,
            number_of_shares=payload.number_of_shares,
            distinctive_from=payload.distinctive_from,
            distinctive_to=payload.distinctive_to,
            face_value=payload.face_value,
            issue_date=payload.issue_date,
            signatory_director_1=payload.signatory_director_1,
            signatory_director_2=payload.signatory_director_2,
            signatory_secretary_or_authorized=payload.signatory_secretary_or_authorized
        )
        await db.commit()
        return ShareCertificateResponse.model_validate(cert)
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/share-certificates", response_model=List[ShareCertificateResponse])
async def list_share_certificates(
    ctx: IAMContext = Depends(require_any_employee),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists issued Form SH-1 Share Certificates.
    """
    certs = await MCARegistersService.list_share_certificates(session=db, tenant_id=ctx.tenant.id)
    return [ShareCertificateResponse.model_validate(c) for c in certs]

