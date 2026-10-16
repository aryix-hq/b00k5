'use client';

import React, { useState, useEffect } from 'react';
import {
  Building2,
  IndianRupee,
  Calendar,
  Clock,
  Plus,
  Play,
  CheckCircle2,
  Layers,
  ArrowRight,
  TrendingDown,
  Info
} from 'lucide-react';
import { fetchApi } from '@/lib/api';

interface ScheduleIICategory {
  category: string;
  category_name: string;
  statutory_useful_life_years: number;
  asset_count: number;
  gross_block: number;
  accumulated_depreciation: number;
  net_block: number;
}

interface ScheduleIISummary {
  fiscal_year: string;
  as_of_date: string;
  total_gross_block: number;
  total_accumulated_depreciation: number;
  total_net_block: number;
  categories: ScheduleIICategory[];
}

interface FixedAsset {
  id: string;
  asset_code: string;
  asset_name: string;
  category: string;
  category_display?: string;
  purchase_date: string;
  gross_block: number;
  salvage_value: number;
  useful_life_years: number;
  depreciation_method: string;
  accumulated_depreciation: number;
  net_block: number;
  location?: string;
  serial_number?: string;
  status: string;
}

interface DepreciationRun {
  id: string;
  fiscal_year: string;
  period_start: string;
  period_end: string;
  run_date: string;
  total_depreciation_amount: number;
  journal_entry_number?: string;
  status: string;
  asset_count: number;
  created_at: string;
}

const SCHEDULE_II_CATEGORIES = [
  { key: 'COMPUTERS_DESKTOP_LAPTOP', name: 'Computers & Laptops', useful_life: 3.0 },
  { key: 'SERVERS_NETWORK', name: 'Servers & Network Hardware', useful_life: 6.0 },
  { key: 'OFFICE_EQUIPMENT', name: 'Office Equipment', useful_life: 5.0 },
  { key: 'FURNITURE_FIXTURES', name: 'Furniture & Fixtures', useful_life: 10.0 },
  { key: 'PLANT_MACHINERY', name: 'Plant & Machinery', useful_life: 15.0 },
  { key: 'MOTOR_VEHICLES', name: 'Motor Vehicles', useful_life: 8.0 },
  { key: 'BUILDINGS', name: 'Buildings & Premises', useful_life: 30.0 }
];

