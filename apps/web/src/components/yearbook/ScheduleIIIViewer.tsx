'use client';

import React, { useState, useEffect } from 'react';
import {
  FileText,
  Download,
  ShieldCheck,
  TrendingUp,
  Percent,
  Scale,
  Building,
  Calendar,
  CheckCircle2,
  RefreshCw,
  Loader2,
  ExternalLink,
  ChevronDown,
  ChevronUp
} from 'lucide-react';
import { fetchApi } from '@/lib/api';

function getClosingYear(fyStr: string): string {
  if (!fyStr) return '2027';
  const clean = fyStr.replace(/[^0-9]/g, '');
  if (clean.length >= 8) {
    return clean.slice(4, 8);
  }
  if (clean.length === 6) {
    return clean.slice(0, 2) + clean.slice(4, 6);
  }
  const parts = fyStr.split('-');
  if (parts.length > 1) {
    const end = parts[1].trim();
    if (end.length === 2) return `20${end}`;
    if (end.length === 4) return end;
  }
  return '2027';
}

interface ScheduleIIIData {
  company_meta: {
    legal_name: string;
    cin: string;
    pan: string;
    gstin: string;
    registered_office: string;
    entity_type: string;
    auditor_firm: string;
    auditor_proprietor: string;
    auditor_frn: string;
    auditor_mno: string;
    director_name: string;
    director_din: string;
    as_of_date: string;
    financial_year: string;
  };
  balance_sheet: {
    equity_and_liabilities: {
      shareholders_funds: {
        share_capital: number;
        reserves_and_surplus: number;
        total: number;
      };
      non_current_liabilities: {
        long_term_borrowings: number;
        deferred_tax_liabilities: number;
        total: number;
      };
      current_liabilities: {
        short_term_borrowings: number;
        trade_payables: number;
        other_current_liabilities: number;
        short_term_provisions: number;
        total: number;
      };
      total_equity_and_liabilities: number;
    };
    assets: {
      non_current_assets: {
        property_plant_equipment: number;
        ppe_gross: number;
        ppe_depreciation: number;
        long_term_loans: number;
        other_non_current_assets: number;
        total: number;
      };
      current_assets: {
        trade_receivables: number;
        cash_and_bank: number;
        short_term_loans: number;
        other_current_assets: number;
        total: number;
      };
      total_assets: number;
    };
  };
  profit_and_loss: {
    revenue_from_operations: number;
    other_income: number;
    total_revenue: number;
    expenses: {
      employee_benefits: number;
      finance_costs: number;
      depreciation: number;
      other_expenses: number;
      total_expenses: number;
    };
    profit_before_tax: number;
    tax_expense: number;
    profit_for_period: number;
  };
  accounting_ratios: {
    current_ratio: number;
    debt_equity_ratio: number;
    net_profit_margin_percent: number;
    return_on_equity_percent: number;
  };
}

export function formatIndianDateWithSuffix(d: Date): string {
  const day = d.getDate();
  let suffix = 'th';
  if (day < 11 || day > 13) {
    const rem = day % 10;
    if (rem === 1) suffix = 'st';
    else if (rem === 2) suffix = 'nd';
    else if (rem === 3) suffix = 'rd';
  }
  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];
  return `${day}${suffix} ${monthNames[d.getMonth()]}, ${d.getFullYear()}`;
}

export type RoundingUnit = 'hundreds' | 'thousands' | 'lakhs' | 'crores' | 'rupees' | 'raw';

export const formatScheduleIIICurrency = (val: number | undefined | null, unit: RoundingUnit = 'hundreds') => {
  if (val === undefined || val === null) return '-';
  const isNeg = val < 0;
  const abs = Math.abs(val);

  let displayVal = abs;
  let fractionDigits = 2;

  if (unit === 'hundreds') {
    // Schedule III Small Company Default: Rs. '00 (in hundreds with .00 to .99 precision)
    displayVal = abs / 100;
    fractionDigits = 2;
  } else if (unit === 'thousands') {
    displayVal = abs / 1000;
    fractionDigits = 2;
  } else if (unit === 'lakhs') {
    displayVal = abs / 100000;
    fractionDigits = 2;
  } else if (unit === 'crores') {
    displayVal = abs / 10000000;
    fractionDigits = 2;
  } else if (unit === 'rupees') {
    // Whole rupees with paise
    displayVal = abs;
    fractionDigits = 2;
  } else {
    displayVal = abs;
    fractionDigits = 2;
  }

  if (Math.abs(displayVal) < 0.005) return '-';

  const formatted = new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits
  }).format(displayVal);

  return isNeg ? `(${formatted})` : formatted;
};

