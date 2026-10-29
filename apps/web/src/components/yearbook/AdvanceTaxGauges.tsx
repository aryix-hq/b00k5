'use client';

import React, { useState, useEffect } from 'react';
import { IndianRupee, AlertTriangle, CheckCircle2, Clock, ShieldCheck, ArrowUpRight, TrendingUp } from 'lucide-react';

interface Installment {
  quarter: string;
  due_date: string;
  cumulative_percent: number;
  target_amount: number;
  safe_harbor_amount: number;
  paid_in_quarter: number;
  cumulative_paid: number;
  is_compliant: boolean;
  shortfall: number;
}

interface AdvanceTaxForecastData {
  tenant_id: string;
  fiscal_year: string;
  assessment_year: string;
  calculation_date: string;
  tax_regime: string;
  effective_tax_rate_percent: number;
  annual_projection: {
    projected_net_taxable_income: number;
    gross_tax_liability: number;
    tds_credits_claimed: number;
    net_advance_tax_payable: number;
    is_sec208_mandatory: boolean;
    statutory_threshold_rule: string;
  };
  installments: Installment[];
  next_action: {
    quarter: string;
    due_date: string;
    target_amount: number;
    payable_now: number;
    recommended_monthly_savings_reserve: number;
  };
  penal_interest_simulation: {
    section_234c_deferral_interest: number;
    section_234b_default_interest: number;
    total_statutory_penalty_risk: number;
  };
}

interface AdvanceTaxGaugesProps {
  selectedFY: string;
}

