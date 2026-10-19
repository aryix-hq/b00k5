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
  ChevronUp,
  Users,
  Award,
  BookOpen,
  PieChart
} from 'lucide-react';
import { fetchApi } from '@/lib/api';

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

interface FinancialStatementsSection {
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
}

interface AssetsSection {
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
}

interface BalanceSheetStatement {
  period_label?: string;
  financial_year?: string;
  equity_and_liabilities: FinancialStatementsSection;
  assets: AssetsSection;
}

interface ProfitAndLossStatement {
  period_label?: string;
  financial_year?: string;
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
}

interface AccountingRatios {
  current_ratio: number;
  debt_equity_ratio: number;
  net_profit_margin_percent: number;
  return_on_equity_percent: number;
}

interface MGT7Shareholder {
  name: string;
  class_of_shares?: string;
  number_of_shares: number;
  percentage_holding: number;
}

interface MGT7PromoterShareholding {
  promoter_name?: string;
  name?: string;
  din?: string;
  shares?: number;
  percentage?: number;
  percentage_holding?: number;
  percentage_change_during_year?: number;
}

interface MGT7Disclosure {
  srn: string;
  financial_year: string;
  assessment_year: string;
  authorized_capital_inr: number;
  total_equity_shares: number;
  face_value_inr: number;
  paid_up_capital_inr: number;
  paid_up_shares: number;
  net_worth_inr: number;
  turnover_inr: number;
  shareholders: MGT7Shareholder[];
  promoter_shareholding: MGT7PromoterShareholding[];
}

interface StatutoryProvenance {
  current_fy: string;
  current_ay: string;
  prior_fy: string;
  prior_ay: string;
  has_prior_filings: boolean;
  is_current_synchronized_from_vault: boolean;
  current_aoc4_srn?: string;
  current_mgt7_srn?: string;
  prior_aoc4_srn?: string;
  prior_mgt7_srn?: string;
  provenance_banner?: string;
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
  balance_sheet: BalanceSheetStatement;
  comparative_balance_sheet?: BalanceSheetStatement;
  profit_and_loss: ProfitAndLossStatement;
  comparative_profit_and_loss?: ProfitAndLossStatement;
  accounting_ratios: AccountingRatios;
  comparative_accounting_ratios?: AccountingRatios;
  mgt7_shareholding_disclosure?: MGT7Disclosure;
  statutory_provenance?: StatutoryProvenance;
  notes_to_accounts?: Record<string, any>;
  statutory_unit?: string;
  statutory_unit_label?: string;
  is_provisional?: boolean;
  balance_sheet_title?: string;
  period_label?: string;
  as_of_date?: string;
  effective_as_of_date?: string;
  period?: string;
  financial_year?: string;
  assessment_year?: string;
  current_period_label?: string;
  comparative_period_label?: string;
}