export function FixedAssetsTab() {
  const [summary, setSummary] = useState<ScheduleIISummary | null>(null);
  const [assets, setAssets] = useState<FixedAsset[]>([]);
  const [runs, setRuns] = useState<DepreciationRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedFy, setSelectedFy] = useState<string>('2026-27');

  // Modal: Register Asset
  const [isRegisterModalOpen, setIsRegisterModalOpen] = useState(false);
  const [assetName, setAssetName] = useState('');
  const [assetCategory, setAssetCategory] = useState('COMPUTERS_DESKTOP_LAPTOP');
  const [purchaseDate, setPurchaseDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [grossBlock, setGrossBlock] = useState('');
  const [deprMethod, setDeprMethod] = useState<'SLM' | 'WDV'>('SLM');
  const [location, setLocation] = useState('');
  const [serialNo, setSerialNo] = useState('');
  const [registerSubmitting, setRegisterSubmitting] = useState(false);
  const [registerError, setRegisterError] = useState<string | null>(null);
  const [registerSuccess, setRegisterSuccess] = useState<string | null>(null);

  // Modal: Run Depreciation
  const [isRunModalOpen, setIsRunModalOpen] = useState(false);
  const [periodStart, setPeriodStart] = useState('2026-04-01');
  const [periodEnd, setPeriodEnd] = useState(() => new Date().toISOString().split('T')[0]);
  const [runSubmitting, setRunSubmitting] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [runSuccess, setRunSuccess] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const summaryData = await fetchApi(`/api/v1/assets/schedule-ii-summary?fiscal_year=${selectedFy}`);
      setSummary(summaryData);

      const assetsData = await fetchApi('/api/v1/assets/registry?status=ACTIVE');
      setAssets(assetsData || []);

      const runsData = await fetchApi(`/api/v1/assets/depreciation-runs?fiscal_year=${selectedFy}`);
      setRuns(runsData || []);
    } catch (err) {
      console.error('Error fetching fixed assets data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [selectedFy]);

  const handleRegisterAsset = async (e: React.FormEvent) => {
    e.preventDefault();
    const g = parseFloat(grossBlock);
    if (!g || g <= 0) {
      setRegisterError('Please enter a valid Gross Block purchase amount.');
      return;
    }
    setRegisterSubmitting(true);
    setRegisterError(null);
    setRegisterSuccess(null);

    try {
      const payload = {
        asset_name: assetName.trim(),
        category: assetCategory,
        purchase_date: purchaseDate,
        gross_block: g,
        depreciation_method: deprMethod,
        location: location.trim() || undefined,
        serial_number: serialNo.trim() || undefined,
        auto_post_purchase_jv: false
      };

      const res = await fetchApi('/api/v1/assets/register', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      setRegisterSuccess(`Asset registered as ${res.asset_code}! Useful Life: ${res.useful_life_years}y, Salvage: ₹${res.salvage_value}`);
      setTimeout(() => {
        setIsRegisterModalOpen(false);
        setRegisterSuccess(null);
        setAssetName('');
        setGrossBlock('');
        setLocation('');
        setSerialNo('');
        loadData();
      }, 1500);
    } catch (err: any) {
      setRegisterError(err.message || 'Failed to register fixed asset');
    } finally {
      setRegisterSubmitting(false);
    }
  };

  const handleRunDepreciation = async (e: React.FormEvent) => {
    e.preventDefault();
    setRunSubmitting(true);
    setRunError(null);
    setRunSuccess(null);

    try {
      const payload = {
        fiscal_year: selectedFy,
        period_start: periodStart,
        period_end: periodEnd,
        auto_post_jv: true
      };

      const res = await fetchApi('/api/v1/assets/run-depreciation', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      setRunSuccess(`Depreciation run complete! Total: ₹${res.total_depreciation_amount}. Auto-posted JV: ${res.journal_entry_number || 'Posted'}`);
      setTimeout(() => {
        setIsRunModalOpen(false);
        setRunSuccess(null);
        loadData();
      }, 1500);
    } catch (err: any) {
      setRunError(err.message || 'Failed to run depreciation');
    } finally {
      setRunSubmitting(false);
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

  const selectedCategoryObj = SCHEDULE_II_CATEGORIES.find(c => c.key === assetCategory);
  const estimatedSalvage = parseFloat(grossBlock) ? parseFloat(grossBlock) * 0.05 : 0;

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs uppercase font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/30">
              Schedule II Part C Compliance
            </span>
            <span className="text-xs font-mono text-slate-400">
              Companies Act 2013 Statutory Useful Life &amp; 5% Salvage Floor
            </span>
          </div>
          <h2 className="text-xl font-bold text-white mt-1">
            Fixed Assets &amp; Depreciation Engine
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Automated pro-rata daily straight-line/WDV depreciation, accumulated contra-asset tracking (1059), and period-end balanced journal posting.
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

          <button
            onClick={() => setIsRegisterModalOpen(true)}
            className="px-3.5 py-2 bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold rounded-lg shadow-sm flex items-center gap-1.5 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Register Fixed Asset
          </button>

          <button
            onClick={() => setIsRunModalOpen(true)}
            className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg shadow-sm flex items-center gap-1.5 transition-colors"
          >
            <Play className="w-4 h-4" />
            Run Period Depreciation
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Total Gross Block</span>
            <span className="p-1.5 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20">
              <Layers className="w-4 h-4" />
            </span>
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-2">
            {formatINR(summary?.total_gross_block || 0)}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            Historical acquisition cost of all PPE
          </p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Accumulated Depreciation</span>
            <span className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
              <TrendingDown className="w-4 h-4" />
            </span>
          </div>
          <div className="text-2xl font-bold font-mono text-amber-400 mt-2">
            {formatINR(summary?.total_accumulated_depreciation || 0)}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            Contra-Asset Account 1059 balance
          </p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Net Carrying Value (Net Block)</span>
            <span className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Building2 className="w-4 h-4" />
            </span>
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400 mt-2">
            {formatINR(summary?.total_net_block || 0)}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            Schedule III Non-Current Assets disclosure
          </p>
        </div>

        <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Active Capital Assets</span>
            <span className="p-1.5 rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Clock className="w-4 h-4" />
            </span>
          </div>
          <div className="text-2xl font-bold font-mono text-white mt-2">
            {assets.length}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">
            Tracked in statutory asset registry
          </p>
        </div>
      </div>

      {/* Schedule II Part C Summary Table */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Building2 className="w-4 h-4 text-sky-400" />
            Companies Act 2013 Schedule II Part C Disclosure Summary
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Category-wise statutory useful life disclosure required for Balance Sheet Note on Property, Plant and Equipment.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                <th className="p-3">Asset Category</th>
                <th className="p-3 text-center">Statutory Life</th>
                <th className="p-3 text-center">Assets</th>
                <th className="p-3 text-right">Gross Block (₹)</th>
                <th className="p-3 text-right">Accumulated Depr (₹)</th>
                <th className="p-3 text-right">Net Carrying Value (₹)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {summary?.categories && summary.categories.length > 0 ? (
                summary.categories.map((c) => (
                  <tr key={c.category} className="hover:bg-slate-800/30 transition-colors">
                    <td className="p-3 font-semibold text-white">{c.category_name}</td>
                    <td className="p-3 text-center text-sky-400 font-bold">{c.statutory_useful_life_years} Years</td>
                    <td className="p-3 text-center text-slate-300">{c.asset_count}</td>
                    <td className="p-3 text-right text-slate-200">{formatINR(c.gross_block)}</td>
                    <td className="p-3 text-right text-amber-400">{formatINR(c.accumulated_depreciation)}</td>
                    <td className="p-3 text-right font-bold text-emerald-400">{formatINR(c.net_block)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="p-6 text-center text-slate-500">
                    No capital assets registered yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Full Asset Registry Table */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Layers className="w-4 h-4 text-emerald-400" />
              Statutory Asset Registry
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Individual asset records with Schedule II salvage value floors and contra-asset balances.
            </p>
          </div>
        </div>

        {loading ? (
          <div className="py-12 text-center text-slate-500 text-xs font-mono">
            Loading asset registry...
          </div>
        ) : assets.length === 0 ? (
          <div className="py-12 text-center text-slate-500 space-y-2">
            <CheckCircle2 className="w-8 h-8 text-slate-600 mx-auto" />
            <p className="text-sm font-medium text-slate-400">No active fixed assets registered.</p>
            <p className="text-xs text-slate-500">
              Click &quot;Register Fixed Asset&quot; to add servers, laptops, or office equipment.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                  <th className="p-3">Asset Code</th>
                  <th className="p-3">Name &amp; Category</th>
                  <th className="p-3">Purchase Date</th>
                  <th className="p-3 text-right">Gross Block (₹)</th>
                  <th className="p-3 text-right">Useful Life</th>
                  <th className="p-3 text-right">Salvage Floor (5%)</th>
                  <th className="p-3 text-right">Accumulated Depr (₹)</th>
                  <th className="p-3 text-right">Net Block (₹)</th>
                  <th className="p-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {assets.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="p-3 text-sky-400 font-bold">{a.asset_code}</td>
                    <td className="p-3">
                      <div className="font-semibold text-white">{a.asset_name}</div>
                      <div className="text-[11px] text-slate-400">{a.category_display || a.category}</div>
                    </td>
                    <td className="p-3 text-slate-300">{a.purchase_date}</td>
                    <td className="p-3 text-right font-medium text-slate-200">{formatINR(a.gross_block)}</td>
                    <td className="p-3 text-right text-sky-300">{a.useful_life_years}y</td>
                    <td className="p-3 text-right text-slate-400">{formatINR(a.salvage_value)}</td>
                    <td className="p-3 text-right font-semibold text-amber-400">{formatINR(a.accumulated_depreciation)}</td>
                    <td className="p-3 text-right font-bold text-emerald-400">{formatINR(a.net_block)}</td>
                    <td className="p-3">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                        {a.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Depreciation Runs History */}
      {runs.length > 0 && (
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl space-y-4">
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Clock className="w-4 h-4 text-amber-400" />
            Depreciation Runs &amp; Auto-Posted Balancing Vouchers
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                  <th className="p-3">Period</th>
                  <th className="p-3">Run Date</th>
                  <th className="p-3 text-center">Assets Processed</th>
                  <th className="p-3 text-right">Depreciation Expense (₹)</th>
                  <th className="p-3">Journal Entry Number</th>
                  <th className="p-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {runs.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="p-3 text-slate-300">{r.period_start} to {r.period_end}</td>
                    <td className="p-3 text-slate-400">{r.run_date}</td>
                    <td className="p-3 text-center text-slate-300">{r.asset_count}</td>
                    <td className="p-3 text-right font-bold text-amber-400">{formatINR(r.total_depreciation_amount)}</td>
                    <td className="p-3 text-sky-400 font-bold">{r.journal_entry_number || 'Auto-Posted JV'}</td>
                    <td className="p-3">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                        <CheckCircle2 className="w-3 h-3" /> {r.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal: Register Fixed Asset */}
      {isRegisterModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Building2 className="w-5 h-5 text-sky-400" />
                Register Asset (Schedule II Part C)
              </h3>
              <button
                onClick={() => setIsRegisterModalOpen(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleRegisterAsset} className="space-y-4 text-xs">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">
                  Schedule II Asset Category*
                </label>
                <select
                  value={assetCategory}
                  onChange={(e) => setAssetCategory(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-medium focus:outline-none focus:border-sky-500"
                >
                  {SCHEDULE_II_CATEGORIES.map(c => (
                    <option key={c.key} value={c.key}>
                      {c.name} — Useful Life: {c.useful_life}y (Schedule II)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">
                  Asset Name / Description*
                </label>
                <input
                  type="text"
                  value={assetName}
                  onChange={(e) => setAssetName(e.target.value)}
                  placeholder="e.g. MacBook Pro M3 Max 64GB"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-medium focus:outline-none focus:border-sky-500"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">
                    Purchase Date*
                  </label>
                  <input
                    type="date"
                    value={purchaseDate}
                    onChange={(e) => setPurchaseDate(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-sky-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-semibold mb-1">
                    Gross Block Cost (₹)*
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={grossBlock}
                    onChange={(e) => setGrossBlock(e.target.value)}
                    placeholder="e.g. 250000"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-sky-500"
                    required
                  />
                </div>
              </div>

              {/* Statutory Info Box */}
              <div className="p-3 rounded-lg bg-sky-500/10 border border-sky-500/20 text-sky-300 text-[11px] space-y-1">
                <div className="flex items-center gap-1.5 font-semibold">
                  <Info className="w-3.5 h-3.5" />
                  Statutory Calculations (Companies Act 2013)
                </div>
                <div>Statutory Useful Life: <span className="font-bold">{selectedCategoryObj?.useful_life} Years</span></div>
                <div>Statutory 5% Salvage Floor: <span className="font-bold">{formatINR(estimatedSalvage)}</span></div>
                <div className="text-slate-400 text-[10px]">Depreciable Base: {formatINR((parseFloat(grossBlock) || 0) - estimatedSalvage)}</div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">
                    Depreciation Method
                  </label>
                  <select
                    value={deprMethod}
                    onChange={(e) => setDeprMethod(e.target.value as 'SLM' | 'WDV')}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-medium focus:outline-none focus:border-sky-500"
                  >
                    <option value="SLM">Straight Line Method (SLM)</option>
                    <option value="WDV">Written Down Value (WDV)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-300 font-semibold mb-1">
                    Serial / Tag Number
                  </label>
                  <input
                    type="text"
                    value={serialNo}
                    onChange={(e) => setSerialNo(e.target.value)}
                    placeholder="e.g. SN-981249"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-sky-500"
                  />
                </div>
              </div>

              {registerError && (
                <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400">
                  {registerError}
                </div>
              )}

              {registerSuccess && (
                <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                  {registerSuccess}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsRegisterModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={registerSubmitting}
                  className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:bg-sky-800 text-white font-semibold flex items-center gap-1.5"
                >
                  {registerSubmitting ? 'Registering...' : 'Register Asset in Schedule II'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Run Depreciation */}
      {isRunModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Play className="w-5 h-5 text-emerald-400" />
                Execute Period Depreciation Run
              </h3>
              <button
                onClick={() => setIsRunModalOpen(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleRunDepreciation} className="space-y-4 text-xs">
              <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 space-y-1">
                <div className="font-semibold">Automated Balancing Journal Entry:</div>
                <div className="font-mono text-[11px] text-white">
                  DR 4070 (Depreciation Expense) ⇌ CR 1059 (Accumulated Depreciation - Fixed Assets)
                </div>
                <div className="text-[10px] text-slate-400">
                  Computes exact daily pro-rata depreciation while strictly guarding the 5% salvage value floor.
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">
                    Period Start Date*
                  </label>
                  <input
                    type="date"
                    value={periodStart}
                    onChange={(e) => setPeriodStart(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-emerald-500"
                    required
                  />
                </div>

                <div>
                  <label className="block text-slate-300 font-semibold mb-1">
                    Period End Date*
                  </label>
                  <input
                    type="date"
                    value={periodEnd}
                    onChange={(e) => setPeriodEnd(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-emerald-500"
                    required
                  />
                </div>
              </div>

              {runError && (
                <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400">
                  {runError}
                </div>
              )}

              {runSuccess && (
                <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400">
                  {runSuccess}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsRunModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={runSubmitting}
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white font-semibold flex items-center gap-1.5"
                >
                  {runSubmitting ? 'Calculating & Posting...' : 'Post Period Depreciation Entry'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

