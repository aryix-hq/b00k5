'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import {
  Receipt,
  Plus,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  Clock,
  UserCheck,
  ShieldCheck,
  Edit2,
  Trash2,
  History,
  Building2,
  DollarSign,
  ArrowRight,
  X,
  FileText,
  Download,
  Search,
  Filter,
  XCircle,
  Ban,
  UploadCloud,
  Calendar
} from 'lucide-react';
import { fetchApi } from '@/lib/api';
import { BatchDropzone } from '@/components/upload/BatchDropzone';

const STANDARD_EXPENSE_CATEGORIES = [
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

function getExpenseFY(dateStr?: string): string {
  if (!dateStr) return 'N/A';
  const clean = dateStr.split('T')[0];
  const parts = clean.split('-');
  if (parts.length < 3) return 'N/A';
  const year = parseInt(parts[0], 10);
  const month = parseInt(parts[1], 10);
  if (isNaN(year) || isNaN(month)) return 'N/A';
  if (month >= 4) {
    return `FY ${year}-${String(year + 1).slice(-2)}`;
  } else {
    return `FY ${year - 1}-${String(year).slice(-2)}`;
  }
}

function matchFY(itemFY: string, selectedPeriod: string): boolean {
  if (!selectedPeriod || selectedPeriod === 'all') return true;
  const cleanSel = selectedPeriod.replace(/[^0-9]/g, '');
  const cleanItem = itemFY.replace(/[^0-9]/g, '');
  if (cleanSel.startsWith('2025') && cleanItem.startsWith('2025')) return true;
  if (cleanSel.startsWith('2026') && cleanItem.startsWith('2026')) return true;
  if (cleanSel.startsWith('2024') && cleanItem.startsWith('2024')) return true;
  return cleanSel === cleanItem;
}

interface ExpenseItem {
  id: string;
  merchant_name: string;
  expense_date: string;
  category: string;
  total_amount: number;
  payment_mode: string;
  paid_personally: boolean;
  director_name?: string;
  merchant_gstin?: string;
  status: string;
  settlement_status: string;
  itc_eligible: boolean;
  igst_amount: number;
  journal_entry_number?: string;
  created_at?: string;
  notes?: string;
}

interface SummaryData {
  total_expenses_count: number;
  total_expenses_amount: number;
  personal_out_of_pocket_count: number;
  personal_out_of_pocket_amount: number;
  pending_personal_count: number;
  pending_personal_amount: number;
  director_payable_balance: number;
  total_itc_claimed_on_personal: number;
  dpt3_deemed_deposit_warning: boolean;
  company_bank_expenses_count: number;
  company_bank_expenses_amount: number;
}

interface AuditLogEntry {
  id: string;
  action: string;
  field_changes: Record<string, any>;
  reason: string;
  created_at: string;
  changed_by_name: string;
  changed_by_email: string;
}

export default function ExpensesHubPage() {
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [expenses, setExpenses] = useState<ExpenseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'personal' | 'pending' | 'company' | 'all' | 'struck_off'>('personal');
  const [selectedFY, setSelectedFY] = useState<string>('all');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [exportingAuditor, setExportingAuditor] = useState(false);
  const [batchUploadModalOpen, setBatchUploadModalOpen] = useState(false);
  const [notification, setNotification] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  // Audit Logs State
  const [selectedExpenseForAudit, setSelectedExpenseForAudit] = useState<ExpenseItem | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);

  // Edit Expense State
  const [editExpense, setEditExpense] = useState<ExpenseItem | null>(null);
  const [editMerchant, setEditMerchant] = useState('');
  const [editAmount, setEditAmount] = useState('');
  const [editCategory, setEditCategory] = useState('');
  const [isEditCustomCategory, setIsEditCustomCategory] = useState(false);
  const [editDate, setEditDate] = useState('');
  const [editPaidPersonally, setEditPaidPersonally] = useState(false);
  const [editDirectorName, setEditDirectorName] = useState('Vikram');
  const [editNotes, setEditNotes] = useState('');
  const [editReason, setEditReason] = useState('');
  const [submittingEdit, setSubmittingEdit] = useState(false);

  // Strike-off Expense State
  const [strikeOffItem, setStrikeOffItem] = useState<ExpenseItem | null>(null);
  const [strikeOffReason, setStrikeOffReason] = useState('Misclassified or voided transaction per statutory review');
  const [submittingStrikeOff, setSubmittingStrikeOff] = useState(false);

  // Settlement Modal State
  const [settlementOpen, setSettlementOpen] = useState(false);
  const [settleAmount, setSettleAmount] = useState('0');
  const [settleDirector, setSettleDirector] = useState('Vikram');
  const [settleRef, setSettleRef] = useState('NEFT-FOUNDER-SETTLE');
  const [submittingSettle, setSubmittingSettle] = useState(false);
  const [syncingGL, setSyncingGL] = useState(false);

  const handleSyncGL = async () => {
    setSyncingGL(true);
    try {
      const res = await fetchApi('/api/v1/expenses/sync-gl', { method: 'POST' });
      setNotification({
        type: 'success',
        message: `General Ledger fully synchronized! ${res.total_expenses || 0} expense vouchers verified and balanced 1:1 with General Ledger.`
      });
      await loadData();
    } catch (err: any) {
      setNotification({ type: 'error', message: err.message || 'Failed to sync with General Ledger' });
    } finally {
      setSyncingGL(false);
    }
  };

  async function loadData() {
    setLoading(true);
    try {
      const [sumRes, expRes] = await Promise.all([
        fetchApi('/api/v1/expenses/summary').catch(() => null),
        fetchApi('/api/v1/expenses').catch(() => [])
      ]);
      if (sumRes) setSummary(sumRes);
      if (expRes && Array.isArray(expRes)) setExpenses(expRes);
    } catch (e: any) {
      console.error('Error fetching expenses:', e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('b00k5_selected_fy');
      if (stored) setSelectedFY(stored);

      const onFYChanged = (e: any) => {
        if (e.detail) setSelectedFY(e.detail);
      };
      window.addEventListener('b00k5_fy_changed', onFYChanged);
      return () => window.removeEventListener('b00k5_fy_changed', onFYChanged);
    }
  }, []);

  const handleExportAuditorDossier = async () => {
    setExportingAuditor(true);
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = typeof window !== 'undefined' ? localStorage.getItem('b00k5_tenant_id') : null;
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/expenses/export-auditor-package`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
        }
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to generate auditor package');
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Auditor_Dossier_FY2025-26.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      setNotification({
        type: 'success',
        message: 'Statutory Auditor Dossier (.zip) exported successfully with ledgers & source receipts.'
      });
    } catch (err: any) {
      setNotification({ type: 'error', message: err.message || 'Error exporting auditor package' });
    } finally {
      setExportingAuditor(false);
    }
  };

  const openAuditLogs = async (item: ExpenseItem) => {
    setSelectedExpenseForAudit(item);
    setLoadingAudit(true);
    try {
      const logs = await fetchApi(`/api/v1/expenses/${item.id}/audit-logs`);
      setAuditLogs(Array.isArray(logs) ? logs : []);
    } catch (e: any) {
      setAuditLogs([]);
    } finally {
      setLoadingAudit(false);
    }
  };

  const openEditModal = (item: ExpenseItem) => {
    setEditExpense(item);
    setEditMerchant(item.merchant_name || '');
    setEditAmount(String(item.total_amount || ''));
    const isStandard = STANDARD_EXPENSE_CATEGORIES.includes(item.category);
    setEditCategory(item.category || STANDARD_EXPENSE_CATEGORIES[0]);
    setIsEditCustomCategory(!isStandard && Boolean(item.category));
    setEditDate(item.expense_date ? item.expense_date.split('T')[0] : '');
    setEditPaidPersonally(Boolean(item.paid_personally));
    setEditDirectorName(item.director_name || 'Vikram');
    setEditNotes(item.notes || '');
    setEditReason('');
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editExpense) return;
    if (!editReason.trim()) {
      alert('Statutory Rule 3 requires an explanation/reason for modifying an accounting record.');
      return;
    }
    setSubmittingEdit(true);
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = typeof window !== 'undefined' ? localStorage.getItem('b00k5_tenant_id') : null;
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/expenses/${editExpense.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
        },
        body: JSON.stringify({
          merchant_name: editMerchant,
          total_amount: parseFloat(editAmount) || editExpense.total_amount,
          category: editCategory,
          expense_date: editDate || undefined,
          paid_personally: editPaidPersonally,
          director_name: editDirectorName,
          notes: editNotes,
          edit_reason: editReason
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to update expense');
      setNotification({ type: 'success', message: 'Expense modified successfully with MCA Sec 128 audit trail.' });
      setEditExpense(null);
      await loadData();
    } catch (err: any) {
      setNotification({ type: 'error', message: err.message || 'Error updating expense' });
    } finally {
      setSubmittingEdit(false);
    }
  };

  const handleConfirmStrikeOff = async () => {
    if (!strikeOffItem) return;
    setSubmittingStrikeOff(true);
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = typeof window !== 'undefined' ? localStorage.getItem('b00k5_tenant_id') : null;
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/expenses/${strikeOffItem.id}?reason=${encodeURIComponent(strikeOffReason)}`,
        {
          method: 'DELETE',
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
          }
        }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to strike off expense');
      setNotification({
        type: 'success',
        message: `Expense struck off per MCA rules. Reversal voucher ${data.reversal_journal_entry || ''} posted to General Ledger.`
      });
      setStrikeOffItem(null);
      await loadData();
    } catch (err: any) {
      setNotification({ type: 'error', message: err.message || 'Error striking off expense' });
    } finally {
      setSubmittingStrikeOff(false);
    }
  };

  const handleFounderSettlement = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmittingSettle(true);
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = typeof window !== 'undefined' ? localStorage.getItem('b00k5_tenant_id') : null;
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/expenses/settle-reimbursement`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
        },
        body: JSON.stringify({
          director_name: settleDirector,
          settlement_amount: parseFloat(settleAmount) || 0,
          bank_account_code: '1010',
          reference_number: settleRef
        })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Settlement failed');
      setNotification({
        type: 'success',
        message: `Settled ₹${data.settled_amount?.toLocaleString('en-IN')} via ${data.entry_number}. Account 2105 balance: ₹${data.director_payable_balance?.toLocaleString('en-IN')}`
      });
      setSettlementOpen(false);
      await loadData();
    } catch (err: any) {
      setNotification({ type: 'error', message: err.message || 'Settlement transaction failed' });
    } finally {
      setSubmittingSettle(false);
    }
  };

  // Derive unique categories present in expenses for the filter dropdown
  const availableCategories = Array.from(
    new Set([...STANDARD_EXPENSE_CATEGORIES, ...expenses.map((e) => e.category).filter(Boolean)])
  );

  // Filtered List based on tab, category, FY, and search query
  const filteredExpenses = expenses.filter((item) => {
    const isStruckOff =
      item.status === 'struck_off' || item.status === 'rejected' || item.settlement_status === 'voided';

    if (activeTab === 'struck_off') {
      if (!isStruckOff) return false;
    } else {
      if (isStruckOff) return false;
      if (activeTab === 'personal' && !item.paid_personally) return false;
      if (activeTab === 'pending' && (!item.paid_personally || item.settlement_status !== 'pending')) return false;
      if (activeTab === 'company' && item.paid_personally) return false;
    }

    // Filter by Financial Year
    if (selectedFY !== 'all') {
      const itemFY = getExpenseFY(item.expense_date);
      if (!matchFY(itemFY, selectedFY)) {
        return false;
      }
    }

    if (categoryFilter !== 'all' && item.category !== categoryFilter) {
      return false;
    }

    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      const matchMerchant = item.merchant_name?.toLowerCase().includes(q);
      const matchCategory = item.category?.toLowerCase().includes(q);
      const matchGstin = item.merchant_gstin?.toLowerCase().includes(q);
      const matchJv = item.journal_entry_number?.toLowerCase().includes(q);
      const matchDirector = item.director_name?.toLowerCase().includes(q);
      if (!matchMerchant && !matchCategory && !matchGstin && !matchJv && !matchDirector) {
        return false;
      }
    }

    return true;
  });

  // Dynamically computed metrics scoped to selected FY filter
  const activeFYExpenses = expenses.filter((e) => {
    if (selectedFY === 'all') return true;
    return matchFY(getExpenseFY(e.expense_date), selectedFY);
  });
  const fyPersonalOutOfPocket = activeFYExpenses.filter((e) => e.paid_personally && e.status !== 'struck_off');
  const fyPendingPersonal = activeFYExpenses.filter((e) => e.paid_personally && e.settlement_status === 'pending' && e.status !== 'struck_off');
  const fyCompanyBank = activeFYExpenses.filter((e) => !e.paid_personally && e.status !== 'struck_off');

  const displayPendingAmount = selectedFY === 'all'
    ? (summary?.pending_personal_amount || 0)
    : fyPendingPersonal.reduce((acc, e) => acc + (Number(e.total_amount) || 0), 0);
  const displayPendingCount = selectedFY === 'all'
    ? (summary?.pending_personal_count || 0)
    : fyPendingPersonal.length;

  const displayPersonalCount = selectedFY === 'all'
    ? (summary?.personal_out_of_pocket_count || 0)
    : fyPersonalOutOfPocket.length;
  const displayCompanyCount = selectedFY === 'all'
    ? (summary?.company_bank_expenses_count || 0)
    : fyCompanyBank.length;
  const displayAllActiveCount = activeFYExpenses.filter((x) => x.status !== 'struck_off' && x.status !== 'rejected').length;

  const struckOffCount = expenses.filter(
    (x) => x.status === 'struck_off' || x.status === 'rejected' || x.settlement_status === 'voided'
  ).length;

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Navbar />

        <main className="p-8 space-y-6 max-w-7xl mx-auto w-full">
          {/* Header */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800/60">
                  MCA Rule 3 / Section 128 Audit Trail Compliant
                </span>
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800/60">
                  Account 2105 Out-of-Pocket Ledger
                </span>
              </div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2 mt-1">
                <Receipt className="w-6 h-6 text-emerald-400" />
                Expenses &amp; Founder Reimbursements Workbench
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Track corporate bills, out-of-pocket director expenses, statutory ITC claims, strike-offs, and immutable edit logs.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={handleSyncGL}
                disabled={syncingGL}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-emerald-400 hover:text-emerald-300 text-xs font-semibold rounded-lg flex items-center gap-2 border border-emerald-500/30 shadow-sm transition disabled:opacity-50"
                title="Synchronize all expenses and founder claims 1:1 with General Ledger double-entry vouchers"
              >
                <RefreshCw className={`w-4 h-4 ${syncingGL ? 'animate-spin' : ''}`} />
                {syncingGL ? 'Syncing with GL...' : 'Sync with General Ledger'}
              </button>

              <button
                onClick={handleExportAuditorDossier}
                disabled={exportingAuditor}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-sky-300 hover:text-sky-200 text-xs font-semibold rounded-lg flex items-center gap-2 border border-sky-800/60 shadow-sm transition disabled:opacity-50"
                title="Download complete external CA auditor package with CSV ledgers and original PDFs"
              >
                <Download className="w-4 h-4 text-sky-400" />
                {exportingAuditor ? 'Exporting Package...' : 'Export Auditor Dossier (.zip)'}
              </button>

              <button
                onClick={() => {
                  setSettleAmount(String(summary?.director_payable_balance || 0));
                  setSettlementOpen(true);
                }}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg flex items-center gap-2 border border-slate-700 transition"
              >
                <DollarSign className="w-4 h-4 text-emerald-400" />
                Settle Reimbursement
              </button>

              <button
                onClick={() => setBatchUploadModalOpen(true)}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 shadow-sm transition"
              >
                <UploadCloud className="w-4 h-4" />
                Batch Ingest Receipts (50 max)
              </button>

              <Link
                href="/expenses/new"
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 shadow-sm transition"
              >
                <Plus className="w-4 h-4" />
                Record New Expense / Bill
              </Link>
            </div>
          </div>

          {notification && (
            <div
              className={`p-4 rounded-xl text-xs flex items-center justify-between ${
                notification.type === 'success'
                  ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
                  : 'bg-rose-500/10 border border-rose-500/30 text-rose-400'
              }`}
            >
              <div className="flex items-center gap-2">
                {notification.type === 'success' ? (
                  <CheckCircle2 className="w-4 h-4" />
                ) : (
                  <AlertTriangle className="w-4 h-4" />
                )}
                <span>{notification.message}</span>
              </div>
              <button onClick={() => setNotification(null)} className="text-slate-400 hover:text-white">
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Telemetry Summary Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Total Paid Personally (Founder Out of Pocket) */}
            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
              <span className="text-xs text-slate-400 font-medium flex items-center gap-1.5">
                <UserCheck className="w-4 h-4 text-sky-400" /> Paid Personally by Founder
              </span>
              <div className="text-2xl font-bold text-white font-mono">
                ₹{(summary?.personal_out_of_pocket_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <p className="text-[11px] text-sky-400">
                {summary?.personal_out_of_pocket_count || 0} bills paid from personal account
              </p>
            </div>

            {/* Account 2105 Balance (Payable to Director) */}
            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
              <span className="text-xs text-slate-400 font-medium flex items-center gap-1.5">
                <Building2 className="w-4 h-4 text-amber-400" /> Account 2105 Liability
              </span>
              <div className="text-2xl font-bold text-amber-400 font-mono">
                ₹{(summary?.director_payable_balance || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <p className="text-[11px] text-slate-400">
                {summary?.dpt3_deemed_deposit_warning ? (
                  <span className="text-amber-400 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" /> Rule 2(1)(c)(viii) DPT-3 Alert
                  </span>
                ) : (
                  'Reimbursements payable balance'
                )}
              </p>
            </div>

            {/* Pending Reimbursement Claims */}
            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
              <span className="text-xs text-slate-400 font-medium flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-emerald-400" /> Pending Reimbursements
              </span>
              <div className="text-2xl font-bold text-emerald-400 font-mono">
                ₹{displayPendingAmount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <p className="text-[11px] text-slate-400">
                {displayPendingCount} claims awaiting bank payout
              </p>
            </div>

            {/* Total ITC Input Credit Saved */}
            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
              <span className="text-xs text-slate-400 font-medium flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-400" /> ITC Input Credit Claimed
              </span>
              <div className="text-2xl font-bold text-white font-mono">
                ₹{(summary?.total_itc_claimed_on_personal || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </div>
              <p className="text-[11px] text-emerald-400">GST verified &amp; offset against output tax</p>
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="flex border-b border-slate-800 gap-6 text-xs">
            <button
              onClick={() => setActiveTab('personal')}
              className={`pb-3 font-semibold transition flex items-center gap-2 border-b-2 ${
                activeTab === 'personal'
                  ? 'border-sky-500 text-sky-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <UserCheck className="w-4 h-4" />
              Paid from Personal Account ({displayPersonalCount})
            </button>
            <button
              onClick={() => setActiveTab('pending')}
              className={`pb-3 font-semibold transition flex items-center gap-2 border-b-2 ${
                activeTab === 'pending'
                  ? 'border-amber-500 text-amber-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Clock className="w-4 h-4" />
              Pending Reimbursement ({displayPendingCount})
            </button>
            <button
              onClick={() => setActiveTab('company')}
              className={`pb-3 font-semibold transition flex items-center gap-2 border-b-2 ${
                activeTab === 'company'
                  ? 'border-emerald-500 text-emerald-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Building2 className="w-4 h-4" />
              Company Bank Paid ({displayCompanyCount})
            </button>
            <button
              onClick={() => setActiveTab('all')}
              className={`pb-3 font-semibold transition flex items-center gap-2 border-b-2 ${
                activeTab === 'all'
                  ? 'border-slate-300 text-white'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              All Active Expenses ({displayAllActiveCount})
            </button>
            <button
              onClick={() => setActiveTab('struck_off')}
              className={`pb-3 font-semibold transition flex items-center gap-2 border-b-2 ${
                activeTab === 'struck_off'
                  ? 'border-rose-500 text-rose-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <XCircle className="w-4 h-4" />
              Struck Off / Cancelled ({struckOffCount})
            </button>
          </div>

          {/* Filter Bar: Category & Search */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3 bg-slate-900 border border-slate-800 rounded-xl text-xs">
            <div className="flex flex-1 items-center gap-2 bg-slate-950 px-3 py-2 rounded-lg border border-slate-800">
              <Search className="w-4 h-4 text-slate-500 shrink-0" />
              <input
                type="text"
                placeholder="Search merchant, category, GSTIN, voucher..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-transparent text-white placeholder-slate-500 focus:outline-none w-full text-xs"
              />
              {searchTerm && (
                <button onClick={() => setSearchTerm('')} className="text-slate-500 hover:text-white">
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>

            <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
              {/* Financial Year Period Switcher */}
              <div className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs">
                <Calendar className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                <span className="text-slate-400 font-medium whitespace-nowrap">Period:</span>
                <select
                  value={selectedFY}
                  onChange={(e) => setSelectedFY(e.target.value)}
                  className="bg-transparent text-amber-300 font-mono font-bold focus:outline-none cursor-pointer"
                >
                  <option value="all" className="bg-slate-900 text-white">All Financial Years</option>
                  <option value="FY 2026-2027" className="bg-slate-900 text-white">FY 2026-27 (Active Period)</option>
                  <option value="FY 2025-2026" className="bg-slate-900 text-white">FY 2025-26 (Audited Period)</option>
                  <option value="FY 2024-2025" className="bg-slate-900 text-white">FY 2024-25</option>
                </select>
              </div>

              <span className="text-slate-400 flex items-center gap-1 font-medium whitespace-nowrap">
                <Filter className="w-3.5 h-3.5 text-slate-500" /> Category:
              </span>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white text-xs max-w-xs focus:ring-1 focus:ring-sky-500"
              >
                <option value="all">All Categories</option>
                {availableCategories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>

              <button
                onClick={loadData}
                title="Refresh Table"
                className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Expenses Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
            {loading ? (
              <div className="p-12 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                <RefreshCw className="w-4 h-4 animate-spin text-sky-400" />
                <span>Loading ledger transactions...</span>
              </div>
            ) : filteredExpenses.length === 0 ? (
              <div className="p-12 text-center text-xs text-slate-500 space-y-3">
                <Receipt className="w-8 h-8 text-slate-600 mx-auto" />
                <p>No expenses found in this view.</p>
                <Link
                  href="/expenses/new"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded text-xs font-semibold transition"
                >
                  <Plus className="w-3.5 h-3.5" /> Record Expense Now
                </Link>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950/60 border-b border-slate-800 text-slate-400 font-mono text-[11px] uppercase">
                    <tr>
                      <th className="py-3 px-4">Date</th>
                      <th className="py-3 px-4">Merchant / Bill</th>
                      <th className="py-3 px-4">Category</th>
                      <th className="py-3 px-4">Payment &amp; Payee</th>
                      <th className="py-3 px-4 text-right">Amount (₹)</th>
                      <th className="py-3 px-4">ITC Status</th>
                      <th className="py-3 px-4">Settlement</th>
                      <th className="py-3 px-4">Voucher (JV)</th>
                      <th className="py-3 px-4 text-right">MCA Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-sans">
                    {filteredExpenses.map((item) => {
                      const isStruckOff =
                        item.status === 'struck_off' ||
                        item.status === 'rejected' ||
                        item.settlement_status === 'voided';

                      return (
                        <tr
                          key={item.id}
                          className={`hover:bg-slate-800/40 transition ${
                            isStruckOff ? 'bg-rose-950/10 opacity-70' : ''
                          }`}
                        >
                          <td className="py-3.5 px-4 font-mono text-slate-300 whitespace-nowrap">
                            <div>{item.expense_date ? new Date(item.expense_date).toLocaleDateString('en-IN') : 'N/A'}</div>
                            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-sky-400 border border-slate-700/60 inline-block mt-0.5">
                              {getExpenseFY(item.expense_date)}
                            </span>
                          </td>
                          <td className="py-3.5 px-4 font-semibold">
                            <div className={isStruckOff ? 'line-through text-slate-400' : 'text-white'}>
                              {item.merchant_name}
                            </div>
                            {item.merchant_gstin && (
                              <span className="text-[10px] font-mono text-slate-400">
                                GSTIN: {item.merchant_gstin}
                              </span>
                            )}
                            {isStruckOff && item.notes && (
                              <div className="text-[10px] text-rose-400 font-normal italic mt-0.5">
                                {item.notes}
                              </div>
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-slate-300">
                            <span
                              className={`px-2 py-0.5 rounded text-[11px] ${
                                isStruckOff
                                  ? 'bg-rose-950/30 text-rose-400 border border-rose-900 line-through'
                                  : 'bg-slate-800 border border-slate-700/60 text-slate-300'
                              }`}
                            >
                              {item.category}
                            </span>
                          </td>
                          <td className="py-3.5 px-4">
                            {item.paid_personally ? (
                              <div className="space-y-0.5">
                                <span className="px-2 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800/60 text-[10px] font-semibold inline-flex items-center gap-1">
                                  <UserCheck className="w-3 h-3" /> Founder Paid ({item.director_name || 'Vikram'})
                                </span>
                                <div className="text-[10px] text-slate-500 font-mono">Liability Account 2105</div>
                              </div>
                            ) : (
                              <div className="space-y-0.5">
                                <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800/60 text-[10px] font-semibold inline-flex items-center gap-1">
                                  <Building2 className="w-3 h-3" /> Company Bank Account
                                </span>
                                <div className="text-[10px] text-slate-500 font-mono">Account 1010</div>
                              </div>
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-right font-mono font-bold whitespace-nowrap">
                            <span className={isStruckOff ? 'line-through text-rose-400' : 'text-white'}>
                              ₹{Number(item.total_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                            </span>
                          </td>
                          <td className="py-3.5 px-4">
                            {isStruckOff ? (
                              <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30 text-[10px] font-medium">
                                Reversed / Struck Off
                              </span>
                            ) : item.itc_eligible ? (
                              <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[10px] font-medium">
                                Eligible (₹{Number(item.igst_amount || 0).toFixed(0)})
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-[10px]">
                                Ineligible
                              </span>
                            )}
                          </td>
                          <td className="py-3.5 px-4">
                            {isStruckOff ? (
                              <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/30 text-[10px] font-medium">
                                Struck Off (Cancelled)
                              </span>
                            ) : item.settlement_status === 'settled' || item.status === 'reimbursed' ? (
                              <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[10px] font-medium">
                                Discharged
                              </span>
                            ) : (
                              <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30 text-[10px] font-medium">
                                Pending Payout
                              </span>
                            )}
                          </td>
                          <td className="py-3.5 px-4 font-mono text-[11px] whitespace-nowrap">
                            {item.journal_entry_number ? (
                              <Link
                                href={`/reports/general-ledger?entry=${item.journal_entry_number}`}
                                className="text-sky-400 hover:text-sky-300 hover:underline inline-flex items-center gap-1 font-semibold"
                                title="View balanced journal voucher in General Ledger"
                              >
                                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                                <span>{item.journal_entry_number}</span>
                              </Link>
                            ) : (
                              <span className="text-amber-400/80 text-[10px] font-sans">Pending GL Post</span>
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-right whitespace-nowrap space-x-1">
                            <button
                              onClick={() => openAuditLogs(item)}
                              title="View MCA Section 128 Audit Trail"
                              className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-sky-400 transition"
                            >
                              <History className="w-4 h-4" />
                            </button>
                            {!isStruckOff && (
                              <>
                                <button
                                  onClick={() => openEditModal(item)}
                                  title="Edit Expense with Audit Log"
                                  className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-amber-400 transition"
                                >
                                  <Edit2 className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => {
                                    setStrikeOffItem(item);
                                    setStrikeOffReason('Cancelled / reversed per statutory review');
                                  }}
                                  title="Strike Off Expense (MCA Section 128 & Rule 3 Reversal)"
                                  className="p-1.5 rounded hover:bg-rose-950 text-slate-400 hover:text-rose-400 transition"
                                >
                                  <Ban className="w-4 h-4" />
                                </button>
                              </>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Edit Expense Modal */}
          {editExpense && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
              <div className="bg-slate-900 border border-slate-700 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden p-6 space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <Edit2 className="w-5 h-5 text-amber-400" />
                    <h3 className="text-sm font-bold text-white">Edit Expense &amp; Record Audit Trail</h3>
                  </div>
                  <button onClick={() => setEditExpense(null)} className="text-slate-400 hover:text-white">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <form onSubmit={handleSaveEdit} className="space-y-4 text-xs">
                  <div>
                    <label className="text-slate-300 font-medium block mb-1">Merchant / Supplier Name:</label>
                    <input
                      type="text"
                      required
                      value={editMerchant}
                      onChange={(e) => setEditMerchant(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-medium"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">Total Amount (₹):</label>
                      <input
                        type="number"
                        step="0.01"
                        required
                        value={editAmount}
                        onChange={(e) => setEditAmount(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
                      />
                    </div>
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">Expense Date:</label>
                      <input
                        type="date"
                        value={editDate}
                        onChange={(e) => setEditDate(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <label className="text-slate-300 font-medium">Expense Category:</label>
                      <button
                        type="button"
                        onClick={() => setIsEditCustomCategory(!isEditCustomCategory)}
                        className="text-[11px] text-sky-400 hover:text-sky-300"
                      >
                        {isEditCustomCategory ? 'Select from standard categories' : '+ Custom Category'}
                      </button>
                    </div>
                    {isEditCustomCategory ? (
                      <input
                        type="text"
                        required
                        placeholder="e.g. SaaS Subscriptions, Legal & Compliance"
                        value={editCategory}
                        onChange={(e) => setEditCategory(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
                      />
                    ) : (
                      <select
                        value={editCategory}
                        onChange={(e) => setEditCategory(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
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
                    <label className="text-slate-300 font-medium block mb-1">Notes / Narration:</label>
                    <input
                      type="text"
                      placeholder="Optional notes or invoice reference"
                      value={editNotes}
                      onChange={(e) => setEditNotes(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
                    />
                  </div>

                  <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editPaidPersonally}
                        onChange={(e) => setEditPaidPersonally(e.target.checked)}
                        className="rounded border-slate-700 text-sky-600 focus:ring-sky-500"
                      />
                      <span className="text-white font-medium">Paid from Personal Account (Founder Out-of-Pocket)</span>
                    </label>
                    {editPaidPersonally && (
                      <div className="pt-2">
                        <label className="text-slate-400 block mb-1">Director Payee Name:</label>
                        <input
                          type="text"
                          value={editDirectorName}
                          onChange={(e) => setEditDirectorName(e.target.value)}
                          className="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1.5 text-white"
                        />
                      </div>
                    )}
                  </div>

                  <div className="p-3 bg-amber-950/30 border border-amber-800/60 rounded-xl space-y-2">
                    <label className="text-amber-300 font-semibold block">
                      Statutory Edit Explanation (Mandatory for MCA Section 128 Audit Trail):
                    </label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Corrected supplier GSTIN and rectified gross invoice total"
                      value={editReason}
                      onChange={(e) => setEditReason(e.target.value)}
                      className="w-full bg-slate-950 border border-amber-700/80 rounded px-3 py-2 text-white placeholder-slate-500"
                    />
                  </div>

                  <div className="flex gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => setEditExpense(null)}
                      className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold rounded-lg transition"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={submittingEdit}
                      className="flex-1 py-2 bg-amber-600 hover:bg-amber-500 disabled:bg-slate-800 text-white font-semibold rounded-lg transition flex items-center justify-center gap-2"
                    >
                      {submittingEdit ? 'Saving Revision...' : 'Save & Log Revision'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Strike Off Expense Confirmation Modal */}
          {strikeOffItem && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
              <div className="bg-slate-900 border border-rose-800/60 w-full max-w-md rounded-2xl shadow-2xl overflow-hidden p-6 space-y-4">
                <div className="flex items-center gap-2 text-rose-400 pb-2 border-b border-slate-800">
                  <Ban className="w-5 h-5 shrink-0" />
                  <h3 className="text-sm font-bold text-white">Strike Off Expense Record</h3>
                </div>

                <div className="p-3.5 bg-rose-950/40 border border-rose-900 text-rose-300 rounded-xl text-xs space-y-2">
                  <p className="font-semibold text-rose-200">Statutory Notice (MCA Section 128 &amp; Rule 3):</p>
                  <p>
                    Per statutory rules, accounting entries cannot be deleted. Striking off will permanently mark this expense
                    as struck off/cancelled, post a reversing voucher{' '}
                    <span className="font-mono text-white">
                      JV-REV-{strikeOffItem.journal_entry_number || 'EXP'}
                    </span>{' '}
                    to the General Ledger, and log an immutable audit event in the company audit trail.
                  </p>
                </div>

                <div className="text-xs space-y-2">
                  <label className="text-slate-300 font-medium block">Reason for Striking Off / Reversal:</label>
                  <input
                    type="text"
                    required
                    value={strikeOffReason}
                    onChange={(e) => setStrikeOffReason(e.target.value)}
                    placeholder="e.g. Disputed charge, vendor refund, duplicate voucher entry"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
                  />
                </div>

                <div className="flex gap-3 pt-2">
                  <button
                    type="button"
                    onClick={() => setStrikeOffItem(null)}
                    className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold rounded-lg text-xs transition"
                  >
                    Keep Expense
                  </button>
                  <button
                    type="button"
                    onClick={handleConfirmStrikeOff}
                    disabled={submittingStrikeOff}
                    className="flex-1 py-2 bg-rose-600 hover:bg-rose-500 disabled:bg-slate-800 text-white font-semibold rounded-lg text-xs transition flex items-center justify-center gap-2"
                  >
                    {submittingStrikeOff ? 'Striking Off & Reversing...' : 'Strike Off & Post Reversal'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Audit Trail Drawer / Modal */}
          {selectedExpenseForAudit && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
              <div className="bg-slate-900 border border-slate-700 w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden p-6 space-y-4 max-h-[85vh] flex flex-col">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800 shrink-0">
                  <div className="flex items-center gap-2">
                    <History className="w-5 h-5 text-sky-400" />
                    <div>
                      <h3 className="text-sm font-bold text-white">MCA Section 128 Audit Trail &amp; Edit Logs</h3>
                      <p className="text-[11px] text-slate-400">
                        {selectedExpenseForAudit.merchant_name} (₹{Number(selectedExpenseForAudit.total_amount).toLocaleString('en-IN')})
                      </p>
                    </div>
                  </div>
                  <button onClick={() => setSelectedExpenseForAudit(null)} className="text-slate-400 hover:text-white">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="flex-1 overflow-y-auto space-y-3 pr-1 text-xs">
                  {loadingAudit ? (
                    <div className="py-12 text-center text-slate-500 flex items-center justify-center gap-2">
                      <RefreshCw className="w-4 h-4 animate-spin text-sky-400" />
                      <span>Fetching audit chain...</span>
                    </div>
                  ) : auditLogs.length === 0 ? (
                    <div className="py-12 text-center text-slate-500">
                      No prior edit history found for this transaction.
                    </div>
                  ) : (
                    auditLogs.map((log) => (
                      <div key={log.id} className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl space-y-2">
                        <div className="flex items-center justify-between">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${
                              log.action === 'CREATED'
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                                : log.action === 'STRUCK_OFF' || log.action === 'VOIDED'
                                ? 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                                : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                            }`}
                          >
                            {log.action}
                          </span>
                          <span className="text-[10px] font-mono text-slate-500">
                            {log.created_at ? new Date(log.created_at).toLocaleString('en-IN') : 'N/A'}
                          </span>
                        </div>

                        <div className="text-slate-300">
                          <span className="text-slate-400">Author:</span>{' '}
                          <strong className="text-white">{log.changed_by_name}</strong>
                          <span className="text-slate-500 ml-1">({log.changed_by_email})</span>
                        </div>

                        {log.reason && (
                          <div className="text-sky-300 bg-sky-950/30 border border-sky-800/40 p-2 rounded text-[11px]">
                            💬 <span className="text-slate-400">Reason:</span> {log.reason}
                          </div>
                        )}

                        {log.field_changes && Object.keys(log.field_changes).length > 0 && (
                          <div className="bg-slate-900 p-2.5 rounded border border-slate-800/80 font-mono text-[11px] space-y-1">
                            <span className="text-slate-400 block font-sans font-semibold text-[10px] uppercase">
                              Modified Fields Diff:
                            </span>
                            {Object.entries(log.field_changes).map(([field, diff]: [string, any]) => (
                              <div key={field} className="flex items-center gap-2">
                                <span className="text-amber-400">{field}:</span>
                                {typeof diff === 'object' && diff !== null && 'old' in diff ? (
                                  <span className="text-slate-300">
                                    <span className="line-through text-rose-400">{String(diff.old)}</span>
                                    <span className="mx-1 text-slate-500">➔</span>
                                    <span className="text-emerald-400 font-bold">{String(diff.new)}</span>
                                  </span>
                                ) : (
                                  <span className="text-slate-300">{JSON.stringify(diff)}</span>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>

                <div className="pt-2 border-t border-slate-800 flex justify-end">
                  <button
                    onClick={() => setSelectedExpenseForAudit(null)}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold"
                  >
                    Close Audit Trail
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Settle Founder Reimbursement Modal */}
          {settlementOpen && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
              <div className="bg-slate-900 border border-slate-700 w-full max-w-md rounded-2xl shadow-2xl overflow-hidden p-6 space-y-4">
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-2">
                    <DollarSign className="w-5 h-5 text-emerald-400" />
                    <h3 className="text-sm font-bold text-white">Settle Founder Out-of-Pocket Reimbursement</h3>
                  </div>
                  <button onClick={() => setSettlementOpen(false)} className="text-slate-400 hover:text-white">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <p className="text-xs text-slate-400">
                  Transfers corporate bank funds to discharge Account 2105 Director Reimbursements Payable.
                </p>

                <form onSubmit={handleFounderSettlement} className="space-y-4 text-xs">
                  <div>
                    <label className="text-slate-300 font-medium block mb-1">Director Name:</label>
                    <input
                      type="text"
                      required
                      value={settleDirector}
                      onChange={(e) => setSettleDirector(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
                    />
                  </div>

                  <div>
                    <label className="text-slate-300 font-medium block mb-1">Settlement Amount (₹):</label>
                    <input
                      type="number"
                      step="0.01"
                      required
                      value={settleAmount}
                      onChange={(e) => setSettleAmount(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono font-bold"
                    />
                  </div>

                  <div>
                    <label className="text-slate-300 font-medium block mb-1">Bank Payment Reference / UTR:</label>
                    <input
                      type="text"
                      required
                      value={settleRef}
                      onChange={(e) => setSettleRef(e.target.value)}
                      placeholder="e.g. NEFT-FOUNDER-SETTLE or HDFC-IMPS-98124"
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
                    />
                  </div>

                  <div className="p-3 bg-emerald-950/30 border border-emerald-800/60 rounded-xl space-y-1 text-[11px] text-emerald-300">
                    <div className="font-semibold flex items-center gap-1.5">
                      <ShieldCheck className="w-4 h-4 text-emerald-400" /> Double-Entry General Ledger Impact:
                    </div>
                    <div>• <strong>DR 2105</strong> Director Reimbursements Payable (Discharge liability)</div>
                    <div>• <strong>CR 1010</strong> Bank Current Account (HDFC Bank)</div>
                  </div>

                  <div className="flex gap-3 pt-2">
                    <button
                      type="button"
                      onClick={() => setSettlementOpen(false)}
                      className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold rounded-lg transition"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={submittingSettle}
                      className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 text-white font-semibold rounded-lg transition flex items-center justify-center gap-2"
                    >
                      {submittingSettle ? 'Posting Payout...' : 'Confirm Payout'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Batch Multi-Upload Modal */}
          {batchUploadModalOpen && (
            <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
                <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
                      <UploadCloud className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white">Parallel Batch Receipt &amp; Bill Ingestion</h3>
                      <p className="text-[11px] text-slate-400">Drag &amp; drop up to 50 bills with statutory Schedule III auto-categorization &amp; zero-drift deduplication</p>
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      setBatchUploadModalOpen(false);
                      loadData();
                    }}
                    className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 transition"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
                <div className="p-6 overflow-y-auto">
                  <BatchDropzone
                    type="expenses"
                    activeUIFY={selectedFY}
                    onUploadComplete={() => {
                      loadData();
                    }}
                  />
                </div>
                <div className="px-6 py-3 border-t border-slate-800 bg-slate-950 flex justify-end">
                  <button
                    onClick={() => {
                      setBatchUploadModalOpen(false);
                      loadData();
                    }}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg transition"
                  >
                    Done &amp; Refresh Expenses
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