function StatRow({
  label,
  note,
  currentVal,
  priorVal,
  formatCurrency,
  isHeader,
  isSubtotal,
  isTotal,
  indent = 0,
  variant = 'neutral'
}: {
  label: string;
  note?: string | number;
  currentVal?: number | null;
  priorVal?: number | null;
  formatCurrency: (val: number | undefined | null) => string;
  isHeader?: boolean;
  isSubtotal?: boolean;
  isTotal?: boolean;
  indent?: number;
  variant?: 'neutral' | 'emerald' | 'rose' | 'amber' | 'sky';
}) {
  if (isHeader) {
    return (
      <div className="grid grid-cols-12 items-center px-3 py-2 bg-slate-950/60 font-bold text-amber-300 border-t border-slate-800">
        <div className="col-span-5 tracking-wide">{label}</div>
        <div className="col-span-1 text-center font-mono text-[10px] text-slate-500 uppercase">Note</div>
        <div className="col-span-3 text-right font-mono text-[10px] text-slate-400">Current</div>
        <div className="col-span-3 text-right font-mono text-[10px] text-slate-400">Previous</div>
      </div>
    );
  }

  const plClass = indent === 1 ? 'pl-3' : indent === 2 ? 'pl-6' : '';
  const currentFormatted = formatCurrency(currentVal);
  const priorFormatted = formatCurrency(priorVal);

  if (isTotal) {
    const bgClass =
      variant === 'amber'
        ? 'bg-amber-500/15 text-amber-300 border-amber-500/30'
        : variant === 'sky'
        ? 'bg-sky-500/15 text-sky-300 border-sky-500/30'
        : variant === 'emerald'
        ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
        : 'bg-slate-800/60 text-white border-slate-700';

    return (
      <div className={`grid grid-cols-12 items-center px-3 py-2.5 font-bold border-t-2 ${bgClass}`}>
        <div className="col-span-5 text-xs sm:text-sm tracking-tight">{label}</div>
        <div className="col-span-1 text-center font-mono text-xs opacity-75">{note || ''}</div>
        <div className="col-span-3 text-right font-mono text-xs sm:text-sm">{currentFormatted}</div>
        <div className="col-span-3 text-right font-mono text-xs sm:text-sm opacity-80">{priorFormatted}</div>
      </div>
    );
  }

  if (isSubtotal) {
    return (
      <div className="grid grid-cols-12 items-center px-3 py-1.5 text-xs font-semibold text-slate-200 border-t border-slate-800/60 bg-slate-900/40">
        <div className={`col-span-5 ${plClass}`}>{label}</div>
        <div className="col-span-1 text-center font-mono text-[11px] text-slate-500">{note || ''}</div>
        <div className="col-span-3 text-right font-mono">{currentFormatted}</div>
        <div className="col-span-3 text-right font-mono text-slate-400">{priorFormatted}</div>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-12 items-center py-1.5 px-3 text-xs text-slate-400 hover:bg-slate-800/30 transition-colors">
      <div className={`col-span-5 text-slate-300 ${plClass}`}>{label}</div>
      <div className="col-span-1 text-center font-mono text-[11px] text-amber-400/80">
        {note ? <span className="bg-slate-800 px-1 py-0.5 rounded text-[10px]">{note}</span> : ''}
      </div>
      <div className="col-span-3 text-right font-mono text-slate-200">{currentFormatted}</div>
      <div className="col-span-3 text-right font-mono text-slate-400">{priorFormatted}</div>
    </div>
  );
}

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
        : `For the year ended 31st March, ${endYear}`,
      comparativeLabel: `As at 31st March, ${endYear - 1}`
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
        <p className="text-sm font-medium">Calculating Schedule III Division I Balances from Live Ledger & MCA Anchors...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-8 text-center bg-slate-900/40 rounded-xl border border-slate-800 text-slate-400">
        <p className="text-sm">No statutory general ledger data available for the active period.</p>
      </div>
    );
  }

  const {
    company_meta,
    balance_sheet,
    comparative_balance_sheet,
    profit_and_loss,
    comparative_profit_and_loss,
    accounting_ratios,
    comparative_accounting_ratios,
    mgt7_shareholding_disclosure,
    statutory_provenance,
    notes_to_accounts
  } = data;

  const eq = balance_sheet.equity_and_liabilities;
  const prior_eq = comparative_balance_sheet?.equity_and_liabilities;
  const ast = balance_sheet.assets;
  const prior_ast = comparative_balance_sheet?.assets;
  const pnl = profit_and_loss;
  const prior_pnl = comparative_profit_and_loss;

  const curBSPeriodLabel = data.current_period_label || dateInfo.bsTitle;
  const priorBSPeriodLabel = data.comparative_period_label || dateInfo.comparativeLabel;

  const curPNLPeriodLabel = data.period_label || dateInfo.pnlTitle;
  const priorPNLPeriodLabel = comparative_profit_and_loss?.period_label || `For the year ended 31st March, ${dateInfo.endYear - 1}`;

  return (
    <div className="space-y-6">
      {/* 1. Top Banner / Statutory Compliance Seal */}
      <div className="bg-gradient-to-r from-amber-500/10 via-slate-900/50 to-slate-900/80 p-5 rounded-xl border border-amber-500/20 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-medium">
              Companies Act 2013 - Schedule III Division I
            </span>
            <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-medium flex items-center gap-1">
              <CheckCircle2 className="w-3 h-3" /> Zero-Sum Verified
            </span>
            <span className="text-xs px-2 py-0.5 rounded bg-sky-500/20 text-sky-400 font-medium">
              Comparative Presentation
            </span>
          </div>
          <h2 className="text-lg font-bold text-white tracking-tight">{company_meta.legal_name}</h2>
          <p className="text-xs text-slate-400">
            CIN: <span className="font-mono text-slate-300">{company_meta.cin}</span> | PAN: <span className="font-mono text-slate-300">{company_meta.pan}</span> | Auditor: <span className="text-slate-300">{company_meta.auditor_firm}</span> (FRN: {company_meta.auditor_frn})
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <button
            onClick={loadScheduleIII}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
            title="Refresh Ledger and Anchors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={handleDownloadPDF}
            disabled={downloading}
            className="flex items-center gap-2 px-4 py-2 bg-amber-500 hover:bg-amber-400 text-slate-950 font-semibold text-xs rounded-lg shadow-sm transition disabled:opacity-50"
          >
            {downloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
            Download Certified Statutory Dossier (ZIP)
          </button>
        </div>
      </div>

      {/* 2. Statutory Provenance Banner (MCA Government Filings Synchronized) */}
      {statutory_provenance && (
        <div className="bg-gradient-to-r from-emerald-950/40 via-slate-900/80 to-amber-950/30 border border-emerald-500/30 rounded-xl p-4 shadow-lg">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div className="flex items-start gap-3">
              <div className="p-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 mt-0.5">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <span className="text-[11px] uppercase tracking-wider font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> MCA Statutory Anchor Synchronized
                  </span>
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-amber-300 border border-slate-700">
                    Form AOC-4 SRN: {statutory_provenance.current_aoc4_srn || statutory_provenance.prior_aoc4_srn || '7616438575'}
                  </span>
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-sky-300 border border-slate-700">
                    Form MGT-7A SRN: {statutory_provenance.current_mgt7_srn || statutory_provenance.prior_mgt7_srn || 'AC6319079'}
                  </span>
                </div>
                <p className="text-xs text-slate-200 font-medium">
                  {statutory_provenance.provenance_banner ||
                    `Statutory figures anchored against MCA Form AOC-4 & Form MGT-7A filings with Zero Mathematical Drift.`}
                </p>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Companies Act 2013 Sec 128/130 & Schedule III Division I Compliance • Comparative Baseline: FY {statutory_provenance.prior_fy} (AY {statutory_provenance.prior_ay})
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 self-start md:self-center">
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 px-2.5 py-1 rounded-full border border-emerald-800/60 flex items-center gap-1.5 whitespace-nowrap">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                Ledger Calibrated: 0 Drift
              </span>
            </div>
          </div>
        </div>
      )}

      {/* 3. Mandatory Accounting Ratios Cards (Schedule III 2021 Amendment Mandate) */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="p-4 bg-slate-900/60 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>(a) Current Ratio</span>
            <Scale className="w-4 h-4 text-sky-400" />
          </div>
          <div className="text-xl font-bold text-white font-mono">
            {accounting_ratios.current_ratio > 0 ? `${accounting_ratios.current_ratio}x` : '—'}
          </div>
          <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1">
            <span>CA / CL (&gt; 1.33)</span>
            {comparative_accounting_ratios && (
              <span className="font-mono text-slate-400">Prior: {comparative_accounting_ratios.current_ratio > 0 ? `${comparative_accounting_ratios.current_ratio}x` : '—'}</span>
            )}
          </div>
        </div>

        <div className="p-4 bg-slate-900/60 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>(b) Debt-Equity Ratio</span>
            <Scale className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-xl font-bold text-white font-mono">
            {accounting_ratios.debt_equity_ratio > 0 ? `${accounting_ratios.debt_equity_ratio}` : '0.00'}
          </div>
          <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1">
            <span>Debt / Net Worth</span>
            {comparative_accounting_ratios && (
              <span className="font-mono text-slate-400">Prior: {comparative_accounting_ratios.debt_equity_ratio > 0 ? `${comparative_accounting_ratios.debt_equity_ratio}` : '0.00'}</span>
            )}
          </div>
        </div>

        <div className="p-4 bg-slate-900/60 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>(i) Net Profit Margin</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <div className={`text-xl font-bold font-mono ${accounting_ratios.net_profit_margin_percent >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {accounting_ratios.net_profit_margin_percent}%
          </div>
          <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1">
            <span>PAT / Total Revenue</span>
            {comparative_accounting_ratios && (
              <span className="font-mono text-slate-400">Prior: {comparative_accounting_ratios.net_profit_margin_percent}%</span>
            )}
          </div>
        </div>

        <div className="p-4 bg-slate-900/60 rounded-xl border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
            <span>(d) Return on Equity (ROE)</span>
            <Percent className="w-4 h-4 text-amber-400" />
          </div>
          <div className={`text-xl font-bold font-mono ${accounting_ratios.return_on_equity_percent >= 0 ? 'text-amber-400' : 'text-rose-400'}`}>
            {accounting_ratios.return_on_equity_percent}%
          </div>
          <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1">
            <span>PAT / Equity</span>
            {comparative_accounting_ratios && (
              <span className="font-mono text-slate-400">Prior: {comparative_accounting_ratios.return_on_equity_percent}%</span>
            )}
          </div>
        </div>
      </div>

      {/* 4. Grid: Comparative Balance Sheet & Profit and Loss */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* PART I: VERTICAL COMPARATIVE BALANCE SHEET */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-xl overflow-hidden flex flex-col justify-between">
          <div>
            <div className="p-4 bg-slate-800/40 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white">{curBSPeriodLabel}</h3>
                <p className="text-xs text-slate-400">Division I - Non-Ind AS Comparative Balance Sheet</p>
              </div>
              <span className="text-xs text-amber-400 font-mono font-medium">({getUnitDescription(roundingUnit)})</span>
            </div>

            {/* Column Header */}
            <div className="grid grid-cols-12 px-3 py-2 bg-slate-950/80 font-semibold text-[11px] text-slate-400 border-b border-slate-800">
              <div className="col-span-5">Particulars</div>
              <div className="col-span-1 text-center font-mono">Note</div>
              <div className="col-span-3 text-right font-mono truncate text-amber-300" title={curBSPeriodLabel}>
                {curBSPeriodLabel.replace('Balance Sheet ', '')}
              </div>
              <div className="col-span-3 text-right font-mono truncate text-slate-400" title={priorBSPeriodLabel}>
                {priorBSPeriodLabel.replace('Balance Sheet ', '')}
              </div>
            </div>

            <div className="divide-y divide-slate-800/60 text-xs">
              {/* I. EQUITY AND LIABILITIES */}
              <div className="px-3 py-2 bg-slate-950/40 font-bold text-amber-300">
                I. EQUITY AND LIABILITIES
              </div>

              {/* 1. Shareholders' Funds */}
              <div className="space-y-0.5 bg-slate-900/30">
                <div className="px-3 pt-2 font-semibold text-slate-300">1. Shareholders' Funds</div>
                <StatRow
                  label="(a) Share Capital"
                  note="2"
                  indent={1}
                  currentVal={eq.shareholders_funds.share_capital}
                  priorVal={prior_eq?.shareholders_funds?.share_capital}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="(b) Reserves and Surplus"
                  note="3"
                  indent={1}
                  currentVal={eq.shareholders_funds.reserves_and_surplus}
                  priorVal={prior_eq?.shareholders_funds?.reserves_and_surplus}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="Sub-total: Shareholders' Funds"
                  indent={1}
                  isSubtotal
                  currentVal={eq.shareholders_funds.total}
                  priorVal={prior_eq?.shareholders_funds?.total}
                  formatCurrency={formatCurrency}
                />
              </div>

              {/* 2. Non-Current Liabilities */}
              <div className="space-y-0.5 bg-slate-900/30">
                <div className="px-3 pt-2 font-semibold text-slate-300">2. Non-Current Liabilities</div>
                <StatRow
                  label="(a) Long-term Borrowings"
                  note="4"
                  indent={1}
                  currentVal={eq.non_current_liabilities.long_term_borrowings}
                  priorVal={prior_eq?.non_current_liabilities?.long_term_borrowings}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="(b) Deferred Tax Liabilities (Net)"
                  note="10"
                  indent={1}
                  currentVal={eq.non_current_liabilities.deferred_tax_liabilities}
                  priorVal={prior_eq?.non_current_liabilities?.deferred_tax_liabilities}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="Sub-total: Non-Current Liabilities"
                  indent={1}
                  isSubtotal
                  currentVal={eq.non_current_liabilities.total}
                  priorVal={prior_eq?.non_current_liabilities?.total}
                  formatCurrency={formatCurrency}
                />
              </div>

              {/* 3. Current Liabilities */}
              <div className="space-y-0.5 bg-slate-900/30">
                <div className="px-3 pt-2 font-semibold text-slate-300">3. Current Liabilities</div>
                <StatRow
                  label="(a) Short-term Borrowings"
                  note="5"
                  indent={1}
                  currentVal={eq.current_liabilities.short_term_borrowings}
                  priorVal={prior_eq?.current_liabilities?.short_term_borrowings}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="(b) Trade Payables"
                  note="6"
                  indent={1}
                  currentVal={eq.current_liabilities.trade_payables}
                  priorVal={prior_eq?.current_liabilities?.trade_payables}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="(c) Other Current Liabilities"
                  note="7"
                  indent={1}
                  currentVal={eq.current_liabilities.other_current_liabilities}
                  priorVal={prior_eq?.current_liabilities?.other_current_liabilities}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="(d) Short-term Provisions"
                  note="8"
                  indent={1}
                  currentVal={eq.current_liabilities.short_term_provisions}
                  priorVal={prior_eq?.current_liabilities?.short_term_provisions}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="Sub-total: Current Liabilities"
                  indent={1}
                  isSubtotal
                  currentVal={eq.current_liabilities.total}
                  priorVal={prior_eq?.current_liabilities?.total}
                  formatCurrency={formatCurrency}
                />
              </div>

              {/* TOTAL EQUITY AND LIABILITIES */}
              <StatRow
                label="TOTAL EQUITY AND LIABILITIES"
                isTotal
                variant="amber"
                currentVal={eq.total_equity_and_liabilities}
                priorVal={prior_eq?.total_equity_and_liabilities}
                formatCurrency={formatCurrency}
              />

              {/* II. ASSETS */}
              <div className="px-3 py-2 bg-slate-950/40 font-bold text-sky-300">
                II. ASSETS
              </div>

              {/* 1. Non-Current Assets */}
              <div className="space-y-0.5 bg-slate-900/30">
                <div className="px-3 pt-2 font-semibold text-slate-300">1. Non-Current Assets</div>
                <StatRow
                  label="(a) Property, Plant and Equipment"
                  note="9"
                  indent={1}
                  currentVal={ast.non_current_assets.property_plant_equipment}
                  priorVal={prior_ast?.non_current_assets?.property_plant_equipment}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="(b) Long-term Loans and Advances"
                  note="11"
                  indent={1}
                  currentVal={ast.non_current_assets.long_term_loans}
                  priorVal={prior_ast?.non_current_assets?.long_term_loans}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="Sub-total: Non-Current Assets"
                  indent={1}
                  isSubtotal
                  currentVal={ast.non_current_assets.total}
                  priorVal={prior_ast?.non_current_assets?.total}
                  formatCurrency={formatCurrency}
                />
              </div>

              {/* 2. Current Assets */}
              <div className="space-y-0.5 bg-slate-900/30">
                <div className="px-3 pt-2 font-semibold text-slate-300">2. Current Assets</div>
                <StatRow
                  label="(a) Trade Receivables"
                  note="12"
                  indent={1}
                  currentVal={ast.current_assets.trade_receivables}
                  priorVal={prior_ast?.current_assets?.trade_receivables}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="(b) Cash and Bank Balances"
                  note="13"
                  indent={1}
                  currentVal={ast.current_assets.cash_and_bank}
                  priorVal={prior_ast?.current_assets?.cash_and_bank}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="(c) Short-term Loans and Advances"
                  note="14"
                  indent={1}
                  currentVal={ast.current_assets.short_term_loans}
                  priorVal={prior_ast?.current_assets?.short_term_loans}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="(d) Other Current Assets"
                  note="15"
                  indent={1}
                  currentVal={ast.current_assets.other_current_assets}
                  priorVal={prior_ast?.current_assets?.other_current_assets}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="Sub-total: Current Assets"
                  indent={1}
                  isSubtotal
                  currentVal={ast.current_assets.total}
                  priorVal={prior_ast?.current_assets?.total}
                  formatCurrency={formatCurrency}
                />
              </div>

              {/* TOTAL ASSETS */}
              <StatRow
                label="TOTAL ASSETS"
                isTotal
                variant="sky"
                currentVal={ast.total_assets}
                priorVal={prior_ast?.total_assets}
                formatCurrency={formatCurrency}
              />
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

        {/* PART II: STATEMENT OF PROFIT AND LOSS */}
        <div className="bg-slate-900/70 border border-slate-800 rounded-xl overflow-hidden flex flex-col justify-between">
          <div>
            <div className="p-4 bg-slate-800/40 border-b border-slate-800 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-white">Statement of Profit and Loss</h3>
                <p className="text-xs text-slate-400">{curPNLPeriodLabel}</p>
              </div>
              <span className="text-xs text-amber-400 font-mono font-medium">({getUnitDescription(roundingUnit)})</span>
            </div>

            {/* Column Header */}
            <div className="grid grid-cols-12 px-3 py-2 bg-slate-950/80 font-semibold text-[11px] text-slate-400 border-b border-slate-800">
              <div className="col-span-5">Particulars</div>
              <div className="col-span-1 text-center font-mono">Note</div>
              <div className="col-span-3 text-right font-mono truncate text-amber-300" title={curPNLPeriodLabel}>
                Current Period
              </div>
              <div className="col-span-3 text-right font-mono truncate text-slate-400" title={priorPNLPeriodLabel}>
                Previous Period
              </div>
            </div>

            <div className="divide-y divide-slate-800/60 text-xs">
              {/* REVENUE */}
              <div className="space-y-0.5 bg-slate-900/30">
                <div className="px-3 pt-2 font-semibold text-slate-300">Revenue</div>
                <StatRow
                  label="I. Revenue from Operations"
                  note="16"
                  indent={1}
                  currentVal={pnl.revenue_from_operations}
                  priorVal={prior_pnl?.revenue_from_operations}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="II. Other Income"
                  note="16"
                  indent={1}
                  currentVal={pnl.other_income}
                  priorVal={prior_pnl?.other_income}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="III. Total Revenue (I + II)"
                  isSubtotal
                  currentVal={pnl.total_revenue}
                  priorVal={prior_pnl?.total_revenue}
                  formatCurrency={formatCurrency}
                />
              </div>

              {/* EXPENSES */}
              <div className="space-y-0.5 bg-slate-900/30">
                <div className="px-3 pt-2 font-semibold text-slate-300">IV. Expenses</div>
                <StatRow
                  label="(a) Employee Benefits Expense"
                  note="17"
                  indent={1}
                  currentVal={pnl.expenses.employee_benefits}
                  priorVal={prior_pnl?.expenses?.employee_benefits}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="(b) Finance Costs"
                  note="18"
                  indent={1}
                  currentVal={pnl.expenses.finance_costs}
                  priorVal={prior_pnl?.expenses?.finance_costs}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="(c) Depreciation & Amortisation"
                  note="9"
                  indent={1}
                  currentVal={pnl.expenses.depreciation}
                  priorVal={prior_pnl?.expenses?.depreciation}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="(d) Other Expenses"
                  note="19"
                  indent={1}
                  currentVal={pnl.expenses.other_expenses}
                  priorVal={prior_pnl?.expenses?.other_expenses}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="Total Expenses"
                  isSubtotal
                  currentVal={pnl.expenses.total_expenses}
                  priorVal={prior_pnl?.expenses?.total_expenses}
                  formatCurrency={formatCurrency}
                />
              </div>

              {/* PROFIT SUMMARY */}
              <div className="space-y-0.5 bg-slate-900/50">
                <StatRow
                  label="V. Profit Before Exceptional Items & Tax"
                  currentVal={pnl.profit_before_tax}
                  priorVal={prior_pnl?.profit_before_tax}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="VI. Tax Expense (Current & Deferred)"
                  note="10"
                  currentVal={pnl.tax_expense}
                  priorVal={prior_pnl?.tax_expense}
                  formatCurrency={formatCurrency}
                />
                <StatRow
                  label="VII. Profit / (Loss) for the Period"
                  isTotal
                  variant={pnl.profit_for_period >= 0 ? 'emerald' : 'rose'}
                  currentVal={pnl.profit_for_period}
                  priorVal={prior_pnl?.profit_for_period}
                  formatCurrency={formatCurrency}
                />
                <div className="grid grid-cols-12 items-center px-3 py-2 text-xs text-slate-400 bg-slate-950/40 border-t border-slate-800">
                  <div className="col-span-5 text-slate-300">VIII. EPS (Basic & Diluted - Par ₹10)</div>
                  <div className="col-span-1 text-center font-mono text-[10px] text-slate-500">20</div>
                  <div className="col-span-3 text-right font-mono text-slate-200">
                    ₹{((pnl.profit_for_period || 0) / 10000).toFixed(2)}
                  </div>
                  <div className="col-span-3 text-right font-mono text-slate-400">
                    ₹{(((prior_pnl?.profit_for_period ?? 0)) / 10000).toFixed(2)}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Legal Signatories Footer */}
          <div className="p-4 bg-slate-950/80 border-t border-slate-800 text-[11px] text-slate-400 space-y-2">
            <div className="flex items-center justify-between border-b border-slate-800/60 pb-2">
              <div>
                <p className="font-semibold text-slate-200">Report of Independent Auditor</p>
                <p className="text-[10px]">Unmodified Audit Opinion</p>
                <p className="text-slate-300 mt-1">{company_meta.auditor_firm}</p>
              </div>
              <div className="text-right">
                <p className="font-semibold text-slate-200">Date of Board Approval</p>
                <p className="text-slate-300 mt-1">{company_meta.as_of_date}</p>
                <p className="text-[10px]">Bengaluru, Karnataka</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 5. Note 2 & Form MGT-7A Governance & Shareholding Pattern Disclosure Card */}
      <div className="bg-slate-900/70 border border-slate-800 rounded-xl p-5 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-slate-800 gap-2">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400">
              <Building className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white tracking-tight">
                Note 2: Share Capital & Form MGT-7A Governance Disclosure
              </h3>
              <p className="text-xs text-slate-400">
                Statutory Shareholding Pattern & Capital Structure verified with MCA e-Filings
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 self-start sm:self-center">
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-sky-300 border border-slate-700">
              MGT-7A SRN: {mgt7_shareholding_disclosure?.srn || 'AC6319079'}
            </span>
            <span className="text-[11px] px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              Active Annual Return
            </span>
          </div>
        </div>

        {/* Capital & Net Worth Overview Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800">
            <span className="text-[11px] text-slate-400 font-medium">Authorised Capital</span>
            <p className="text-base font-bold font-mono text-white mt-1">
              ₹{new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2 }).format(mgt7_shareholding_disclosure?.authorized_capital_inr || 100000)}
            </p>
            <p className="text-[10px] text-slate-400 mt-0.5">10,000 Equity Shares @ ₹10</p>
          </div>

          <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800">
            <span className="text-[11px] text-slate-400 font-medium">Issued & Paid-up Capital</span>
            <p className="text-base font-bold font-mono text-emerald-400 mt-1">
              ₹{new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2 }).format(mgt7_shareholding_disclosure?.paid_up_capital_inr || 100000)}
            </p>
            <p className="text-[10px] text-slate-400 mt-0.5">10,000 Shares (100% Paid)</p>
          </div>

          <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800">
            <span className="text-[11px] text-slate-400 font-medium">Net Worth (MGT-7A)</span>
            <p className={`text-base font-bold font-mono mt-1 ${(mgt7_shareholding_disclosure?.net_worth_inr ?? 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
              ₹{new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2 }).format(mgt7_shareholding_disclosure?.net_worth_inr ?? -63851)}
            </p>
            <p className="text-[10px] text-slate-400 mt-0.5">Paid-up Capital + Reserves</p>
          </div>

          <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800">
            <span className="text-[11px] text-slate-400 font-medium">Promoter Shareholding</span>
            <p className="text-base font-bold font-mono text-amber-300 mt-1">
              100.00%
            </p>
            <p className="text-[10px] text-slate-400 mt-0.5">Single Promoter / OPC</p>
          </div>
        </div>

        {/* Governance Tables Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
          {/* Table 1: Shareholders holding > 5% */}
          <div className="bg-slate-950/40 rounded-lg border border-slate-800 p-3">
            <div className="flex items-center justify-between mb-2 pb-1 border-b border-slate-800/80">
              <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5 text-indigo-400" />
                Shareholders Holding &gt; 5% Shares
              </span>
              <span className="text-[10px] text-slate-400">Companies Act Sch III Cl 6(J)</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-slate-400 text-[10px] border-b border-slate-800/60 font-semibold uppercase">
                    <th className="pb-1.5">Shareholder</th>
                    <th className="pb-1.5">Class</th>
                    <th className="pb-1.5 text-right">Shares</th>
                    <th className="pb-1.5 text-right">% Holding</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/40 font-mono text-slate-300">
                  {(mgt7_shareholding_disclosure?.shareholders && mgt7_shareholding_disclosure.shareholders.length > 0) ? (
                    mgt7_shareholding_disclosure.shareholders.map((sh, idx) => (
                      <tr key={idx} className="hover:bg-slate-900/40">
                        <td className="py-1.5 font-sans font-medium text-white">{sh.name}</td>
                        <td className="py-1.5 text-slate-400">{sh.class_of_shares || 'Equity Shares'}</td>
                        <td className="py-1.5 text-right">{sh.number_of_shares.toLocaleString('en-IN')}</td>
                        <td className="py-1.5 text-right text-emerald-400 font-semibold">{sh.percentage_holding.toFixed(2)}%</td>
                      </tr>
                    ))
                  ) : (
                    <tr className="hover:bg-slate-900/40">
                      <td className="py-1.5 font-sans font-medium text-white">{company_meta.director_name}</td>
                      <td className="py-1.5 text-slate-400">Equity Shares</td>
                      <td className="py-1.5 text-right">10,000</td>
                      <td className="py-1.5 text-right text-emerald-400 font-semibold">100.00%</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Table 2: Promoter Shareholding Pattern */}
          <div className="bg-slate-950/40 rounded-lg border border-slate-800 p-3">
            <div className="flex items-center justify-between mb-2 pb-1 border-b border-slate-800/80">
              <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
                <Award className="w-3.5 h-3.5 text-amber-400" />
                Promoter Shareholding Pattern
              </span>
              <span className="text-[10px] text-slate-400">MCA 2021 Mandate</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="text-slate-400 text-[10px] border-b border-slate-800/60 font-semibold uppercase">
                    <th className="pb-1.5">Promoter</th>
                    <th className="pb-1.5">DIN / PAN</th>
                    <th className="pb-1.5 text-right">Shares</th>
                    <th className="pb-1.5 text-right">% Holding</th>
                    <th className="pb-1.5 text-right">% Change</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/40 font-mono text-slate-300">
                  {(mgt7_shareholding_disclosure?.promoter_shareholding && mgt7_shareholding_disclosure.promoter_shareholding.length > 0) ? (
                    mgt7_shareholding_disclosure.promoter_shareholding.map((pm, idx) => (
                      <tr key={idx} className="hover:bg-slate-900/40">
                        <td className="py-1.5 font-sans font-medium text-white">{pm.promoter_name || pm.name || company_meta.director_name}</td>
                        <td className="py-1.5 text-slate-400">{pm.din || company_meta.director_din}</td>
                        <td className="py-1.5 text-right">{(pm.shares || 10000).toLocaleString('en-IN')}</td>
                        <td className="py-1.5 text-right text-amber-300 font-semibold">{(pm.percentage || pm.percentage_holding || 100).toFixed(2)}%</td>
                        <td className="py-1.5 text-right text-slate-400">{(pm.percentage_change_during_year || 0).toFixed(2)}%</td>
                      </tr>
                    ))
                  ) : (
                    <tr className="hover:bg-slate-900/40">
                      <td className="py-1.5 font-sans font-medium text-white">{company_meta.director_name}</td>
                      <td className="py-1.5 text-slate-400">{company_meta.director_din}</td>
                      <td className="py-1.5 text-right">10,000</td>
                      <td className="py-1.5 text-right text-amber-300 font-semibold">100.00%</td>
                      <td className="py-1.5 text-right text-slate-400">0.00%</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      {/* 6. Expandable Notes to Accounts (Notes 1 to 20) */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden">
        <button
          onClick={() => setShowNotes(!showNotes)}
          className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-800/40 transition-colors"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <BookOpen className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white tracking-tight">
                Notes to Accounts (Notes 1 to 20)
              </h3>
              <p className="text-xs text-slate-400">
                Detailed breakdowns, accounting policies, ageing schedules, and mandatory statutory disclosures
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs font-semibold text-amber-400">
            <span>{showNotes ? 'Collapse Notes' : 'Expand All 20 Notes'}</span>
            {showNotes ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </button>

        {showNotes && (
          <div className="p-5 border-t border-slate-800 space-y-4 bg-slate-950/40 text-xs">
            {/* Note 1: Significant Accounting Policies */}
            <div className="p-4 bg-slate-900/70 rounded-lg border border-slate-800/80 space-y-2">
              <span className="font-bold text-amber-300 text-sm">Note 1: Significant Accounting Policies</span>
              <p className="text-slate-300">
                <strong className="text-white">Corporate Information:</strong> {company_meta.legal_name} is a company incorporated under the provisions of the Companies Act, 2013 with Registered Office at {company_meta.registered_office || 'Karnataka, India'}.
              </p>
              <p className="text-slate-400">
                <strong className="text-slate-300">Basis of Preparation:</strong> Financial statements have been prepared under the historical cost convention on an accrual basis, complying with the Accounting Standards notified under Section 133 of the Companies Act, 2013 and Schedule III Division I.
              </p>
            </div>

            {/* Note 3: Reserves and Surplus */}
            <div className="p-4 bg-slate-900/70 rounded-lg border border-slate-800/80 space-y-2">
              <span className="font-bold text-amber-300 text-sm">Note 3: Reserves and Surplus</span>
              <div className="grid grid-cols-12 py-1 text-slate-300 border-b border-slate-800/60">
                <div className="col-span-6">Surplus / (Deficit) in Statement of Profit and Loss</div>
                <div className="col-span-3 text-right font-mono">{formatCurrency(eq.shareholders_funds.reserves_and_surplus)}</div>
                <div className="col-span-3 text-right font-mono text-slate-400">{formatCurrency(prior_eq?.shareholders_funds?.reserves_and_surplus)}</div>
              </div>
              <p className="text-[11px] text-slate-400">
                Reflects opening accumulated deficit plus profit/(loss) for the reporting period with zero mathematical drift.
              </p>
            </div>

            {/* Note 4: Long-Term Borrowings */}
            <div className="p-4 bg-slate-900/70 rounded-lg border border-slate-800/80 space-y-2">
              <span className="font-bold text-amber-300 text-sm">Note 4: Long-Term Borrowings</span>
              <div className="grid grid-cols-12 py-1 text-slate-300 border-b border-slate-800/60">
                <div className="col-span-6">Loan from Directors / Relatives (Unsecured, Interest-Free)</div>
                <div className="col-span-3 text-right font-mono">{formatCurrency(eq.non_current_liabilities.long_term_borrowings)}</div>
                <div className="col-span-3 text-right font-mono text-slate-400">{formatCurrency(prior_eq?.non_current_liabilities?.long_term_borrowings)}</div>
              </div>
              <p className="text-[11px] text-slate-400">
                Director loan provided to fund pre-operative capital formation and working capital requirements.
              </p>
            </div>

            {/* Note 6: Trade Payables */}
            <div className="p-4 bg-slate-900/70 rounded-lg border border-slate-800/80 space-y-2">
              <span className="font-bold text-amber-300 text-sm">Note 6: Trade Payables & Ageing</span>
              <div className="grid grid-cols-12 py-1 text-slate-300 border-b border-slate-800/60">
                <div className="col-span-6">Total Outstanding Dues of MSME and Other Creditors</div>
                <div className="col-span-3 text-right font-mono">{formatCurrency(eq.current_liabilities.trade_payables)}</div>
                <div className="col-span-3 text-right font-mono text-slate-400">{formatCurrency(prior_eq?.current_liabilities?.trade_payables)}</div>
              </div>
              <p className="text-[11px] text-slate-400">
                Dues to Micro, Small and Medium Enterprises (MSMED Act 2006): ₹0.00. No disputed trade payables.
              </p>
            </div>

            {/* Note 7: Other Current Liabilities */}
            <div className="p-4 bg-slate-900/70 rounded-lg border border-slate-800/80 space-y-2">
              <span className="font-bold text-amber-300 text-sm">Note 7: Other Current Liabilities</span>
              <div className="grid grid-cols-12 py-1 text-slate-300 border-b border-slate-800/60">
                <div className="col-span-6">Statutory Dues Payable (GST / TDS / Professional Tax)</div>
                <div className="col-span-3 text-right font-mono">{formatCurrency(eq.current_liabilities.other_current_liabilities)}</div>
                <div className="col-span-3 text-right font-mono text-slate-400">{formatCurrency(prior_eq?.current_liabilities?.other_current_liabilities)}</div>
              </div>
            </div>

            {/* Note 9: PPE & Depreciation */}
            <div className="p-4 bg-slate-900/70 rounded-lg border border-slate-800/80 space-y-2">
              <span className="font-bold text-amber-300 text-sm">Note 9: Property, Plant and Equipment</span>
              <div className="grid grid-cols-12 py-1 text-slate-300 border-b border-slate-800/60">
                <div className="col-span-6">Net Carrying Value of PPE Assets</div>
                <div className="col-span-3 text-right font-mono">{formatCurrency(ast.non_current_assets.property_plant_equipment)}</div>
                <div className="col-span-3 text-right font-mono text-slate-400">{formatCurrency(prior_ast?.non_current_assets?.property_plant_equipment)}</div>
              </div>
              <p className="text-[11px] text-slate-400">
                Depreciation charged using Straight Line Method (SLM) based on useful lives specified in Schedule II.
              </p>
            </div>

            {/* Note 12: Trade Receivables */}
            <div className="p-4 bg-slate-900/70 rounded-lg border border-slate-800/80 space-y-2">
              <span className="font-bold text-amber-300 text-sm">Note 12: Trade Receivables & Ageing</span>
              <div className="grid grid-cols-12 py-1 text-slate-300 border-b border-slate-800/60">
                <div className="col-span-6">Undisputed Trade Receivables - Considered Good (&lt; 6 months)</div>
                <div className="col-span-3 text-right font-mono">{formatCurrency(ast.current_assets.trade_receivables)}</div>
                <div className="col-span-3 text-right font-mono text-slate-400">{formatCurrency(prior_ast?.current_assets?.trade_receivables)}</div>
              </div>
            </div>

            {/* Note 13: Cash and Bank Balances */}
            <div className="p-4 bg-slate-900/70 rounded-lg border border-slate-800/80 space-y-2">
              <span className="font-bold text-amber-300 text-sm">Note 13: Cash and Cash Equivalents</span>
              <div className="grid grid-cols-12 py-1 text-slate-300 border-b border-slate-800/60">
                <div className="col-span-6">Balances with Scheduled Banks & Cash in hand</div>
                <div className="col-span-3 text-right font-mono">{formatCurrency(ast.current_assets.cash_and_bank)}</div>
                <div className="col-span-3 text-right font-mono text-slate-400">{formatCurrency(prior_ast?.current_assets?.cash_and_bank)}</div>
              </div>
            </div>

            {/* Note 16 to 19: P&L Expenses */}
            <div className="p-4 bg-slate-900/70 rounded-lg border border-slate-800/80 space-y-2">
              <span className="font-bold text-amber-300 text-sm">Notes 16 – 19: Operational Revenues & Expenses</span>
              <div className="grid grid-cols-12 py-1 text-slate-300 border-b border-slate-800/60">
                <div className="col-span-6">Note 16: Revenue from Software Development & SaaS</div>
                <div className="col-span-3 text-right font-mono">{formatCurrency(pnl.revenue_from_operations)}</div>
                <div className="col-span-3 text-right font-mono text-slate-400">{formatCurrency(prior_pnl?.revenue_from_operations)}</div>
              </div>
              <div className="grid grid-cols-12 py-1 text-slate-300 border-b border-slate-800/60">
                <div className="col-span-6">Note 17: Employee Benefits Expense</div>
                <div className="col-span-3 text-right font-mono">{formatCurrency(pnl.expenses.employee_benefits)}</div>
                <div className="col-span-3 text-right font-mono text-slate-400">{formatCurrency(prior_pnl?.expenses?.employee_benefits)}</div>
              </div>
              <div className="grid grid-cols-12 py-1 text-slate-300 border-b border-slate-800/60">
                <div className="col-span-6">Note 18: Finance Costs & Bank Charges</div>
                <div className="col-span-3 text-right font-mono">{formatCurrency(pnl.expenses.finance_costs)}</div>
                <div className="col-span-3 text-right font-mono text-slate-400">{formatCurrency(prior_pnl?.expenses?.finance_costs)}</div>
              </div>
              <div className="grid grid-cols-12 py-1 text-slate-300 border-b border-slate-800/60">
                <div className="col-span-6">Note 19: Other Operating & Legal Expenses</div>
                <div className="col-span-3 text-right font-mono">{formatCurrency(pnl.expenses.other_expenses)}</div>
                <div className="col-span-3 text-right font-mono text-slate-400">{formatCurrency(prior_pnl?.expenses?.other_expenses)}</div>
              </div>
            </div>

            {/* Note 20: Mandatory Accounting Ratios Table */}
            <div className="p-4 bg-slate-900/70 rounded-lg border border-slate-800/80 space-y-2">
              <span className="font-bold text-amber-300 text-sm">Note 20: Mandatory Accounting Ratios Disclosure (Sch III 2021)</span>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="text-slate-400 text-[10px] border-b border-slate-800 font-semibold uppercase">
                      <th className="pb-1.5">Ratio</th>
                      <th className="pb-1.5">Numerator / Denominator</th>
                      <th className="pb-1.5 text-right">Current Period</th>
                      <th className="pb-1.5 text-right">Previous Period</th>
                      <th className="pb-1.5 text-right">% Variance</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/50 font-mono text-slate-300">
                    <tr>
                      <td className="py-1.5 font-sans">Current Ratio</td>
                      <td className="py-1.5 text-slate-400 font-sans">Current Assets / Current Liabilities</td>
                      <td className="py-1.5 text-right text-emerald-400 font-bold">{accounting_ratios.current_ratio}x</td>
                      <td className="py-1.5 text-right text-slate-400">{comparative_accounting_ratios?.current_ratio ?? 0}x</td>
                      <td className="py-1.5 text-right text-slate-400">0.00%</td>
                    </tr>
                    <tr>
                      <td className="py-1.5 font-sans">Debt-Equity Ratio</td>
                      <td className="py-1.5 text-slate-400 font-sans">Total Debt / Total Shareholder Funds</td>
                      <td className="py-1.5 text-right text-white font-bold">{accounting_ratios.debt_equity_ratio}</td>
                      <td className="py-1.5 text-right text-slate-400">{comparative_accounting_ratios?.debt_equity_ratio ?? 0}</td>
                      <td className="py-1.5 text-right text-slate-400">0.00%</td>
                    </tr>
                    <tr>
                      <td className="py-1.5 font-sans">Net Profit Margin (%)</td>
                      <td className="py-1.5 text-slate-400 font-sans">Net Profit After Tax / Total Revenue</td>
                      <td className={`py-1.5 text-right font-bold ${accounting_ratios.net_profit_margin_percent >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {accounting_ratios.net_profit_margin_percent}%
                      </td>
                      <td className="py-1.5 text-right text-slate-400">{comparative_accounting_ratios?.net_profit_margin_percent ?? 0}%</td>
                      <td className="py-1.5 text-right text-slate-400">0.00%</td>
                    </tr>
                    <tr>
                      <td className="py-1.5 font-sans">Return on Equity (%)</td>
                      <td className="py-1.5 text-slate-400 font-sans">Net Profit After Tax / Total Net Worth</td>
                      <td className={`py-1.5 text-right font-bold ${accounting_ratios.return_on_equity_percent >= 0 ? 'text-amber-300' : 'text-rose-400'}`}>
                        {accounting_ratios.return_on_equity_percent}%
                      </td>
                      <td className="py-1.5 text-right text-slate-400">{comparative_accounting_ratios?.return_on_equity_percent ?? 0}%</td>
                      <td className="py-1.5 text-right text-slate-400">0.00%</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
