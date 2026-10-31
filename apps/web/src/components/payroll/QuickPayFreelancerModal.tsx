'use client';

import React, { useState, useMemo } from 'react';
import {
  Zap,
  X,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  ShieldCheck,
  Building,
  User,
  ArrowRight,
  Receipt,
  CreditCard
} from 'lucide-react';
import { fetchApi } from '@/lib/api';

interface QuickPayFreelancerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function QuickPayFreelancerModal({ isOpen, onClose, onSuccess }: QuickPayFreelancerModalProps) {
  const [name, setName] = useState('');
  const [amount, setAmount] = useState<string>('');
  const [amountType, setAmountType] = useState<'gross' | 'net'>('gross');
  const [serviceType, setServiceType] = useState<string>('194J_TECH');
  const [pan, setPan] = useState('');
  const [email, setEmail] = useState('');
  const [description, setDescription] = useState('');
  const [utr, setUtr] = useState('');
  const [paymentDate, setPaymentDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [disburseImmediately, setDisburseImmediately] = useState<boolean>(true);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successResult, setSuccessResult] = useState<any | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Dynamic TDS rate resolution
  const tdsRate = useMemo(() => {
    switch (serviceType) {
      case '194J_TECH':
        return 2.0;
      case '194J_PROF':
        return 10.0;
      case '194C':
        return 1.0;
      case 'NO_TDS':
        return 0.0;
      default:
        return 2.0;
    }
  }, [serviceType]);

  // Dynamic breakdown calculation
  const breakdown = useMemo(() => {
    const rawVal = parseFloat(amount);
    if (isNaN(rawVal) || rawVal <= 0) {
      return { gross: 0, tds: 0, net: 0, rate: tdsRate };
    }

    if (amountType === 'net') {
      const netVal = rawVal;
      const rateFrac = tdsRate / 100;
      const grossVal = tdsRate > 0 ? netVal / (1 - rateFrac) : netVal;
      const tdsVal = grossVal - netVal;
      return {
        gross: Math.round(grossVal * 100) / 100,
        tds: Math.round(tdsVal * 100) / 100,
        net: Math.round(netVal * 100) / 100,
        rate: tdsRate
      };
    } else {
      const grossVal = rawVal;
      const tdsVal = grossVal * (tdsRate / 100);
      const netVal = grossVal - tdsVal;
      return {
        gross: Math.round(grossVal * 100) / 100,
        tds: Math.round(tdsVal * 100) / 100,
        net: Math.round(netVal * 100) / 100,
        rate: tdsRate
      };
    }
  }, [amount, amountType, tdsRate]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Freelancer name is required.');
      return;
    }
    const numAmt = parseFloat(amount);
    if (isNaN(numAmt) || numAmt <= 0) {
      setError('Please enter a valid amount.');
      return;
    }

    setLoading(true);
    setError(null);
    setSuccessResult(null);

