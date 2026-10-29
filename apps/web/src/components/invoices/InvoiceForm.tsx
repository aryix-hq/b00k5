'use client';

import React from 'react';
import { Plus, Trash2, Info, AlertCircle } from 'lucide-react';

export interface InvoiceLineItem {
  id: string;
  description: string;
  hsn_sac: string;
  uqc: string;
  quantity: number;
  unit_price: number;
  gst_rate: number;
  taxable_amount: number;
  cgst_amount: number;
  sgst_amount: number;
  igst_amount: number;
  total_amount: number;
}

// Official 44+ GSTN UQC Standard Codes
export const GSTN_UQC_OPTIONS: { code: string; label: string }[] = [
  { code: 'NOS', label: 'NOS - Numbers' },
  { code: 'PCS', label: 'PCS - Pieces' },
  { code: 'BOX', label: 'BOX - Boxes' },
  { code: 'KGS', label: 'KGS - Kilograms' },
  { code: 'MTR', label: 'MTR - Meters' },
  { code: 'SET', label: 'SET - Sets' },
  { code: 'BAG', label: 'BAG - Bags' },
  { code: 'BAL', label: 'BAL - Bale' },
  { code: 'BDL', label: 'BDL - Bundles' },
  { code: 'BKL', label: 'BKL - Buckles' },
  { code: 'BOU', label: 'BOU - Billion of Units' },
  { code: 'BTL', label: 'BTL - Bottles' },
  { code: 'BUN', label: 'BUN - Bunches' },
  { code: 'CAN', label: 'CAN - Cans' },
  { code: 'CBM', label: 'CBM - Cubic Meters' },
  { code: 'CCM', label: 'CCM - Cubic Centimeters' },
  { code: 'CMS', label: 'CMS - Centimeters' },
  { code: 'CTN', label: 'CTN - Cartons' },
  { code: 'DOZ', label: 'DOZ - Dozens' },
  { code: 'DRM', label: 'DRM - Drums' },
  { code: 'GGK', label: 'GGK - Great Gross' },
  { code: 'GMS', label: 'GMS - Grammes' },
  { code: 'GRS', label: 'GRS - Gross' },
  { code: 'GYD', label: 'GYD - Gross Yards' },
  { code: 'KLR', label: 'KLR - Kilolitre' },
  { code: 'KME', label: 'KME - Kilometre' },
  { code: 'MLT', label: 'MLT - Millilitre' },
  { code: 'MTS', label: 'MTS - Metric Ton' },
  { code: 'PAC', label: 'PAC - Packs' },
  { code: 'PRS', label: 'PRS - Pairs' },
  { code: 'QTL', label: 'QTL - Quintal' },
  { code: 'ROL', label: 'ROL - Rolls' },
  { code: 'SQF', label: 'SQF - Square Feet' },
  { code: 'SQM', label: 'SQM - Square Meters' },
  { code: 'SQY', label: 'SQY - Square Yards' },
  { code: 'TBS', label: 'TBS - Tablets' },
  { code: 'TGM', label: 'TGM - Ten Gross' },
  { code: 'THD', label: 'THD - Thousands' },
  { code: 'TON', label: 'TON - Tonnes' },
  { code: 'TUB', label: 'TUB - Tubes' },
  { code: 'UGS', label: 'UGS - US Gallons' },
  { code: 'UNT', label: 'UNT - Units' },
  { code: 'YDS', label: 'YDS - Yards' },
  { code: 'OTH', label: 'OTH - Others' },
];

export const isServiceHSN = (hsn: string): boolean => {
  return String(hsn || '').trim().startsWith('99');
};

interface InvoiceFormProps {
  lineItems: InvoiceLineItem[];
  onChange: (items: InvoiceLineItem[]) => void;
  placeOfSupply: string;
  supplierStateCode?: string;
}

