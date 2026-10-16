import uuid
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.models.mca_registers import (
    StatutoryMember,
    StatutoryLoanGuarantee,
    StatutoryContractInterestedDirector,
    DirectorAnnualDisclosure,
    ShareCertificate
)

class MCARegistersService:
    """
    Statutory MCA Registers and Director Disclosures Service:
    - Form MGT-1: Register of Members (Sec 88)
    - Form MBP-2: Register of Loans, Guarantees & Securities (Sec 186)
    - Form MBP-4: Register of Contracts with Interested Directors (Sec 189)
    - Form MBP-1: Director Notice of Interest (Sec 184)
    - Form DIR-8: Director Non-Disqualification Intimation (Sec 164(2))
    - Form SH-1: Share Certificate Generation (Sec 46 & Rule 5)
    """

    # --- 1. Form MGT-1: Register of Members ---
    @classmethod
    async def register_member(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        folio_number: str,
        member_name: str,
        number_of_shares: Decimal,
        distinctive_from: int,
        distinctive_to: int,
        nominal_value_per_share: Decimal = Decimal("10.00"),
        amount_paid_per_share: Decimal = Decimal("10.00"),
        date_of_becoming_member: Optional[date] = None,
        father_or_spouse_name: Optional[str] = None,
        pan: Optional[str] = None,
        email: Optional[str] = None,
        address: Optional[str] = None,
        certificate_number: Optional[str] = None
    ) -> StatutoryMember:
        if distinctive_to < distinctive_from:
            raise ValueError(f"Invalid distinctive numbers: distinctive_to ({distinctive_to}) cannot be less than distinctive_from ({distinctive_from}).")

        calculated_count = Decimal(distinctive_to - distinctive_from + 1)
        if number_of_shares != calculated_count:
            raise ValueError(f"Share count mismatch: number_of_shares ({number_of_shares}) does not match distinctive range ({calculated_count}).")

        existing_q = select(StatutoryMember).where(
            StatutoryMember.tenant_id == tenant_id,
            StatutoryMember.folio_number == folio_number.strip()
        )
        existing = (await session.execute(existing_q)).scalar_one_or_none()
        if existing:
            raise ValueError(f"Member with Folio Number '{folio_number}' already exists for this entity.")

        member = StatutoryMember(
            tenant_id=tenant_id,
            folio_number=folio_number.strip(),
            member_name=member_name.strip(),
            father_or_spouse_name=father_or_spouse_name.strip() if father_or_spouse_name else None,
            pan=pan.strip().upper() if pan else None,
            email=email.strip().lower() if email else None,
            address=address.strip() if address else None,
            date_of_becoming_member=date_of_becoming_member or date.today(),
            number_of_shares=number_of_shares,
            distinctive_from=distinctive_from,
            distinctive_to=distinctive_to,
            nominal_value_per_share=nominal_value_per_share,
            amount_paid_per_share=amount_paid_per_share,
            certificate_number=certificate_number.strip() if certificate_number else None,
            status="ACTIVE"
        )
        session.add(member)
        await session.flush()
        return member

    @classmethod
    async def list_members(cls, session: AsyncSession, tenant_id: uuid.UUID) -> List[StatutoryMember]:
        q = (
            select(StatutoryMember)
            .where(StatutoryMember.tenant_id == tenant_id)
            .order_by(StatutoryMember.distinctive_from)
        )
        res = await session.execute(q)
        return list(res.scalars().all())

    # --- 2. Form MBP-2: Register of Loans & Guarantees ---
    @classmethod
    async def record_loan_guarantee(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        transaction_type: str,
        body_corporate_name: str,
        amount: Decimal,
        board_resolution_date: date,
        interest_rate_pct: Optional[Decimal] = None,
        tenure_months: Optional[int] = None,
        cin_or_pan: Optional[str] = None,
        special_resolution_date: Optional[date] = None,
        notes: Optional[str] = None
    ) -> StatutoryLoanGuarantee:
        # Enforce Section 186 statutory checks
        if amount <= Decimal("0.00"):
            raise ValueError("Amount for loan, guarantee, or investment must be greater than zero.")

        # If interest rate is lower than RBI prevailing repo yield for loans given
        if transaction_type == "LOAN_GIVEN" and interest_rate_pct is not None and interest_rate_pct < Decimal("5.00"):
            raise ValueError("Section 186(7) Statutory Guard: No loan shall be given at a rate of interest lower than the prevailing yield of 1-year/3-year/5-year/10-year Government Security.")

        entry = StatutoryLoanGuarantee(
            tenant_id=tenant_id,
            transaction_type=transaction_type,
            body_corporate_name=body_corporate_name.strip(),
            cin_or_pan=cin_or_pan.strip().upper() if cin_or_pan else None,
            amount=amount,
            interest_rate_pct=interest_rate_pct,
            tenure_months=tenure_months,
            board_resolution_date=board_resolution_date,
            special_resolution_date=special_resolution_date,
            status="ACTIVE",
            notes=notes
        )
        session.add(entry)
        await session.flush()
        return entry

    @classmethod
    async def list_loans_guarantees(cls, session: AsyncSession, tenant_id: uuid.UUID) -> List[StatutoryLoanGuarantee]:
        q = (
            select(StatutoryLoanGuarantee)
            .where(StatutoryLoanGuarantee.tenant_id == tenant_id)
            .order_by(desc(StatutoryLoanGuarantee.board_resolution_date))
        )
        res = await session.execute(q)
        return list(res.scalars().all())

    # --- 3. Form MBP-4: Register of Contracts with Interested Directors ---
    @classmethod
    async def record_contract(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        contract_date: date,
        party_name: str,
        nature_of_contract: str,
        director_name: str,
        nature_of_interest: str,
        board_meeting_date: date,
        contract_value: Optional[Decimal] = None,
        director_din: Optional[str] = None,
        voting_status: str = "ABSTAINED"
    ) -> StatutoryContractInterestedDirector:
        entry = StatutoryContractInterestedDirector(
            tenant_id=tenant_id,
            contract_date=contract_date,
            party_name=party_name.strip(),
            nature_of_contract=nature_of_contract.strip(),
            contract_value=contract_value,
            director_name=director_name.strip(),
            director_din=director_din.strip() if director_din else None,
            nature_of_interest=nature_of_interest.strip(),
            board_meeting_date=board_meeting_date,
            voting_status=voting_status
        )
        session.add(entry)
        await session.flush()
        return entry

    @classmethod
    async def list_contracts(cls, session: AsyncSession, tenant_id: uuid.UUID) -> List[StatutoryContractInterestedDirector]:
        q = (
            select(StatutoryContractInterestedDirector)
            .where(StatutoryContractInterestedDirector.tenant_id == tenant_id)
            .order_by(desc(StatutoryContractInterestedDirector.contract_date))
        )
        res = await session.execute(q)
        return list(res.scalars().all())

    # --- 4. Director Annual Disclosures (MBP-1 & DIR-8) ---
    @classmethod
    async def record_director_disclosure(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        fiscal_year: str,
        form_type: str,
        director_name: str,
        director_din: str,
        disclosure_payload: Dict[str, Any],
        filing_date: Optional[date] = None,
        is_digitally_signed: bool = False,
        signed_hash: Optional[str] = None
    ) -> DirectorAnnualDisclosure:
        clean_din = director_din.strip()
        if len(clean_din) != 8 or not clean_din.isdigit():
            raise ValueError(f"Invalid Director Identification Number (DIN): '{director_din}'. Must be an 8-digit numeric string.")

        if form_type not in ("MBP_1", "DIR_8"):
            raise ValueError(f"Invalid form_type: '{form_type}'. Must be 'MBP_1' or 'DIR_8'.")

        disclosure = DirectorAnnualDisclosure(
            tenant_id=tenant_id,
            fiscal_year=fiscal_year.strip(),
            form_type=form_type,
            director_name=director_name.strip(),
            director_din=clean_din,
            filing_date=filing_date or date.today(),
            disclosure_payload=disclosure_payload,
            is_digitally_signed=is_digitally_signed,
            signed_hash=signed_hash
        )
        session.add(disclosure)
        await session.flush()
        return disclosure

    @classmethod
    async def list_director_disclosures(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        fiscal_year: Optional[str] = None,
        form_type: Optional[str] = None
    ) -> List[DirectorAnnualDisclosure]:
        q = select(DirectorAnnualDisclosure).where(DirectorAnnualDisclosure.tenant_id == tenant_id)
        if fiscal_year:
            q = q.where(DirectorAnnualDisclosure.fiscal_year == fiscal_year)
        if form_type:
            q = q.where(DirectorAnnualDisclosure.form_type == form_type)
        q = q.order_by(desc(DirectorAnnualDisclosure.filing_date))
        res = await session.execute(q)
        return list(res.scalars().all())

    # --- 5. Form SH-1: Share Certificate Generation ---
    @classmethod
    async def issue_share_certificate(
        cls,
        session: AsyncSession,
        tenant_id: uuid.UUID,
        member_id: uuid.UUID,
        certificate_number: str,
        number_of_shares: int,
        distinctive_from: int,
        distinctive_to: int,
        face_value: Decimal = Decimal("10.00"),
        issue_date: Optional[date] = None,
        signatory_director_1: Optional[str] = None,
        signatory_director_2: Optional[str] = None,
        signatory_secretary_or_authorized: Optional[str] = None
    ) -> ShareCertificate:
        # Validate member exists
        member_q = select(StatutoryMember).where(
            StatutoryMember.id == member_id,
            StatutoryMember.tenant_id == tenant_id
        )
        member = (await session.execute(member_q)).scalar_one_or_none()
        if not member:
            raise ValueError(f"Member {member_id} not found in statutory register.")

        if distinctive_to < distinctive_from:
            raise ValueError("distinctive_to cannot be less than distinctive_from.")

        cert = ShareCertificate(
            tenant_id=tenant_id,
            certificate_number=certificate_number.strip(),
            member_id=member_id,
            number_of_shares=number_of_shares,
            distinctive_from=distinctive_from,
            distinctive_to=distinctive_to,
            face_value=face_value,
            issue_date=issue_date or date.today(),
            signatory_director_1=signatory_director_1.strip() if signatory_director_1 else None,
            signatory_director_2=signatory_director_2.strip() if signatory_director_2 else None,
            signatory_secretary_or_authorized=signatory_secretary_or_authorized.strip() if signatory_secretary_or_authorized else None,
            status="ISSUED"
        )
        session.add(cert)
        # Update member certificate_number
        member.certificate_number = certificate_number.strip()
        await session.flush()
        return cert

    @classmethod
    async def list_share_certificates(cls, session: AsyncSession, tenant_id: uuid.UUID) -> List[ShareCertificate]:
        q = (
            select(ShareCertificate)
            .where(ShareCertificate.tenant_id == tenant_id)
            .order_by(desc(ShareCertificate.issue_date))
        )
        res = await session.execute(q)
        return list(res.scalars().all())

    # --- 6. Registers Summary Dashboard ---
    @classmethod
    async def get_registers_summary(cls, session: AsyncSession, tenant_id: uuid.UUID) -> Dict[str, Any]:
        members = await cls.list_members(session, tenant_id)
        loans = await cls.list_loans_guarantees(session, tenant_id)
        contracts = await cls.list_contracts(session, tenant_id)
        disclosures = await cls.list_director_disclosures(session, tenant_id)
        certificates = await cls.list_share_certificates(session, tenant_id)

        total_shares = sum(m.number_of_shares for m in members)
        active_loans_exposure = sum(l.amount for l in loans if l.status == "ACTIVE")

        return {
            "total_members": len(members),
            "total_equity_shares": float(total_shares),
            "total_loans_guarantees": len(loans),
            "active_loans_exposure": float(active_loans_exposure),
            "total_contracts_interested_directors": len(contracts),
            "total_disclosures": len(disclosures),
            "total_share_certificates": len(certificates),
        }
