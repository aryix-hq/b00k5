'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { FilePlus, IndianRupee, Calendar, User, Plus, Trash2, CheckCircle2, AlertTriangle, ArrowLeft, UploadCloud } from 'lucide-react';
import Link from 'next/link';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';

interface LineItem {
  id: string;
  description: string;
  hsn_sac: string;
  unit_price: number;
  quantity: number;
  gst_rate: number;
  taxable_amount: number;
  cgst_amount: number;
  sgst_amount: number;
  igst_amount: number;
  total_amount: number;
}

function NewInvoiceInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [activeFY, setActiveFY] = useState<string>('2026-27');
  const [customerName, setCustomerName] = useState<string>('');
  const [customerGstin, setCustomerGstin] = useState<string>('');
  const [placeOfSupply, setPlaceOfSupply] = useState<string>('29'); // 29 = Karnataka (Intra-state)
  const [invoiceNumber, setInvoiceNumber] = useState<string>('');
  const [invoiceDate, setInvoiceDate] = useState<string>(() => new Date().toISOString().split('T')[0]);
  const [dateError, setDateError] = useState<string | null>(null);

  // Upload & OCR Scan State
  const [scanning, setScanning] = useState<boolean>(false);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const [duplicateWarning, setDuplicateWarning] = useState<string | null>(null);
  const [confirmDuplicate, setConfirmDuplicate] = useState<boolean>(false);
  const [contactId, setContactId] = useState<string | null>(null);

  const [lineItems, setLineItems] = useState<LineItem[]>([
    {
      id: 'item-1',
      description: '',
      hsn_sac: '998314',
      unit_price: 0.00,
      quantity: 1,
      gst_rate: 18,
      taxable_amount: 0.00,
      cgst_amount: 0.00,
      sgst_amount: 0.00,
      igst_amount: 0.00,
      total_amount: 0.00
    }
  ]);

  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Load FY & pending converted items
  useEffect(() => {
    const updateFY = () => {
      if (typeof window !== 'undefined') {
        const rawFy = localStorage.getItem('b00k5_selected_fy') || '2026-27';
        const normalized = rawFy.replace('FY', '').trim();
        setActiveFY(normalized);
        const inputElem = document.getElementById('invoice-date-input') as HTMLInputElement | null;
        const currentD = inputElem?.value || invoiceDate;
        if (currentD) {
          validateDateWithFY(currentD, normalized);
        }
      }
    };

    updateFY();

    if (typeof window !== 'undefined') {
      window.addEventListener('b00k5_fy_changed', updateFY);
      window.addEventListener('storage', updateFY);

      // Check if item was converted from calculator
      const convertedJson = localStorage.getItem('b00k5_pending_invoice_item');
      if (convertedJson) {
        try {
          const item = JSON.parse(convertedJson);
          setLineItems([
            {
              id: 'converted-1',
              description: item.description || 'Software Consulting & Development Services',
              hsn_sac: item.hsn_sac || '998314',
              unit_price: Number(item.unit_price) || 16000.00,
              quantity: Number(item.quantity) || 1,
              gst_rate: Number(item.gst_rate) || 18,
              taxable_amount: Number(item.taxable_amount) || 16000.00,
              cgst_amount: Number(item.cgst_amount) || 1440.00,
              sgst_amount: Number(item.sgst_amount) || 1440.00,
              igst_amount: Number(item.igst_amount) || 0.00,
              total_amount: Number(item.total_amount) || 18880.00
            }
          ]);
        } catch (e) {
          console.warn('Failed to parse converted invoice item:', e);
        }
      }
    }

    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('b00k5_fy_changed', updateFY);
        window.removeEventListener('storage', updateFY);
      }
    };
  }, [invoiceDate]);

  // Fetch sequential invoice number in INV-YYYY-MM-XXX format
  useEffect(() => {
    async function fetchNextNumber() {
      try {
        const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
        const tenantId = typeof window !== 'undefined' ? localStorage.getItem('b00k5_tenant_id') : null;
        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/invoices/next-number?invoice_date=${invoiceDate}`, {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
          }
        });
        if (res.ok) {
          const data = await res.json();
          if (data.next_invoice_number && (!invoiceNumber || invoiceNumber.startsWith('INV-'))) {
            setInvoiceNumber(data.next_invoice_number);
          }
        }
      } catch (e) {
        console.warn('Failed to fetch next invoice number:', e);
      }
    }
    fetchNextNumber();
  }, [invoiceDate]);

  // Financial Year Date Validator
  const handleDateChange = (val: string) => {
    setInvoiceDate(val);
    validateDateWithFY(val, activeFY);
  };

  const validateDateWithFY = (dStr: string, fy: string) => {
    if (!dStr) return true;
    const dt = new Date(dStr);
    const startYr = parseInt(fy.replace('FY', '').trim().split(/[-/]/)[0], 10) || 2025;
    const minDate = new Date(`${startYr}-04-01`);
    const maxDate = new Date(`${startYr + 1}-03-31`);

    if (dt < minDate || dt > maxDate) {
      const shortFy = `${startYr}-${String(startYr + 1).slice(-2)}`;
      const err = `Invoice date does not fall within the selected Financial Year (${shortFy})`;
      setDateError(err);
      return false;
    } else {
      setDateError(null);
      return true;
    }
  };

  const calculateSubtotal = () => lineItems.reduce((acc, it) => acc + it.taxable_amount, 0);
  const calculateCgst = () => lineItems.reduce((acc, it) => acc + it.cgst_amount, 0);
  const calculateSgst = () => lineItems.reduce((acc, it) => acc + it.sgst_amount, 0);
  const calculateIgst = () => lineItems.reduce((acc, it) => acc + it.igst_amount, 0);
  const calculateGrandTotal = () => calculateSubtotal() + calculateCgst() + calculateSgst() + calculateIgst();

  const handleInvoiceUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setScanning(true);
    setDuplicateWarning(null);
    setUploadedFileName(file.name);

    const fd = new FormData();
    fd.append('file', file);

    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = typeof window !== 'undefined' ? localStorage.getItem('b00k5_tenant_id') : null;

      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/invoices/scan-invoice`, {
        method: 'POST',
        headers,
        body: fd
      });

      const data = await res.json();
      if (res.ok && data.success) {
        if (data.invoice_number) setInvoiceNumber(data.invoice_number);
        if (data.issue_date) {
          setInvoiceDate(data.issue_date);
          validateDateWithFY(data.issue_date, activeFY);
        }
        if (data.customer_name) setCustomerName(data.customer_name);
        if (data.customer_gstin) setCustomerGstin(data.customer_gstin);
        if (data.place_of_supply) setPlaceOfSupply(data.place_of_supply);
        if (data.contact_id) setContactId(data.contact_id);

        if (Array.isArray(data.items) && data.items.length > 0) {
          setLineItems(data.items.map((it: any, idx: number) => ({
            id: `scanned-${idx}`,
            description: it.item_description,
            hsn_sac: it.hsn_sac_code || '998314',
            unit_price: Number(it.unit_price) || 0,
            quantity: Number(it.quantity) || 1,
            gst_rate: Number(it.gst_rate_percent) || 18,
            taxable_amount: Number(it.taxable_value) || 0,
            cgst_amount: Number(it.cgst_amount) || 0,
            sgst_amount: Number(it.sgst_amount) || 0,
            igst_amount: Number(it.igst_amount) || 0,
            total_amount: Number(it.total_amount) || 0
          })));
        }

        if (data.is_duplicate) {
          setDuplicateWarning(data.duplicate_reason || 'Duplicate invoice detected in your ledger.');
        } else {
          setDuplicateWarning(null);
        }
      } else {
        alert(data.detail || 'Failed to scan invoice.');
      }
    } catch (err: any) {
      alert(err.message || 'Error uploading invoice');
    } finally {
      setScanning(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateDateWithFY(invoiceDate, activeFY)) {
      return;
    }

    if (duplicateWarning && !confirmDuplicate) {
      alert('Please confirm duplicate override or change the invoice number.');
      return;
    }

    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = typeof window !== 'undefined' ? localStorage.getItem('b00k5_tenant_id') : null;

      let targetContactId = contactId;
      if (!targetContactId) {
        const conRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/invoices/contacts?is_customer=true`, {
          headers: {
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
          }
        });
        const contacts = await conRes.json();
        if (Array.isArray(contacts) && contacts.length > 0) {
          targetContactId = contacts[0].id;
        } else {
          const newConRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/invoices/contacts`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
              ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
            },
            body: JSON.stringify({
              name: customerName,
              is_customer: true,
              gstin: customerGstin,
              state_code: placeOfSupply
            })
          });
          const newCon = await newConRes.json();
          targetContactId = newCon.id;
        }
      }

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/invoices/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
        },
        body: JSON.stringify({
          contact_id: targetContactId,
          invoice_number: invoiceNumber,
          place_of_supply: placeOfSupply,
          issue_date: invoiceDate,
          due_date: new Date(new Date(invoiceDate).getTime() + 15 * 86400000).toISOString().split('T')[0],
          items: lineItems.map(it => ({
            item_description: it.description,
            hsn_sac_code: it.hsn_sac,
            quantity: it.quantity,
            unit_price: it.unit_price,
            gst_rate_percent: it.gst_rate
          }))
        })
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to issue invoice');
      }

      setSuccessMsg('Invoice generated and posted to General Ledger atomically!');
      if (typeof window !== 'undefined') {
        localStorage.removeItem('b00k5_pending_invoice_item');
      }
      setTimeout(() => {
        router.push('/invoices');
      }, 1200);
    } catch (err: any) {
      alert(err.message || 'Error submitting invoice');
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Navbar />
        <main className="flex-1 overflow-y-auto p-8 max-w-5xl mx-auto w-full space-y-6">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div className="flex items-center gap-3">
          <Link href="/invoices" className="p-2 rounded-lg bg-slate-800 text-slate-400 hover:text-white transition">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <FilePlus className="w-5 h-5 text-sky-400" />
              Generate Tax Invoice
            </h1>
            <p className="text-xs text-slate-400">
              Active Financial Period: <span className="font-mono text-amber-300 font-bold">FY {activeFY}</span>
            </p>
          </div>
        </div>

        <div className="text-xs px-3 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700">
          State: <span className="font-mono text-sky-400">29 - Karnataka</span>
        </div>
      </div>

      {dateError && (
        <div id="invoice-date-error" className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 flex items-center gap-3 text-sm">
          <AlertTriangle className="w-5 h-5 shrink-0" />
          <span>{dateError}</span>
        </div>
      )}

      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center gap-3 text-sm">
          <CheckCircle2 className="w-5 h-5 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Upload Invoice Card with SmartScan & Deduplication */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <UploadCloud className="w-4 h-4 text-sky-400" />
              Upload &amp; Scan Existing or Razorpay Invoice (SmartScan OCR)
            </h3>
            <p className="text-xs text-slate-400">
              Upload Razorpay or customer invoices (PDF, image, CSV, or JSON) to auto-extract line items, customer GSTIN, and sync with your ledger.
            </p>
          </div>
        </div>

        <div className="border border-dashed border-slate-700/80 rounded-xl p-4 bg-slate-950/60 flex flex-col items-center justify-center text-center">
          <UploadCloud className="w-8 h-8 text-sky-400 mb-2" />
          <input
            type="file"
            id="invoice-file-upload"
            accept=".pdf,.png,.jpg,.jpeg,.csv,.json"
            onChange={handleInvoiceUpload}
            disabled={scanning}
            className="text-xs text-slate-400 file:mr-4 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:bg-sky-600 file:text-white hover:file:bg-sky-500 cursor-pointer disabled:opacity-50"
          />
          {scanning && (
            <span className="text-xs text-sky-400 font-mono mt-2 animate-pulse flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-sky-400 animate-ping" />
              Extracting invoice line items &amp; checking ledger for duplicates...
            </span>
          )}
          {uploadedFileName && !scanning && (
            <span className="text-xs text-emerald-300 font-mono mt-2">
              Parsed File: {uploadedFileName}
            </span>
          )}
        </div>

        {duplicateWarning && (
          <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs space-y-2">
            <div className="flex items-center gap-2 font-semibold">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
              <span>{duplicateWarning}</span>
            </div>
            <label className="flex items-center gap-2 cursor-pointer pt-1 text-slate-300">
              <input
                type="checkbox"
                checked={confirmDuplicate}
                onChange={(e) => setConfirmDuplicate(e.target.checked)}
                className="rounded border-slate-700 bg-slate-900 text-amber-500 focus:ring-0"
              />
              <span>I confirm this is not an accidental duplicate and wish to proceed anyway.</span>
            </label>
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Invoice Metadata */}
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Customer / Recipient</label>
            <input
              type="text"
              id="customer-name-input"
              value={customerName}
              onChange={(e) => setCustomerName(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none"
              placeholder="Customer Name"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Invoice Number</label>
            <input
              type="text"
              id="invoice-number-input"
              value={invoiceNumber}
              onChange={(e) => setInvoiceNumber(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono text-sm focus:outline-none"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Invoice Date</label>
            <input
              type="date"
              id="invoice-date-input"
              value={invoiceDate}
              onChange={(e) => handleDateChange(e.target.value)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono text-sm focus:outline-none"
              required
            />
          </div>
        </div>

        {/* Line Items Table */}
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold text-white">Invoice Items & HSN/SAC Decomposition</h3>
            <span className="text-xs text-sky-400 font-mono">1 Item Attached</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950 text-slate-400 font-mono uppercase text-[11px] border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Description</th>
                  <th className="py-2.5 px-3">HSN/SAC</th>
                  <th className="py-2.5 px-3">Taxable Price (₹)</th>
                  <th className="py-2.5 px-3">GST %</th>
                  <th className="py-2.5 px-3">Tax (₹)</th>
                  <th className="py-2.5 px-3 text-right">Total (₹)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {lineItems.map((item, idx) => (
                  <tr key={item.id} className="hover:bg-slate-800/30">
                    <td className="py-3 px-3 font-sans font-medium text-white">{item.description}</td>
                    <td className="py-3 px-3 text-slate-400">{item.hsn_sac}</td>
                    <td className="py-3 px-3 text-slate-100 font-bold" id="item-unit-price">
                      ₹{item.unit_price.toFixed(2)}
                    </td>
                    <td className="py-3 px-3 text-amber-300 font-bold" id="item-gst-rate">
                      {item.gst_rate}%
                    </td>
                    <td className="py-3 px-3 text-slate-300">
                      ₹{(item.cgst_amount + item.sgst_amount + item.igst_amount).toFixed(2)}
                    </td>
                    <td className="py-3 px-3 text-right font-bold text-emerald-400">
                      ₹{item.total_amount.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Totals Summary */}
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 flex justify-end">
          <div className="w-80 space-y-2 text-xs font-mono">
            <div className="flex justify-between text-slate-400">
              <span>Subtotal (Taxable Base):</span>
              <span className="text-white">₹{calculateSubtotal().toFixed(2)}</span>
            </div>
            {calculateCgst() > 0 && (
              <>
                <div className="flex justify-between text-slate-400">
                  <span>CGST (9%):</span>
                  <span className="text-amber-400">₹{calculateCgst().toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>SGST (9%):</span>
                  <span className="text-amber-400">₹{calculateSgst().toFixed(2)}</span>
                </div>
              </>
            )}
            {calculateIgst() > 0 && (
              <div className="flex justify-between text-slate-400">
                <span>IGST (18%):</span>
                <span className="text-amber-400">₹{calculateIgst().toFixed(2)}</span>
              </div>
            )}
            <div className="flex justify-between text-base font-bold text-emerald-400 border-t border-slate-800 pt-2">
              <span>Grand Total:</span>
              <span id="grand-total-display">₹{calculateGrandTotal().toFixed(2)}</span>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <button
            type="submit"
            id="save-invoice-btn"
            className="px-6 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 font-semibold text-white text-sm shadow-lg shadow-sky-600/30 transition"
          >
            Post and Issue Tax Invoice
          </button>
        </div>
      </form>
        </main>
      </div>
    </div>
  );
}

export default function NewInvoicePage() {
  return (
    <Suspense fallback={<div className="p-8 text-white">Loading invoice form...</div>}>
      <NewInvoiceInner />
    </Suspense>
  );
}
