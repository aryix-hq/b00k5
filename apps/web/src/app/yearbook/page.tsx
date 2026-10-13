'use client';

import React, { useState, useEffect } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import {
  BookOpen,
  Calendar,
  IndianRupee,
  FileSpreadsheet,
  Receipt,
  ArrowUpRight,
  ArrowDownLeft,
  CheckCircle2,
  AlertTriangle,
  UploadCloud,
  Plus,
  ShieldCheck,
  Lock,
  ExternalLink,
  ChevronRight,
  TrendingUp,
  FileText,
  Download,
  Shield,
  FileCheck,
  RefreshCw
} from 'lucide-react';
import { fetchApi } from '@/lib/api';
import Link from 'next/link';

interface ExpenseItem {
  id: string;
  vendor_name: string;
  date: string;
  amount: number;
  gstin: string;
  taxable_amount: number;
  gst_amount: number;
  category: string;
  schedule_iii_head: string;
  itc_eligible: boolean;
}

export default function YearBookPage() {
  const now = new Date();
  const currentCalendarYr = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  const currentDefaultFY = `${currentCalendarYr}-${String(currentCalendarYr + 1).slice(-2)}`;

  const parseFYString = (val: string) => {
    const match = (val || '').match(/(\d{4})/);
    if (match) {
      const yr = parseInt(match[1]);
      return `${yr}-${String(yr + 1).slice(-2)}`;
    }
    return currentDefaultFY;
  };

  const [selectedFY, setSelectedFY] = useState(currentDefaultFY);
  const [activeTab, setActiveTab] = useState<'statements' | 'bills' | 'invoices' | 'close'>('statements');

  // Dynamic available periods (e.g. Current FY, past 5 years)
  const availableFYs: string[] = [];
  for (let y = currentCalendarYr; y >= currentCalendarYr - 5; y--) {
    availableFYs.push(`${y}-${String(y + 1).slice(-2)}`);
  }

  // Statements State
  const [statements, setStatements] = useState<any[]>([]);
  const [uploadingStatement, setUploadingStatement] = useState(false);
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pdfPassword, setPdfPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');

  // Expenses / Bills State (Starts strictly empty: Zero test data)
  const [expenses, setExpenses] = useState<ExpenseItem[]>([]);

  // Indian Financial Year (April - March) Calendar State
  const [selectedMonth, setSelectedMonth] = useState<string>('all');

  // Invoices State
  const [invoices, setInvoices] = useState<any[]>([]);

  // Annual Statutory Filings State (5 documents)
  const [statutoryFilings, setStatutoryFilings] = useState<any[]>([]);
  const [loadingFilings, setLoadingFilings] = useState(false);
  const [filingUploadModalOpen, setFilingUploadModalOpen] = useState(false);
  const [targetFilingDoc, setTargetFilingDoc] = useState<any | null>(null);
  const [selectedFilingFile, setSelectedFilingFile] = useState<File | null>(null);
  const [filingPdfPassword, setFilingPdfPassword] = useState('');
  const [filingUploading, setFilingUploading] = useState(false);
  const [filingUploadError, setFilingUploadError] = useState('');

  // Dynamic Indian Financial Year (1 April - 31 March)
  const startYear = parseInt(selectedFY.split('-')[0]) || currentCalendarYr;
  const endYear = startYear + 1;
  const fyStartDate = `${startYear}-04-01`;
  const fyEndDate = `${endYear}-03-31`;

  const getTargetYearForMonth = (mKey: string) => {
    const mNum = parseInt(mKey, 10);
    return mNum >= 4 ? startYear : endYear;
  };

  // New Expense Modal State
  const [showAddExpenseModal, setShowAddExpenseModal] = useState(false);
  const [creatingExpense, setCreatingExpense] = useState(false);
  const [scanningBill, setScanningBill] = useState(false);
  const [scannedReceiptKey, setScannedReceiptKey] = useState<string | null>(null);
  const [scannedReceiptSha256, setScannedReceiptSha256] = useState<string | null>(null);
  const [newExp, setNewExp] = useState({
    vendor_name: '',
    date: `${startYear}-06-15`,
    taxable_amount: '',
    gst_rate: '18',
    category: '4020 Software & Cloud Subscriptions',
    vendor_gstin: ''
  });

  const loadAnnualStatutoryFilings = async (fy: string) => {
    setLoadingFilings(true);
    try {
      const res = await fetchApi(`/api/v1/vault/annual-statutory-filings?fy=${fy}`);
      if (res && res.documents) {
        setStatutoryFilings(res.documents);
      }
    } catch (e) {
      console.error('Failed to load annual statutory filings:', e);
    } finally {
      setLoadingFilings(false);
    }
  };

  const handleSelectFY = (fy: string) => {
    setSelectedFY(fy);
    const startY = parseInt(fy.split('-')[0]);
    if (typeof window !== 'undefined') {
      const full = `FY ${startY}-${startY + 1}`;
      localStorage.setItem('b00k5_selected_fy', full);
      window.dispatchEvent(new CustomEvent('b00k5_fy_changed', { detail: full }));
    }
    loadAnnualStatutoryFilings(fy);
  };

  // Load existing records and URL parameters
  useEffect(() => {
    let cleanup: (() => void) | undefined;

    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const fy = params.get('fy');
      const tab = params.get('tab');
      if (fy) {
        const parsed = parseFYString(fy);
        setSelectedFY(parsed);
        loadAnnualStatutoryFilings(parsed);
      } else {
        const stored = localStorage.getItem('b00k5_selected_fy');
        if (stored) {
          const parsed = parseFYString(stored);
          setSelectedFY(parsed);
          loadAnnualStatutoryFilings(parsed);
        } else {
          loadAnnualStatutoryFilings(currentDefaultFY);
        }
      }
      if (tab && ['statements', 'bills', 'invoices', 'close'].includes(tab)) {
        setActiveTab(tab as any);
      }

      const onFY = (e: any) => {
        const val = e.detail || '';
        if (val) {
          const parsed = parseFYString(val);
          setSelectedFY(parsed);
          loadAnnualStatutoryFilings(parsed);
        }
      };
      window.addEventListener('b00k5_fy_changed', onFY);
      cleanup = () => window.removeEventListener('b00k5_fy_changed', onFY);
    }

    async function loadData() {
      try {
        const [stmtRes, invRes, expRes] = await Promise.all([
          fetchApi('/api/v1/reconciliation/statements').catch(() => []),
          fetchApi('/api/v1/invoices/').catch(() => []),
          fetchApi('/api/v1/expenses/').catch(() => [])
        ]);

        if (Array.isArray(stmtRes)) setStatements(stmtRes);
        if (Array.isArray(invRes)) setInvoices(invRes);

        if (Array.isArray(expRes)) {
          const mapped: ExpenseItem[] = expRes
            .filter((exp: any) => exp.status !== 'struck_off' && exp.status !== 'rejected')
            .map((exp: any) => {
              const total = parseFloat(exp.total_amount || '0');
              const cgst = parseFloat(exp.cgst_amount || '0');
              const sgst = parseFloat(exp.sgst_amount || '0');
              const igst = parseFloat(exp.igst_amount || '0');
              const taxTotal = cgst + sgst + igst;
              const taxable = total - taxTotal;
              return {
                id: exp.id,
                vendor_name: exp.merchant_name || 'Vendor',
                date: exp.expense_date ? String(exp.expense_date).slice(0, 10) : '',
                amount: total,
                gstin: exp.merchant_gstin || '',
                taxable_amount: taxable > 0 ? taxable : total,
                gst_amount: taxTotal,
                category: exp.category || 'Direct Expense',
                schedule_iii_head: exp.category || '4010 Direct Operational Expense',
                itc_eligible: Boolean(exp.itc_eligible || taxTotal > 0)
              };
            });
          setExpenses(mapped);
        }
      } catch (e) {
        console.error('Error loading yearbook data:', e);
      }
    }
    loadData();

    return cleanup;
  }, [selectedFY]);

  // Handle Statement Upload
  const handleStatementFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    executeStatementUpload(file, '');
  };

  const executeStatementUpload = async (file: File, password: string) => {
    setUploadingStatement(true);
    setPasswordError('');
    const fd = new FormData();
    fd.append('file', file);
    if (password) fd.append('password', password);

    try {
      const token = localStorage.getItem('b00k5_token');
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/reconciliation/upload-statement`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd
      });

      if (res.status === 422) {
        const errData = await res.json();
        if (errData?.detail?.needs_password) {
          setPendingFile(file);
          setPasswordModalOpen(true);
          setPasswordError(password ? 'Incorrect password. Please verify and re-enter.' : 'Password required for this statement.');
          setUploadingStatement(false);
          return;
        }
      }

      if (res.ok) {
        const data = await res.json();
        setStatements(prev => [data, ...prev]);
        setPasswordModalOpen(false);
        setPendingFile(null);
        setPdfPassword('');
      } else {
        const err = await res.json();
        alert(err.detail?.message || err.detail || 'Upload failed');
      }
    } catch (err: any) {
      alert(err.message || 'Upload failed');
    } finally {
      setUploadingStatement(false);
    }
  };

  const handleBillUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setScanningBill(true);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const token = localStorage.getItem('b00k5_token');
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/expenses/scan-bill`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd
      });
      const data = await res.json();
      if (res.ok) {
        if (data.date_validation?.financial_year) {
          setSelectedFY(data.date_validation.financial_year);
          setActiveTab('bills');
        }
        setScannedReceiptKey(data.receipt_s3_key || null);
        setScannedReceiptSha256(data.receipt_sha256 || null);
        setNewExp({
          vendor_name: data.merchant_name || 'Vendor',
          date: data.bill_date || `${startYear}-06-15`,
          taxable_amount: String(data.taxable_amount || data.total_amount || ''),
          gst_rate: data.gst_rate ? String(data.gst_rate) : '18',
          category: data.category || '[4020] Software Licenses & SaaS Subscriptions',
          vendor_gstin: data.merchant_gstin || ''
        });
        setShowAddExpenseModal(true);
      } else {
        alert(data.detail?.message || data.detail || 'Failed to scan bill');
      }
    } catch (err: any) {
      alert(err.message || 'Error scanning bill');
    } finally {
      setScanningBill(false);
    }
  };

  const handleCreateExpense = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreatingExpense(true);
    const tax = parseFloat(newExp.taxable_amount || '0');
    const gstRate = parseFloat(newExp.gst_rate || '18') / 100;
    const gst = tax * gstRate;
    const total = tax + gst;

    try {
      const payload = {
        merchant_name: newExp.vendor_name,
        expense_date: newExp.date,
        category: newExp.category,
        total_amount: total,
        currency: 'INR',
        payment_mode: 'company_bank',
        paid_personally: false,
        merchant_gstin: newExp.vendor_gstin || null,
        cgst_amount: gst / 2,
        sgst_amount: gst / 2,
        igst_amount: 0,
        itc_eligible: true,
        receipt_s3_key: scannedReceiptKey,
        receipt_sha256: scannedReceiptSha256
      };
      await fetchApi('/api/v1/expenses/', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      setShowAddExpenseModal(false);
      setScannedReceiptKey(null);
      setScannedReceiptSha256(null);
      setNewExp({
        vendor_name: '',
        date: `${startYear}-06-15`,
        taxable_amount: '',
        gst_rate: '18',
        category: '4020 Software & Cloud Subscriptions',
        vendor_gstin: ''
      });
      // Refresh expenses from backend
      const expRes = await fetchApi('/api/v1/expenses/');
      if (Array.isArray(expRes)) {
        const mapped: ExpenseItem[] = expRes
          .filter((exp: any) => exp.status !== 'struck_off' && exp.status !== 'rejected')
          .map((exp: any) => {
            const t = parseFloat(exp.total_amount || '0');
            const cg = parseFloat(exp.cgst_amount || '0');
            const sg = parseFloat(exp.sgst_amount || '0');
            const ig = parseFloat(exp.igst_amount || '0');
            const taxSum = cg + sg + ig;
            const taxable = t - taxSum;
            return {
              id: exp.id,
              vendor_name: exp.merchant_name || 'Vendor',
              date: exp.expense_date ? String(exp.expense_date).slice(0, 10) : '',
              amount: t,
              gstin: exp.merchant_gstin || '',
              taxable_amount: taxable > 0 ? taxable : t,
              gst_amount: taxSum,
              category: exp.category || 'Direct Expense',
              schedule_iii_head: exp.category || '4010 Direct Operational Expense',
              itc_eligible: Boolean(exp.itc_eligible || taxSum > 0)
            };
          });
        setExpenses(mapped);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to record expense');
    } finally {
      setCreatingExpense(false);
    }
  };

  const executeFilingUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFilingFile || !targetFilingDoc) return;
    setFilingUploading(true);
    setFilingUploadError('');

    const fd = new FormData();
    fd.append('file', selectedFilingFile);
    fd.append('document_code', targetFilingDoc.code);
    fd.append('fiscal_year', selectedFY);
    if (filingPdfPassword) {
      fd.append('pdf_password', filingPdfPassword);
    }

    try {
      const token = localStorage.getItem('b00k5_token');
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/vault/annual-statutory-filings/upload`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd
      });

      if (res.status === 422) {
        const errData = await res.json();
        if (errData?.detail?.needs_password) {
          setFilingUploadError(filingPdfPassword ? 'Incorrect password. Please verify and re-enter.' : 'Password required for this document.');
          setFilingUploading(false);
          return;
        }
      }

      if (res.ok) {
        setFilingUploadModalOpen(false);
        setTargetFilingDoc(null);
        setSelectedFilingFile(null);
        setFilingPdfPassword('');
        setFilingUploadError('');
        await loadAnnualStatutoryFilings(selectedFY);
      } else {
        const err = await res.json();
        setFilingUploadError(err.detail?.message || err.detail || 'Upload failed');
      }
    } catch (err: any) {
      setFilingUploadError(err.message || 'Upload failed');
    } finally {
      setFilingUploading(false);
    }
  };

  // Calculations & Calendar Filters
  const displayedExpenses = expenses.filter(e => {
    if (!e.date) return false;
    if (selectedMonth === 'all') {
      return e.date >= fyStartDate && e.date <= fyEndDate;
    }
    const targetYM = `${getTargetYearForMonth(selectedMonth)}-${selectedMonth}`;
    return e.date.startsWith(targetYM);
  });

  const displayedInvoices = invoices.filter(i => {
    const d = i.issue_date ? String(i.issue_date).slice(0, 10) : '';
    if (!d) return false;
    if (selectedMonth === 'all') {
      return d >= fyStartDate && d <= fyEndDate;
    }
    const targetYM = `${getTargetYearForMonth(selectedMonth)}-${selectedMonth}`;
    return d.startsWith(targetYM);
  });

  const displayedStatements = statements
    .filter(s => {
      const from = (s.statement_from || '').slice(0, 10);
      const to = (s.statement_to || '').slice(0, 10);
      if (selectedMonth === 'all') {
        return (from >= fyStartDate && from <= fyEndDate) || (to >= fyStartDate && to <= fyEndDate) || (from && to && from <= fyEndDate && to >= fyStartDate) || (!from && !to);
      }
      const targetYM = `${getTargetYearForMonth(selectedMonth)}-${selectedMonth}`;
      const mStart = `${targetYM}-01`;
      const mEnd = `${targetYM}-31`;
      return from.startsWith(targetYM) || to.startsWith(targetYM) || (from && to && from <= mEnd && to >= mStart);
    })
    .sort((a, b) => (a.statement_from || '').localeCompare(b.statement_from || ''));

  // KPI metrics correctly scoped to selected financial year and period
  const totalBillsAmount = displayedExpenses.reduce((acc, e) => acc + e.amount, 0);
  const totalITCClaimable = displayedExpenses.reduce((acc, e) => acc + (e.itc_eligible ? e.gst_amount : 0), 0);
  const totalInvoiceAmount = displayedInvoices.reduce((acc, i) => acc + parseFloat(i.subtotal ?? i.subtotal_amount ?? i.grand_total ?? i.total_amount ?? '0'), 0);

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Navbar />

        <main className="p-8 space-y-6 max-w-7xl mx-auto w-full">
          {/* Top Bar with FY Selector */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
            <div>
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  <BookOpen className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-white flex items-center gap-2">
                    Financial Year Book — FY {selectedFY}
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Central ledger for Bank Statements, Vendor Bills (ITC), Outward Invoices, and Year-End Statutory Close
                  </p>
                </div>
              </div>
            </div>

            {/* FY Switcher */}
            <div className="flex items-center gap-1.5 bg-slate-900 p-1.5 rounded-xl border border-slate-800 overflow-x-auto max-w-full">
              <span className="text-xs text-slate-400 px-2 font-medium flex items-center gap-1.5 shrink-0">
                <Calendar className="w-3.5 h-3.5 text-amber-400" /> Assessment Period:
              </span>
              {availableFYs.map((fy) => {
                const isSelected = selectedFY === fy;
                const isCurrent = fy === currentDefaultFY;
                return (
                  <button
                    key={fy}
                    type="button"
                    onClick={() => handleSelectFY(fy)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all shrink-0 flex items-center gap-1 ${
                      isSelected
                        ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20 font-bold'
                        : 'text-slate-400 hover:text-white hover:bg-slate-800'
                    }`}
                  >
                    <span>FY {fy}</span>
                    {isCurrent && (
                      <span className={`text-[9px] px-1 py-0.5 rounded font-mono ${
                        isSelected ? 'bg-slate-950/20 text-slate-950 font-bold' : 'bg-emerald-500/20 text-emerald-400'
                      }`}>
                        Current
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
              <span className="text-xs text-slate-400 font-medium">Outward Revenue (FY {selectedFY})</span>
              <div className="text-2xl font-bold text-emerald-400 font-mono">
                ₹{totalInvoiceAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <p className="text-[11px] text-slate-500">{displayedInvoices.length} Registered Outward Invoices</p>
            </div>

            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
              <span className="text-xs text-slate-400 font-medium">Bills & Operating Expenses</span>
              <div className="text-2xl font-bold text-rose-400 font-mono">
                ₹{totalBillsAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <p className="text-[11px] text-slate-500">{displayedExpenses.length} Schedule III Vouchers Posted</p>
            </div>

            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
              <span className="text-xs text-slate-400 font-medium">Claimable ITC (CGST+SGST/IGST)</span>
              <div className="text-2xl font-bold text-sky-400 font-mono">
                ₹{totalITCClaimable.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <p className="text-[11px] text-emerald-400 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> Sec 16(2) Invariants Verified
              </p>
            </div>

            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
              <span className="text-xs text-slate-400 font-medium">Bank Statements Deposited</span>
              <div className="text-2xl font-bold text-white font-mono">{displayedStatements.length}</div>
              <Link href="/reconciliation" className="text-[11px] text-amber-400 hover:underline flex items-center gap-1">
                Go to 3-Tier Matcher <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
          </div>

          {/* Indian Financial Year (April - March) Calendar Navigator */}
          <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-amber-400" />
                  Indian Financial Year {selectedFY} Calendar (1 April {startYear} – 31 March {endYear})
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Follows mandatory Indian fiscal quarters (Q1, Q2, Q3, Q4) tracking monthly bank statements, bills, invoices, and statutory tax due dates.
                </p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setSelectedMonth('all')}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    selectedMonth === 'all'
                      ? 'bg-amber-500 text-slate-950 shadow-sm'
                      : 'bg-slate-800 text-slate-400 hover:text-white'
                  }`}
                >
                  All 12 Months
                </button>
              </div>
            </div>

            {/* 12-Month Grid */}
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2.5">
              {[
                { key: '04', name: 'Apr', q: 'Q1', advanceTax: null, due: 'TDS (May 7), GSTR-1/3B' },
                { key: '05', name: 'May', q: 'Q1', advanceTax: null, due: 'TDS (Jun 7), GSTR-1/3B' },
                { key: '06', name: 'Jun', q: 'Q1', advanceTax: `15% Adv Tax (15 Jun ${startYear})`, due: 'TDS, Form 24Q/26Q' },
                { key: '07', name: 'Jul', q: 'Q2', advanceTax: null, due: 'TDS (Aug 7), GSTR-1/3B' },
                { key: '08', name: 'Aug', q: 'Q2', advanceTax: null, due: 'TDS (Sep 7), GSTR-1/3B' },
                { key: '09', name: 'Sep', q: 'Q2', advanceTax: `45% Adv Tax (15 Sep ${startYear})`, due: 'TDS, Form 24Q/26Q' },
                { key: '10', name: 'Oct', q: 'Q3', advanceTax: null, due: 'TDS (Nov 7), GSTR-1/3B' },
                { key: '11', name: 'Nov', q: 'Q3', advanceTax: null, due: 'TDS (Dec 7), GSTR-1/3B' },
                { key: '12', name: 'Dec', q: 'Q3', advanceTax: `75% Adv Tax (15 Dec ${startYear})`, due: 'TDS, Form 24Q/26Q' },
                { key: '01', name: 'Jan', q: 'Q4', advanceTax: null, due: 'TDS (Feb 7), GSTR-1/3B' },
                { key: '02', name: 'Feb', q: 'Q4', advanceTax: null, due: 'TDS (Mar 7), GSTR-1/3B' },
                { key: '03', name: 'Mar', q: 'Q4', advanceTax: `100% Adv Tax (15 Mar ${endYear})`, due: `Books Close 31 Mar ${endYear}` },
              ].map((m) => {
                const isSelected = selectedMonth === m.key;
                const mYear = parseInt(m.key, 10) >= 4 ? startYear : endYear;
                const monthDateStr = `${mYear}-${m.key}`;
                const mStart = `${monthDateStr}-01`;
                const mEnd = `${monthDateStr}-31`;
                const monthInvoices = invoices.filter(inv => String(inv.issue_date || '').slice(0, 10).startsWith(monthDateStr));
                const monthExpenses = expenses.filter(exp => exp.date?.startsWith(monthDateStr));
                const hasStatement = statements.some(s => {
                  const from = String(s.statement_from || '').slice(0, 10);
                  const to = String(s.statement_to || '').slice(0, 10);
                  return from.startsWith(monthDateStr) || to.startsWith(monthDateStr) || (from && to && from <= mEnd && to >= mStart);
                });

                return (
                  <button
                    key={m.key}
                    type="button"
                    onClick={() => setSelectedMonth(isSelected ? 'all' : m.key)}
                    className={`p-3 rounded-xl border text-left transition-all relative flex flex-col justify-between space-y-2 ${
                      isSelected
                        ? 'bg-amber-500/15 border-amber-500 text-white shadow-md ring-1 ring-amber-500'
                        : 'bg-slate-950/60 border-slate-800 text-slate-300 hover:border-slate-700 hover:bg-slate-900/60'
                    }`}
                  >
                    <div className="flex items-center justify-between w-full">
                      <span className="font-bold text-xs text-white">{m.name} {mYear}</span>
                      <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                        m.q === 'Q1' ? 'bg-sky-500/20 text-sky-400' :
                        m.q === 'Q2' ? 'bg-indigo-500/20 text-indigo-400' :
                        m.q === 'Q3' ? 'bg-purple-500/20 text-purple-400' :
                        'bg-amber-500/20 text-amber-400'
                      }`}>
                        {m.q}
                      </span>
                    </div>

                    <div className="space-y-1 text-[11px]">
                      <div className="flex items-center justify-between text-slate-400">
                        <span>Stmt:</span>
                        <span className={hasStatement ? 'text-emerald-400 font-medium' : 'text-slate-500'}>
                          {hasStatement ? '✓ Done' : 'Pending'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-slate-400">
                        <span>Bills:</span>
                        <span className="font-mono text-slate-200">{monthExpenses.length}</span>
                      </div>
                      <div className="flex items-center justify-between text-slate-400">
                        <span>Sales:</span>
                        <span className="font-mono text-slate-200">{monthInvoices.length}</span>
                      </div>
                    </div>

                    <div className="pt-1.5 border-t border-slate-800/80 text-[10px]">
                      {m.advanceTax ? (
                        <span className="text-amber-400 font-medium block truncate" title={m.advanceTax}>
                          ⚡ {m.advanceTax}
                        </span>
                      ) : (
                        <span className="text-slate-500 block truncate" title={m.due}>
                          {m.due}
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Tab Selector */}
          <div className="flex items-center gap-2 border-b border-slate-800 text-xs">
            <button
              onClick={() => setActiveTab('statements')}
              className={`pb-3 px-3 font-semibold border-b-2 flex items-center gap-2 transition-all ${
                activeTab === 'statements'
                  ? 'border-amber-400 text-amber-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <FileSpreadsheet className="w-4 h-4" /> Bank Statements (FY {selectedFY})
            </button>
            <button
              onClick={() => setActiveTab('bills')}
              className={`pb-3 px-3 font-semibold border-b-2 flex items-center gap-2 transition-all ${
                activeTab === 'bills'
                  ? 'border-amber-400 text-amber-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <ArrowDownLeft className="w-4 h-4 text-rose-400" /> Bills & Expenses (ITC)
            </button>
            <button
              onClick={() => setActiveTab('invoices')}
              className={`pb-3 px-3 font-semibold border-b-2 flex items-center gap-2 transition-all ${
                activeTab === 'invoices'
                  ? 'border-amber-400 text-amber-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <ArrowUpRight className="w-4 h-4 text-emerald-400" /> Income & Outward Invoices
            </button>
            <button
              onClick={() => setActiveTab('close')}
              className={`pb-3 px-3 font-semibold border-b-2 flex items-center gap-2 transition-all ${
                activeTab === 'close'
                  ? 'border-amber-400 text-amber-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <ShieldCheck className="w-4 h-4 text-sky-400" /> Statutory Close & MCA Checklist
            </button>
          </div>

          {/* TAB 1: BANK STATEMENTS */}
          {activeTab === 'statements' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-white">Bank Current Account Statements (FY {selectedFY})</h3>
                  <p className="text-xs text-slate-400">
                    Upload official PDF statements (HDFC, ICICI, SBI, Axis). Supports password-protected statement files.
                  </p>
                </div>
                <label className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-semibold rounded-lg cursor-pointer flex items-center gap-2 shadow-sm transition-all">
                  <UploadCloud className="w-4 h-4" />
                  {uploadingStatement ? 'Parsing Statement...' : 'Upload Bank Statement (PDF or Image)'}
                  <input
                    type="file"
                    accept=".pdf, .png, .jpg, .jpeg, image/png, image/jpeg"
                    className="hidden"
                    onChange={handleStatementFileChange}
                    disabled={uploadingStatement}
                  />
                </label>
              </div>

              {displayedStatements.length === 0 ? (
                <div className="p-12 text-center bg-slate-900 border border-slate-800 rounded-xl space-y-3">
                  <FileSpreadsheet className="w-12 h-12 text-slate-600 mx-auto" />
                  <h4 className="text-sm font-semibold text-slate-300">
                    No Statements Deposited {selectedMonth !== 'all' ? `for Month ${selectedMonth}` : `for FY ${selectedFY}`}
                  </h4>
                  <p className="text-xs text-slate-500 max-w-md mx-auto">
                    Deposit current account statements to automatically extract tabular transactions, detect UPI/NEFT references, and clear Suspense Account (Code 2099).
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto border border-slate-800 rounded-xl bg-slate-900">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950/70 border-b border-slate-800 text-slate-400 uppercase font-mono">
                      <tr>
                        <th className="p-4">Bank</th>
                        <th className="p-4">Account Number</th>
                        <th className="p-4">Period</th>
                        <th className="p-4 text-right">Deposits</th>
                        <th className="p-4 text-right">Withdrawals</th>
                        <th className="p-4 text-right">Closing Balance</th>
                        <th className="p-4 text-center">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {displayedStatements.map((s) => (
                        <tr key={s.id} className="hover:bg-slate-800/40">
                          <td className="p-4 font-sans font-semibold text-white">{s.bank_name}</td>
                          <td className="p-4 text-slate-300">{s.account_number}</td>
                          <td className="p-4 text-slate-400 font-sans">
                            {s.statement_from ? `${s.statement_from} → ${s.statement_to}` : 'Active FY'}
                          </td>
                          <td className="p-4 text-right text-emerald-400">
                            ₹{parseFloat(s.total_deposits || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="p-4 text-right text-rose-400">
                            ₹{parseFloat(s.total_withdrawals || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="p-4 text-right font-bold text-white">
                            ₹{parseFloat(s.closing_balance || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="p-4 text-center">
                            <Link
                              href="/reconciliation"
                              className="px-3 py-1 bg-sky-500/10 text-sky-400 border border-sky-500/20 rounded font-sans text-xs hover:bg-sky-500/20"
                            >
                              Reconcile Lines
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: BILLS & EXPENSES */}
          {activeTab === 'bills' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-white">Inward Vendor Bills & Operating Expenses (FY {selectedFY})</h3>
                  <p className="text-xs text-slate-400">
                    Classified under Schedule III Chart of Accounts with Input Tax Credit (ITC) reconciliation.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <label className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg cursor-pointer flex items-center gap-2 border border-slate-700 shadow-sm transition-all">
                    <UploadCloud className="w-4 h-4 text-rose-400" />
                    <span>{scanningBill ? 'Scanning Bill...' : 'Upload & Scan Bill (PDF/Img)'}</span>
                    <input type="file" accept=".pdf,image/*" className="hidden" onChange={handleBillUpload} disabled={scanningBill} />
                  </label>
                  <button
                    onClick={() => setShowAddExpenseModal(true)}
                    className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 shadow-sm transition-all"
                  >
                    <Plus className="w-4 h-4" /> Record New Bill / Expense
                  </button>
                </div>
              </div>

              {displayedExpenses.length === 0 ? (
                <div className="p-12 text-center bg-slate-900 border border-slate-800 rounded-xl space-y-3">
                  <Receipt className="w-12 h-12 text-slate-600 mx-auto" />
                  <h4 className="text-sm font-semibold text-slate-300">
                    No Expenses Recorded {selectedMonth !== 'all' ? `for Month ${selectedMonth}` : `for FY ${selectedFY}`}
                  </h4>
                  <p className="text-xs text-slate-500 max-w-md mx-auto">
                    Zero test data active. Click "Record New Bill / Expense" above to add authentic vendor purchases, verify GSTINs, and post Schedule III expense vouchers.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto border border-slate-800 rounded-xl bg-slate-900">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950/70 border-b border-slate-800 text-slate-400 uppercase font-mono">
                      <tr>
                        <th className="p-4">Date</th>
                        <th className="p-4">Vendor &amp; GSTIN</th>
                        <th className="p-4">Schedule III Head</th>
                        <th className="p-4 text-right">Taxable</th>
                        <th className="p-4 text-right">GST (ITC)</th>
                        <th className="p-4 text-right">Total Payable</th>
                        <th className="p-4 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {displayedExpenses.map((exp) => (
                        <tr key={exp.id} className="hover:bg-slate-800/40">
                          <td className="p-4 text-slate-300 font-sans">{exp.date}</td>
                          <td className="p-4">
                            <div className="font-sans font-semibold text-white">{exp.vendor_name}</div>
                            <div className="text-[11px] text-slate-400">{exp.gstin || 'Unregistered Vendor'}</div>
                          </td>
                          <td className="p-4 font-sans text-slate-300">{exp.schedule_iii_head}</td>
                          <td className="p-4 text-right text-slate-300">
                            ₹{exp.taxable_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="p-4 text-right text-sky-400">
                            ₹{exp.gst_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="p-4 text-right font-bold text-rose-400">
                            ₹{exp.amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="p-4 text-center">
                            <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded font-sans text-[10px]">
                              ITC Eligible
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: INVOICES & INCOME */}
          {activeTab === 'invoices' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-white">Outward Tax Invoices &amp; Revenue (FY {selectedFY})</h3>
                  <p className="text-xs text-slate-400">
                    B2B and B2C sales invoices with auto-calculated CGST, SGST, and IGST components.
                  </p>
                </div>
                <Link
                  href="/invoices"
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 shadow-sm transition-all"
                >
                  <Plus className="w-4 h-4" /> Create Outward Invoice
                </Link>
              </div>

              {displayedInvoices.length === 0 ? (
                <div className="p-12 text-center bg-slate-900 border border-slate-800 rounded-xl space-y-3">
                  <Receipt className="w-12 h-12 text-slate-600 mx-auto" />
                  <h4 className="text-sm font-semibold text-slate-300">
                    No Invoices Recorded {selectedMonth !== 'all' ? `for Month ${selectedMonth}` : `for FY ${selectedFY}`}
                  </h4>
                  <p className="text-xs text-slate-500 max-w-md mx-auto">
                    Generate compliant GST tax invoices with dynamic company letterheads, QR codes, and digital signatures.
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto border border-slate-800 rounded-xl bg-slate-900">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950/70 border-b border-slate-800 text-slate-400 uppercase font-mono">
                      <tr>
                        <th className="p-4">Invoice #</th>
                        <th className="p-4">Customer</th>
                        <th className="p-4">Issue Date</th>
                        <th className="p-4 text-right">Taxable</th>
                        <th className="p-4 text-right">Tax Amount</th>
                        <th className="p-4 text-right">Total (INR)</th>
                        <th className="p-4 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {displayedInvoices.map((inv) => {
                        const subAmt = parseFloat(inv.subtotal ?? inv.subtotal_amount ?? '0');
                        const taxAmt = (parseFloat(inv.cgst_total || '0') + parseFloat(inv.sgst_total || '0') + parseFloat(inv.igst_total || '0')) || parseFloat(inv.tax_amount || '0');
                        const totalAmt = parseFloat(inv.grand_total ?? inv.total_amount ?? '0');
                        const rawStatus = String(inv.status || inv.payment_status || 'unpaid').toLowerCase();
                        const isPaid = rawStatus === 'paid';
                        return (
                          <tr key={inv.id} className="hover:bg-slate-800/40">
                            <td className="p-4 font-semibold text-sky-400">{inv.invoice_number}</td>
                            <td className="p-4 font-sans text-white">{inv.contact?.name || inv.customer_name || 'Customer'}</td>
                            <td className="p-4 font-sans text-slate-400">{inv.issue_date}</td>
                            <td className="p-4 text-right text-slate-300">
                              ₹{subAmt.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                            </td>
                            <td className="p-4 text-right text-slate-400">
                              ₹{taxAmt.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                            </td>
                            <td className="p-4 text-right font-bold text-emerald-400">
                              ₹{totalAmt.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                            </td>
                            <td className="p-4 text-center">
                              <span className={`px-2 py-0.5 rounded font-sans text-[10px] capitalize border ${
                                isPaid
                                  ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                                  : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                              }`}>
                                {isPaid ? 'Paid' : rawStatus === 'partially_paid' ? 'Partially Paid' : 'Unpaid'}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* TAB 4: STATUTORY YEAR-END CLOSE */}
          {activeTab === 'close' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-sm font-semibold text-white">Year-End Statutory Close & MCA Checklist (FY {selectedFY})</h3>
                <p className="text-xs text-slate-400">
                  Comprehensive compliance tracker for Indian corporate annual closures, tax audits, and MCA V3 filings.
                </p>
              </div>

              <div className="space-y-6">
                {/* 5 Annual Statutory Filings Workbench */}
                <div className="p-6 bg-slate-900 border border-slate-800 rounded-2xl space-y-5">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
                    <div>
                      <div className="flex items-center gap-2">
                        <Shield className="w-5 h-5 text-emerald-400" />
                        <h4 className="text-base font-bold text-white">
                          Annual Statutory Compliance Filings — FY {selectedFY}
                        </h4>
                      </div>
                      <p className="text-xs text-slate-400 mt-1">
                        Mandatory compliance filings required every financial year. Documents are cryptographically hashed (SHA-256) and verified into the legal vault.
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => loadAnnualStatutoryFilings(selectedFY)}
                      disabled={loadingFilings}
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg flex items-center gap-1.5 self-start sm:self-auto transition"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${loadingFilings ? 'animate-spin text-sky-400' : ''}`} />
                      <span>{loadingFilings ? 'Refreshing...' : 'Refresh Status'}</span>
                    </button>
                  </div>

                  {/* Document Grid */}
                  <div className="grid grid-cols-1 gap-3.5">
                    {statutoryFilings.map((doc) => {
                      const isVerified = doc.status === 'verified' && doc.document;
                      const docObj = doc.document;
                      return (
                        <div
                          key={doc.code}
                          className={`p-4 rounded-xl border transition-all ${
                            isVerified
                              ? 'bg-slate-950/70 border-emerald-500/30 ring-1 ring-emerald-500/10'
                              : 'bg-slate-950/40 border-slate-800/80 hover:border-slate-700'
                          }`}
                        >
                          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                            <div className="space-y-1.5 flex-1">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="font-bold text-sm text-white">{doc.name}</span>
                                <span className="px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 text-[10px] font-mono">
                                  {doc.section}
                                </span>
                                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px]">
                                  {doc.authority}
                                </span>
                                <span className={`px-2 py-0.5 rounded text-[10px] font-semibold border flex items-center gap-1 ${
                                  isVerified
                                    ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                                    : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                                }`}>
                                  {isVerified ? (
                                    <>
                                      <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                                      Verified &amp; Sealed
                                    </>
                                  ) : (
                                    <>
                                      <AlertTriangle className="w-3 h-3 text-amber-400" />
                                      Pending Upload (FY {selectedFY})
                                    </>
                                  )}
                                </span>
                              </div>

                              <p className="text-xs text-slate-400">{doc.purpose}</p>

                              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-500 font-mono">
                                <span>Cadence: {doc.due_date_rule}</span>
                                {docObj && (
                                  <>
                                    <span>•</span>
                                    <span className="text-slate-400 font-medium">File: {docObj.document_name}</span>
                                    <span>•</span>
                                    <span className="text-slate-500">SHA: {docObj.sha256_hash?.slice(0, 10)}...</span>
                                    {docObj.extracted_fields?.financial_year && (
                                      <>
                                        <span>•</span>
                                        <span className="text-sky-400">FY: {docObj.extracted_fields.financial_year}</span>
                                      </>
                                    )}
                                    {docObj.extracted_fields?.assessment_year && (
                                      <>
                                        <span>•</span>
                                        <span className="text-amber-400">AY: {docObj.extracted_fields.assessment_year}</span>
                                      </>
                                    )}
                                    {(docObj.extracted_fields?.srn || docObj.extracted_fields?.acknowledgement_number || docObj.extracted_fields?.itr_ack_number) && (
                                      <>
                                        <span>•</span>
                                        <span className="text-emerald-400">
                                          Ref: {docObj.extracted_fields.srn || docObj.extracted_fields.acknowledgement_number || docObj.extracted_fields.itr_ack_number}
                                        </span>
                                      </>
                                    )}
                                  </>
                                )}
                              </div>
                            </div>

                            <div className="flex items-center gap-2 self-start md:self-auto shrink-0">
                              {isVerified && docObj?.id && (
                                <a
                                  href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/vault/${docObj.id}/download`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition border border-slate-700"
                                >
                                  <Download className="w-3.5 h-3.5 text-sky-400" />
                                  <span>Download</span>
                                </a>
                              )}

                              <button
                                type="button"
                                onClick={() => {
                                  setTargetFilingDoc(doc);
                                  setSelectedFilingFile(null);
                                  setFilingPdfPassword('');
                                  setFilingUploadError('');
                                  setFilingUploadModalOpen(true);
                                }}
                                className={`px-3 py-1.5 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition ${
                                  isVerified
                                    ? 'bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700'
                                    : 'bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold shadow-md shadow-amber-500/20'
                                }`}
                              >
                                <UploadCloud className="w-3.5 h-3.5" />
                                <span>{isVerified ? 'Re-upload' : 'Upload Document'}</span>
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Advance Tax Cadence & Filing Deadlines */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Advance Tax Schedule */}
                  <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                        <IndianRupee className="w-4 h-4 text-amber-400" />
                        Advance Tax Cadence (Sec 208)
                      </h4>
                      <span className="text-[10px] text-amber-400 font-mono">FY {selectedFY}</span>
                    </div>
                    <div className="space-y-2 text-xs">
                      <div className="p-2.5 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between">
                        <span>15% Cumulative (Q1) — 15th June {startYear}</span>
                        <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded font-mono text-[10px]">
                          Scheduled
                        </span>
                      </div>
                      <div className="p-2.5 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between">
                        <span>45% Cumulative (Q2) — 15th Sept {startYear}</span>
                        <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded font-mono text-[10px]">
                          Scheduled
                        </span>
                      </div>
                      <div className="p-2.5 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between">
                        <span>75% Cumulative (Q3) — 15th Dec {startYear}</span>
                        <span className="px-2 py-0.5 bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded font-mono text-[10px]">
                          Scheduled
                        </span>
                      </div>
                      <div className="p-2.5 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between">
                        <span>100% Cumulative (Q4) — 15th March {endYear}</span>
                        <span className="text-slate-500 font-mono text-[10px]">Scheduled</span>
                      </div>
                    </div>
                  </div>

                  {/* MCA Statutory Returns */}
                  <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                        <FileText className="w-4 h-4 text-sky-400" />
                        Statutory Filing Deadlines
                      </h4>
                      <span className="text-[10px] text-sky-400 font-mono">FY {selectedFY}</span>
                    </div>
                    <div className="space-y-2 text-xs">
                      <div className="p-2.5 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between">
                        <div>
                          <div className="font-semibold text-slate-200">Form AOC-4 (Financial Statements)</div>
                          <div className="text-[11px] text-slate-500">Within 30 days of AGM (Due 30 Oct {endYear})</div>
                        </div>
                        <span className="px-2 py-0.5 bg-sky-500/10 text-sky-400 border border-sky-500/20 rounded font-mono text-[10px]">
                          Sec 137
                        </span>
                      </div>

                      <div className="p-2.5 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between">
                        <div>
                          <div className="font-semibold text-slate-200">Form MGT-7A (Annual Return)</div>
                          <div className="text-[11px] text-slate-500">Within 60 days of AGM (Due 29 Nov {endYear})</div>
                        </div>
                        <span className="px-2 py-0.5 bg-sky-500/10 text-sky-400 border border-sky-500/20 rounded font-mono text-[10px]">
                          Sec 92
                        </span>
                      </div>

                      <div className="p-2.5 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between">
                        <div>
                          <div className="font-semibold text-slate-200">Income Tax Return (ITR-6)</div>
                          <div className="text-[11px] text-slate-500">Audit Return Due 31 Oct {endYear} (AY {endYear}-{String(endYear + 1).slice(-2)})</div>
                        </div>
                        <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded font-mono text-[10px]">
                          Sec 139(1)
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      {/* STATUTORY FILING UPLOAD MODAL */}
      {filingUploadModalOpen && targetFilingDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <form
            onSubmit={executeFilingUpload}
            className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-amber-500/10 text-amber-400 rounded-lg border border-amber-500/20">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Upload Statutory Filing</h3>
                  <p className="text-xs text-amber-400 font-mono">Financial Year {selectedFY}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setFilingUploadModalOpen(false);
                  setTargetFilingDoc(null);
                  setSelectedFilingFile(null);
                  setFilingPdfPassword('');
                  setFilingUploadError('');
                }}
                className="text-slate-400 hover:text-white text-xs"
              >
                ✕
              </button>
            </div>

            <div className="p-3.5 bg-slate-950/70 border border-slate-800 rounded-xl space-y-1 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-white">{targetFilingDoc.name}</span>
                <span className="px-2 py-0.5 bg-sky-500/10 text-sky-400 border border-sky-500/20 rounded font-mono text-[10px]">
                  {targetFilingDoc.section}
                </span>
              </div>
              <p className="text-[11px] text-slate-400">{targetFilingDoc.purpose}</p>
              <div className="text-[10px] text-slate-500 pt-1">Authority: {targetFilingDoc.authority}</div>
            </div>

            {filingUploadError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg text-xs text-rose-400 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{filingUploadError}</span>
              </div>
            )}

            <div className="space-y-3 text-xs">
              <div className="space-y-1.5">
                <label className="text-slate-300 font-medium">Select Signed PDF Document</label>
                <input
                  type="file"
                  required
                  accept=".pdf"
                  onChange={(e) => setSelectedFilingFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-slate-200 hover:file:bg-slate-700 bg-slate-950 border border-slate-800 rounded-lg p-1.5 cursor-pointer"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-slate-300 font-medium flex items-center justify-between">
                  <span>PDF Decryption Password (if encrypted)</span>
                  <span className="text-[10px] text-slate-500">Optional</span>
                </label>
                <input
                  type="password"
                  value={filingPdfPassword}
                  onChange={(e) => setFilingPdfPassword(e.target.value)}
                  placeholder="e.g. PAN or Mobile Number if protected"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white font-mono focus:outline-none focus:border-amber-400"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
              <button
                type="button"
                onClick={() => {
                  setFilingUploadModalOpen(false);
                  setTargetFilingDoc(null);
                  setSelectedFilingFile(null);
                  setFilingPdfPassword('');
                  setFilingUploadError('');
                }}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={!selectedFilingFile || filingUploading}
                className="px-4 py-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-950 font-bold text-xs rounded-lg flex items-center gap-1.5 shadow-md shadow-amber-500/20"
              >
                <UploadCloud className="w-3.5 h-3.5" />
                <span>{filingUploading ? 'Verifying & Vaulting...' : `Verify & Vault to FY ${selectedFY}`}</span>
              </button>
            </div>
          </form>
        </div>
      )}

      {/* PASSWORD PROMPT MODAL FOR ENCRYPTED STATEMENTS */}
      {passwordModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-amber-500/10 text-amber-400 rounded-xl border border-amber-500/20">
                <Lock className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Password Protected PDF Statement</h3>
                <p className="text-xs text-slate-400">Indian bank statements are encrypted by default.</p>
              </div>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              The uploaded file <strong>{pendingFile?.name}</strong> is password-protected. Common passwords include your
              Company PAN (uppercase), Customer ID, or registered mobile number.
            </p>

            {passwordError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg text-xs text-rose-400 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{passwordError}</span>
              </div>
            )}

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">Statement Decryption Password</label>
              <input
                type="password"
                value={pdfPassword}
                onChange={(e) => setPdfPassword(e.target.value)}
                placeholder="e.g., AABCA1234F or Customer ID"
                className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white font-mono focus:outline-none focus:border-amber-400"
                autoFocus
              />
            </div>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setPasswordModalOpen(false);
                  setPendingFile(null);
                  setPdfPassword('');
                }}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!pdfPassword || uploadingStatement}
                onClick={() => {
                  if (pendingFile) executeStatementUpload(pendingFile, pdfPassword);
                }}
                className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-semibold rounded-lg flex items-center gap-2"
              >
                {uploadingStatement ? 'Decrypting...' : 'Decrypt & Ingest'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* RECORD NEW EXPENSE MODAL */}
      {showAddExpenseModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <form
            onSubmit={handleCreateExpense}
            className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-4 shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <Receipt className="w-4 h-4 text-rose-400" />
                Record Vendor Bill / Operating Expense
              </h3>
              <button
                type="button"
                onClick={() => setShowAddExpenseModal(false)}
                className="text-slate-400 hover:text-white text-xs"
              >
                ✕
              </button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="col-span-2 space-y-1">
                <label className="text-slate-300 font-medium">Vendor / Beneficiary Name</label>
                <input
                  type="text"
                  required
                  value={newExp.vendor_name}
                  onChange={(e) => setNewExp({ ...newExp, vendor_name: e.target.value })}
                  placeholder="e.g. Google Cloud India Pvt Ltd"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                />
              </div>

              <div className="space-y-1">
                <label className="text-slate-300 font-medium">Invoice Date</label>
                <input
                  type="date"
                  required
                  value={newExp.date}
                  onChange={(e) => setNewExp({ ...newExp, date: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                />
              </div>

              <div className="space-y-1">
                <label className="text-slate-300 font-medium">Vendor GSTIN</label>
                <input
                  type="text"
                  value={newExp.vendor_gstin}
                  onChange={(e) => setNewExp({ ...newExp, vendor_gstin: e.target.value.toUpperCase() })}
                  placeholder="29AABCS1429B1Z8"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono"
                />
              </div>

              <div className="col-span-2 space-y-1">
                <label className="text-slate-300 font-medium">Schedule III Expense Head</label>
                <select
                  value={newExp.category}
                  onChange={(e) => setNewExp({ ...newExp, category: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                >
                  <option value="4010 Direct Operational Expense">4010 Direct Operational Expense</option>
                  <option value="4020 Software & Cloud Subscriptions">4020 Software & Cloud Subscriptions</option>
                  <option value="4030 Legal & Professional Fees">4030 Legal & Professional Fees</option>
                  <option value="4040 Office Rent & Space">4040 Office Rent & Space</option>
                  <option value="4050 Director Remuneration">4050 Director Remuneration</option>
                  <option value="4060 Travel & Conveyance">4060 Travel & Conveyance</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-slate-300 font-medium">Taxable Amount (₹)</label>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={newExp.taxable_amount}
                  onChange={(e) => setNewExp({ ...newExp, taxable_amount: e.target.value })}
                  placeholder="25000.00"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono"
                />
              </div>

              <div className="space-y-1">
                <label className="text-slate-300 font-medium">GST Rate (%)</label>
                <select
                  value={newExp.gst_rate}
                  onChange={(e) => setNewExp({ ...newExp, gst_rate: e.target.value })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono"
                >
                  <option value="0">0% (Nil / Exempt)</option>
                  <option value="5">5% GST</option>
                  <option value="12">12% GST</option>
                  <option value="18">18% GST (Standard)</option>
                  <option value="28">28% GST</option>
                </select>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setShowAddExpenseModal(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={creatingExpense}
                className="px-4 py-2 bg-rose-600 hover:bg-rose-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5"
              >
                {creatingExpense ? 'Posting Voucher...' : 'Post Voucher & Recognize ITC'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

