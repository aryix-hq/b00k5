'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Receipt, User, Building2, UploadCloud, AlertCircle, CheckCircle2, ShieldCheck, FileCheck, IndianRupee, Calendar } from 'lucide-react';

export const STANDARD_EXPENSE_CATEGORIES = [
  '[4010] Cloud Infrastructure & Hosting (AWS/GCP)',
  '[4020] Software Licenses & SaaS Subscriptions',
  '[4030] Payment Gateway & Bank Wire Charges',
  '[4040] Legal, MCA Compliance & Professional Fees',
  '[4050] Rent & Office Utilities',
  '[4060] Office Equipment, Computers & IT Hardware',
  '[4070] Travel, Lodging & Local Conveyance',
  '[4080] Food & Staff Welfare Expenses',
  '[4090] Advertising & Digital Marketing',
  '[4100] Books, Periodicals & Research',
  '[4110] Director Remuneration & Board Sitting Fees',
  '[4120] Repairs & Maintenance',
  '[4130] Communication & Internet Charges',
  '[4140] Auditor Retainer & Certification Fees',
  '[4150] Printing & Office Stationery',
  '[4160] Marketplace, E-Commerce & Platform Fees',
  '[4199] Miscellaneous Operating Expenses'
];

export function ExpenseForm() {
  const router = useRouter();

  // Form Fields
  const [paymentSource, setPaymentSource] = useState<'company_bank' | 'personal_account'>('company_bank');
  const [directors, setDirectors] = useState<Array<{ name: string; din: string; designation: string }>>([]);
  const [payeeDirector, setPayeeDirector] = useState<string>('');
  const [merchantName, setMerchantName] = useState<string>('');
  const [totalAmount, setTotalAmount] = useState<string>('');
  const [expenseDate, setExpenseDate] = useState<string>(() => new Date().toISOString().split('T')[0]);
  const [category, setCategory] = useState<string>('[4010] Cloud Infrastructure & Hosting (AWS/GCP)');
  const [isCustomCategory, setIsCustomCategory] = useState<boolean>(false);
  const [paymentMode, setPaymentMode] = useState<string>('online');

  // Year Book & Date Validation state
  const [yearBookInfo, setYearBookInfo] = useState<{ financial_year: string; label: string; warning?: string } | null>(null);

  // Mandatory Company Document Gate
  const [isMandatoryDocsLocked, setIsMandatoryDocsLocked] = useState<boolean>(false);

  // Statutory & ITC verification state
  const [receiptFileName, setReceiptFileName] = useState<string>('');
  const [receiptS3Key, setReceiptS3Key] = useState<string>('');
  const [receiptSha256, setReceiptSha256] = useState<string>('');
  const [extractedGstin, setExtractedGstin] = useState<string>('');
  const [companyGstin, setCompanyGstin] = useState<string>('');
  const [itcEligible, setItcEligible] = useState<boolean>(false);
  const [itcMessage, setItcMessage] = useState<string>('Upload a vendor tax invoice or enter supplier GSTIN to evaluate Input Tax Credit.');
  const [sec40aWarning, setSec40aWarning] = useState<string | null>(null);

  // Statutory Self-Voucher (Expense Without Bill) state
  const [isUnvouchedSelfVoucher, setIsUnvouchedSelfVoucher] = useState<boolean>(false);

  // Live OCR & Deduplication state
  const [scanning, setScanning] = useState<boolean>(false);
  const [duplicateWarning, setDuplicateWarning] = useState<string | null>(null);
  const [confirmDuplicate, setConfirmDuplicate] = useState<boolean>(false);
  const [passwordModalOpen, setPasswordModalOpen] = useState<boolean>(false);
  const [pendingBillFile, setPendingBillFile] = useState<File | null>(null);
  const [pdfPassword, setPdfPassword] = useState<string>('');
  const [passwordError, setPasswordError] = useState<string>('');

  const [loading, setLoading] = useState<boolean>(false);
  const [success, setSuccess] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Phase 10: TDS Withholding state
  const [withholdTds, setWithholdTds] = useState<boolean>(false);
  const [tdsSection, setTdsSection] = useState<string>('194J');
  const [vendorPan, setVendorPan] = useState<string>('');
  const [tdsRate, setTdsRate] = useState<string>('10.0');
  const [tdsAmount, setTdsAmount] = useState<number>(0);
  const [netPayable, setNetPayable] = useState<number>(0);

  // Resolve verified company GSTIN and Director Roster from backend
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const g = localStorage.getItem('b00k5_extracted_gstin') || localStorage.getItem('b00k5_gstin') || '';
      if (g && !g.startsWith('29AABCA')) {
        const cleanG = g.trim().toUpperCase();
        setCompanyGstin(cleanG);
      }

      const token = localStorage.getItem('b00k5_token');
      const tenantId = localStorage.getItem('b00k5_tenant_id');
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/compliance/directors`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(data => {
          if (data && Array.isArray(data.directors) && data.directors.length > 0) {
            setDirectors(data.directors);
            setPayeeDirector(prev => prev || data.directors[0].name);
          }
        })
        .catch(() => {});

      // Check Mandatory Document Gate Status
      fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/vault/statutory-profile`, { headers })
        .then(r => r.ok ? r.json() : null)
        .then(prof => {
          if (prof) {
            const statusVal = prof.onboarding_status;
            const coiOk = Boolean(prof.coi_verified);
            const panOk = Boolean(prof.pan_verified);
            if (statusVal === 'PENDING_DOCUMENTS' && !(coiOk && panOk)) {
              setIsMandatoryDocsLocked(true);
            } else {
              setIsMandatoryDocsLocked(false);
            }
          }
        })
        .catch(() => {});
    }
  }, []);

  // Evaluate Section 40A(3) and GST ITC eligibility dynamically
  useEffect(() => {
    const amt = parseFloat(totalAmount) || 0;

    // 1. Cash Disallowance Check
    if (paymentMode === 'cash' && amt > 10000) {
      setSec40aWarning('Disallowed under Section 40A(3) of the Income Tax Act. Cash payment exceeds statutory limit of ₹10,000.');
    } else {
      setSec40aWarning(null);
    }

    // 2. GST ITC Check
    if (isUnvouchedSelfVoucher) {
      setItcEligible(false);
      setItcMessage('No ITC Claimable: Unvouched expense / Internal self-voucher (Sec 16(2) CGST Act). Full gross booked to Expense.');
    } else if (companyGstin && extractedGstin && extractedGstin.trim().toUpperCase() === companyGstin) {
      const igstPart = Math.round((amt - (amt / 1.18)) * 100) / 100;
      setItcEligible(true);
      setItcMessage(`Eligible: ₹${igstPart.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} IGST Input Credit Claimable`);
    } else if (!companyGstin) {
      setItcEligible(false);
      setItcMessage('Ineligible for ITC: No verified company GSTIN certificate on record.');
    } else {
      setItcEligible(false);
      setItcMessage('Ineligible for ITC: Company GSTIN missing on supplier receipt. Full gross booked to Expense.');
    }
  }, [totalAmount, paymentMode, extractedGstin, companyGstin, isUnvouchedSelfVoucher]);

  // Phase 10: Automatic statutory TDS calculation
  useEffect(() => {
    const amt = parseFloat(totalAmount) || 0;
    if (!withholdTds || amt <= 0) {
      setTdsAmount(0);
      setNetPayable(amt);
      return;
    }

    let defaultRate = 10.0;
    const cleanPan = vendorPan.trim().toUpperCase();
    const isPanValid = /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/.test(cleanPan);

    if (cleanPan && !isPanValid) {
      defaultRate = 20.0; // Section 206AA penal rate
    } else if (tdsSection === '194C') {
      const isIndivOrHuf = isPanValid && (cleanPan[3] === 'P' || cleanPan[3] === 'H');
      defaultRate = isIndivOrHuf ? 1.0 : 2.0;
    } else if (tdsSection === '194J') {
      defaultRate = 10.0;
    } else if (tdsSection === '194I') {
      defaultRate = 10.0;
    } else if (tdsSection === '194Q') {
      defaultRate = 0.1;
    }

    setTdsRate(defaultRate.toString());
    const rateVal = defaultRate;
    const calcTds = Math.round(amt * (rateVal / 100) * 100) / 100;
    setTdsAmount(calcTds);
    setNetPayable(Math.round((amt - calcTds) * 100) / 100);
  }, [totalAmount, withholdTds, tdsSection, vendorPan]);

  const doScanBill = async (file: File, pwd?: string) => {
    setScanning(true);
    setErrorMsg(null);
    setDuplicateWarning(null);
    setPasswordError('');

    const fd = new FormData();
    fd.append('file', file);
    if (pwd) fd.append('password', pwd);

    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = typeof window !== 'undefined' ? localStorage.getItem('b00k5_tenant_id') : null;

      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/expenses/scan-bill`, {
        method: 'POST',
        headers,
        body: fd
      });

      const data = await res.json();

      if (res.status === 422 && (data?.detail?.needs_password || data?.needs_password)) {
        setPendingBillFile(file);
        setPasswordModalOpen(true);
        setPasswordError(data?.detail?.message || 'Password required to decrypt bill PDF.');
        setScanning(false);
        return;
      }

      if (res.ok && data.success) {
        setPasswordModalOpen(false);
        setPdfPassword('');
        setPendingBillFile(null);
        setReceiptFileName(file.name);
        if (data.receipt_s3_key) setReceiptS3Key(data.receipt_s3_key);
        if (data.receipt_sha256) setReceiptSha256(data.receipt_sha256);

        if (data.merchant_name) setMerchantName(data.merchant_name);
        if (data.total_amount) setTotalAmount(data.total_amount.toString());
        if (data.expense_date) setExpenseDate(data.expense_date);
        if (data.category) setCategory(data.category);
        if (data.recipient_gstin) setExtractedGstin(data.recipient_gstin);

        if (data.year_book || data.date_validation) {
          const now = new Date();
          const curY = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
          const defaultFY = `${curY}-${String(curY + 1).slice(-2)}`;
          const resolvedFY = data.year_book?.financial_year || data.date_validation?.financial_year || defaultFY;
          setYearBookInfo({
            financial_year: resolvedFY,
            label: data.year_book?.label || `FY ${resolvedFY} Year Book`,
            warning: data.date_validation?.warning || undefined
          });
        }

        if (data.is_duplicate) {
          setDuplicateWarning(data.duplicate_reason || 'Duplicate bill detected in your ledger.');
        } else {
          setDuplicateWarning(null);
        }
      } else {
        if (passwordModalOpen) {
          setPasswordError(data.detail?.message || data.detail || 'Incorrect password');
        } else {
          setErrorMsg(data.detail || 'Failed to scan bill');
        }
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Error uploading and scanning bill');
    } finally {
      setScanning(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      doScanBill(file);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isMandatoryDocsLocked) {
      setErrorMsg('Commercial operations restricted: Company COI and PAN must be uploaded and verified in Vault first.');
      return;
    }
    setLoading(true);
    setErrorMsg(null);

    try {
      const amt = parseFloat(totalAmount) || 0;
      const isPersonal = paymentSource === 'personal_account';

      const payload = {
        merchant_name: merchantName,
        total_amount: amt,
        expense_date: expenseDate,
        category: category,
        payment_mode: paymentMode,
        paid_personally: isPersonal,
        director_name: payeeDirector.replace(' (Director)', ''),
        recipient_gstin: isUnvouchedSelfVoucher ? '' : extractedGstin,
        has_company_gstin: isUnvouchedSelfVoucher ? false : itcEligible,
        itc_eligible: isUnvouchedSelfVoucher ? false : itcEligible,
        igst_amount: isUnvouchedSelfVoucher ? 0 : (itcEligible ? Math.round((amt - (amt / 1.18)) * 100) / 100 : 0),
        receipt_s3_key: isUnvouchedSelfVoucher ? undefined : (receiptS3Key || undefined),
        receipt_sha256: isUnvouchedSelfVoucher ? undefined : (receiptSha256 || undefined),
        notes: isUnvouchedSelfVoucher ? '[Statutory Internal Self-Voucher / Sec 37(1) IT Act]' : undefined,
        allow_duplicate: true,
        tds_section: withholdTds ? tdsSection : 'none',
        tds_rate: withholdTds ? parseFloat(tdsRate) || 0 : 0,
        tds_amount: withholdTds ? tdsAmount : 0,
        deductee_pan: withholdTds && vendorPan ? vendorPan.trim().toUpperCase() : undefined
      };

      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = typeof window !== 'undefined' ? localStorage.getItem('b00k5_tenant_id') : null;

      const headers: Record<string, string> = {
        'Content-Type': 'application/json'
      };
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/expenses`, {
        method: 'POST',
        headers,
        body: JSON.stringify(payload)
      });

      if (!res.ok && res.status !== 409) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to submit expense');
      }

      setSuccess(true);
      if (typeof window !== 'undefined') {
        // Store in localStorage for ledger and reconciliation screens
        localStorage.setItem('b00k5_last_expense_settlement_pending', JSON.stringify({
          director: payeeDirector,
          amount: amt,
          merchant: merchantName,
          date: expenseDate
        }));
      }

      setTimeout(() => {
        router.push('/reports/general-ledger');
      }, 600);

    } catch (err: any) {
      setErrorMsg(err.message || 'Error creating expense record');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Mandatory Document Gate Warning Banner */}
      {isMandatoryDocsLocked && (
        <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="font-semibold text-white">Commercial Operations Locked — Mandatory Documents Pending</div>
            <div className="text-slate-300 mt-0.5">
              Under Companies Act 2013 §10A, corporate expense recording and ledger disbursements are restricted until the Certificate of Incorporation (COI) and Company PAN Card have been uploaded and verified in the Corporate Vault.
            </div>
            <Link href="/vault" className="inline-block mt-2 font-semibold text-sky-400 hover:underline">
              Go to Corporate Vault to Complete Verification &rarr;
            </Link>
          </div>
        </div>
      )}

      {/* Payment Source Selection */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Building2 className="w-4 h-4 text-sky-400" />
          Payment Disbursement Source
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label
            className={`p-4 rounded-xl border flex items-start gap-3 cursor-pointer transition-all ${
              paymentSource === 'company_bank'
                ? 'bg-sky-500/10 border-sky-500/40 text-white'
                : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            <input
              type="radio"
              name="paymentSource"
              checked={paymentSource === 'company_bank'}
              onChange={() => setPaymentSource('company_bank')}
              className="mt-1 text-sky-500 focus:ring-0 cursor-pointer"
            />
            <div>
              <div className="font-semibold text-xs text-white">Company Bank Account</div>
              <div className="text-[11px] text-slate-400">Direct debit from primary current account (HDFC/ICICI)</div>
            </div>
          </label>

          <label
            id="paid-personally-toggle"
            className={`p-4 rounded-xl border flex items-start gap-3 cursor-pointer transition-all ${
              paymentSource === 'personal_account'
                ? 'bg-amber-500/10 border-amber-500/40 text-white'
                : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
            }`}
          >
            <input
              type="radio"
              id="paid-personally-radio"
              name="paymentSource"
              checked={paymentSource === 'personal_account'}
              onChange={() => setPaymentSource('personal_account')}
              className="mt-1 text-amber-500 focus:ring-0 cursor-pointer"
            />
            <div>
              <div className="font-semibold text-xs text-amber-300">Paid from Personal Account</div>
              <div className="text-[11px] text-slate-400">Out-of-Pocket by Founder/Director (Creates 2105 Liability)</div>
            </div>
          </label>
        </div>

        {paymentSource === 'personal_account' && (
          <div className="pt-2 animate-fadeIn">
            <label className="block text-xs font-medium text-amber-300 mb-1.5 flex items-center gap-1.5">
              <User className="w-3.5 h-3.5" />
              Director / Payee Claimant (from Corporate Statutory Roster)
            </label>
            {directors.length > 0 ? (
              <select
                id="director-payee-select"
                value={payeeDirector}
                onChange={(e) => setPayeeDirector(e.target.value)}
                className="w-full bg-slate-950 border border-amber-500/30 rounded-lg px-3 py-2 text-white text-xs font-medium focus:outline-none focus:border-amber-400 cursor-pointer"
              >
                {directors.map((d, idx) => (
                  <option key={`${d.name}-${idx}`} value={d.name}>
                    {d.name} ({d.designation || 'Director'}{d.din && d.din !== 'N/A' ? ` — DIN: ${d.din}` : ''})
                  </option>
                ))}
              </select>
            ) : (
              <input
                type="text"
                id="director-payee-select"
                value={payeeDirector}
                onChange={(e) => setPayeeDirector(e.target.value)}
                placeholder="Enter Director Name"
                className="w-full bg-slate-950 border border-amber-500/30 rounded-lg px-3 py-2 text-white text-xs font-medium focus:outline-none focus:border-amber-400"
                required
              />
            )}
          </div>
        )}
      </div>

      {/* Expense Details */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Receipt className="w-4 h-4 text-emerald-400" />
          Receipt & Vendor Information
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Merchant / Vendor</label>
            <input
              type="text"
              id="merchant-input"
              value={merchantName}
              onChange={(e) => setMerchantName(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:border-sky-500"
              placeholder="Cloud Server Services"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center justify-between">
              <span>Expense Category</span>
              <button
                type="button"
                onClick={() => setIsCustomCategory(!isCustomCategory)}
                className="text-[10px] text-sky-400 hover:underline"
              >
                {isCustomCategory ? 'Choose from list' : '+ Custom'}
              </button>
            </label>
            {isCustomCategory ? (
              <input
                type="text"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="Enter custom category"
                className="w-full bg-slate-950 border border-sky-500/50 rounded-lg px-3 py-2 text-white text-xs focus:outline-none"
                required
              />
            ) : (
              <select
                id="category-select"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white text-xs focus:outline-none focus:border-sky-500 cursor-pointer"
              >
                {STANDARD_EXPENSE_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Total Bill Amount (₹)</label>
            <div className="relative">
              <span className="absolute left-3 top-2 text-slate-500 text-xs font-mono">₹</span>
              <input
                type="number"
                id="amount-input"
                step="0.01"
                value={totalAmount}
                onChange={(e) => setTotalAmount(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-7 pr-3 py-2 text-white font-mono text-xs focus:outline-none focus:border-sky-500"
                placeholder="11800.00"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Expense Date</label>
            <input
              type="date"
              id="expense-date-input"
              value={expenseDate}
              onChange={(e) => setExpenseDate(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono text-xs focus:outline-none focus:border-sky-500"
              required
            />
          </div>
        </div>

        {/* Receipt Upload & OCR ITC Verification */}
        <div className="pt-2 space-y-3">
          {/* Statutory Unvouched Expense / Internal Self-Voucher Toggle */}
          <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3">
            <label className="flex items-start gap-3 cursor-pointer">
              <input
                type="checkbox"
                id="unvouched-self-voucher-toggle"
                checked={isUnvouchedSelfVoucher}
                onChange={(e) => {
                  const val = e.target.checked;
                  setIsUnvouchedSelfVoucher(val);
                  if (val) {
                    setReceiptFileName('Internal Debit Self-Voucher (Sec 37(1))');
                    setExtractedGstin('');
                  } else {
                    setReceiptFileName('');
                  }
                }}
                className="mt-0.5 rounded border-slate-700 bg-slate-900 text-amber-500 focus:ring-0 cursor-pointer"
              />
              <div className="flex-1">
                <div className="text-xs font-semibold text-amber-300 flex items-center gap-1.5">
                  <FileCheck className="w-3.5 h-3.5 text-amber-400" />
                  Record as Unvouched Expense / Internal Self-Voucher (No Bill Available)
                </div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  Permitted under Section 37(1) of the Income Tax Act for petty disbursements, conveyance, daily labor, and incidental operating costs without vendor bills.
                </div>
              </div>
            </label>

            {isUnvouchedSelfVoucher && (
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[11px] space-y-1.5 animate-fadeIn">
                <div className="font-semibold flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
                  Statutory Invariants &amp; Tax Compliance Rules
                </div>
                <ul className="list-disc list-inside space-y-1 text-slate-300">
                  <li>
                    <strong className="text-white">Zero GST Input Tax Credit (§16(2) CGST Act):</strong> No ITC can be claimed without a tax invoice. 100% of the gross disbursement will be charged directly to nominal expense.
                  </li>
                  <li>
                    <strong className="text-white">Section 40A(3) Cash Limit (₹10,000):</strong> Cash disbursements exceeding ₹10,000 per person per day are 100% disallowed as tax deductions. Use bank transfers / UPI for higher amounts.
                  </li>
                  <li>
                    <strong className="text-white">Section 69C / Section 115BBE Punitive Tax Risk:</strong> Unjustified or unvouched business expenditures risk disallowance by the Assessing Officer as unexplained expenditure, taxed at a punitive rate of 78% (60% base tax + 25% surcharge + 4% cess). Ensure genuine commercial expediency, claimant signature, and Director authorization.
                  </li>
                  <li>
                    <strong className="text-white">Internal Debit Voucher:</strong> A pre-formatted Section 37(1) internal expense voucher will be generated and booked to the General Ledger.
                  </li>
                </ul>
              </div>
            )}
          </div>

          {!isUnvouchedSelfVoucher ? (
            <>
              <label className="block text-xs font-medium text-slate-400">
                Upload Tax Invoice / Bill (SmartScan OCR)
              </label>
              <div className="border border-dashed border-slate-700/80 rounded-xl p-4 bg-slate-950/60 flex flex-col items-center justify-center text-center">
                <UploadCloud className="w-8 h-8 text-sky-400 mb-2" />
                <input
                  type="file"
                  id="receipt-file-input"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={handleFileUpload}
                  disabled={scanning}
                  className="text-xs text-slate-400 file:mr-4 file:py-1 file:px-3 file:rounded-md file:border-0 file:text-xs file:bg-sky-600 file:text-white hover:file:bg-sky-500 cursor-pointer disabled:opacity-50"
                />
                {scanning && (
                  <span className="text-xs text-sky-400 font-mono mt-2 animate-pulse flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-sky-400 animate-ping" />
                    Parsing document &amp; checking ledger for duplicates...
                  </span>
                )}
                {receiptFileName && !scanning && (
                  <span className="text-xs text-sky-300 font-mono mt-2">
                    Attached: {receiptFileName}
                  </span>
                )}
              </div>
            </>
          ) : (
            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center gap-3">
              <FileCheck className="w-5 h-5 text-emerald-400 shrink-0" />
              <div className="text-xs">
                <span className="font-semibold text-emerald-300">Internal Self-Voucher Mode Active</span>
                <p className="text-[11px] text-slate-400 mt-0.5">Physical receipt upload waived under Section 37(1). An internal ledger journal voucher (JV) will be recorded automatically.</p>
              </div>
            </div>
          )}

          {/* Indian Financial Year & Year Book Routing Banner */}
          {yearBookInfo && (
            <div className="p-3.5 rounded-xl bg-sky-950/60 border border-sky-500/30 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
              <div className="flex items-center gap-2 text-sky-300">
                <Calendar className="w-4 h-4 text-sky-400 shrink-0" />
                <span>
                  Statutory Accounting Period: <strong className="text-white">FY {yearBookInfo.financial_year}</strong> • Routes to {yearBookInfo.label}
                </span>
              </div>
              {yearBookInfo.warning && (
                <span className="text-[11px] text-amber-400 font-mono flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  {yearBookInfo.warning}
                </span>
              )}
            </div>
          )}

          {/* Duplicate Detection Alert Banner */}
          {duplicateWarning && (
            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs space-y-2">
              <div className="flex items-center gap-2 font-semibold">
                <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                <span>{duplicateWarning}</span>
              </div>
              <label className="flex items-center gap-2 cursor-pointer pt-1 text-slate-300">
                <input
                  type="checkbox"
                  checked={confirmDuplicate}
                  onChange={(e) => setConfirmDuplicate(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-900 text-amber-500 focus:ring-0"
                />
                <span>I confirm this is not a duplicate and wish to record it anyway.</span>
              </label>
            </div>
          )}

          {/* Password Prompt Modal for Encrypted Bills */}
          {passwordModalOpen && (
            <div className="p-4 rounded-xl bg-slate-900 border border-amber-500/40 space-y-3">
              <div className="flex items-center gap-2 text-amber-400 text-xs font-semibold">
                <AlertCircle className="w-4 h-4" />
                <span>Password-Protected Bill PDF</span>
              </div>
              <p className="text-xs text-slate-400">
                This document is encrypted. Please enter the password to decrypt and extract billing data.
              </p>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={pdfPassword}
                  onChange={(e) => setPdfPassword(e.target.value)}
                  placeholder="Enter PDF password"
                  className="flex-1 bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white"
                />
                <button
                  type="button"
                  onClick={() => pendingBillFile && doScanBill(pendingBillFile, pdfPassword)}
                  className="px-4 py-1.5 bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold rounded"
                >
                  Unlock &amp; Scan
                </button>
              </div>
              {passwordError && <p className="text-[11px] text-rose-400">{passwordError}</p>}
            </div>
          )}

          {/* ITC Indicator Banner */}
          <div
            id="itc-indicator-banner"
            className={`p-3.5 rounded-xl border flex items-center gap-3 text-xs transition-all ${
              itcEligible
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
            }`}
          >
            {itcEligible ? (
              <ShieldCheck className="w-4 h-4 shrink-0 text-emerald-400" />
            ) : (
              <AlertCircle className="w-4 h-4 shrink-0 text-amber-400" />
            )}
            <div className="flex-1">
              <span className="font-semibold">{itcMessage}</span>
              <div className="text-[11px] text-slate-400 mt-0.5">
                Recipient Company GSTIN Verified: <span className="font-mono text-white">{extractedGstin}</span>
              </div>
            </div>
          </div>

          {/* Section 40A(3) Warning */}
          {sec40aWarning && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 flex items-center gap-3 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{sec40aWarning}</span>
            </div>
          )}
        </div>
      </div>

      {/* Chapter XVII-B TDS Withholding Section */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <IndianRupee className="w-4 h-4 text-amber-400" />
            <h3 className="text-sm font-semibold text-white">
              Chapter XVII-B Statutory TDS Withholding
            </h3>
          </div>
          <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-300">
            <input
              type="checkbox"
              checked={withholdTds}
              onChange={(e) => setWithholdTds(e.target.checked)}
              className="rounded border-slate-700 bg-slate-950 text-amber-500 focus:ring-0 cursor-pointer"
            />
            <span className="font-semibold text-amber-400">Withhold TDS on this Expense</span>
          </label>
        </div>

        {withholdTds && (
          <div className="space-y-4 pt-2 border-t border-slate-800/80 animate-fadeIn text-xs">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  TDS Section*
                </label>
                <select
                  value={tdsSection}
                  onChange={(e) => setTdsSection(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-medium focus:outline-none focus:border-amber-500"
                >
                  <option value="194J">194J — Professional / Tech Fees (10% / 2%)</option>
                  <option value="194C">194C — Contractor / Vendor (1% / 2%)</option>
                  <option value="194I">194I — Rent of Land / Building (10%)</option>
                  <option value="194Q">194Q — Purchase of Goods (0.1%)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Vendor / Deductee PAN*
                </label>
                <input
                  type="text"
                  maxLength={10}
                  value={vendorPan}
                  onChange={(e) => setVendorPan(e.target.value.toUpperCase())}
                  placeholder="e.g. ABCPD1234F"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-amber-500 uppercase"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-medium mb-1">
                  Applicable Rate (%)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={tdsRate}
                  onChange={(e) => {
                    setTdsRate(e.target.value);
                    const r = parseFloat(e.target.value) || 0;
                    const a = parseFloat(totalAmount) || 0;
                    const calc = Math.round(a * (r / 100) * 100) / 100;
                    setTdsAmount(calc);
                    setNetPayable(Math.round((a - calc) * 100) / 100);
                  }}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-amber-400 font-mono font-bold focus:outline-none focus:border-amber-500"
                />
              </div>
            </div>

            {/* Validation / Penal Rate Alert */}
            {vendorPan && !/^[A-Z]{5}[0-9]{4}[A-Z]{1}$/.test(vendorPan) && (
              <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-[11px] flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
                <span>
                  Section 206AA Alert: Invalid or missing PAN attracts statutory higher withholding rate of 20.00%.
                </span>
              </div>
            )}

            {/* Liability Split Calculation Card */}
            <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 grid grid-cols-1 sm:grid-cols-3 gap-3 font-mono text-center">
              <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-800">
                <div className="text-[10px] text-slate-400 uppercase">Gross Expense Base</div>
                <div className="text-sm font-bold text-white mt-0.5">
                  ₹{(parseFloat(totalAmount) || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </div>
              </div>

              <div className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30">
                <div className="text-[10px] text-amber-400 uppercase">TDS Withheld (Sub-Ledger 206x)</div>
                <div className="text-sm font-bold text-amber-300 mt-0.5">
                  ₹{tdsAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </div>
              </div>

              <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30">
                <div className="text-[10px] text-emerald-400 uppercase">Net Payable to Vendor (2040)</div>
                <div className="text-sm font-bold text-emerald-300 mt-0.5">
                  ₹{netPayable.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {errorMsg && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
          {errorMsg}
        </div>
      )}

      {success && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4" />
          <span>Expense verified and recorded. Redirecting to General Ledger...</span>
        </div>
      )}

      <div className="flex justify-end gap-3">
        <button
          type="submit"
          id="submit-expense-btn"
          disabled={loading || isMandatoryDocsLocked}
          className="px-6 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 font-semibold text-white text-sm shadow-lg shadow-sky-600/30 transition disabled:opacity-50"
        >
          {loading ? 'Validating & Posting...' : isMandatoryDocsLocked ? 'Locked (Upload COI & PAN in Vault)' : 'Save & Submit Expense'}
        </button>
      </div>
    </form>
  );
}