export function AdvanceTaxGauges({ selectedFY }: AdvanceTaxGaugesProps) {
  const [data, setData] = useState<AdvanceTaxForecastData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function fetchForecast() {
      setLoading(true);
      setError(null);
      try {
        const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
        const tenantId = typeof window !== 'undefined' ? localStorage.getItem('b00k5_tenant_id') : null;

        const headers: Record<string, string> = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        if (tenantId) headers['X-Tenant-ID'] = tenantId;

        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/compliance/advance-tax/forecast?fy=${selectedFY}`,
          { headers }
        );

        if (!res.ok) {
          throw new Error(`Failed to load Advance Tax forecast: HTTP ${res.status}`);
        }

        const resData = await res.json();
        if (isMounted) {
          setData(resData);
        }
      } catch (err: any) {
        if (isMounted) {
          setError(err.message || 'Error fetching Advance Tax forecast');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    fetchForecast();

    return () => {
      isMounted = false;
    };
  }, [selectedFY]);

  if (loading) {
    return (
      <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl animate-pulse space-y-4">
        <div className="h-4 bg-slate-800 rounded w-1/3"></div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-slate-950/60 rounded-lg"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-4 bg-slate-900/60 border border-slate-800 rounded-xl text-xs text-slate-400">
        <div className="flex items-center gap-2 text-amber-400 font-semibold mb-1">
          <AlertTriangle className="w-4 h-4" />
          <span>Advance Tax Forecast Offline</span>
        </div>
        <p>{error || 'Ledger projection currently unavailable for this period.'}</p>
      </div>
    );
  }

  const { annual_projection, installments, penal_interest_simulation, next_action } = data;
  const isMandatory = annual_projection.is_sec208_mandatory;
  const totalPenalty = penal_interest_simulation.total_statutory_penalty_risk;

  const formatDate = (iso: string) => {
    try {
      const d = new Date(iso);
      return d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
    } catch {
      return iso;
    }
  };

  return (
    <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-4 shadow-lg">
      {/* 1. Header & Summary Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h4 className="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-2">
              <IndianRupee className="w-4 h-4 text-amber-400" />
              Advance Tax §208 & Penalty Gauges (§234B / §234C)
            </h4>
            <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
              FY {selectedFY}
            </span>
            {isMandatory ? (
              <span className="text-[10px] px-2 py-0.5 rounded font-medium bg-rose-500/10 text-rose-300 border border-rose-500/20">
                §208 Mandatory (&gt; ₹10k)
              </span>
            ) : (
              <span className="text-[10px] px-2 py-0.5 rounded font-medium bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                §208 Exempt (&le; ₹10k)
              </span>
            )}
          </div>
          <p className="text-xs text-slate-400">
            Projected Tax: <span className="font-mono text-slate-200">₹{annual_projection.net_advance_tax_payable.toLocaleString('en-IN')}</span> | Rate: <span className="font-mono text-slate-300">{data.effective_tax_rate_percent}%</span> ({data.tax_regime.toUpperCase()})
          </p>
        </div>

        {/* Penalty Risk Badge */}
        <div className="flex items-center gap-2">
          {totalPenalty > 0 ? (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-rose-950/60 border border-rose-600/50 text-rose-300 text-xs shadow-inner">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
              <div>
                <div className="text-[10px] uppercase font-bold tracking-wider text-rose-400">Statutory Penalty Risk</div>
                <div className="font-mono font-bold text-rose-200">₹{totalPenalty.toLocaleString('en-IN')}</div>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-950/40 border border-emerald-600/30 text-emerald-300 text-xs">
              <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
              <div>
                <div className="text-[10px] uppercase font-bold tracking-wider text-emerald-400">§234B/C Status</div>
                <div className="font-mono text-slate-200">Zero Penalties Accrued</div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 2. Four Quarterly Advance Tax Gauges */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {installments.map((inst) => {
          const target = inst.target_amount;
          const paid = inst.cumulative_paid;
          const pctPaid = target > 0 ? Math.min(100, Math.round((paid / target) * 100)) : 100;
          const isOverdue = !inst.is_compliant;
          const isDueSoon = !isOverdue && paid < target;

          return (
            <div
              key={inst.quarter}
              className={`p-3.5 rounded-xl border transition flex flex-col justify-between ${
                isOverdue
                  ? 'bg-rose-950/20 border-rose-500/30 hover:border-rose-500/50'
                  : paid >= target
                  ? 'bg-emerald-950/20 border-emerald-500/30 hover:border-emerald-500/50'
                  : 'bg-slate-950/60 border-slate-800 hover:border-slate-700'
              }`}
            >
              <div>
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <span className="font-bold text-white tracking-wide">
                    {inst.quarter} ({inst.cumulative_percent}%)
                  </span>
                  {inst.is_compliant ? (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1">
                      <CheckCircle2 className="w-2.5 h-2.5" /> Compliant
                    </span>
                  ) : (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center gap-1">
                      <AlertTriangle className="w-2.5 h-2.5" /> Shortfall
                    </span>
                  )}
                </div>

                <div className="text-[11px] text-slate-400 mb-2 flex items-center justify-between font-mono">
                  <span>Due: {formatDate(inst.due_date)}</span>
                  <span>{pctPaid}%</span>
                </div>

                {/* Progress Gauge */}
                <div className="relative w-full h-2 bg-slate-800 rounded-full overflow-hidden mb-2">
                  <div
                    className={`h-full transition-all duration-500 rounded-full ${
                      isOverdue
                        ? 'bg-rose-500'
                        : pctPaid >= 100
                        ? 'bg-emerald-500'
                        : 'bg-amber-400'
                    }`}
                    style={{ width: `${pctPaid}%` }}
                  />
                  {/* Safe Harbor Marker for Q1 (12%) and Q2 (36%) */}
                  {(inst.quarter === 'Q1' || inst.quarter === 'Q2') && (
                    <div
                      className="absolute top-0 bottom-0 w-0.5 bg-sky-400 z-10"
                      style={{
                        left: inst.quarter === 'Q1' ? '80%' : '80%', // 12% is 80% of 15%; 36% is 80% of 45%
                      }}
                      title="Safe Harbor Threshold (80% of quarterly quota)"
                    />
                  )}
                </div>
              </div>

              {/* Targets and Shortfall */}
              <div className="space-y-1 font-mono text-[11px] border-t border-slate-800/60 pt-2 mt-1">
                <div className="flex justify-between text-slate-400">
                  <span>Target:</span>
                  <span className="text-slate-200">₹{target.toLocaleString('en-IN')}</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Paid:</span>
                  <span className={paid >= target ? 'text-emerald-400' : 'text-slate-300'}>
                    ₹{paid.toLocaleString('en-IN')}
                  </span>
                </div>
                {inst.shortfall > 0 && (
                  <div className="flex justify-between text-rose-400 font-semibold">
                    <span>Shortfall:</span>
                    <span>₹{inst.shortfall.toLocaleString('en-IN')}</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 3. Action Callout & Safe Harbor Advisory */}
      <div className="bg-slate-950/80 border border-slate-800/90 rounded-lg p-3 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="space-y-0.5">
          <div className="text-slate-200 font-medium flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5 text-sky-400" />
            <span>
              Next Installment: <span className="font-mono text-amber-400 font-bold">{next_action.quarter}</span> (Due {formatDate(next_action.due_date)})
            </span>
            <span className="text-slate-400 font-normal">
              • Payable: <span className="font-mono text-white font-semibold">₹{next_action.payable_now.toLocaleString('en-IN')}</span>
            </span>
          </div>
          <p className="text-[11px] text-slate-400">
            Recommended monthly savings reserve: <span className="font-mono text-sky-300">₹{next_action.recommended_monthly_savings_reserve.toLocaleString('en-IN')}/mo</span> to avoid §234C deferral interest (1% p.m.).
          </p>
        </div>

        <a
          href="/banking"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 border border-amber-500/30 text-[11px] font-semibold whitespace-nowrap transition self-start sm:self-center"
        >
          <span>Record Challan 280</span>
          <ArrowUpRight className="w-3.5 h-3.5" />
        </a>
      </div>
    </div>
  );
}

