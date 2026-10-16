'use client';

import React, { useState, useEffect } from 'react';
import {
  FileText,
  IndianRupee,
  CheckCircle2,
  Clock,
  Download,
  Plus,
  RefreshCw,
  AlertTriangle,
  Building2,
  FileCheck,
  Calendar,
  ExternalLink
} from 'lucide-react';
import { fetchApi, fetchRawApi } from '@/lib/api';

interface TDSSummary {
  fiscal_year: string;
  total_deducted: number;
  total_deposited: number;
  total_pending_deposit: number;
  next_due_date: string;
  pending_count: number;
  deposited_count: number;
}

interface TDSDeduction {
  id: string;
  section: string;
  section_description?: string;
  deductee_name?: string;
  deductee_pan?: string;
  pan_status: string;
  gross_amount: number;
  rate_pct: number;
  tds_amount: number;
  deduction_date: string;
  status: string;
  challan_id?: string;
  challan_bsr_code?: string;
  challan_serial_no?: string;
  challan_payment_date?: string;
}

export function TDSComplianceTab() {
  const [summary, setSummary] = useState<TDSSummary | null>(null);
  const [deductions, setDeductions] = useState<TDSDeduction[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFy, setSelectedFy] = useState<string>('2026-27');
  const [selectedQuarter, setSelectedQuarter] = useState<string>('Q3');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  // Modal State for ITNS 281 Challan
  const [isChallanModalOpen, setIsChallanModalOpen] = useState(false);
  const [bsrCode, setBsrCode] = useState('');
  const [challanSerial, setChallanSerial] = useState('');
  const [challanPaymentDate, setChallanPaymentDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [selectedDeductionIds, setSelectedDeductionIds] = useState<string[]>([]);
  const [challanSubmitting, setChallanSubmitting] = useState(false);
  const [challanError, setChallanError] = useState<string | null>(null);
  const [challanSuccess, setChallanSuccess] = useState<string | null>(null);

  // Form 26Q Export State
  const [exporting26Q, setExporting26Q] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const summaryData = await fetchApi(`/api/v1/tds/summary?fiscal_year=${selectedFy}`);
      setSummary(summaryData);

      const statusParam = statusFilter !== 'ALL' ? `&status=${statusFilter}` : '';
      const deductionsData = await fetchApi(`/api/v1/tds/deductions?fiscal_year=${selectedFy}${statusParam}`);
      setDeductions(deductionsData || []);
    } catch (err) {
      console.error('Error fetching TDS compliance data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedFy, statusFilter]);

  const handleSelectAllPending = () => {
    const pendingIds = deductions.filter(d => d.status === 'PENDING_DEPOSIT').map(d => d.id);
    if (selectedDeductionIds.length === pendingIds.length) {
      setSelectedDeductionIds([]);
    } else {
      setSelectedDeductionIds(pendingIds);
    }
  };

  const handleToggleDeduction = (id: string) => {
    setSelectedDeductionIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const handleRecordChallan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedDeductionIds.length === 0) {
      setChallanError('Please select at least one deduction to link to this Challan.');
      return;
    }
    if (!bsrCode || bsrCode.length !== 7) {
      setChallanError('BSR Code must be exactly 7 numeric digits.');
      return;
    }
    if (!challanSerial || challanSerial.length < 5) {
      setChallanError('Challan Serial Number must be at least 5 digits.');
      return;
    }

    setChallanSubmitting(true);
    setChallanError(null);
    setChallanSuccess(null);

    try {
      const payload = {
        bsr_code: bsrCode.trim(),
        challan_serial_no: challanSerial.trim(),
        payment_date: challanPaymentDate,
        fiscal_year: selectedFy,
        quarter: selectedQuarter,
        minor_head: '200',
        deduction_ids: selectedDeductionIds,
        auto_post_jv: true
      };

      const res = await fetchApi('/api/v1/tds/record-challan', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      setChallanSuccess(`Challan recorded! Auto-posted Journal Entry ${res.journal_entry_number || ''}`);
      setTimeout(() => {
        setIsChallanModalOpen(false);
        setChallanSuccess(null);
        setSelectedDeductionIds([]);
        setBsrCode('');
        setChallanSerial('');
        loadData();
      }, 1500);
    } catch (err: any) {
      setChallanError(err.message || 'Failed to record Challan ITNS 281');
    } finally {
      setChallanSubmitting(false);
    }
  };

  const handleExportForm26Q = async () => {
    setExporting26Q(true);
    try {
      const res = await fetchRawApi(`/api/v1/tds/form26q-export?fiscal_year=${selectedFy}&quarter=${selectedQuarter}`);
      if (!res.ok) {
        throw new Error('Failed to generate Form 26Q file');
      }
      const text = await res.text();
      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `FORM26Q_${selectedFy}_${selectedQuarter}.txt`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      alert(`Error exporting Form 26Q: ${err.message}`);
    } finally {
      setExporting26Q(false);
    }
  };

  const formatINR = (val: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(val);
  };

  return (
    <div className="space-y-6">
      {/* Top Controls Banner */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs uppercase font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
              Chapter XVII-B Compliance
            </span>
            <span className="text-xs font-mono text-slate-400">
              Sections 194C, 194J, 194I, 194Q &amp; 206AA
            </span>
          </div>
          <h2 className="text-xl font-bold text-white mt-1">
            Indian TDS &amp; TCS Withholding Engine
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Automated liability splitting, ITNS 281 Challan bank remittance, and Protean/NSDL Form 26Q e-TDS export.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <select
            value={selectedFy}
            onChange={(e) => setSelectedFy(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-sky-300 text-xs rounded-lg px-3 py-2 font-mono focus:outline-none focus:border-sky-500"
          >
            <option value="2026-27">FY 2026-27 (AY 2027-28)</option>
            <option value="2025-26">FY 2025-26 (AY 2026-27)</option>
            <option value="2024-25">FY 2024-25 (AY 2025-26)</option>
          </select>

          <select
            value={selectedQuarter}
            onChange={(e) => setSelectedQuarter(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-2 font-mono focus:outline-none focus:border-slate-500"
          >
            <option value="Q1">Q1 (Apr - Jun)</option>
            <option value="Q2">Q2 (Jul - Sep)</option>
            <option value="Q3">Q3 (Oct - Dec)</option>
            <option value="Q4">Q4 (Jan - Mar)</option>
          </select>

          <button
            onClick={() => {
              setSelectedDeductionIds(deductions.filter(d => d.status === 'PENDING_DEPOSIT').map(d => d.id));
              setIsChallanModalOpen(true);
            }}
            className="px-3.5 py-2 bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold rounded-lg shadow-sm flex items-center gap-1.5 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Record ITNS 281 Challan
          </button>

          <button
            onClick={handleExportForm26Q}
            disabled={exporting26Q}
            className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-900 text-white text-xs font-semibold rounded-lg shadow-sm flex items-center gap-1.5 transition-colors"
          >
            <Download className="w-4 h-4" />
            {exporting26Q ? 'Generating...' : 'Export Form 26Q (NSDL)'}
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Total Deducted YTD</span>
            <span className="p-1.5 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
              <IndianRupee className="w-4 h-4" />
            </span>
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-2">
            {formatINR(summary?.total_deducted || 0)}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            Gross TDS withheld from vendor disbursements
          </p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Deposited (ITNS 281)</span>
            <span className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <CheckCircle2 className="w-4 h-4" />
            </span>
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400 mt-2">
            {formatINR(summary?.total_deposited || 0)}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            Remitted to Central Govt via OLTAS
          </p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Pending Deposit</span>
            <span className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <Clock className="w-4 h-4" />
            </span>
          </div>
          <div className="text-2xl font-bold font-mono text-amber-400 mt-2">
            {formatINR(summary?.total_pending_deposit || 0)}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            {summary?.pending_count || 0} deduction(s) awaiting remittance
          </p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Next Statutory Due Date</span>
            <span className="p-1.5 rounded-lg bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <Calendar className="w-4 h-4" />
            </span>
          </div>
          <div className="text-xl font-bold font-mono text-rose-300 mt-2">
            {summary?.next_due_date || '7th of Next Month'}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            Due 7th u/r 30 (30th April for March)
          </p>
        </div>
      </div>

      {/* Deductions Register */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <FileText className="w-4 h-4 text-sky-400" />
              TDS Withholding Sub-Ledger Register
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Breakdown of individual deductions across sub-accounts 2060, 2061, 2062, and 2063.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Filter:</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="bg-slate-950 border border-slate-700 text-xs rounded-lg px-2.5 py-1 text-slate-200 font-medium focus:outline-none"
            >
              <option value="ALL">All Deductions</option>
              <option value="PENDING_DEPOSIT">Pending Deposit</option>
              <option value="DEPOSITED">Deposited (Challan Attached)</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="py-12 text-center text-slate-500 text-xs font-mono">
            Loading TDS records...
          </div>
        ) : deductions.length === 0 ? (
          <div className="py-12 text-center text-slate-500 space-y-2">
            <CheckCircle2 className="w-8 h-8 text-slate-600 mx-auto" />
            <p className="text-sm font-medium text-slate-400">No TDS deductions found for {selectedFy}.</p>
            <p className="text-xs text-slate-500">
              When booking vendor expenses with TDS withholding, deductions will appear here automatically.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                  <th className="p-3 w-8">
                    <input
                      type="checkbox"
                      checked={
                        deductions.filter(d => d.status === 'PENDING_DEPOSIT').length > 0 &&
                        selectedDeductionIds.length === deductions.filter(d => d.status === 'PENDING_DEPOSIT').length
                      }
                      onChange={handleSelectAllPending}
                      className="rounded border-slate-700 text-amber-500 focus:ring-0 cursor-pointer"
                    />
                  </th>
                  <th className="p-3">Date</th>
                  <th className="p-3">Deductee / PAN</th>
                  <th className="p-3">Section</th>
                  <th className="p-3 text-right">Gross (₹)</th>
                  <th className="p-3 text-right">Rate</th>
                  <th className="p-3 text-right">TDS Withheld (₹)</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Challan Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {deductions.map((row) => (
                  <tr key={row.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="p-3">
                      {row.status === 'PENDING_DEPOSIT' ? (
                        <input
                          type="checkbox"
                          checked={selectedDeductionIds.includes(row.id)}
                          onChange={() => handleToggleDeduction(row.id)}
                          className="rounded border-slate-700 text-amber-500 focus:ring-0 cursor-pointer"
                        />
                      ) : (
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                      )}
                    </td>
                    <td className="p-3 text-slate-300">{row.deduction_date}</td>
                    <td className="p-3">
                      <div className="font-semibold text-white">{row.deductee_name || 'Vendor'}</div>
                      <div className="text-[11px] text-slate-400 font-mono">
                        {row.deductee_pan || 'PAN NOT PROVIDED'}
                        {row.pan_status === 'INVALID_OR_MISSING' && (
                          <span className="ml-1.5 text-rose-400 font-bold">(Sec 206AA: 20%)</span>
                        )}
                      </div>
                    </td>
                    <td className="p-3">
                      <span className="px-2 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800/60 font-bold">
                        {row.section}
                      </span>
                    </td>
                    <td className="p-3 text-right font-medium text-slate-300">
                      {formatINR(row.gross_amount)}
                    </td>
                    <td className="p-3 text-right font-semibold text-amber-400">
                      {row.rate_pct}%
                    </td>
                    <td className="p-3 text-right font-bold text-white">
                      {formatINR(row.tds_amount)}
                    </td>
                    <td className="p-3">
                      {row.status === 'DEPOSITED' ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                          <CheckCircle2 className="w-3 h-3" /> DEPOSITED
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30">
                          <Clock className="w-3 h-3" /> PENDING
                        </span>
                      )}
                    </td>
                    <td className="p-3 text-slate-400 text-[11px]">
                      {row.challan_serial_no ? (
                        <div>
                          <span className="text-slate-300 font-semibold">BSR: {row.challan_bsr_code}</span>
                          <span className="ml-1.5 text-slate-400">Challan: {row.challan_serial_no}</span>
                          <div className="text-[10px] text-slate-500">{row.challan_payment_date}</div>
                        </div>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Record Challan ITNS 281 Modal */}
      {isChallanModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Building2 className="w-5 h-5 text-amber-400" />
                Record Challan ITNS 281 Remittance
              </h3>
              <button
                onClick={() => setIsChallanModalOpen(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleRecordChallan} className="space-y-4 text-xs">
              <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300">
                You have selected <span className="font-bold">{selectedDeductionIds.length}</span> pending deduction(s).
                Posting this challan will automatically post a balanced Journal Entry:
                <div className="font-mono mt-1 text-[11px] text-white">
                  DR 206x (TDS Payable) ⇌ CR 1010 (Company Bank Account)
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">
                    BSR Code (7 Digits)*
                  </label>
                  <input
                    type="text"
                    maxLength={7}
                    value={bsrCode}
                    onChange={(e) => setBsrCode(e.target.value.replace(/\D/g, ''))}
                    placeholder="e.g. 0510302"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-amber-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-semibold mb-1">
                    Challan Serial No*
                  </label>
                  <input
                    type="text"
                    maxLength={10}
                    value={challanSerial}
                    onChange={(e) => setChallanSerial(e.target.value.replace(/\D/g, ''))}
                    placeholder="e.g. 00045"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-amber-500"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">
                    Payment Date*
                  </label>
                  <input
                    type="date"
                    value={challanPaymentDate}
                    onChange={(e) => setChallanPaymentDate(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-amber-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-semibold mb-1">
                    Minor Head
                  </label>
                  <input
                    type="text"
                    disabled
                    value="200 (TDS Payable by Company)"
                    className="w-full bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-2 text-slate-400 font-mono"
                  />
                </div>
              </div>

              {challanError && (
                <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400">
                  {challanError}
                </div>
              )}

              {challanSuccess && (
                <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                  {challanSuccess}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsChallanModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={challanSubmitting}
                  className="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 disabled:bg-amber-800 text-white font-semibold flex items-center gap-1.5"
                >
                  {challanSubmitting ? 'Recording & Balancing...' : 'Confirm ITNS 281 Deposit'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

