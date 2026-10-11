'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Calculator, ArrowRight, ArrowLeft, RefreshCw, Percent, IndianRupee, Layers, FileText, CheckCircle2, AlertCircle } from 'lucide-react';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';

export default function CalculatorPage() {
  const router = useRouter();

  // Primary Calculator States
  const [directCost, setDirectCost] = useState<string>('10000.00');
  const [overheadCost, setOverheadCost] = useState<string>('2000.00');
  const [pricingMode, setPricingMode] = useState<'markup' | 'margin'>('margin');
  const [marginPct, setMarginPct] = useState<string>('25.00');
  const [gstRate, setGstRate] = useState<string>('18');
  const [transactionType, setTransactionType] = useState<'intra_state' | 'inter_state'>('intra_state');
  const [itemDescription, setItemDescription] = useState<string>('Software Consulting & Development Services');
  const [hsnSac, setHsnSac] = useState<string>('998314');

  // Outputs
  const [totalCostBase, setTotalCostBase] = useState<number>(12000.00);
  const [taxableBasePrice, setTaxableBasePrice] = useState<number>(16000.00);
  const [netProfit, setNetProfit] = useState<number>(4000.00);
  const [effectiveMargin, setEffectiveMargin] = useState<number>(25.00);
  const [cgstAmount, setCgstAmount] = useState<number>(1440.00);
  const [sgstAmount, setSgstAmount] = useState<number>(1440.00);
  const [igstAmount, setIgstAmount] = useState<number>(0.00);
  const [finalInvoicedPrice, setFinalInvoicedPrice] = useState<number>(18880.00);

  // Reverse Calculator States
  const [reverseMrp, setReverseMrp] = useState<string>('18880.00');
  const [reverseGstRate, setReverseGstRate] = useState<string>('18');
  const [reverseTargetMargin, setReverseTargetMargin] = useState<string>('25.00');
  const [reverseBase, setReverseBase] = useState<number>(16000.00);
  const [reverseTax, setReverseTax] = useState<number>(2880.00);
  const [reverseAllowableCost, setReverseAllowableCost] = useState<number>(12000.00);

  const [toastMsg, setToastMsg] = useState<string | null>(null);

  // Recalculate forward pricing
  useEffect(() => {
    const cDirect = parseFloat(directCost) || 0;
    const cOverhead = parseFloat(overheadCost) || 0;
    const cTotal = cDirect + cOverhead;
    setTotalCostBase(cTotal);

    const mPct = parseFloat(marginPct) || 0;
    let base = 0;

    if (pricingMode === 'markup') {
      base = cTotal * (1 + mPct / 100);
    } else {
      if (mPct < 100) {
        base = cTotal / (1 - mPct / 100);
      } else {
        base = cTotal;
      }
    }

    base = Math.round(base * 100) / 100;
    setTaxableBasePrice(base);

    const profit = Math.round((base - cTotal) * 100) / 100;
    setNetProfit(profit);
    setEffectiveMargin(base > 0 ? Math.round((profit / base) * 10000) / 100 : 0);

    const gRate = parseFloat(gstRate) || 0;
    if (transactionType === 'intra_state') {
      const halfRate = gRate / 2;
      const cgst = Math.round(((base * halfRate) / 100) * 100) / 100;
      const sgst = Math.round(((base * halfRate) / 100) * 100) / 100;
      setCgstAmount(cgst);
      setSgstAmount(sgst);
      setIgstAmount(0);
      setFinalInvoicedPrice(Math.round((base + cgst + sgst) * 100) / 100);
    } else {
      const igst = Math.round(((base * gRate) / 100) * 100) / 100;
      setCgstAmount(0);
      setSgstAmount(0);
      setIgstAmount(igst);
      setFinalInvoicedPrice(Math.round((base + igst) * 100) / 100);
    }
  }, [directCost, overheadCost, pricingMode, marginPct, gstRate, transactionType]);

  // Recalculate reverse pricing
  useEffect(() => {
    const mrp = parseFloat(reverseMrp) || 0;
    const gRate = parseFloat(reverseGstRate) || 0;
    const targetMargin = parseFloat(reverseTargetMargin) || 0;

    const base = Math.round((mrp / (1 + gRate / 100)) * 100) / 100;
    const tax = Math.round((mrp - base) * 100) / 100;
    const maxCost = Math.round((base * (1 - targetMargin / 100)) * 100) / 100;

    setReverseBase(base);
    setReverseTax(tax);
    setReverseAllowableCost(maxCost);
  }, [reverseMrp, reverseGstRate, reverseTargetMargin]);

  const handleConvertToInvoice = () => {
    const pendingItem = {
      description: itemDescription,
      hsn_sac: hsnSac,
      unit_price: taxableBasePrice,
      quantity: 1,
      taxable_amount: taxableBasePrice,
      gst_rate: parseFloat(gstRate) || 18,
      cgst_amount: cgstAmount,
      sgst_amount: sgstAmount,
      igst_amount: igstAmount,
      total_amount: finalInvoicedPrice,
      transaction_type: transactionType
    };

    if (typeof window !== 'undefined') {
      localStorage.setItem('b00k5_pending_invoice_item', JSON.stringify(pendingItem));
    }

    setToastMsg('Line item converted! Redirecting to new invoice...');
    setTimeout(() => {
      router.push(`/invoices/new?converted=true&price=${taxableBasePrice}&gst=${gstRate}`);
    }, 600);
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Navbar />
        <main className="flex-1 overflow-y-auto p-8 max-w-7xl mx-auto w-full space-y-8">
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-sky-500/10 border border-sky-500/20 rounded-xl text-sky-400">
              <Calculator className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">
                Cost-Plus Margin & GST Tax Calculator
              </h1>
              <p className="text-sm text-slate-400">
                Precision Pricing Engine with Dual GST Decomposition & 1-Click Invoice Line Conversion
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/dashboard"
            id="exit-calculator-btn"
            className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-medium transition-all text-sm font-sans"
          >
            <ArrowLeft className="w-4 h-4" />
            Exit to Dashboard
          </Link>
          <button
            id="convert-to-invoice-btn"
            onClick={handleConvertToInvoice}
            className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-medium shadow-lg shadow-sky-600/20 transition-all text-sm font-sans"
          >
            <FileText className="w-4 h-4" />
            Convert to Invoice Item
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {toastMsg && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center gap-3 text-sm">
          <CheckCircle2 className="w-5 h-5 shrink-0" />
          <span>{toastMsg}</span>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Inputs (7 Cols) */}
        <div className="lg:col-span-7 space-y-6">
          {/* Card 1: Cost Base */}
          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
            <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
              <Layers className="w-4 h-4 text-sky-400" />
              1. Cost Base Inputs
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Direct Cost (₹)
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-slate-500 font-mono text-sm">₹</span>
                  <input
                    id="direct-cost-input"
                    type="number"
                    step="0.01"
                    value={directCost}
                    onChange={(e) => setDirectCost(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700/80 rounded-lg pl-8 pr-3 py-2 text-white font-mono text-sm focus:outline-none focus:border-sky-500"
                    placeholder="10000.00"
                  />
                </div>
                <p className="text-[11px] text-slate-500 mt-1">Materials, labor, servers</p>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Indirect Overhead Cost (₹)
                </label>
                <div className="relative">
                  <span className="absolute left-3 top-2.5 text-slate-500 font-mono text-sm">₹</span>
                  <input
                    id="overhead-cost-input"
                    type="number"
                    step="0.01"
                    value={overheadCost}
                    onChange={(e) => setOverheadCost(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700/80 rounded-lg pl-8 pr-3 py-2 text-white font-mono text-sm focus:outline-none focus:border-sky-500"
                    placeholder="2000.00"
                  />
                </div>
                <p className="text-[11px] text-slate-500 mt-1">Platform fees, logistics, rent</p>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-slate-800/40 border border-slate-800 flex justify-between items-center text-xs">
              <span className="text-slate-400">Total Consolidated Cost Base (C_total):</span>
              <span id="total-cost-display" className="font-mono font-bold text-slate-200 text-sm">
                ₹{totalCostBase.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>
          </div>

          {/* Card 2: Margin & Pricing Strategy */}
          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
            <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
              <Percent className="w-4 h-4 text-emerald-400" />
              2. Profit Margin & Pricing Strategy
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Pricing Mode
                </label>
                <div className="grid grid-cols-2 gap-2 p-1 bg-slate-950 rounded-lg border border-slate-800 text-xs">
                  <button
                    type="button"
                    id="mode-markup"
                    onClick={() => setPricingMode('markup')}
                    className={`py-1.5 px-3 rounded text-center transition-all ${
                      pricingMode === 'markup'
                        ? 'bg-sky-600 text-white font-semibold shadow'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    Markup on Cost
                  </button>
                  <button
                    type="button"
                    id="mode-gross-margin"
                    onClick={() => setPricingMode('margin')}
                    className={`py-1.5 px-3 rounded text-center transition-all ${
                      pricingMode === 'margin'
                        ? 'bg-sky-600 text-white font-semibold shadow'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    Gross Margin %
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Target {pricingMode === 'markup' ? 'Markup' : 'Margin'} (%)
                </label>
                <div className="relative">
                  <input
                    id="margin-percentage-input"
                    type="number"
                    step="0.01"
                    value={marginPct}
                    onChange={(e) => setMarginPct(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-white font-mono text-sm focus:outline-none focus:border-sky-500"
                    placeholder="25.00"
                  />
                  <span className="absolute right-3 top-2.5 text-slate-500 font-mono text-sm">%</span>
                </div>
              </div>
            </div>
          </div>

          {/* Card 3: GST Slab & Transaction Type */}
          <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
            <h2 className="text-base font-semibold text-slate-200 flex items-center gap-2">
              <IndianRupee className="w-4 h-4 text-amber-400" />
              3. GST Slab & State Classification
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Applicable GST Slab
                </label>
                <div className="flex gap-2">
                  {['0', '5', '12', '18', '28'].map((rate) => (
                    <button
                      key={rate}
                      type="button"
                      id={`gst-rate-${rate}`}
                      onClick={() => setGstRate(rate)}
                      className={`flex-1 py-1.5 rounded-lg border text-xs font-mono font-bold transition-all ${
                        gstRate === rate
                          ? 'bg-amber-500/20 border-amber-500/40 text-amber-300'
                          : 'bg-slate-950 border-slate-800 text-slate-400 hover:text-white'
                      }`}
                    >
                      {rate}%
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">
                  Transaction Jurisdiction
                </label>
                <select
                  id="transaction-type-select"
                  value={transactionType}
                  onChange={(e) => setTransactionType(e.target.value as any)}
                  className="w-full bg-slate-950 border border-slate-700/80 rounded-lg px-3 py-2 text-white font-medium text-xs focus:outline-none focus:border-sky-500 cursor-pointer"
                >
                  <option value="intra_state">Intra-State (Karnataka) — CGST 9% + SGST 9%</option>
                  <option value="inter_state">Inter-State — IGST 18%</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  HSN / SAC Code
                </label>
                <input
                  type="text"
                  value={hsnSac}
                  onChange={(e) => setHsnSac(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-slate-300 font-mono text-xs focus:outline-none"
                  placeholder="998314"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">
                  Line Description
                </label>
                <input
                  type="text"
                  value={itemDescription}
                  onChange={(e) => setItemDescription(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-slate-300 text-xs focus:outline-none"
                  placeholder="Software Consulting Services"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Right Summary Panel (5 Cols) */}
        <div className="lg:col-span-5 space-y-6">
          {/* Summary Card */}
          <div className="p-6 rounded-2xl bg-gradient-to-b from-slate-900/90 to-slate-950 border border-slate-800 space-y-6 shadow-xl relative overflow-hidden">
            <div className="absolute top-0 right-0 w-32 h-32 bg-sky-500/5 rounded-full blur-3xl" />

            <h3 className="text-base font-bold text-white tracking-tight flex items-center justify-between">
              <span>Financial Quotation Summary</span>
              <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                Banker's Rounded
              </span>
            </h3>

            {/* Invoiced Price Highlight */}
            <div className="p-4 rounded-xl bg-slate-800/40 border border-slate-700/60 space-y-1">
              <span className="text-xs font-medium text-slate-400">Final Invoiced Price (Gross MRP)</span>
              <div id="final-invoiced-price" className="text-3xl font-extrabold font-mono text-emerald-400">
                ₹{finalInvoicedPrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
              <div className="text-[11px] text-slate-500 flex items-center gap-1.5">
                <span>Inclusive of all statutory Goods & Services Taxes</span>
              </div>
            </div>

            {/* Breakdown List */}
            <div className="space-y-3 text-xs divide-y divide-slate-800/60">
              <div className="flex justify-between items-center pt-2">
                <span className="text-slate-400">Taxable Base Selling Price:</span>
                <span id="taxable-base-price" className="font-mono font-bold text-slate-100 text-sm">
                  ₹{taxableBasePrice.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>

              <div className="flex justify-between items-center pt-2">
                <span className="text-slate-400">Consolidated Cost Base:</span>
                <span className="font-mono text-slate-300">
                  ₹{totalCostBase.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
              </div>

              <div className="flex justify-between items-center pt-2">
                <span className="text-slate-400">Net Profit Margin:</span>
                <span id="net-profit-display" className="font-mono font-bold text-emerald-400">
                  ₹{netProfit.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ({effectiveMargin}%)
                </span>
              </div>

              {transactionType === 'intra_state' ? (
                <>
                  <div className="flex justify-between items-center pt-2">
                    <span className="text-slate-400">CGST (Central Tax 9%):</span>
                    <span id="cgst-amount-display" className="font-mono text-amber-300">
                      ₹{cgstAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                  <div className="flex justify-between items-center pt-2">
                    <span className="text-slate-400">SGST (State Tax 9%):</span>
                    <span id="sgst-amount-display" className="font-mono text-amber-300">
                      ₹{sgstAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </span>
                  </div>
                </>
              ) : (
                <div className="flex justify-between items-center pt-2">
                  <span className="text-slate-400">IGST (Integrated Tax {gstRate}%):</span>
                  <span id="igst-amount-display" className="font-mono text-amber-300">
                    ₹{igstAmount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </span>
                </div>
              )}
            </div>

            <button
              onClick={handleConvertToInvoice}
              className="w-full py-3 rounded-xl bg-sky-600 hover:bg-sky-500 font-semibold text-white text-sm shadow-lg shadow-sky-600/30 transition-all flex items-center justify-center gap-2"
            >
              <FileText className="w-4 h-4" />
              Transfer to Active Invoice Draft
            </button>
          </div>

          {/* Reverse Backward Pricing Card */}
          <div className="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <RefreshCw className="w-3.5 h-3.5 text-sky-400" />
              Backward / Reverse MRP Extraction
            </h4>

            <div className="space-y-3">
              <div>
                <label className="block text-[11px] text-slate-500 mb-1">Target Gross Selling Price (MRP)</label>
                <div className="relative">
                  <span className="absolute left-3 top-2 text-slate-500 font-mono text-xs">₹</span>
                  <input
                    type="number"
                    value={reverseMrp}
                    onChange={(e) => setReverseMrp(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-7 pr-3 py-1.5 text-xs font-mono text-white focus:outline-none"
                    placeholder="18880.00"
                  />
                </div>
              </div>

              <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800 space-y-1.5 text-xs font-mono">
                <div className="flex justify-between">
                  <span className="text-slate-400">Extractable Taxable Base:</span>
                  <span className="text-slate-200">₹{reverseBase.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Statutory Tax Portion:</span>
                  <span className="text-amber-400">₹{reverseTax.toFixed(2)}</span>
                </div>
                <div className="flex justify-between border-t border-slate-800 pt-1">
                  <span className="text-slate-400">Allowable Cost Ceiling (25%):</span>
                  <span className="text-emerald-400 font-bold">₹{reverseAllowableCost.toFixed(2)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
        </main>
      </div>
    </div>
  );
}