export const getUnitDescription = (unit: RoundingUnit) => {
  switch (unit) {
    case 'crores':
      return "Amount in Rs. Crores";
    case 'lakhs':
      return "Amount in Rs. Lakhs";
    case 'thousands':
      return "Amount in Rs. '000 (Nearest Thousands)";
    case 'hundreds':
      return "Amount in Rs. '00 (Nearest Hundreds)";
    case 'rupees':
      return "Amount in ₹ (Whole Rupee)";
    case 'raw':
      return "Amount in ₹ (Exact with Paise)";
  }
};

export function ScheduleIIIViewer({ selectedFY }: { selectedFY: string }) {
  const [data, setData] = useState<ScheduleIIIData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [downloading, setDownloading] = useState<boolean>(false);
  const [showNotes, setShowNotes] = useState<boolean>(false);

  // Schedule III Clause 4: Automatic Rounding Determination based on Scale (Turnover / Assets)
  const roundingUnit: RoundingUnit = React.useMemo(() => {
    if (data && (data as any).statutory_unit) {
      const u = String((data as any).statutory_unit).toLowerCase();
      if (['hundreds', 'thousands', 'lakhs', 'crores'].includes(u)) {
        return u as RoundingUnit;
      }
    }
    if (!data) return 'hundreds';
    const totalRev = Math.abs(data.profit_and_loss?.total_revenue || 0);
    const totalAssets = Math.abs(data.balance_sheet?.assets?.total_assets || 0);
    const totalExp = Math.abs(data.profit_and_loss?.expenses?.total_expenses || 0);
    const scaleBase = Math.max(totalRev, totalAssets, totalExp);
    if (scaleBase >= 100_00_00_000) return 'crores';
    if (scaleBase >= 1_00_00_000) return 'lakhs';
    if (scaleBase >= 10_00_000) return 'thousands';
    return 'hundreds';
  }, [data]);

  // Date and Provisional Status Determination
  const dateInfo = React.useMemo(() => {
    const fyStr = selectedFY || 'FY 2026-27';
    const clean = fyStr.replace('FY', '').trim();
    const parts = clean.split('-');
    let startYear = 2026;
    let endYear = 2027;
    if (parts.length > 0 && !isNaN(parseInt(parts[0], 10))) {
      startYear = parseInt(parts[0], 10);
      if (parts.length > 1) {
        const eStr = parts[1].trim();
        endYear = parseInt(eStr.length === 2 ? `20${eStr}` : eStr, 10);
      } else {
        endYear = startYear + 1;
      }
    }
    const fyEnd = new Date(endYear, 2, 31); // 31st March
    const today = new Date();
    const isProvisional = today < fyEnd;
    const effectiveDate = isProvisional ? today : fyEnd;

    return {
      startYear,
      endYear,
      isProvisional,
      effectiveDate,
      bsTitle: isProvisional
        ? `Balance Sheet as at ${formatIndianDateWithSuffix(effectiveDate)} (Provisional)`
        : `Balance Sheet as at 31st March, ${endYear}`,
      pnlTitle: isProvisional
        ? `For the period 1st April, ${startYear} to ${formatIndianDateWithSuffix(effectiveDate)} (Provisional)`
        : `For the year ended 31st March, ${endYear}`
    };
  }, [selectedFY]);

  const formatCurrency = (val: number | undefined | null) => {
    return formatScheduleIIICurrency(val, roundingUnit);
  };

  const loadScheduleIII = async () => {
    setLoading(true);
    try {
      const fyParam = selectedFY ? selectedFY.replace('FY', '').trim() : '';
      const url = fyParam
        ? `/api/v1/reports/schedule-iii-balance-sheet?fy=${encodeURIComponent(fyParam)}`
        : '/api/v1/reports/schedule-iii-balance-sheet';
      const res = await fetchApi(url);
      if (res && res.balance_sheet) {
        setData(res);
      }
    } catch (err) {
      console.error('Failed to load Schedule III summary:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadScheduleIII();
  }, [selectedFY]);

  const handleDownloadPDF = async () => {
    setDownloading(true);
    try {
      const token = typeof window !== 'undefined' ? (localStorage.getItem('b00k5_token') || localStorage.getItem('token')) : null;
      const activeTenant = typeof window !== 'undefined' ? (localStorage.getItem('b00k5_active_tenant_id') || localStorage.getItem('b00k5_tenant_id')) : null;
      
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (activeTenant) headers['X-Tenant-ID'] = activeTenant;

      const fyParam = selectedFY ? selectedFY.replace('FY', '').trim() : '2026-27';
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const res = await fetch(`${apiUrl}/api/v1/vault/export-auditor-pack?fy=${encodeURIComponent(fyParam)}&unit=auto`, {
        headers
      });

      if (!res.ok) throw new Error('Download failed');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Auditor_Dossier_FY${fyParam}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Failed to download Schedule III pack:', e);
      alert('Could not download auditor pack. Please ensure you are logged in as Owner or Auditor.');
    } finally {
      setDownloading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 bg-slate-900/40 rounded-xl border border-slate-800 text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-amber-400 mb-3" />
        <p className="text-sm">Calculating Schedule III Division I Balances from Live Ledger...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-8 text-center bg-slate-900/40 rounded-xl border border-slate-800 text-slate-400">
        <p className="text-sm">No general ledger data available for the active period.</p>
      </div>
    );
  }

  const { company_meta, balance_sheet, profit_and_loss, accounting_ratios } = data;
  const eq = balance_sheet.equity_and_liabilities;
  const ast = balance_sheet.assets;
  const pnl = profit_and_loss;

  return (
    <div className="space-y-6">
      {/* Top Banner / Compliance Seal */}
      <div className="bg-gradient-to-r from-amber-500/10 via-slate-900/50 to-slate-900/80 p-5 rounded-xl border border-amber-500/20 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-medium">
              Companies Act 2013 - Schedule III Division I
            </span>
            <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-medium flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" /> Zero-Sum Verified
            </span>
          </div>
          <h2 className="text-lg font-bold text-white tracking-tight">{company_meta.legal_name}</h2>
          <p className="text-xs text-slate-400">
            CIN: <span className="font-mono text-slate-300">{company_meta.cin}</span> | PAN: <span className="font-mono text-slate-300">{company_meta.pan}</span> | Auditor: <span className="text-slate-300">{company_meta.auditor_firm}</span> (FRN: {company_meta.auditor_frn})
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Schedule III Clause 4 Automatic Rounding Badge */}
          <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 rounded-xl px-3 py-1.5 text-xs shadow-inner">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="text-slate-400 font-mono text-[11px] uppercase tracking-wider font-semibold">Schedule III Cl. 4:</span>
            <span className="text-amber-400 font-mono font-medium">{getUnitDescription(roundingUnit)}</span>
            <span className="text-[10px] text-slate-400 bg-slate-800 px-1.5 py-0.5 rounded border border-slate-700">Auto</span>
          </div>

          <button
            onClick={loadScheduleIII}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
            title="Refresh Ledger"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={handleDownloadPDF}
            disabled={downloading}
            className="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold text-xs rounded-lg shadow-sm transition disabled:opacity-50"
          >
            {downloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            Download Certified Schedule III PDF
          </button>
        </div>
      </div>

      {/* Mandatory Accounting Ratios Cards (Schedule III 2021 Amendment Mandate) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-slate-900/60 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>(a) Current Ratio</span>
            <Scale className="w-4 h-4 text-sky-400" />
          </div>
          <div className="text-xl font-bold text-white font-mono">
            {accounting_ratios.current_ratio > 0 ? `${accounting_ratios.current_ratio}x` : '—'}
          </div>
          <p className="text-[10px] text-slate-500 mt-1">Current Assets / Current Liabilities (Benchmark: &gt; 1.33)</p>
        </div>

        <div className="p-4 bg-slate-900/60 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>(b) Debt-Equity Ratio</span>
            <Scale className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-xl font-bold text-white font-mono">
            {accounting_ratios.debt_equity_ratio > 0 ? `${accounting_ratios.debt_equity_ratio}` : '0.00'}
          </div>
          <p className="text-[10px] text-slate-500 mt-1">Total Debt / Total Shareholder Funds</p>
        </div>

        <div className="p-4 bg-slate-900/60 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>(i) Net Profit Margin</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <div className={`text-xl font-bold font-mono ${accounting_ratios.net_profit_margin_percent >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {accounting_ratios.net_profit_margin_percent}%
          </div>
          <p className="text-[10px] text-slate-500 mt-1">Net Profit After Tax / Revenue</p>
        </div>

        <div className="p-4 bg-slate-900/60 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>(d) Return on Equity (ROE)</span>
            <Percent className="w-4 h-4 text-amber-400" />
          </div>
          <div className={`text-xl font-bold font-mono ${accounting_ratios.return_on_equity_percent >= 0 ? 'text-amber-400' : 'text-rose-400'}`}>
            {accounting_ratios.return_on_equity_percent}%
          </div>
          <p className="text-[10px] text-slate-500 mt-1">Net Profit / Shareholder Equity</p>
        </div>
      </div>

      {/* Grid: Balance Sheet & Profit and Loss */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* PART I: VERTICAL BALANCE SHEET */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-xl overflow-hidden">
          <div className="p-4 bg-slate-800/40 border-b border-slate-800 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-white">{dateInfo.bsTitle}</h3>
              <p className="text-xs text-slate-400">Division I - Non-Ind AS Financial Statements</p>
            </div>
            <span className="text-xs text-amber-400 font-mono font-medium">({getUnitDescription(roundingUnit)})</span>
          </div>

          <div className="divide-y divide-slate-800/60 text-xs">
            {/* I. EQUITY AND LIABILITIES */}
            <div className="p-3 bg-slate-950/40 font-bold text-amber-300">
              I. EQUITY AND LIABILITIES
            </div>

            {/* 1. Shareholders' Funds */}
            <div className="p-3 space-y-1.5 bg-slate-900/30">
              <div className="font-semibold text-slate-300">1. Shareholders' Funds</div>
              <div className="flex justify-between text-slate-400 pl-4">
                <span>(a) Share Capital [Note 2]</span>
                <span className="font-mono text-slate-200">{formatCurrency(eq.shareholders_funds.share_capital)}</span>
              </div>
              <div className="flex justify-between text-slate-400 pl-4">
                <span>(b) Reserves and Surplus [Note 3]</span>
                <span className="font-mono text-slate-200">{formatCurrency(eq.shareholders_funds.reserves_and_surplus)}</span>
              </div>
              <div className="flex justify-between font-medium text-slate-300 pt-1 border-t border-slate-800/40 pl-4">
                <span>Sub-total: Shareholders' Funds</span>
                <span className="font-mono">{formatCurrency(eq.shareholders_funds.total)}</span>
              </div>
            </div>

            {/* 2. Non-Current Liabilities */}
            <div className="p-3 space-y-1.5 bg-slate-900/30">
              <div className="font-semibold text-slate-300">2. Non-Current Liabilities</div>
              <div className="flex justify-between text-slate-400 pl-4">
                <span>(a) Long-term Borrowings [Note 4]</span>
                <span className="font-mono text-slate-200">{formatCurrency(eq.non_current_liabilities.long_term_borrowings)}</span>
              </div>
              <div className="flex justify-between font-medium text-slate-300 pt-1 border-t border-slate-800/40 pl-4">
                <span>Sub-total: Non-Current Liabilities</span>
                <span className="font-mono">{formatCurrency(eq.non_current_liabilities.total)}</span>
              </div>
            </div>

            {/* 3. Current Liabilities */}
            <div className="p-3 space-y-1.5 bg-slate-900/30">
              <div className="font-semibold text-slate-300">3. Current Liabilities</div>
              <div className="flex justify-between text-slate-400 pl-4">
                <span>(a) Short-term Borrowings [Note 5]</span>
                <span className="font-mono text-slate-200">{formatCurrency(eq.current_liabilities.short_term_borrowings)}</span>
              </div>
              <div className="flex justify-between text-slate-400 pl-4">
                <span>(b) Trade Payables [Note 6]</span>
                <span className="font-mono text-slate-200">{formatCurrency(eq.current_liabilities.trade_payables)}</span>
              </div>
              <div className="flex justify-between text-slate-400 pl-4">
                <span>(c) Other Current Liabilities [Note 7]</span>
                <span className="font-mono text-slate-200">{formatCurrency(eq.current_liabilities.other_current_liabilities)}</span>
              </div>
              <div className="flex justify-between text-slate-400 pl-4">
                <span>(d) Short-term Provisions [Note 8]</span>
                <span className="font-mono text-slate-200">{formatCurrency(eq.current_liabilities.short_term_provisions)}</span>
              </div>
              <div className="flex justify-between font-medium text-slate-300 pt-1 border-t border-slate-800/40 pl-4">
                <span>Sub-total: Current Liabilities</span>
                <span className="font-mono">{formatCurrency(eq.current_liabilities.total)}</span>
              </div>
            </div>

            {/* TOTAL EQUITY AND LIABILITIES */}
            <div className="p-3 bg-amber-500/10 font-bold flex justify-between text-amber-300 border-t-2 border-amber-500/30">
              <span>TOTAL EQUITY AND LIABILITIES</span>
              <span className="font-mono text-sm">{formatCurrency(eq.total_equity_and_liabilities)}</span>
            </div>

            {/* II. ASSETS */}
            <div className="p-3 bg-slate-950/40 font-bold text-sky-300">
              II. ASSETS
            </div>

            {/* 1. Non-Current Assets */}
            <div className="p-3 space-y-1.5 bg-slate-900/30">
              <div className="font-semibold text-slate-300">1. Non-Current Assets</div>
              <div className="flex justify-between text-slate-400 pl-4">
                <span>(a) Property, Plant and Equipment [Note 9]</span>
                <span className="font-mono text-slate-200">{formatCurrency(ast.non_current_assets.property_plant_equipment)}</span>
              </div>
              <div className="flex justify-between text-slate-400 pl-4">
                <span>(b) Long-term Loans and Advances [Note 11]</span>
                <span className="font-mono text-slate-200">{formatCurrency(ast.non_current_assets.long_term_loans)}</span>
              </div>
              <div className="flex justify-between font-medium text-slate-300 pt-1 border-t border-slate-800/40 pl-4">
                <span>Sub-total: Non-Current Assets</span>
                <span className="font-mono">{formatCurrency(ast.non_current_assets.total)}</span>
              </div>
            </div>

            {/* 2. Current Assets */}
            <div className="p-3 space-y-1.5 bg-slate-900/30">
              <div className="font-semibold text-slate-300">2. Current Assets</div>
              <div className="flex justify-between text-slate-400 pl-4">
                <span>(a) Trade Receivables [Note 13]</span>
                <span className="font-mono text-slate-200">{formatCurrency(ast.current_assets.trade_receivables)}</span>
              </div>
              <div className="flex justify-between text-slate-400 pl-4">
                <span>(b) Cash and Bank Balances [Note 14]</span>
                <span className="font-mono text-slate-200">{formatCurrency(ast.current_assets.cash_and_bank)}</span>
              </div>
              <div className="flex justify-between text-slate-400 pl-4">
                <span>(c) Short-term Loans and Advances [Note 15]</span>
                <span className="font-mono text-slate-200">{formatCurrency(ast.current_assets.short_term_loans)}</span>
              </div>
              <div className="flex justify-between text-slate-400 pl-4">
                <span>(d) Other Current Assets [Note 15]</span>
                <span className="font-mono text-slate-200">{formatCurrency(ast.current_assets.other_current_assets)}</span>
              </div>
              <div className="flex justify-between font-medium text-slate-300 pt-1 border-t border-slate-800/40 pl-4">
                <span>Sub-total: Current Assets</span>
                <span className="font-mono">{formatCurrency(ast.current_assets.total)}</span>
              </div>
            </div>

            {/* TOTAL ASSETS */}
            <div className="p-3 bg-sky-500/10 font-bold flex justify-between text-sky-300 border-t-2 border-sky-500/30">
              <span>TOTAL ASSETS</span>
              <span className="font-mono text-sm">{formatCurrency(ast.total_assets)}</span>
            </div>
          </div>
        </div>

        {/* PART II: STATEMENT OF PROFIT AND LOSS */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-xl overflow-hidden flex flex-col justify-between">
          <div>
            <div className="p-4 bg-slate-800/40 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white">Statement of Profit and Loss</h3>
                <p className="text-xs text-slate-400">{dateInfo.pnlTitle}</p>
              </div>
              <span className="text-xs text-amber-400 font-mono font-medium">({getUnitDescription(roundingUnit)})</span>
            </div>

            <div className="divide-y divide-slate-800/60 text-xs">
              {/* REVENUE */}
              <div className="p-3 space-y-2 bg-slate-900/30">
                <div className="flex justify-between text-slate-300 font-semibold">
                  <span>I. Revenue from Operations [Note 16]</span>
                  <span className="font-mono text-white">{formatCurrency(pnl.revenue_from_operations)}</span>
                </div>
                <div className="flex justify-between text-slate-400 pl-4">
                  <span>II. Other Income [Note 16]</span>
                  <span className="font-mono text-slate-300">{formatCurrency(pnl.other_income)}</span>
                </div>
                <div className="flex justify-between font-bold text-emerald-300 bg-emerald-500/10 p-2 rounded">
                  <span>III. Total Revenue (I + II)</span>
                  <span className="font-mono">{formatCurrency(pnl.total_revenue)}</span>
                </div>
              </div>

              {/* EXPENSES */}
              <div className="p-3 space-y-2 bg-slate-900/30">
                <div className="font-semibold text-slate-300">IV. Expenses</div>
                <div className="flex justify-between text-slate-400 pl-4">
                  <span>(a) Employee Benefits Expense [Note 17]</span>
                  <span className="font-mono text-slate-200">{formatCurrency(pnl.expenses.employee_benefits)}</span>
                </div>
                <div className="flex justify-between text-slate-400 pl-4">
                  <span>(b) Finance Costs [Note 18]</span>
                  <span className="font-mono text-slate-200">{formatCurrency(pnl.expenses.finance_costs)}</span>
                </div>
                <div className="flex justify-between text-slate-400 pl-4">
                  <span>(c) Depreciation & Amortisation [Note 9]</span>
                  <span className="font-mono text-slate-200">{formatCurrency(pnl.expenses.depreciation)}</span>
                </div>
                <div className="flex justify-between text-slate-400 pl-4">
                  <span>(d) Other Expenses [Note 19]</span>
                  <span className="font-mono text-slate-200">{formatCurrency(pnl.expenses.other_expenses)}</span>
                </div>
                <div className="flex justify-between font-bold text-rose-300 bg-rose-500/10 p-2 rounded">
                  <span>Total Expenses</span>
                  <span className="font-mono">{formatCurrency(pnl.expenses.total_expenses)}</span>
                </div>
              </div>

              {/* PROFIT SUMMARY */}
              <div className="p-3 space-y-2 bg-slate-900/50">
                <div className="flex justify-between text-slate-300 font-semibold">
                  <span>V. Profit Before Exceptional Items and Tax</span>
                  <span className="font-mono">{formatCurrency(pnl.profit_before_tax)}</span>
                </div>
                <div className="flex justify-between text-slate-400 pl-4">
                  <span>VI. Tax Expense (Current & Deferred)</span>
                  <span className="font-mono text-slate-300">{formatCurrency(pnl.tax_expense)}</span>
                </div>
                <div className={`flex justify-between font-bold p-3 rounded text-sm ${pnl.profit_for_period >= 0 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'}`}>
                  <span>VII. Profit / (Loss) for the Period</span>
                  <span className="font-mono">{formatCurrency(pnl.profit_for_period)}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Legal Signatories Footer */}
          <div className="p-4 bg-slate-950/80 border-t border-slate-800 text-[11px] text-slate-400 space-y-2">
            <div className="flex items-center justify-between border-b border-slate-800/60 pb-2">
              <div>
                <p className="font-semibold text-slate-200">For {company_meta.auditor_firm}</p>
                <p className="text-[10px]">Chartered Accountants (FRN: {company_meta.auditor_frn})</p>
                <p className="text-slate-300 mt-1">{company_meta.auditor_proprietor} (M.No: {company_meta.auditor_mno})</p>
              </div>
              <div className="text-right">
                <p className="font-semibold text-slate-200">For and on behalf of the Board</p>
                <p className="text-slate-300 mt-1">{company_meta.director_name}</p>
                <p className="text-[10px]">Director (DIN: {company_meta.director_din})</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

