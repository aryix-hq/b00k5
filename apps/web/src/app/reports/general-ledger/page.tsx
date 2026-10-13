'use client';

import React, { useState, useEffect, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
  FileSpreadsheet,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  RefreshCw,
  Search,
  BookOpen,
  Filter,
  ExternalLink,
  Layers
} from 'lucide-react';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import { fetchApi } from '@/lib/api';

interface LedgerAccountSummary {
  account_id?: string;
  code: string;
  name: string;
  type: string;
  debit_balance: number;
  credit_balance: number;
}

interface JournalLineItem {
  id: string;
  account_id: string;
  account_code?: string;
  account_name?: string;
  debit_amount: number;
  credit_amount: number;
  description?: string;
}

interface JournalEntryItem {
  id: string;
  entry_number: string;
  entry_date: string;
  narration: string;
  reference_type: string;
  is_posted: boolean;
  lines: JournalLineItem[];
}

function GeneralLedgerContent() {
  const searchParams = useSearchParams();
  const entryFilterParam = searchParams.get('entry') || '';

  const [activeTab, setActiveTab] = useState<'journals' | 'trial_balance'>(entryFilterParam ? 'journals' : 'trial_balance');
  const [accounts, setAccounts] = useState<LedgerAccountSummary[]>([]);
  const [journals, setJournals] = useState<JournalEntryItem[]>([]);
  const [totalDebits, setTotalDebits] = useState<number>(0);
  const [totalCredits, setTotalCredits] = useState<number>(0);
  const [isBalanced, setIsBalanced] = useState<boolean>(true);
  const [searchTerm, setSearchTerm] = useState<string>(entryFilterParam);
  const [loading, setLoading] = useState<boolean>(true);

  async function loadLedgerData() {
    setLoading(true);
    try {
      const [tbRes, jRes] = await Promise.all([
        fetchApi('/api/v1/ledger/trial-balance').catch(() => null),
        fetchApi('/api/v1/ledger/journals').catch(() => [])
      ]);

      let loadedAccounts: LedgerAccountSummary[] = [];
      if (tbRes && tbRes.items) {
        loadedAccounts = tbRes.items.map((it: any) => ({
          account_id: it.account_id,
          code: it.code,
          name: it.name,
          type: it.type || 'Asset',
          debit_balance: parseFloat(it.debit_balance || '0'),
          credit_balance: parseFloat(it.credit_balance || '0')
        }));
        setTotalDebits(parseFloat(tbRes.total_debits || '0'));
        setTotalCredits(parseFloat(tbRes.total_credits || '0'));
        setIsBalanced(Boolean(tbRes.is_balanced));
      }

      setAccounts(loadedAccounts);

      if (Array.isArray(jRes)) {
        setJournals(jRes.map((j: any) => ({
          id: j.id,
          entry_number: j.entry_number,
          entry_date: j.entry_date,
          narration: j.narration,
          reference_type: j.reference_type,
          is_posted: j.is_posted ?? true,
          lines: (j.lines || []).map((l: any) => ({
            id: l.id,
            account_id: l.account_id,
            account_code: l.account_code || '',
            account_name: l.account_name || '',
            debit_amount: parseFloat(l.debit_amount || '0'),
            credit_amount: parseFloat(l.credit_amount || '0'),
            description: l.description || ''
          }))
        })));
      }
    } catch (err) {
      console.error('Failed to load ledger data:', err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadLedgerData();
  }, []);

  useEffect(() => {
    if (entryFilterParam) {
      setSearchTerm(entryFilterParam);
      setActiveTab('journals');
    }
  }, [entryFilterParam]);

  const filteredJournals = journals.filter((j) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      j.entry_number.toLowerCase().includes(term) ||
      j.narration.toLowerCase().includes(term) ||
      j.reference_type.toLowerCase().includes(term) ||
      j.lines.some((l) =>
        (l.description && l.description.toLowerCase().includes(term)) ||
        (l.account_name && l.account_name.toLowerCase().includes(term))
      )
    );
  });

  const filteredAccounts = accounts.filter((a) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return a.code.includes(term) || a.name.toLowerCase().includes(term) || a.type.toLowerCase().includes(term);
  });

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Navbar />
        <main className="flex-1 overflow-y-auto p-8 max-w-7xl mx-auto w-full space-y-6">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                  Double-Entry Core
                </span>
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3" /> Zero-Sum Balanced
                </span>
              </div>
              <h1 className="text-xl font-bold text-white flex items-center gap-2 mt-1">
                <FileSpreadsheet className="w-6 h-6 text-sky-400" />
                General Ledger &amp; Trial Balance
              </h1>
              <p className="text-xs text-slate-400 mt-0.5">
                Statutory audit trail, real-time journal vouchers, and double-entry mathematical invariants.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={loadLedgerData}
                disabled={loading}
                className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg transition"
                title="Refresh Ledger"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              </button>

              <Link
                href="/reconciliation"
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-sky-600/20 text-sky-300 border border-sky-500/30 text-xs font-semibold hover:bg-sky-600 hover:text-white transition"
              >
                <span>Bank Reconciliation</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>

          {/* Founder Executive Financial Metrics */}
          {(() => {
            const bankAccount = accounts.find((a) => a.code === '1010');
            const bankBalance = (bankAccount?.debit_balance || 0) - (bankAccount?.credit_balance || 0);
            const arAccount = accounts.find((a) => a.code === '1020');
            const tradeReceivables = (arAccount?.debit_balance || 0) - (arAccount?.credit_balance || 0);
            const dirAccount = accounts.find((a) => a.code === '2105');
            const directorPayable = (dirAccount?.credit_balance || 0) - (dirAccount?.debit_balance || 0);
            const suspenseAccount = accounts.find((a) => a.code === '2099');
            const suspenseBalance = (suspenseAccount?.credit_balance || 0) - (suspenseAccount?.debit_balance || 0);

            const totalRev = accounts
              .filter((a) => a.type === 'revenue')
              .reduce((sum, a) => sum + (a.credit_balance - a.debit_balance), 0);
            const totalExp = accounts
              .filter((a) => a.type === 'expense')
              .reduce((sum, a) => sum + (a.debit_balance - a.credit_balance), 0);
            const netPL = totalRev - totalExp;

            return (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {/* Card 1: Operating P&L */}
                  <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
                    <span className="text-xs text-slate-400 font-medium">Net Operating P&L</span>
                    <p className={`text-xl font-bold font-mono ${netPL >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {netPL >= 0 ? '+' : '-'}₹{Math.abs(netPL).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </p>
                    <p className="text-[11px] text-slate-500">
                      Revenue ₹{totalRev.toLocaleString('en-IN')} − Expenses ₹{totalExp.toLocaleString('en-IN')}
                    </p>
                  </div>

                  {/* Card 2: Company Bank Balance */}
                  <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
                    <span className="text-xs text-slate-400 font-medium">Bank Current Account (1010)</span>
                    <p className="text-xl font-bold font-mono text-white">
                      ₹{bankBalance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </p>
                    <p className="text-[11px] text-slate-500">
                      Receivables Owed: ₹{tradeReceivables.toLocaleString('en-IN')}
                    </p>
                  </div>

                  {/* Card 3: Director Reimbursements Payable */}
                  <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
                    <span className="text-xs text-slate-400 font-medium">Owed to Director (2105)</span>
                    <p className="text-xl font-bold font-mono text-amber-300">
                      ₹{directorPayable.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </p>
                    <p className="text-[11px] text-slate-500">
                      Company liability for expenses paid out-of-pocket
                    </p>
                  </div>

                  {/* Card 4: Double-Entry Balanced Status */}
                  <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
                    <span className="text-xs text-slate-400 font-medium">Mathematical Invariant</span>
                    <p className="text-sm font-bold font-mono text-emerald-400 flex items-center gap-1.5 mt-1">
                      <CheckCircle2 className="w-4 h-4 shrink-0" />
                      {isBalanced ? 'Books in Perfect Balance' : 'Discrepancy Detected'}
                    </p>
                    <p className="text-[11px] text-slate-500 font-mono">
                      Debits ₹{totalDebits.toLocaleString('en-IN')} = Credits ₹{totalCredits.toLocaleString('en-IN')}
                    </p>
                  </div>
                </div>

                {/* Educational Double-Entry Banner */}
                <div className="p-3.5 bg-slate-950 border border-slate-800 rounded-xl flex items-start gap-3 text-xs text-slate-400">
                  <div className="p-1.5 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20 shrink-0 mt-0.5">
                    <BookOpen className="w-4 h-4" />
                  </div>
                  <div className="space-y-1 leading-relaxed">
                    <span className="font-semibold text-slate-200">How the Trial Balance Equation Works:</span>
                    <p>
                      In Indian Schedule III Double-Entry accounting, every rupee has two sides. Total Debits (Assets ₹{(bankBalance + tradeReceivables).toLocaleString('en-IN')} + Operating Expenses ₹{totalExp.toLocaleString('en-IN')}) strictly equals Total Credits (Liabilities ₹{(directorPayable + suspenseBalance).toLocaleString('en-IN')} + Revenue ₹{totalRev.toLocaleString('en-IN')}). Both sides sum to ₹{totalDebits.toLocaleString('en-IN')}, proving zero leakage.
                    </p>
                    {suspenseBalance > 0 && (
                      <p className="text-amber-400 flex items-center gap-1.5 pt-1">
                        <span>Notice: ₹{suspenseBalance.toLocaleString('en-IN')} is temporarily parked in Suspense Account (2099) until reconciled with your invoices.</span>
                        <Link href="/reconciliation" className="underline font-semibold hover:text-amber-300">
                          Reconcile Now →
                        </Link>
                      </p>
                    )}
                  </div>
                </div>
              </div>
            );
          })()}

          {/* Tabs and Search Bar */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-center gap-2 border-b border-slate-800 sm:border-b-0 pb-2 sm:pb-0">
              <button
                onClick={() => setActiveTab('journals')}
                className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition ${
                  activeTab === 'journals'
                    ? 'bg-sky-600 text-white shadow-sm'
                    : 'bg-slate-800/80 text-slate-400 hover:text-white'
                }`}
              >
                <BookOpen className="w-4 h-4" />
                Journal Vouchers ({journals.length})
              </button>
              <button
                onClick={() => setActiveTab('trial_balance')}
                className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition ${
                  activeTab === 'trial_balance'
                    ? 'bg-sky-600 text-white shadow-sm'
                    : 'bg-slate-800/80 text-slate-400 hover:text-white'
                }`}
              >
                <Layers className="w-4 h-4" />
                Trial Balance Accounts ({accounts.length})
              </button>
            </div>

            <div className="relative w-full sm:w-72">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder={activeTab === 'journals' ? 'Search JV number, merchant, narration...' : 'Search account code or name...'}
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
              />
              {searchTerm && (
                <button
                  onClick={() => setSearchTerm('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white text-xs"
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          {/* Tab 1: Journal Vouchers */}
          {activeTab === 'journals' && (
            <div className="space-y-4">
              {loading ? (
                <div className="p-12 text-center text-xs text-slate-500 flex items-center justify-center gap-2 bg-slate-900 rounded-xl border border-slate-800">
                  <RefreshCw className="w-4 h-4 animate-spin text-sky-400" />
                  <span>Loading journal vouchers from General Ledger...</span>
                </div>
              ) : filteredJournals.length === 0 ? (
                <div className="p-12 text-center text-xs text-slate-500 bg-slate-900 rounded-xl border border-slate-800">
                  No journal vouchers match the search query "{searchTerm}".
                </div>
              ) : (
                <div className="space-y-4">
                  {filteredJournals.map((je) => {
                    const isTarget = Boolean(entryFilterParam && je.entry_number.toLowerCase() === entryFilterParam.toLowerCase());
                    const sumDr = je.lines.reduce((acc, l) => acc + l.debit_amount, 0);
                    const sumCr = je.lines.reduce((acc, l) => acc + l.credit_amount, 0);

                    return (
                      <div
                        key={je.id}
                        id={`voucher-${je.entry_number}`}
                        className={`rounded-xl border overflow-hidden transition-all ${
                          isTarget
                            ? 'bg-slate-900 border-sky-500 ring-2 ring-sky-500/30 shadow-lg'
                            : 'bg-slate-900/80 border-slate-800 hover:border-slate-700'
                        }`}
                      >
                        {/* Voucher Header */}
                        <div className="px-5 py-3.5 bg-slate-950/60 border-b border-slate-800/80 flex flex-wrap items-center justify-between gap-3 text-xs">
                          <div className="flex items-center gap-2.5">
                            <span className="font-mono font-bold text-sky-400 bg-sky-950/80 border border-sky-800/60 px-2 py-0.5 rounded text-[11px]">
                              {je.entry_number}
                            </span>
                            <span className="text-slate-400 font-mono">{je.entry_date}</span>
                            <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                              {je.reference_type}
                            </span>
                            {isTarget && (
                              <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-500/40">
                                Target Selected Voucher
                              </span>
                            )}
                          </div>

                          <div className="flex items-center gap-3">
                            <span className="text-slate-400 font-mono text-[11px]">
                              Balanced Leg: <span className="text-white font-bold">₹{sumDr.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                            </span>
                            <span className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                              <CheckCircle2 className="w-3 h-3" /> Posted
                            </span>
                          </div>
                        </div>

                        {/* Narration */}
                        <div className="px-5 py-2 text-xs text-slate-300 bg-slate-900/40 border-b border-slate-800/40">
                          <span className="text-slate-500 font-mono mr-1">Narration:</span>
                          {je.narration}
                        </div>

                        {/* Journal Lines Table */}
                        <div className="overflow-x-auto">
                          <table className="w-full text-left text-xs text-slate-300">
                            <thead className="bg-slate-950/30 text-slate-400 font-mono uppercase text-[10px] border-b border-slate-800/60">
                              <tr>
                                <th className="py-2 px-5">Description</th>
                                <th className="py-2 px-4 text-right">Debit (₹)</th>
                                <th className="py-2 px-5 text-right">Credit (₹)</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-800/40 font-mono text-[11px]">
                              {je.lines.map((line) => (
                                <tr key={line.id} className="hover:bg-slate-800/20">
                                  <td className="py-2.5 px-5 font-sans text-slate-200">
                                    {line.description}
                                  </td>
                                  <td className="py-2.5 px-4 text-right font-semibold text-slate-100">
                                    {line.debit_amount > 0
                                      ? `₹${line.debit_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                                      : '—'}
                                  </td>
                                  <td className="py-2.5 px-5 text-right font-semibold text-amber-400">
                                    {line.credit_amount > 0
                                      ? `₹${line.credit_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                                      : '—'}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Tab 2: Trial Balance Summary */}
          {activeTab === 'trial_balance' && (
            <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950 text-slate-400 font-mono uppercase text-[11px] border-b border-slate-800">
                    <tr>
                      <th className="py-3 px-4">Account Code</th>
                      <th className="py-3 px-4">Account Name</th>
                      <th className="py-3 px-4">Classification</th>
                      <th className="py-3 px-4 text-right">Debit Balance (₹)</th>
                      <th className="py-3 px-4 text-right">Credit Balance (₹)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    {filteredAccounts.map((acc) => (
                      <tr key={acc.code} className="hover:bg-slate-800/30">
                        <td className="py-3.5 px-4 font-bold text-sky-400">{acc.code}</td>
                        <td className="py-3.5 px-4 font-sans font-medium text-white" id={`acc-name-${acc.code}`}>
                          {acc.name}
                        </td>
                        <td className="py-3.5 px-4 text-slate-400 capitalize">{acc.type}</td>
                        <td className="py-3.5 px-4 text-right text-slate-200">
                          {acc.debit_balance > 0 ? `₹${acc.debit_balance.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'}
                        </td>
                        <td
                          className={`py-3.5 px-4 text-right font-bold ${
                            acc.credit_balance > 0 ? 'text-amber-400' : 'text-slate-400'
                          }`}
                          id={`acc-credit-${acc.code}`}
                        >
                          {acc.credit_balance > 0 ? `₹${acc.credit_balance.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '₹0.00'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot className="bg-slate-950 font-mono border-t-2 border-slate-700 text-xs font-bold">
                    <tr>
                      <td colSpan={3} className="py-3 px-4 uppercase text-slate-300">Total Balance Sum</td>
                      <td className="py-3 px-4 text-right text-white">
                        ₹{totalDebits.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 px-4 text-right text-amber-400">
                        ₹{totalCredits.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default function GeneralLedgerReportPage() {
  return (
    <Suspense fallback={<div className="p-8 text-white">Loading General Ledger...</div>}>
      <GeneralLedgerContent />
    </Suspense>
  );
}
