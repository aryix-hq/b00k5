'use client';

import React, { useEffect, useState } from 'react';
import {
  ArrowDownLeft,
  ArrowUpRight,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  FileSpreadsheet,
  Check,
  RefreshCw,
  Search,
  Filter,
  Layers,
  Sparkles,
  ShieldCheck,
  IndianRupee,
  UploadCloud,
  FileUp,
  Lock,
  X
} from 'lucide-react';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import { fetchApi } from '@/lib/api';
import { BatchDropzone } from '@/components/upload/BatchDropzone';

interface BankLine {
  id: string;
  line_number: number;
  date: string;
  description: string;
  reference_number: string;
  payment_channel: 'UPI' | 'NEFT' | 'IMPS' | 'CHEQUE' | 'CHARGES' | 'OTHER';
  counterparty: string;
  withdrawal: number;
  deposit: number;
  balance: number;
  tier: 'unreconciled' | 'tier1_exact' | 'tier2_heuristic' | 'tier3_suspense';
  status: 'pending' | 'probable_match' | 'reconciled' | 'suspense_posted';
  confidence_score?: number;
  matched_invoice_id?: string;
  matched_invoice_number?: string;
  notes?: string;
}

interface OpenInvoice {
  id: string;
  invoice_number: string;
  customer_name: string;
  date: string;
  amount: number;
  status: 'unpaid' | 'partially_paid';
}