    try {
      const payload = {
        freelancer_name: name.trim(),
        pan_number: pan.trim() || undefined,
        email: email.trim() || undefined,
        service_type: serviceType,
        amount: numAmt,
        amount_type: amountType,
        description: description.trim() || `Payment to ${name.trim()}`,
        payment_date: paymentDate,
        bank_reference_or_utr: utr.trim() || undefined,
        disburse_immediately: disburseImmediately
      };

      const res = await fetchApi('/api/v1/payroll/contractor-payments/quick-pay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      setSuccessResult(res);
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1500);
    } catch (err: any) {
      setError(err.message || 'Failed to process quick payment.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 space-y-6 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 text-slate-400 hover:text-slate-200 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Modal Header */}
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
            <Zap className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              ⚡ Quick-Pay Freelancer
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 uppercase tracking-wider">
                1-Click GL Entry
              </span>
            </h3>
            <p className="text-xs text-slate-400">
              Auto-onboards freelancer, calculates statutory TDS, and generates balanced double-entry vouchers.
            </p>
          </div>
        </div>

        {error && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {successResult && (
          <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>
              Payment {successResult.payment_number} created successfully! Disbursed ₹{successResult.net_payable.toLocaleString('en-IN')}.
            </span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Freelancer Name */}
            <div className="space-y-1.5 sm:col-span-2">
              <label className="text-xs font-medium text-slate-300">
                Freelancer / Contractor Name <span className="text-rose-400">*</span>
              </label>
              <div className="relative">
                <input
                  type="text"
                  required
                  placeholder="e.g. Priya Sharma, Alex Morgan"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-amber-500"
                />
              </div>
            </div>

            {/* Amount */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300 flex items-center justify-between">
                <span>Amount (₹) <span className="text-rose-400">*</span></span>
              </label>
              <input
                type="number"
                step="0.01"
                min="1"
                required
                placeholder="e.g. 50000"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm font-mono text-white placeholder:text-slate-600 focus:outline-none focus:border-amber-500"
              />
            </div>

            {/* Amount Mode */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">Amount Type</label>
              <div className="grid grid-cols-2 gap-2 bg-slate-950 p-1 rounded-xl border border-slate-800 text-xs font-medium">
                <button
                  type="button"
                  onClick={() => setAmountType('gross')}
                  className={`py-1.5 rounded-lg transition-colors ${
                    amountType === 'gross'
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Gross (Pre-Tax)
                </button>
                <button
                  type="button"
                  onClick={() => setAmountType('net')}
                  className={`py-1.5 rounded-lg transition-colors ${
                    amountType === 'net'
                      ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Net In-Hand
                </button>
              </div>
            </div>

            {/* Service Type / TDS Section */}
            <div className="space-y-1.5 sm:col-span-2">
              <label className="text-xs font-medium text-slate-300 flex items-center justify-between">
                <span>Service Category & Statutory TDS Section</span>
                <span className="text-[10px] font-mono text-amber-400">TDS Rate: {tdsRate}%</span>
              </label>
              <select
                value={serviceType}
                onChange={(e) => setServiceType(e.target.value)}
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-amber-500 font-mono"
              >
                <option value="194J_TECH">Section 194J(1) - Technical Services / Software Development (2%)</option>
                <option value="194J_PROF">Section 194J(1) - Professional / Legal / Design / Medical (10%)</option>
                <option value="194C">Section 194C - Contractor & Operational Works (1%)</option>
                <option value="NO_TDS">Exempt / Below Statutory Threshold (0% TDS)</option>
              </select>
            </div>
          </div>

          {/* Live Calculation Preview Card */}
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Gross Fee (Expense u/s Note 19)</span>
              <span className="font-mono text-white font-semibold">
                ₹{breakdown.gross.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </span>
            </div>
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span className="flex items-center gap-1">
                Statutory TDS Withholding ({breakdown.rate}%)
              </span>
              <span className="font-mono text-amber-400 font-semibold">
                - ₹{breakdown.tds.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </span>
            </div>
            <div className="h-[1px] bg-slate-800"></div>
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium text-white flex items-center gap-1.5">
                <CreditCard className="w-4 h-4 text-emerald-400" />
                Net Payout to Bank
              </span>
              <span className="font-mono text-emerald-400 font-bold text-base">
                ₹{breakdown.net.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
              </span>
            </div>
          </div>

          {/* Immediate Bank Disbursement Checkbox */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950/60 border border-slate-800">
            <div>
              <div className="text-xs font-semibold text-white">Disburse Immediately</div>
              <div className="text-[11px] text-slate-500">
                Posts instant credit to Bank A/C (1010) and marks payment as Disbursed.
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={disburseImmediately}
                onChange={(e) => setDisburseImmediately(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-9 h-5 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-amber-500"></div>
            </label>
          </div>

          {/* Advanced / Optional Fields Toggle */}
          <div>
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1 transition-colors"
            >
              {showAdvanced ? '− Hide Optional Details' : '+ Show Optional Details (PAN, Email, UTR, Date)'}
            </button>

            {showAdvanced && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-3">
                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-slate-400">PAN Number (10 characters)</label>
                  <input
                    type="text"
                    maxLength={10}
                    placeholder="e.g. ABCDE1234F"
                    value={pan}
                    onChange={(e) => setPan(e.target.value.toUpperCase())}
                    className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-white placeholder:text-slate-600 focus:outline-none focus:border-amber-500 uppercase"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-slate-400">Email Address</label>
                  <input
                    type="email"
                    placeholder="freelancer@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-amber-500"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-slate-400">Bank UTR / IMPS Ref</label>
                  <input
                    type="text"
                    placeholder="e.g. UTR1234567890"
                    value={utr}
                    onChange={(e) => setUtr(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-white placeholder:text-slate-600 focus:outline-none focus:border-amber-500"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[11px] font-medium text-slate-400">Payment Date</label>
                  <input
                    type="date"
                    value={paymentDate}
                    onChange={(e) => setPaymentDate(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono text-white focus:outline-none focus:border-amber-500"
                  />
                </div>

                <div className="space-y-1 sm:col-span-2">
                  <label className="text-[11px] font-medium text-slate-400">Description / Memo</label>
                  <input
                    type="text"
                    placeholder="e.g. April 2026 Mobile App UI Design sprint"
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white placeholder:text-slate-600 focus:outline-none focus:border-amber-500"
                  />
                </div>
              </div>
            )}
          </div>

          {/* Form Actions */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-xs transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-950 font-bold text-xs flex items-center gap-2 transition-colors shadow-sm"
            >
              <Zap className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              {loading ? 'Processing Payment...' : '⚡ Confirm & Pay Freelancer'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