export function InvoiceForm({
  lineItems,
  onChange,
  placeOfSupply,
  supplierStateCode = '29' // Karnataka default
}: InvoiceFormProps) {
  const isInterstate = String(placeOfSupply).trim() !== String(supplierStateCode).trim();

  const recalculateItem = (item: Partial<InvoiceLineItem>): InvoiceLineItem => {
    const qty = Number(item.quantity) || 0;
    const price = Number(item.unit_price) || 0;
    const taxable = Math.round(qty * price * 100) / 100;
    const rate = Number(item.gst_rate) || 0;
    const totalTax = Math.round(taxable * (rate / 100) * 100) / 100;

    let cgst = 0;
    let sgst = 0;
    let igst = 0;

    if (isInterstate) {
      igst = totalTax;
    } else {
      cgst = Math.round((totalTax / 2) * 100) / 100;
      sgst = Math.round((totalTax - cgst) * 100) / 100;
    }

    const total = Math.round((taxable + totalTax) * 100) / 100;

    const hsn = item.hsn_sac || '';
    const isService = isServiceHSN(hsn);
    let uqc = item.uqc || (isService ? 'NA' : 'NOS');

    if (isService) {
      uqc = 'NA';
    } else if (uqc === 'NA') {
      uqc = 'NOS';
    }

    return {
      id: item.id || `item-${Date.now()}-${Math.random()}`,
      description: item.description || '',
      hsn_sac: hsn,
      uqc,
      quantity: qty,
      unit_price: price,
      gst_rate: rate,
      taxable_amount: taxable,
      cgst_amount: cgst,
      sgst_amount: sgst,
      igst_amount: igst,
      total_amount: total,
    };
  };

  const handleFieldChange = (id: string, field: keyof InvoiceLineItem, value: any) => {
    const updated = lineItems.map((item) => {
      if (item.id !== id) return item;

      const draft: any = { ...item, [field]: value };

      // Automatic Chapter 99 Service Invariant
      if (field === 'hsn_sac') {
        const hsnVal = String(value || '').trim();
        if (isServiceHSN(hsnVal)) {
          draft.uqc = 'NA';
        } else if (draft.uqc === 'NA') {
          draft.uqc = 'NOS';
        }
      }

      return recalculateItem(draft);
    });
    onChange(updated);
  };

  const addItem = () => {
    const newItem = recalculateItem({
      id: `item-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`,
      description: '',
      hsn_sac: '998314', // Default to software consulting services
      uqc: 'NA',
      quantity: 1,
      unit_price: 0,
      gst_rate: 18,
    });
    onChange([...lineItems, newItem]);
  };

  const removeItem = (id: string) => {
    if (lineItems.length <= 1) return;
    onChange(lineItems.filter((it) => it.id !== id));
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-white">Line Items & HSN/UQC Decomposition</h3>
          <p className="text-xs text-slate-400">
            GST Rule 46: Chapter 99 Services strictly report UQC as <span className="font-mono text-amber-400 font-bold">NA</span>. Goods require standard GSTN unit codes.
          </p>
        </div>
        <button
          type="button"
          onClick={addItem}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-500/20 text-sky-300 hover:bg-sky-500/30 border border-sky-500/30 text-xs font-semibold transition"
        >
          <Plus className="w-3.5 h-3.5" />
          Add Item
        </button>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/80">
        <table className="w-full text-left text-xs text-slate-300 min-w-[760px]">
          <thead className="bg-slate-900/90 text-slate-400 font-mono uppercase text-[11px] border-b border-slate-800">
            <tr>
              <th className="py-2.5 px-3 w-5/12">Description</th>
              <th className="py-2.5 px-2 w-2/12">HSN / SAC</th>
              <th className="py-2.5 px-2 w-2/12">UQC Unit</th>
              <th className="py-2.5 px-2 w-1/12 text-right">Qty</th>
              <th className="py-2.5 px-2 w-2/12 text-right">Rate (₹)</th>
              <th className="py-2.5 px-2 w-1/12 text-right">GST %</th>
              <th className="py-2.5 px-3 w-2/12 text-right">Total (₹)</th>
              <th className="py-2.5 px-2 w-8 text-center"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {lineItems.map((item) => {
              const serviceItem = isServiceHSN(item.hsn_sac);

              return (
                <tr key={item.id} className="hover:bg-slate-900/40 transition">
                  <td className="py-2.5 px-3 font-sans">
                    <input
                      type="text"
                      value={item.description}
                      onChange={(e) => handleFieldChange(item.id, 'description', e.target.value)}
                      placeholder="Item description or service particulars"
                      className="w-full bg-slate-900/90 border border-slate-700/80 rounded px-2.5 py-1.5 text-white text-xs focus:border-sky-500 focus:outline-none"
                      required
                    />
                  </td>

                  <td className="py-2.5 px-2">
                    <input
                      type="text"
                      value={item.hsn_sac}
                      onChange={(e) => handleFieldChange(item.id, 'hsn_sac', e.target.value)}
                      placeholder="e.g. 998314 or 8471"
                      className="w-full bg-slate-900/90 border border-slate-700/80 rounded px-2 py-1.5 text-amber-300 font-mono text-xs focus:border-sky-500 focus:outline-none"
                      required
                    />
                  </td>

                  <td className="py-2.5 px-2">
                    {serviceItem ? (
                      <div className="relative group">
                        <input
                          type="text"
                          value="NA (Services)"
                          readOnly
                          disabled
                          className="w-full bg-slate-900/50 border border-amber-500/30 rounded px-2 py-1.5 text-amber-400 font-mono text-xs cursor-not-allowed opacity-90"
                        />
                        <div className="hidden group-hover:block absolute bottom-full left-0 mb-1 w-52 p-2 bg-slate-900 border border-amber-500/40 rounded-lg shadow-xl text-[10px] text-slate-300 z-30 font-sans">
                          <div className="flex items-start gap-1">
                            <Info className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
                            <span>Chapter 99 (Services) strictly mandates UQC = 'NA' per GSTN rules.</span>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <select
                        value={item.uqc || 'NOS'}
                        onChange={(e) => handleFieldChange(item.id, 'uqc', e.target.value)}
                        className="w-full bg-slate-900/90 border border-slate-700/80 rounded px-1.5 py-1.5 text-sky-300 font-mono text-xs focus:border-sky-500 focus:outline-none cursor-pointer"
                      >
                        {GSTN_UQC_OPTIONS.map((u) => (
                          <option key={u.code} value={u.code}>
                            {u.label}
                          </option>
                        ))}
                      </select>
                    )}
                  </td>

                  <td className="py-2.5 px-2 text-right">
                    <input
                      type="number"
                      step="any"
                      min="0.001"
                      value={item.quantity}
                      onChange={(e) => handleFieldChange(item.id, 'quantity', parseFloat(e.target.value) || 0)}
                      className="w-full bg-slate-900/90 border border-slate-700/80 rounded px-2 py-1.5 text-right text-slate-100 font-mono text-xs focus:border-sky-500 focus:outline-none"
                      required
                    />
                  </td>

                  <td className="py-2.5 px-2 text-right">
                    <input
                      type="number"
                      step="0.01"
                      min="0"
                      value={item.unit_price}
                      onChange={(e) => handleFieldChange(item.id, 'unit_price', parseFloat(e.target.value) || 0)}
                      className="w-full bg-slate-900/90 border border-slate-700/80 rounded px-2 py-1.5 text-right text-slate-100 font-mono text-xs focus:border-sky-500 focus:outline-none"
                      required
                    />
                  </td>

                  <td className="py-2.5 px-2 text-right">
                    <select
                      value={item.gst_rate}
                      onChange={(e) => handleFieldChange(item.id, 'gst_rate', parseFloat(e.target.value) || 0)}
                      className="w-full bg-slate-900/90 border border-slate-700/80 rounded px-1 py-1.5 text-right text-amber-300 font-mono text-xs focus:border-sky-500 focus:outline-none cursor-pointer"
                    >
                      <option value="0">0%</option>
                      <option value="5">5%</option>
                      <option value="12">12%</option>
                      <option value="18">18%</option>
                      <option value="28">28%</option>
                    </select>
                  </td>

                  <td className="py-2.5 px-3 text-right font-bold text-emerald-400">
                    ₹{item.total_amount.toFixed(2)}
                  </td>

                  <td className="py-2.5 px-2 text-center">
                    <button
                      type="button"
                      onClick={() => removeItem(item.id)}
                      disabled={lineItems.length <= 1}
                      className="text-slate-500 hover:text-red-400 disabled:opacity-30 disabled:hover:text-slate-500 transition p-1"
                      title={lineItems.length <= 1 ? 'An invoice must have at least one line item' : 'Remove item'}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