export default function BankReconciliationPage() {
  const [bankLines, setBankLines] = useState<BankLine[]>([]);
  const [openInvoices, setOpenInvoices] = useState<OpenInvoice[]>([]);
  const [selectedLine, setSelectedLine] = useState<BankLine | null>(null);
  const [filterTier, setFilterTier] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [companyName, setCompanyName] = useState('Sovereign Enterprise');
  const [uploading, setUploading] = useState(false);
  const [runningSweep, setRunningSweep] = useState(false);
  const [currentStatementId, setCurrentStatementId] = useState<string | null>(null);
  const [statementOpeningBal, setStatementOpeningBal] = useState<number>(0);
  const [statementClosingBal, setStatementClosingBal] = useState<number>(0);
  const [statementBank, setStatementBank] = useState<string>('HDFC Bank');
  const [statementAccount, setStatementAccount] = useState<string>('');
  const [availableStatements, setAvailableStatements] = useState<any[]>([]);
  const [runningGlobalSweep, setRunningGlobalSweep] = useState(false);

  // Suspense Reallocation State
  const [coaAccounts, setCoaAccounts] = useState<any[]>([]);
  const [selectedTargetAccountId, setSelectedTargetAccountId] = useState<string>('');
  const [allocatingSuspense, setAllocatingSuspense] = useState(false);
  const [processingLineId, setProcessingLineId] = useState<string | null>(null);

  // Password-Protected PDF State
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pdfPassword, setPdfPassword] = useState('');
  const [passwordError, setPasswordError] = useState('');
  const [uploadMessage, setUploadMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [batchStatementModalOpen, setBatchStatementModalOpen] = useState(false);

  const switchStatement = (stmt: any) => {
    if (!stmt) return;
    setCurrentStatementId(stmt.id);
    setStatementOpeningBal(parseFloat(stmt.opening_balance || '0'));
    setStatementClosingBal(parseFloat(stmt.closing_balance || '0'));
    if (stmt.bank_name) setStatementBank(stmt.bank_name);
    if (stmt.account_number) setStatementAccount(stmt.account_number);
    if (stmt.lines && Array.isArray(stmt.lines) && stmt.lines.length > 0) {
      const mapped: BankLine[] = stmt.lines.map((l: any, idx: number) => ({
        id: l.id || `l-${idx}`,
        line_number: l.line_number || idx + 1,
        date: l.transaction_date || new Date().toISOString().split('T')[0],
        description: l.description || 'Transaction',
        reference_number: l.reference_number || '',
        payment_channel: l.payment_channel || 'OTHER',
        counterparty: l.counterparty_name || 'Counterparty',
        withdrawal: parseFloat(l.withdrawal_amount || '0'),
        deposit: parseFloat(l.deposit_amount || '0'),
        balance: parseFloat(l.running_balance || '0'),
        tier: l.reconciliation_tier || 'unreconciled',
        status: l.reconciliation_status || 'pending',
        confidence_score: l.confidence_score,
        matched_invoice_id: l.matched_journal_entry_id ? 'matched' : undefined,
        matched_invoice_number: l.notes,
        notes: l.notes
      }));
      setBankLines(mapped);
      setSelectedLine(mapped[0]);
    } else {
      setBankLines([]);
      setSelectedLine(null);
    }
  };

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('b00k5_legal_name');
      if (stored) setCompanyName(stored);
    }

    async function loadInvoices() {
      try {
        const invs = await fetchApi('/api/v1/invoices/');
        if (Array.isArray(invs) && invs.length > 0) {
          const mapped: OpenInvoice[] = invs.map((inv: any) => ({
            id: inv.id,
            invoice_number: inv.invoice_number,
            customer_name: inv.contact?.name || inv.customer_name || 'Customer',
            date: inv.issue_date,
            amount: parseFloat(inv.grand_total || inv.total_amount || '0'),
            status: inv.status === 'paid' ? 'partially_paid' : 'unpaid'
          }));
          setOpenInvoices(mapped);
        }
      } catch (e) {
        console.error('Failed to load invoices:', e);
      }
    }

    async function loadAccounts() {
      try {
        const accs = await fetchApi('/api/v1/ledger/accounts');
        if (Array.isArray(accs) && accs.length > 0) {
          const valid = accs.filter((a: any) => a.code !== '2099');
          setCoaAccounts(valid);
          if (valid.length > 0) setSelectedTargetAccountId(valid[0].id);
        }
      } catch (e) {
        console.error('Failed to load accounts:', e);
      }
    }

    loadInvoices();
    loadAccounts();
    loadStatements();
  }, []);

  async function loadStatements() {
    try {
      const stmts = await fetchApi('/api/v1/reconciliation/statements');
      if (Array.isArray(stmts) && stmts.length > 0) {
        setAvailableStatements(stmts);
        // Prefer active statement with transactions
        const withLines = stmts.find((s: any) => s.lines && s.lines.length > 0) || stmts[0];
        switchStatement(withLines);
      }
    } catch (e) {
      console.error('Failed to load existing statements:', e);
    }
  }

  // Balance Metrics
  const openingBalance = statementOpeningBal;
  const totalDeposits = bankLines.reduce((acc, l) => acc + l.deposit, 0);
  const totalWithdrawals = bankLines.reduce((acc, l) => acc + l.withdrawal, 0);
  const calculatedClosing = openingBalance + totalDeposits - totalWithdrawals;
  const expectedClosing = statementClosingBal > 0 ? statementClosingBal : calculatedClosing;
  const balanceDrift = Math.abs(expectedClosing - calculatedClosing);

  // Live 3-Tier Match Sweep
  const handleRunSweep = async () => {
    if (!currentStatementId) return;
    setRunningSweep(true);
    setUploadMessage(null);
    try {
      const summary = await fetchApi(`/api/v1/reconciliation/statements/${currentStatementId}/reconcile`, {
        method: 'POST'
      });
      // Refresh statement details
      const stmtDetails = await fetchApi(`/api/v1/reconciliation/statements/${currentStatementId}`);
      if (stmtDetails?.lines && Array.isArray(stmtDetails.lines)) {
        const mapped: BankLine[] = stmtDetails.lines.map((l: any, idx: number) => ({
          id: l.id || `l-${idx}`,
          line_number: l.line_number || idx + 1,
          date: l.transaction_date || new Date().toISOString().split('T')[0],
          description: l.description || 'Transaction',
          reference_number: l.reference_number || '',
          payment_channel: l.payment_channel || 'OTHER',
          counterparty: l.counterparty_name || 'Counterparty',
          withdrawal: parseFloat(l.withdrawal_amount || '0'),
          deposit: parseFloat(l.deposit_amount || '0'),
          balance: parseFloat(l.running_balance || '0'),
          tier: l.reconciliation_tier || 'unreconciled',
          status: l.reconciliation_status || 'pending',
          confidence_score: l.confidence_score,
          matched_invoice_id: l.matched_journal_entry_id ? 'matched' : undefined,
          matched_invoice_number: l.notes,
          notes: l.notes
        }));
        setBankLines(mapped);
        if (mapped.length > 0) setSelectedLine(mapped[0]);
      }
      setUploadMessage({
        type: 'success',
        text: `3-Tier Match Sweep complete: ${summary.tier1_reconciled || 0} Tier 1 exact settled, ${summary.tier2_probable || 0} Tier 2 probable flagged, ${summary.tier3_suspense || 0} routed to Suspense 2099.`
      });
    } catch (err: any) {
      console.error('Sweep failed:', err);
      setUploadMessage({ type: 'error', text: err.message || 'Failed to run 3-tier reconciliation sweep.' });
    } finally {
      setRunningSweep(false);
    }
  };

  const handleRunGlobalSweep = async () => {
    setRunningGlobalSweep(true);
    setUploadMessage(null);
    try {
      const res = await fetchApi('/api/v1/reconciliation/reconcile-all', { method: 'POST' });
      setUploadMessage({
        type: 'success',
        text: res.message || 'Global 3-Tier Reconciliation sweep complete across all bank statements!'
      });
      const stmts = await fetchApi('/api/v1/reconciliation/statements');
      if (Array.isArray(stmts)) {
        setAvailableStatements(stmts);
        const cur = stmts.find((s: any) => s.id === currentStatementId) || stmts[0];
        if (cur) switchStatement(cur);
      }
    } catch (err: any) {
      setUploadMessage({ type: 'error', text: err.message || 'Failed to run global sweep.' });
    } finally {
      setRunningGlobalSweep(false);
    }
  };

  // Actions
  const handleAcceptTier1 = async (lineId: string) => {
    setProcessingLineId(lineId);
    try {
      await fetchApi(`/api/v1/reconciliation/lines/${lineId}/confirm-match`, {
        method: 'POST',
        body: JSON.stringify({ notes: 'Tier 1 exact match confirmed by user' })
      });
      setBankLines(lines => lines.map(l => l.id === lineId ? { ...l, status: 'reconciled', tier: 'tier1_exact' } : l));
      setSelectedLine(prev => prev && prev.id === lineId ? { ...prev, status: 'reconciled', tier: 'tier1_exact' } : prev);
      setUploadMessage({ type: 'success', text: 'Tier 1 exact match confirmed and settlement journal posted to general ledger.' });
    } catch (err: any) {
      console.error(err);
      setUploadMessage({ type: 'error', text: err.message || 'Failed to accept Tier 1 match.' });
    } finally {
      setProcessingLineId(null);
    }
  };

  const handleApproveTier2 = async (lineId: string) => {
    setProcessingLineId(lineId);
    try {
      await fetchApi(`/api/v1/reconciliation/lines/${lineId}/confirm-match`, {
        method: 'POST',
        body: JSON.stringify({ notes: 'Tier 2 probable match approved by user' })
      });
      setBankLines(lines => lines.map(l => l.id === lineId ? { ...l, status: 'reconciled', tier: 'tier2_heuristic' } : l));
      setSelectedLine(prev => prev && prev.id === lineId ? { ...prev, status: 'reconciled', tier: 'tier2_heuristic' } : prev);
      setUploadMessage({ type: 'success', text: 'Tier 2 match approved and settlement journal posted to general ledger.' });
    } catch (err: any) {
      console.error(err);
      setUploadMessage({ type: 'error', text: err.message || 'Failed to approve Tier 2 match.' });
    } finally {
      setProcessingLineId(null);
    }
  };

  const handleRouteToSuspense = async (lineId: string) => {
    setProcessingLineId(lineId);
    try {
      await fetchApi(`/api/v1/reconciliation/lines/${lineId}/route-to-suspense`, {
        method: 'POST'
      });
      setBankLines(lines => lines.map(l => l.id === lineId ? {
        ...l,
        status: 'suspense_posted',
        tier: 'tier3_suspense',
        description: `${l.description} [POSTED TO CODE 2099 SUSPENSE]`
      } : l));
      setSelectedLine(prev => prev && prev.id === lineId ? {
        ...prev,
        status: 'suspense_posted',
        tier: 'tier3_suspense',
        description: `${prev.description} [POSTED TO CODE 2099 SUSPENSE]`
      } : prev);
      setUploadMessage({ type: 'success', text: 'Line routed to Schedule III Suspense Account (Code 2099).' });
    } catch (err: any) {
      console.error(err);
      setUploadMessage({ type: 'error', text: err.message || 'Failed to route to suspense.' });
    } finally {
      setProcessingLineId(null);
    }
  };

  const handleAllocateSuspense = async (lineId: string) => {
    if (!selectedTargetAccountId) return;
    setAllocatingSuspense(true);
    try {
      await fetchApi(`/api/v1/reconciliation/lines/${lineId}/allocate-suspense`, {
        method: 'POST',
        body: JSON.stringify({ target_account_id: selectedTargetAccountId })
      });
      const targetAcc = coaAccounts.find(a => a.id === selectedTargetAccountId);
      const accName = targetAcc ? `${targetAcc.name} (${targetAcc.code})` : 'Target Account';
      setBankLines(lines => lines.map(l => l.id === lineId ? {
        ...l,
        status: 'reconciled',
        description: `${l.description} [RECLASSIFIED TO ${accName}]`
      } : l));
      setSelectedLine(prev => prev && prev.id === lineId ? {
        ...prev,
        status: 'reconciled',
        description: `${prev.description} [RECLASSIFIED TO ${accName}]`
      } : prev);
      setUploadMessage({ type: 'success', text: `Suspense balance successfully reallocated to ${accName}!` });
    } catch (err: any) {
      console.error(err);
      setUploadMessage({ type: 'error', text: err.message || 'Failed to reallocate suspense.' });
    } finally {
      setAllocatingSuspense(false);
    }
  };

  const doUploadStatement = async (file: File, pwd?: string) => {
    setUploading(true);
    setPasswordError('');
    setUploadMessage(null);
    const fd = new FormData();
    fd.append('file', file);
    if (pwd) fd.append('password', pwd);

    try {
      const token = localStorage.getItem('b00k5_token');
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/reconciliation/upload-statement`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`
        },
        body: fd
      });

      const data = await res.json();

      if (res.status === 422 && (data?.detail?.needs_password || data?.needs_password)) {
        setPendingFile(file);
        setPasswordModalOpen(true);
        setPasswordError(data?.detail?.message || 'Password required to decrypt bank statement.');
        return;
      }

      if (res.ok) {
        setPasswordModalOpen(false);
        setPdfPassword('');
        setPendingFile(null);
        setCurrentStatementId(data?.id || data?.statement_id || null);
        setStatementOpeningBal(parseFloat(data?.opening_balance || '0'));
        setStatementClosingBal(parseFloat(data?.closing_balance || '0'));
        if (data?.bank_name) setStatementBank(data.bank_name);
        if (data?.account_number) setStatementAccount(data.account_number);
        const txs = data?.parsed_transactions || data?.lines || [];
        if (Array.isArray(txs)) {
          const mapped: BankLine[] = txs.map((tx: any, idx: number) => ({
            id: tx.id || `l-${idx}`,
            line_number: tx.line_number || idx + 1,
            date: tx.date || tx.transaction_date || new Date().toISOString().split('T')[0],
            description: tx.description || tx.narration || 'Transaction',
            reference_number: tx.reference_number || tx.utr_number || '',
            payment_channel: tx.payment_channel || 'OTHER',
            counterparty: tx.counterparty || tx.counterparty_name || 'Counterparty',
            withdrawal: parseFloat(tx.withdrawal || tx.withdrawal_amount || '0'),
            deposit: parseFloat(tx.deposit || tx.deposit_amount || '0'),
            balance: parseFloat(tx.balance || tx.running_balance || '0'),
            tier: tx.reconciliation_tier || 'unreconciled',
            status: tx.status || tx.reconciliation_status || 'pending',
            confidence_score: tx.confidence_score,
            matched_invoice_id: tx.matched_invoice_id,
            matched_invoice_number: tx.notes || tx.matched_invoice_number,
            notes: tx.notes
          }));
          setBankLines(mapped);
          if (mapped.length > 0) setSelectedLine(mapped[0]);
          setUploadMessage({ type: 'success', text: `Successfully parsed and auto-matched ${mapped.length} bank transactions from ${file.name}.` });
        }
      } else {
        if (passwordModalOpen) {
          setPasswordError(data?.detail?.message || data?.detail || 'Incorrect PDF password.');
        } else {
          setUploadMessage({ type: 'error', text: data?.detail || 'Failed to parse bank statement.' });
        }
      }
    } catch (err: any) {
      console.error('Failed to parse statement', err);
      setUploadMessage({ type: 'error', text: err.message || 'Error uploading bank statement.' });
    } finally {
      setUploading(false);
    }
  };

  const handleStatementUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    doUploadStatement(file);
  };

  const clearLines = () => {
    setBankLines([]);
    setSelectedLine(null);
    setCurrentStatementId(null);
    setStatementOpeningBal(0);
    setStatementClosingBal(0);
    setStatementAccount('');
  };

  const filteredLines = bankLines.filter(line => {
    if (filterTier !== 'all' && line.tier !== filterTier) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        line.description.toLowerCase().includes(q) ||
        line.reference_number.toLowerCase().includes(q) ||
        line.counterparty.toLowerCase().includes(q)
      );
    }
    return true;
  });

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Navbar />
        <main className="p-8 space-y-6 max-w-7xl mx-auto w-full">
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
            <div>
              <div className="flex flex-wrap items-center gap-2 mb-1">
                <span className="text-xs uppercase font-mono px-2 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800/60">
                  {companyName}
                </span>
                {statementAccount && (
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-sky-900/60 text-sky-300 border border-sky-700/60 font-semibold flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                    {statementBank} • A/C: {statementAccount}
                  </span>
                )}
                {bankLines.length > 0 && (
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800/60 font-semibold">
                    {bankLines.length} Ingested Transactions
                  </span>
                )}
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5">
                <FileSpreadsheet className="w-7 h-7 text-sky-400" />
                3-Tier Bank Reconciliation Workbench
              </h1>
              <p className="text-sm text-slate-400 mt-1">
                Deterministic UTR Matching, Window Heuristics, and Schedule III Code 2099 Suspense Auto-Posting
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleRunGlobalSweep}
                disabled={runningGlobalSweep}
                className="px-3.5 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-colors shadow-sm"
                title="Run 3-tier reconciliation sweep across all uploaded statements"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${runningGlobalSweep ? 'animate-spin' : ''}`} />
                <span>{runningGlobalSweep ? 'Reconciling All...' : 'Reconcile All Statements'}</span>
              </button>

              {currentStatementId && bankLines.length > 0 && (
                <button
                  type="button"
                  onClick={handleRunSweep}
                  disabled={runningSweep}
                  className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-colors shadow-sm"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${runningSweep ? 'animate-spin' : ''}`} />
                  <span>{runningSweep ? 'Sweeping Ledgers...' : 'Run 3-Tier Match Sweep'}</span>
                </button>
              )}

              <button
                onClick={() => setBatchStatementModalOpen(true)}
                className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-colors shadow-sm"
              >
                <UploadCloud className="w-4 h-4" />
                <span>Batch Multi-Upload (50 max)</span>
              </button>

              <label className="cursor-pointer px-3.5 py-1.5 bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-colors shadow-sm">
                <UploadCloud className="w-4 h-4" />
                <span>{uploading ? 'Parsing Statement...' : 'Upload Bank Statement'}</span>
                <input type="file" accept=".pdf, .png, .jpg, .jpeg, image/png, image/jpeg" className="hidden" onChange={handleStatementUpload} disabled={uploading} />
              </label>

              {bankLines.length > 0 && (
                <button
                  onClick={clearLines}
                  className="px-3 py-1.5 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-300 transition-colors"
                >
                  Clear
                </button>
              )}
            </div>
          </div>

          {/* Statement Selector & Switcher */}
          {availableStatements.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-slate-900/90 border border-slate-800 text-xs">
              <div className="flex items-center gap-3">
                <span className="text-slate-400 font-medium">Select Statement Period:</span>
                <select
                  value={currentStatementId || ''}
                  onChange={(e) => {
                    const sel = availableStatements.find((s) => s.id === e.target.value);
                    if (sel) switchStatement(sel);
                  }}
                  className="bg-slate-800 border border-slate-700 text-sky-300 font-mono font-bold rounded-lg px-3 py-1.5 focus:outline-none focus:border-sky-500 cursor-pointer"
                >
                  {availableStatements.map((s) => {
                    const label = s.statement_from && s.statement_to
                      ? `${s.statement_from} to ${s.statement_to}`
                      : s.file_name;
                    const txCount = s.lines?.length ?? 0;
                    return (
                      <option key={s.id} value={s.id} className="bg-slate-900 text-white">
                        {label} — {s.status.toUpperCase()} ({txCount} txns)
                      </option>
                    );
                  })}
                </select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-slate-500 font-mono text-[11px]">
                  Showing: <span className="text-slate-300 font-semibold">{bankLines.length}</span> transactions in active statement
                </span>
              </div>
            </div>
          )}

          {uploadMessage && (
            <div className={`p-3 rounded-lg border text-xs flex items-center justify-between ${
              uploadMessage.type === 'success'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
            }`}>
              <div className="flex items-center gap-2">
                {uploadMessage.type === 'success' ? (
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                ) : (
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                )}
                <span>{uploadMessage.text}</span>
              </div>
              <button
                onClick={() => setUploadMessage(null)}
                className="text-slate-400 hover:text-white text-xs ml-4"
              >
                ✕
              </button>
            </div>
          )}

          {/* Zero-Discrepancy Balance Overview Bar */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 p-4 rounded-xl bg-slate-900/80 border border-slate-800 font-mono text-xs">
            <div>
              <span className="text-slate-400 block mb-1">Opening Balance:</span>
              <span className="font-semibold text-white text-sm">₹{openingBalance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
            </div>
            <div>
              <span className="text-emerald-400 block mb-1">+ Total Deposits:</span>
              <span className="font-semibold text-emerald-300 text-sm">₹{totalDeposits.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
            </div>
            <div>
              <span className="text-rose-400 block mb-1">- Withdrawals:</span>
              <span className="font-semibold text-rose-300 text-sm">₹{totalWithdrawals.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
            </div>
            <div>
              <span className="text-sky-400 block mb-1">= Calculated Balance:</span>
              <span className="font-semibold text-sky-300 text-sm">₹{calculatedClosing.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
            </div>
            <div className="flex flex-col justify-center">
              <span className="text-slate-400 block mb-1">Mathematical Drift:</span>
              <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded font-semibold text-xs w-fit ${
                balanceDrift < 0.01
                  ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
                  : 'bg-rose-500/10 border border-rose-500/30 text-rose-400'
              }`}>
                {balanceDrift < 0.01 ? <Check className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                ₹{balanceDrift.toFixed(2)} {balanceDrift < 0.01 ? '(Zero Drift)' : '(Discrepancy)'}
              </span>
            </div>
          </div>

          {bankLines.length === 0 ? (
            /* Clean Empty State for Freshly Onboarded Entity */
            <div className="p-12 text-center bg-slate-900/40 rounded-2xl border border-slate-800/80 space-y-4">
              <div className="w-14 h-14 rounded-2xl bg-sky-500/10 border border-sky-500/20 text-sky-400 flex items-center justify-center mx-auto">
                <FileSpreadsheet className="w-7 h-7" />
              </div>
              <div className="max-w-md mx-auto">
                <h3 className="text-base font-semibold text-white">No Bank Statements Ingested Yet</h3>
                <p className="text-xs text-slate-400 mt-1.5 leading-relaxed">
                  Your financial ledger for <strong className="text-slate-200">{companyName}</strong> is clean. Upload an official bank statement (HDFC, ICICI, SBI, Axis PDF) to begin automated 3-tier reconciliation.
                </p>
              </div>

              <div className="flex items-center justify-center gap-3 pt-2">
                <button
                  onClick={() => setBatchStatementModalOpen(true)}
                  className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 transition-colors shadow-lg shadow-indigo-950/40"
                >
                  <UploadCloud className="w-4 h-4" />
                  <span>Parallel Batch Ingest (Up to 50 Statements)</span>
                </button>
                <label className="cursor-pointer px-5 py-2.5 bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 transition-colors shadow-lg shadow-sky-950/40">
                  <UploadCloud className="w-4 h-4" />
                  <span>Upload Single Statement</span>
                  <input type="file" accept=".pdf, .png, .jpg, .jpeg, image/png, image/jpeg" className="hidden" onChange={handleStatementUpload} disabled={uploading} />
                </label>
              </div>
            </div>
          ) : (
            <>
              {/* Filter and Search Bar */}
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  {['all', 'tier1_exact', 'tier2_heuristic', 'tier3_suspense', 'unreconciled'].map(tier => (
                    <button
                      key={tier}
                      onClick={() => setFilterTier(tier)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all ${
                        filterTier === tier
                          ? 'bg-sky-500 text-white shadow-sm'
                          : 'bg-slate-800/80 text-slate-400 hover:text-slate-200 border border-slate-700/60'
                      }`}
                    >
                      {tier.replace('_', ' ')}
                    </button>
                  ))}
                </div>
                <div className="relative w-64">
                  <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Search narration or UTR..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-700 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white focus:outline-none focus:border-sky-500 font-mono"
                  />
                </div>
              </div>

              {/* Split Workbench Grid */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left Pane: Bank Statement Lines (7 cols) */}
                <div className="lg:col-span-7 bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-lg flex flex-col">
                  <div className="px-4 py-3 bg-slate-800/40 border-b border-slate-800 flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                      <Layers className="w-4 h-4 text-sky-400" /> Statement Lines ({filteredLines.length})
                    </span>
                    <span className="text-[11px] font-mono text-slate-400">{companyName} Operating A/C</span>
                  </div>

                  <div className="divide-y divide-slate-800/60 overflow-y-auto max-h-[560px]">
                    {filteredLines.map(line => {
                      const isSelected = selectedLine?.id === line.id;
                      return (
                        <div
                          key={line.id}
                          onClick={() => setSelectedLine(line)}
                          className={`p-3.5 transition-all cursor-pointer ${
                            isSelected ? 'bg-sky-500/10 border-l-4 border-sky-500' : 'hover:bg-slate-800/40'
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2 mb-1.5">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-mono text-slate-400">{line.date}</span>
                              <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold uppercase ${
                                line.payment_channel === 'UPI' ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30' :
                                line.payment_channel === 'NEFT' ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' :
                                line.payment_channel === 'IMPS' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' :
                                line.payment_channel === 'CHEQUE' ? 'bg-teal-500/20 text-teal-300 border border-teal-500/30' :
                                'bg-slate-700 text-slate-300'
                              }`}>
                                {line.payment_channel}
                              </span>
                              {line.reference_number && (
                                <span className="text-[10px] font-mono text-slate-400 truncate max-w-[140px]">
                                  Ref: {line.reference_number}
                                </span>
                              )}
                            </div>

                            <div className="text-right">
                              {line.deposit > 0 ? (
                                <span className="text-xs font-mono font-bold text-emerald-400 flex items-center gap-0.5">
                                  +₹{line.deposit.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                </span>
                              ) : (
                                <span className="text-xs font-mono font-bold text-rose-400 flex items-center gap-0.5">
                                  -₹{line.withdrawal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                </span>
                              )}
                            </div>
                          </div>

                          <p className="text-xs text-slate-200 line-clamp-1 font-sans">{line.description}</p>

                          <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-slate-800/40 text-[11px]">
                            <span className="text-slate-400">
                              Party: <span className="text-slate-200 font-medium">{line.counterparty || 'Unknown'}</span>
                            </span>

                            <div>
                              {line.status === 'reconciled' ? (
                                <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-semibold inline-flex items-center gap-1">
                                  <CheckCircle2 className="w-3 h-3" /> Reconciled
                                </span>
                              ) : line.status === 'suspense_posted' ? (
                                <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-400 border border-amber-500/30 font-semibold">
                                  Suspense 2099
                                </span>
                              ) : line.tier === 'tier1_exact' ? (
                                <span className="px-2 py-0.5 rounded bg-sky-500/20 text-sky-400 border border-sky-500/30 font-semibold flex items-center gap-1">
                                  <Sparkles className="w-3 h-3" /> Tier 1 Exact Match
                                </span>
                              ) : line.tier === 'tier2_heuristic' ? (
                                <span className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 font-semibold">
                                  Tier 2 ({line.confidence_score}%)
                                </span>
                              ) : (
                                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                                  Unmatched
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Right Pane: Match Details & Action Center (5 cols) */}
                <div className="lg:col-span-5 bg-slate-900/60 border border-slate-800 rounded-xl p-5 shadow-lg space-y-4">
                  <div className="border-b border-slate-800 pb-3 flex items-center justify-between">
                    <h3 className="font-semibold text-white text-sm flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-sky-400" />
                      Reconciliation Action Center
                    </h3>
                    {selectedLine && (
                      <span className="text-xs font-mono text-slate-400">Line #{selectedLine.line_number}</span>
                    )}
                  </div>

                  {selectedLine ? (
                    <div className="space-y-4 text-xs">
                      {/* Selected Line Card */}
                      <div className="p-3.5 rounded-lg bg-slate-800/40 border border-slate-700/60 space-y-2">
                        <div className="flex justify-between items-center">
                          <span className="text-slate-400">Amount:</span>
                          <span className="font-mono text-sm font-bold text-white">
                            ₹{(selectedLine.deposit || selectedLine.withdrawal).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-slate-400">Payment Channel:</span>
                          <span className="font-semibold text-slate-200">{selectedLine.payment_channel}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-slate-400">Reference / UTR:</span>
                          <span className="font-mono text-sky-300">{selectedLine.reference_number || 'N/A'}</span>
                        </div>
                        <div className="flex justify-between items-center">
                          <span className="text-slate-400">Counterparty:</span>
                          <span className="font-semibold text-white">{selectedLine.counterparty || 'N/A'}</span>
                        </div>
                        {selectedLine.notes && (
                          <div className="pt-1.5 border-t border-slate-700/50 text-[11px] text-slate-300">
                            <span className="text-slate-400">Audit Trail: </span>
                            <span className="text-sky-300">{selectedLine.notes}</span>
                          </div>
                        )}
                      </div>

                      {/* Matched Open Invoice Candidate */}
                      {(() => {
                        const matchedOpenInv = selectedLine.deposit > 0
                          ? openInvoices.find(inv =>
                              (selectedLine.notes && selectedLine.notes.includes(inv.invoice_number)) ||
                              Math.abs(inv.amount - selectedLine.deposit) < 0.01
                            )
                          : undefined;
                        const hasCandidate = Boolean(
                          selectedLine.matched_invoice_id ||
                          (selectedLine.confidence_score && selectedLine.confidence_score >= 60) ||
                          matchedOpenInv
                        );
                        const displayScore = selectedLine.confidence_score && selectedLine.confidence_score >= 60
                          ? selectedLine.confidence_score
                          : (matchedOpenInv ? 92 : 100);
                        const displayTitle = matchedOpenInv
                          ? `Invoice #${matchedOpenInv.invoice_number}`
                          : (selectedLine.matched_invoice_number || 'Matching Open Invoice');
                        const displayCustomer = matchedOpenInv
                          ? `${matchedOpenInv.customer_name}${selectedLine.counterparty && selectedLine.counterparty !== matchedOpenInv.customer_name ? ` (via ${selectedLine.counterparty})` : ''}`
                          : selectedLine.counterparty;

                        return hasCandidate ? (
                          <div className="p-3.5 rounded-lg bg-sky-950/20 border border-sky-800/50 space-y-2.5">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-semibold text-sky-400 flex items-center gap-1.5">
                                <CheckCircle2 className="w-4 h-4" /> Candidate Ledger Invoice Match
                              </span>
                              <span className="text-xs font-mono px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-500/30">
                                Score: {displayScore}%
                              </span>
                            </div>

                            <div className="space-y-1 font-mono text-slate-300">
                              <p className="text-white font-bold">{displayTitle}</p>
                              <p className="text-slate-400">Customer: {displayCustomer}</p>
                              <p className="text-emerald-400 font-bold">Grand Total: ₹{(matchedOpenInv?.amount || selectedLine.deposit).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</p>
                            </div>

                            {selectedLine.status !== 'reconciled' && (
                              <div className="pt-2 flex gap-2">
                                {selectedLine.tier === 'tier1_exact' ? (
                                  <button
                                    onClick={() => handleAcceptTier1(selectedLine.id)}
                                    disabled={processingLineId === selectedLine.id}
                                    className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold rounded-lg shadow-sm transition-colors text-xs flex items-center justify-center gap-1.5"
                                  >
                                    {processingLineId === selectedLine.id ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-4 h-4" />}
                                    <span>Accept Tier 1 Exact Match (1-Click)</span>
                                  </button>
                                ) : (
                                  <button
                                    onClick={() => handleApproveTier2(selectedLine.id)}
                                    disabled={processingLineId === selectedLine.id}
                                    className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold rounded-lg shadow-sm transition-colors text-xs flex items-center justify-center gap-1.5"
                                  >
                                    {processingLineId === selectedLine.id ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-4 h-4" />}
                                    <span>Approve Invoice Settlement Match ({displayScore}%)</span>
                                  </button>
                                )}
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="p-3.5 rounded-lg bg-slate-800/40 border border-slate-700/60 space-y-2 text-center py-6">
                            <HelpCircle className="w-8 h-8 text-amber-400 mx-auto opacity-70" />
                            <p className="text-sm font-semibold text-slate-200">No Direct Invoice Match Found</p>
                            <p className="text-xs text-slate-400 max-w-xs mx-auto">
                              This transaction does not correspond to an open AR invoice. You can route it to Suspense Account 2099 for manual allocation.
                            </p>
                          </div>
                        );
                      })()}

                      {/* Action Buttons */}
                      <div className="pt-2 space-y-2">
                        {selectedLine.status !== 'suspense_posted' && selectedLine.status !== 'reconciled' && (
                          <button
                            onClick={() => handleRouteToSuspense(selectedLine.id)}
                            disabled={processingLineId === selectedLine.id}
                            className="w-full py-2 bg-amber-600/20 hover:bg-amber-600/30 text-amber-300 border border-amber-600/40 font-semibold rounded-lg text-xs transition-colors flex items-center justify-center gap-1.5"
                          >
                            {processingLineId === selectedLine.id ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <AlertTriangle className="w-3.5 h-3.5" />}
                            <span>Route to Tier 3 Suspense Account (Code 2099)</span>
                          </button>
                        )}

                        {selectedLine.status === 'reconciled' && (
                          <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-semibold text-center flex items-center justify-center gap-2">
                            <CheckCircle2 className="w-4 h-4" />
                            Transaction Successfully Reconciled with General Ledger
                          </div>
                        )}

                        {/* Suspense Reallocation Box */}
                        {selectedLine.status === 'suspense_posted' && (
                          <div className="p-3.5 rounded-lg bg-amber-950/20 border border-amber-800/40 space-y-3">
                            <div className="flex items-center gap-2 text-amber-400 font-semibold">
                              <AlertTriangle className="w-4 h-4 shrink-0" />
                              <span>Reallocate Suspense (Code 2099) to General Ledger</span>
                            </div>
                            <p className="text-[11px] text-slate-400 leading-relaxed">
                              Select target Chart of Accounts head to reclassify this unallocated transaction from Suspense:
                            </p>
                            <div className="space-y-2">
                              <select
                                value={selectedTargetAccountId}
                                onChange={(e) => setSelectedTargetAccountId(e.target.value)}
                                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white"
                              >
                                {coaAccounts.map(acc => (
                                  <option key={acc.id} value={acc.id}>
                                    {acc.code} - {acc.name} ({acc.type.toUpperCase()})
                                  </option>
                                ))}
                              </select>
                              <button
                                onClick={() => handleAllocateSuspense(selectedLine.id)}
                                disabled={allocatingSuspense || !selectedTargetAccountId}
                                className="w-full py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-semibold rounded-lg text-xs flex items-center justify-center gap-1.5 transition-colors shadow"
                              >
                                {allocatingSuspense ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                                <span>Reallocate &amp; Balance Ledger</span>
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="text-center py-12 text-slate-500">
                      Select a statement line from the left pane to view matching candidates.
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
          {/* Password-Protected PDF Ingestion Modal */}
          {passwordModalOpen && (
            <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <Lock className="w-5 h-5 text-amber-400" />
                    <h3 className="font-semibold text-white text-sm">Password-Protected Bank Statement</h3>
                  </div>
                  <button
                    onClick={() => { setPasswordModalOpen(false); setPendingFile(null); }}
                    className="text-slate-400 hover:text-white text-xs"
                  >
                    ✕
                  </button>
                </div>

                <div className="space-y-3 text-xs">
                  <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300">
                    <span className="font-semibold block mb-1">Encrypted PDF Statement Detected</span>
                    Indian banks encrypt statements using customer details:
                    <ul className="mt-2 list-disc list-inside space-y-0.5 text-slate-300 text-[11px]">
                      <li><span className="text-white font-medium">HDFC Bank:</span> Customer ID or Corporate PAN in CAPS</li>
                      <li><span className="text-white font-medium">ICICI Bank:</span> Date of Birth (DDMMYYYY) or Account Number</li>
                      <li><span className="text-white font-medium">SBI:</span> DOB (DDMMYYYY) + Last 5 digits of mobile</li>
                      <li><span className="text-white font-medium">Axis Bank:</span> First 4 letters of name + DOB (DDMMYYYY)</li>
                    </ul>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-slate-300 font-medium block">
                      Statement PDF Password:
                    </label>
                    <input
                      type="password"
                      value={pdfPassword}
                      onChange={(e) => setPdfPassword(e.target.value)}
                      placeholder="Enter PDF password"
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono text-sm focus:outline-none focus:border-amber-500"
                      autoFocus
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && pendingFile) {
                          doUploadStatement(pendingFile, pdfPassword);
                        }
                      }}
                    />
                  </div>

                  {passwordError && (
                    <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                      {passwordError}
                    </div>
                  )}

                  <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => { setPasswordModalOpen(false); setPendingFile(null); }}
                      className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => { if (pendingFile) doUploadStatement(pendingFile, pdfPassword); }}
                      disabled={uploading || !pdfPassword}
                      className="px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-semibold text-xs rounded-lg flex items-center gap-1.5 shadow"
                    >
                      {uploading ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Unlocking &amp; Parsing...
                        </>
                      ) : (
                        <>
                          <Lock className="w-3.5 h-3.5" /> Unlock &amp; Ingest Statement
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Batch Multi-Upload Bank Statements Modal */}
          {batchStatementModalOpen && (
            <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
                <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-indigo-500/20 text-indigo-400 flex items-center justify-center">
                      <UploadCloud className="w-4 h-4" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white">Parallel Batch Bank Statement Ingestion</h3>
                      <p className="text-[11px] text-slate-400">Drag &amp; drop up to 50 statements (HDFC, ICICI, SBI, Axis) with period &amp; line deduplication</p>
                    </div>
                  </div>
                  <button
                    onClick={() => {
                      setBatchStatementModalOpen(false);
                      loadStatements();
                    }}
                    className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-slate-800 transition"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
                <div className="p-6 overflow-y-auto">
                  <BatchDropzone
                    type="statements"
                    bankAccountId={statementAccount || undefined}
                    onUploadComplete={() => {
                      loadStatements();
                    }}
                  />
                </div>
                <div className="px-6 py-3 border-t border-slate-800 bg-slate-950 flex justify-end">
                  <button
                    onClick={() => {
                      setBatchStatementModalOpen(false);
                      loadStatements();
                    }}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg transition"
                  >
                    Done &amp; View Statements
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
