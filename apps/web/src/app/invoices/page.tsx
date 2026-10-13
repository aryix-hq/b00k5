'use client';

import React, { useEffect, useState, useRef } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import { Plus, Receipt, FileText, CheckCircle, UploadCloud, Loader2, RefreshCw, Sparkles, FileCheck } from 'lucide-react';
import { fetchApi } from '@/lib/api';

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<any[]>([]);
  const [contacts, setContacts] = useState<any[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [showRazorpayModal, setShowRazorpayModal] = useState(false);
  const [showContactModal, setShowContactModal] = useState(false);
  const [loading, setLoading] = useState(true);

  // New Customer Contact Modal state
  const [newContactName, setNewContactName] = useState('');
  const [newContactGstin, setNewContactGstin] = useState('');
  const [newContactState, setNewContactState] = useState('29');
  const [newContactAddress, setNewContactAddress] = useState('');

  // Standard New Invoice Form states
  const [contactId, setContactId] = useState('');
  const [invoiceNumber, setInvoiceNumber] = useState('INV-2026-001');
  const [placeOfSupply, setPlaceOfSupply] = useState('29'); // Karnataka
  const [itemDesc, setItemDesc] = useState('Software Design & Architecture Consulting');
  const [hsnCode, setHsnCode] = useState('998314');
  const [quantity, setQuantity] = useState('1');
  const [unitPrice, setUnitPrice] = useState('150000');
  const [gstRate, setGstRate] = useState('18.00');

  // Razorpay Import Modal states
  const rzpFileInputRef = useRef<HTMLInputElement>(null);
  const [rzpParsing, setRzpParsing] = useState(false);
  const [rzpImporting, setRzpImporting] = useState(false);
  const [rzpUploadedFile, setRzpUploadedFile] = useState<string | null>(null);
  const [rzpBatchItems, setRzpBatchItems] = useState<any[]>([]);
  const [rzpInvoiceNum, setRzpInvoiceNum] = useState('');
  const [rzpInvoiceId, setRzpInvoiceId] = useState('');
  const [rzpPaymentId, setRzpPaymentId] = useState('');
  const [rzpIssueDate, setRzpIssueDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [rzpCustomerName, setRzpCustomerName] = useState('');
  const [rzpCustomerGstin, setRzpCustomerGstin] = useState('');
  const [rzpCustomerEmail, setRzpCustomerEmail] = useState('');
  const [rzpPos, setRzpPos] = useState('29');
  const [rzpItemDesc, setRzpItemDesc] = useState('Software / SaaS Subscription (Razorpay)');
  const [rzpHsn, setRzpHsn] = useState('998314');
  const [rzpQty, setRzpQty] = useState('1');
  const [rzpUnitPrice, setRzpUnitPrice] = useState('');
  const [rzpGstRate, setRzpGstRate] = useState('0.00');
  const [rzpPaymentStatus, setRzpPaymentStatus] = useState<'paid' | 'sent'>('paid');
  const [rzpGatewayFee, setRzpGatewayFee] = useState('0');
  const [rzpPdfS3Key, setRzpPdfS3Key] = useState<string | null>(null);
  const [rzpBanner, setRzpBanner] = useState<string | null>(null);

  const operatingState = '29'; // Default Karnataka
  const isInterstate = placeOfSupply !== operatingState;
  const taxable = parseFloat(quantity || '0') * parseFloat(unitPrice || '0');
  const rate = parseFloat(gstRate || '0');
  const taxAmount = (taxable * rate) / 100;
  const grandTotal = taxable + taxAmount;

  const rzpIsInterstate = rzpPos !== operatingState;
  const rzpTaxable = parseFloat(rzpQty || '0') * parseFloat(rzpUnitPrice || '0');
  const rzpRateVal = parseFloat(rzpGstRate || '0');
  const rzpTaxAmt = (rzpTaxable * rzpRateVal) / 100;
  const rzpGrandTotal = rzpTaxable + rzpTaxAmt;

  async function loadData() {
    try {
      const invRes = await fetchApi('/api/v1/invoices/');
      setInvoices(invRes);
      const conRes = await fetchApi('/api/v1/invoices/contacts?is_customer=true');
      setContacts(conRes);
      if (conRes.length > 0 && !contactId) {
        setContactId(conRes[0].id);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  const handleDirectInvoicePdfUpload = async (invoiceId: string, file?: File | null) => {
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = typeof window !== 'undefined' ? localStorage.getItem('b00k5_tenant_id') : null;
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/invoices/${invoiceId}/pdf`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
        },
        body: fd
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to upload invoice PDF');
      }
      setRzpBanner(`Original tax invoice PDF "${file.name}" attached successfully!`);
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Error attaching invoice PDF');
    }
  };

  const handleCreateContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newContactName.trim()) return;
    try {
      const c = await fetchApi('/api/v1/invoices/contacts', {
        method: 'POST',
        body: JSON.stringify({
          name: newContactName.trim(),
          is_customer: true,
          gstin: newContactGstin.trim() ? newContactGstin.trim().toUpperCase() : null,
          state_code: newContactState.trim() || '29',
          billing_address: newContactAddress.trim() || 'Registered Commercial Address',
        }),
      });
      await loadData();
      setContactId(c.id);
      setShowContactModal(false);
      setNewContactName('');
      setNewContactGstin('');
      setNewContactAddress('');
    } catch (e: any) {
      alert(e.message || 'Failed to add customer');
    }
  };

  const handleCreateInvoice = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await fetchApi('/api/v1/invoices/', {
        method: 'POST',
        body: JSON.stringify({
          contact_id: contactId,
          invoice_number: invoiceNumber,
          place_of_supply: placeOfSupply,
          due_date: new Date(Date.now() + 15 * 86400000).toISOString().split('T')[0],
          items: [
            {
              item_description: itemDesc,
              hsn_sac_code: hsnCode,
              quantity: parseFloat(quantity),
              unit_price: parseFloat(unitPrice),
              gst_rate_percent: parseFloat(gstRate),
            },
          ],
        }),
      });
      setShowModal(false);
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Failed to create invoice');
    }
  };

  const handleRazorpayFileParse = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setRzpParsing(true);
    setRzpUploadedFile(file.name);
    setRzpBanner(null);

    const fd = new FormData();
    fd.append('file', file);

    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = typeof window !== 'undefined' ? localStorage.getItem('b00k5_tenant_id') : null;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/invoices/razorpay/parse`, {
        method: 'POST',
        headers,
        body: fd
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail?.message || data.detail || 'Failed to parse Razorpay file');
      }

      const parsedList = Array.isArray(data.invoices) ? data.invoices : [];
      setRzpBatchItems(parsedList);
      if (data.pdf_s3_key) setRzpPdfS3Key(data.pdf_s3_key);

      if (parsedList.length > 0) {
        const first = parsedList[0];
        if (first.pdf_s3_key) setRzpPdfS3Key(first.pdf_s3_key);
        setRzpInvoiceNum(first.invoice_number || '');
        setRzpInvoiceId(first.razorpay_invoice_id || '');
        setRzpPaymentId(first.razorpay_payment_id || '');
        if (first.issue_date) setRzpIssueDate(first.issue_date);
        setRzpCustomerName(first.customer_name || '');
        setRzpCustomerGstin(first.customer_gstin || '');
        setRzpCustomerEmail(first.customer_email || '');
        setRzpPos(first.place_of_supply || '29');
        setRzpPaymentStatus(first.payment_status === 'sent' ? 'sent' : 'paid');

        const firstItem = Array.isArray(first.items) && first.items.length > 0 ? first.items[0] : null;
        if (firstItem) {
          setRzpItemDesc(firstItem.item_description || `Razorpay Invoice ${first.invoice_number}`);
          setRzpHsn(firstItem.hsn_sac_code || '998314');
          setRzpQty(String(firstItem.quantity || 1));
          setRzpUnitPrice(String(firstItem.unit_price || 0));
          setRzpGstRate(String(Number(firstItem.gst_rate_percent ?? 0).toFixed(2)));
        }
      }
    } catch (err: any) {
      alert(err.message || 'Error parsing Razorpay invoice file');
    } finally {
      setRzpParsing(false);
    }
  };

  const handleRazorpayImportSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setRzpImporting(true);
    setRzpBanner(null);

    try {
      const parsedGstRate = parseFloat(rzpGstRate);
      // If a multi-invoice CSV/JSON batch was uploaded (>1 row), import the batch; otherwise import the form fields
      const invoicesPayload = rzpBatchItems.length > 1
        ? rzpBatchItems.filter(it => !it.is_duplicate)
        : [
            {
              invoice_number: rzpInvoiceNum.trim(),
              razorpay_invoice_id: rzpInvoiceId.trim() || null,
              razorpay_payment_id: rzpPaymentId.trim() || null,
              issue_date: rzpIssueDate,
              customer_name: rzpCustomerName.trim() || 'Razorpay Customer',
              customer_gstin: rzpCustomerGstin.trim() ? rzpCustomerGstin.trim().toUpperCase() : null,
              customer_email: rzpCustomerEmail.trim() || null,
              place_of_supply: rzpPos.trim() || '29',
              payment_status: rzpPaymentStatus,
              gateway_fee: parseFloat(rzpGatewayFee || '0') || 0,
              pdf_s3_key: rzpPdfS3Key || null,
              items: [
                {
                  item_description: rzpItemDesc.trim() || `Razorpay Invoice ${rzpInvoiceNum}`,
                  hsn_sac_code: rzpHsn.trim() || '998314',
                  quantity: parseFloat(rzpQty || '1') || 1,
                  unit_price: parseFloat(rzpUnitPrice || '0') || 0,
                  gst_rate_percent: Number.isNaN(parsedGstRate) ? 0 : parsedGstRate,
                },
              ],
            },
          ];

      const res = await fetchApi('/api/v1/invoices/razorpay/import', {
        method: 'POST',
        body: JSON.stringify({ invoices: invoicesPayload }),
      });

      const impCount = res.imported_count || 0;
      const skipCount = res.skipped_count || 0;
      await loadData();

      if (impCount > 0) {
        const firstImp = res.imported?.[0];
        setRzpBanner(
          `Synced ${impCount} Razorpay invoice(s) to Ledger (${firstImp?.invoice_journal_number}${
            firstImp?.settlement_journal_number ? ` & ${firstImp.settlement_journal_number}` : ''
          } -> FY ${firstImp?.assigned_fy}).`
        );
        setShowRazorpayModal(false);
        setRzpBatchItems([]);
        setRzpUploadedFile(null);
        setRzpPdfS3Key(null);
      } else if (skipCount > 0) {
        setShowRazorpayModal(false);
        setRzpBatchItems([]);
        setRzpUploadedFile(null);
        setRzpPdfS3Key(null);
        setRzpBanner(`Original invoice PDF attached to existing ledger Invoice ${rzpInvoiceNum}.`);
      }
    } catch (err: any) {
      alert(err.message || 'Failed to import Razorpay invoice');
    } finally {
      setRzpImporting(false);
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Navbar />

        <main className="p-8 space-y-6 max-w-7xl mx-auto w-full">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Receipt className="w-6 h-6 text-sky-400" />
                Invoices & Accounts Receivable (AR)
              </h2>
              <p className="text-xs text-slate-400">
                Indian GST Engine with automatic double-entry journal postings, HSN codes & Razorpay Sync
              </p>
            </div>

            <div className="flex items-center gap-3 flex-wrap">
              <button
                onClick={() => setShowContactModal(true)}
                className="px-3 py-2 border border-slate-800 hover:border-slate-700 bg-slate-900 text-xs rounded-lg text-slate-300"
              >
                + Add Customer
              </button>
              <button
                onClick={() => {
                  setRzpBanner(null);
                  setShowRazorpayModal(true);
                }}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 shadow-sm"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Import Razorpay Invoice
              </button>
              <button
                onClick={() => setShowModal(true)}
                className="px-4 py-2 bg-sky-500 hover:bg-sky-600 text-white text-xs font-semibold rounded-lg flex items-center gap-2"
              >
                <Plus className="w-4 h-4" /> New Tax Invoice
              </button>
            </div>
          </div>

          {rzpBanner && (
            <div className="p-3.5 bg-emerald-950/40 border border-emerald-500/40 rounded-xl flex items-center justify-between text-xs text-emerald-200">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{rzpBanner}</span>
              </div>
              <button onClick={() => setRzpBanner(null)} className="text-emerald-400 hover:text-white">✕</button>
            </div>
          )}

          {/* Invoice List Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/60 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-mono">
                <tr>
                  <th className="py-3.5 px-4">Invoice #</th>
                  <th className="py-3.5 px-4">Issue Date</th>
                  <th className="py-3.5 px-4">Place of Supply (POS)</th>
                  <th className="py-3.5 px-4">GST Mode</th>
                  <th className="py-3.5 px-4">Subtotal</th>
                  <th className="py-3.5 px-4">Tax Total</th>
                  <th className="py-3.5 px-4">Grand Total</th>
                  <th className="py-3.5 px-4">Status</th>
                  <th className="py-3.5 px-4 text-right">Original PDF</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {invoices.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-8 text-center text-slate-500">
                      No invoices issued yet. Click &quot;Import Razorpay Invoice&quot; or &quot;New Tax Invoice&quot; to synchronize your billing.
                    </td>
                  </tr>
                ) : (
                  invoices.map((inv) => (
                    <tr key={inv.id} className="hover:bg-slate-800/30">
                      <td className="py-3.5 px-4 font-mono font-medium text-white">{inv.invoice_number}</td>
                      <td className="py-3.5 px-4 text-slate-400">{inv.issue_date}</td>
                      <td className="py-3.5 px-4 font-mono">State {inv.place_of_supply}</td>
                      <td className="py-3.5 px-4">
                        {(parseFloat(inv.cgst_total || '0') + parseFloat(inv.sgst_total || '0') + parseFloat(inv.igst_total || '0')) === 0 ? (
                          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 text-[10px] font-mono">
                            0% GST (Non-GST)
                          </span>
                        ) : inv.is_interstate ? (
                          <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20 text-[10px] font-mono">
                            Interstate (IGST)
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 text-[10px] font-mono">
                            Intrastate (CGST+SGST)
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 font-mono">₹{parseFloat(inv.subtotal).toLocaleString('en-IN')}</td>
                      <td className="py-3.5 px-4 font-mono text-slate-400">
                        ₹{(parseFloat(inv.cgst_total) + parseFloat(inv.sgst_total) + parseFloat(inv.igst_total)).toLocaleString('en-IN')}
                      </td>
                      <td className="py-3.5 px-4 font-mono font-semibold text-emerald-400">
                        ₹{parseFloat(inv.grand_total).toLocaleString('en-IN')}
                      </td>
                      <td className="py-3.5 px-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] uppercase font-mono border ${
                          inv.status === 'paid'
                            ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                            : 'bg-sky-500/10 text-sky-400 border-sky-500/20'
                        }`}>
                          {inv.status}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        {inv.pdf_s3_key ? (
                          <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-[10px] font-mono inline-flex items-center gap-1">
                            <FileCheck className="w-3 h-3" /> Attached
                          </span>
                        ) : (
                          <label className="cursor-pointer px-2.5 py-1 rounded bg-indigo-950 text-indigo-300 border border-indigo-700 hover:bg-indigo-900 text-[10px] font-semibold inline-flex items-center gap-1 transition">
                            <UploadCloud className="w-3 h-3" /> Attach PDF
                            <input
                              type="file"
                              accept=".pdf,.png,.jpg,.jpeg"
                              className="hidden"
                              onChange={(e) => handleDirectInvoicePdfUpload(inv.id, e.target.files?.[0])}
                            />
                          </label>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </main>
      </div>

      {/* Add Customer Modal */}
      {showContactModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-white text-base">Add Customer Contact</h3>
              <button onClick={() => setShowContactModal(false)} className="text-slate-400 hover:text-white text-sm">✕</button>
            </div>
            <form onSubmit={handleCreateContact} className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Customer Legal / Trade Name *</label>
                <input
                  type="text"
                  value={newContactName}
                  onChange={(e) => setNewContactName(e.target.value)}
                  placeholder="e.g. Acme Technologies Pvt Ltd"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Customer GSTIN (Optional)</label>
                  <input
                    type="text"
                    value={newContactGstin}
                    onChange={(e) => {
                      const val = e.target.value.toUpperCase();
                      setNewContactGstin(val);
                      if (val.length >= 2 && /^\d{2}$/.test(val.slice(0, 2))) {
                        setNewContactState(val.slice(0, 2));
                      }
                    }}
                    placeholder="29AAAAA0000A1Z5"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono uppercase"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">State Code (POS)</label>
                  <input
                    type="text"
                    value={newContactState}
                    onChange={(e) => setNewContactState(e.target.value)}
                    placeholder="29"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Billing Address</label>
                <input
                  type="text"
                  value={newContactAddress}
                  onChange={(e) => setNewContactAddress(e.target.value)}
                  placeholder="Registered billing address"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200"
                />
              </div>
              <div className="pt-2 flex justify-end gap-2">
                <button type="button" onClick={() => setShowContactModal(false)} className="px-4 py-2 border border-slate-700 text-slate-300 rounded-lg">
                  Cancel
                </button>
                <button type="submit" className="px-4 py-2 bg-sky-500 hover:bg-sky-600 text-white font-semibold rounded-lg">
                  Save Customer
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Import Razorpay Invoice Modal */}
      {showRazorpayModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl p-6 shadow-2xl space-y-4 my-8">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="font-bold text-white text-base flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-indigo-400" />
                  Import & Sync Razorpay Invoice
                </h3>
                <p className="text-[11px] text-slate-400">
                  Upload a Razorpay Invoice PDF, Image, or CSV/JSON export — or enter details directly to sync with General Ledger & GST.
                </p>
              </div>
              <button onClick={() => setShowRazorpayModal(false)} className="text-slate-400 hover:text-white text-sm">
                ✕
              </button>
            </div>

            {/* File Dropzone for Razorpay PDF / CSV / JSON */}
            <div
              onClick={() => rzpFileInputRef.current?.click()}
              className="border-2 border-dashed border-indigo-500/40 hover:border-indigo-400 bg-indigo-950/15 rounded-xl p-4 text-center cursor-pointer transition"
            >
              <input
                ref={rzpFileInputRef}
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,.csv,.json"
                onChange={handleRazorpayFileParse}
                className="hidden"
              />
              <div className="flex flex-col items-center gap-1.5">
                {rzpParsing ? (
                  <Loader2 className="w-6 h-6 text-indigo-400 animate-spin" />
                ) : (
                  <UploadCloud className="w-6 h-6 text-indigo-400" />
                )}
                <div className="text-xs font-semibold text-slate-200">
                  {rzpParsing
                    ? 'Extracting Razorpay Invoice Details...'
                    : rzpUploadedFile
                      ? `Loaded: ${rzpUploadedFile} (${rzpBatchItems.length} invoice${rzpBatchItems.length === 1 ? '' : 's'} detected)`
                      : 'Click to upload Razorpay Invoice PDF / Image or Razorpay Invoices CSV / JSON Export'}
                </div>
                <div className="text-[10px] text-slate-400 font-mono">
                  Auto-extracts Invoice #, Razorpay Payment ID (pay_...), Customer GSTIN, Line Items & Tax Breakdown
                </div>
              </div>
            </div>

            <form onSubmit={handleRazorpayImportSubmit} className="space-y-4 text-xs">
              {rzpBatchItems.length > 1 ? (
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-2 max-h-56 overflow-y-auto">
                  <div className="font-semibold text-indigo-300">
                    Batch Export Detected: {rzpBatchItems.length} Razorpay Invoices
                  </div>
                  <table className="w-full text-left text-[11px]">
                    <thead className="text-slate-400 border-b border-slate-800 font-mono">
                      <tr>
                        <th className="py-1">Invoice #</th>
                        <th className="py-1">Date</th>
                        <th className="py-1">Customer</th>
                        <th className="py-1">Taxable</th>
                        <th className="py-1">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/50">
                      {rzpBatchItems.map((b, i) => (
                        <tr key={i}>
                          <td className="py-1.5 font-mono text-white">{b.invoice_number}</td>
                          <td className="py-1.5 text-slate-400">{b.issue_date}</td>
                          <td className="py-1.5 text-slate-200">{b.customer_name}</td>
                          <td className="py-1.5 font-mono">₹{Number(b.items?.[0]?.unit_price || 0).toLocaleString('en-IN')}</td>
                          <td className="py-1.5 font-mono uppercase">
                            {b.is_duplicate ? (
                              <span className="text-amber-400">Duplicate (Skip)</span>
                            ) : (
                              <span className="text-emerald-400">{b.payment_status}</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="block text-slate-400 mb-1">Invoice / Receipt # *</label>
                      <input
                        type="text"
                        value={rzpInvoiceNum}
                        onChange={(e) => setRzpInvoiceNum(e.target.value)}
                        placeholder="e.g. INV-2026-001 or inv_..."
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">Invoice Date *</label>
                      <input
                        type="date"
                        value={rzpIssueDate}
                        onChange={(e) => setRzpIssueDate(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">Razorpay Payment ID</label>
                      <input
                        type="text"
                        value={rzpPaymentId}
                        onChange={(e) => setRzpPaymentId(e.target.value)}
                        placeholder="pay_Optional..."
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="block text-slate-400 mb-1">Customer Name *</label>
                      <input
                        type="text"
                        value={rzpCustomerName}
                        onChange={(e) => setRzpCustomerName(e.target.value)}
                        placeholder="Billed To Customer Name"
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">Customer GSTIN (Optional)</label>
                      <input
                        type="text"
                        value={rzpCustomerGstin}
                        onChange={(e) => {
                          const val = e.target.value.toUpperCase();
                          setRzpCustomerGstin(val);
                          if (val.length >= 2 && /^\d{2}$/.test(val.slice(0, 2))) {
                            setRzpPos(val.slice(0, 2));
                          }
                        }}
                        placeholder="29AAAAA0000A1Z5"
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono uppercase"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">Place of Supply (State Code)</label>
                      <input
                        type="text"
                        value={rzpPos}
                        onChange={(e) => setRzpPos(e.target.value)}
                        placeholder="29 (Karnataka)"
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                        required
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    <div className="col-span-2">
                      <label className="block text-slate-400 mb-1">Line Item / Service Description *</label>
                      <input
                        type="text"
                        value={rzpItemDesc}
                        onChange={(e) => setRzpItemDesc(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">SAC / HSN Code</label>
                      <input
                        type="text"
                        value={rzpHsn}
                        onChange={(e) => setRzpHsn(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                        required
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-4 gap-3">
                    <div>
                      <label className="block text-slate-400 mb-1">Taxable Amount (₹) *</label>
                      <input
                        type="number"
                        step="0.01"
                        value={rzpUnitPrice}
                        onChange={(e) => setRzpUnitPrice(e.target.value)}
                        placeholder="e.g. 50000"
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                        required
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">GST Rate %</label>
                      <select
                        value={rzpGstRate}
                        onChange={(e) => setRzpGstRate(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200"
                      >
                        <option value="18.00">18% GST</option>
                        <option value="12.00">12% GST</option>
                        <option value="5.00">5% GST</option>
                        <option value="0.00">0% (Exempt / Export)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">Razorpay Status</label>
                      <select
                        value={rzpPaymentStatus}
                        onChange={(e) => setRzpPaymentStatus(e.target.value as 'paid' | 'sent')}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200"
                      >
                        <option value="paid">Paid (Sync Bank + AR)</option>
                        <option value="sent">Issued / Unpaid (AR Only)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1">Gateway Fee (₹ Optional)</label>
                      <input
                        type="number"
                        step="0.01"
                        value={rzpGatewayFee}
                        onChange={(e) => setRzpGatewayFee(e.target.value)}
                        placeholder="0.00"
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                      />
                    </div>
                  </div>

                  {/* Preview of Ledger Sync */}
                  <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-1.5">
                    <div className="flex justify-between text-slate-400">
                      <span>Taxable Value (CR 3010 Operating Revenue):</span>
                      <span className="font-mono text-white">₹{rzpTaxable.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div className="flex justify-between text-slate-400">
                      <span>
                        GST ({rzpIsInterstate ? `IGST ${rzpRateVal}%` : `CGST ${rzpRateVal / 2}% + SGST ${rzpRateVal / 2}%`}):
                      </span>
                      <span className="font-mono text-white">₹{rzpTaxAmt.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div className="border-t border-slate-800 pt-1 flex justify-between font-semibold text-emerald-400">
                      <span>
                        Grand Total ({rzpPaymentStatus === 'paid' ? 'Auto-Settled to 1010 Bank' : 'Booked to 1020 Trade Receivables'}):
                      </span>
                      <span className="font-mono">₹{rzpGrandTotal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                    </div>
                  </div>
                </>
              )}

              <div className="pt-2 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowRazorpayModal(false)}
                  className="px-4 py-2 border border-slate-700 text-slate-300 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={rzpImporting}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg flex items-center gap-2 disabled:opacity-50"
                >
                  {rzpImporting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  {rzpImporting ? 'Syncing to Ledger...' : 'Import & Sync to General Ledger'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* New Invoice Modal */}
      {showModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-bold text-white text-base">Issue GST Tax Invoice</h3>
              <button onClick={() => setShowModal(false)} className="text-slate-400 hover:text-white text-sm">
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateInvoice} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-slate-400 mb-1">Customer / Billed To</label>
                  <select
                    value={contactId}
                    onChange={(e) => setContactId(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200"
                    required
                  >
                    <option value="">Select customer...</option>
                    {contacts.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.gstin || 'Unregistered'})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Invoice Number</label>
                  <input
                    type="text"
                    value={invoiceNumber}
                    onChange={(e) => setInvoiceNumber(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-slate-400 mb-1">Place of Supply (POS State Code)</label>
                  <input
                    type="text"
                    value={placeOfSupply}
                    onChange={(e) => setPlaceOfSupply(e.target.value)}
                    placeholder="e.g. 07 (Delhi) or 29 (Karnataka)"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                    required
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">SAC / HSN Code</label>
                  <input
                    type="text"
                    value={hsnCode}
                    onChange={(e) => setHsnCode(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Service / Item Description</label>
                <input
                  type="text"
                  value={itemDesc}
                  onChange={(e) => setItemDesc(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200"
                  required
                />
              </div>

              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-slate-400 mb-1">Quantity</label>
                  <input
                    type="number"
                    value={quantity}
                    onChange={(e) => setQuantity(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Unit Price (INR)</label>
                  <input
                    type="number"
                    value={unitPrice}
                    onChange={(e) => setUnitPrice(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">GST Rate %</label>
                  <select
                    value={gstRate}
                    onChange={(e) => setGstRate(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200"
                  >
                    <option value="18.00">18% (Standard Services)</option>
                    <option value="12.00">12%</option>
                    <option value="5.00">5%</option>
                    <option value="0.00">0% (Exempt)</option>
                  </select>
                </div>
              </div>

              {/* Dynamic Tax & Double-Entry Preview */}
              <div className="p-3 bg-slate-950 rounded-xl border border-slate-800 space-y-2">
                <div className="flex justify-between text-slate-400">
                  <span>Taxable Value:</span>
                  <span className="font-mono text-white">₹{taxable.toLocaleString('en-IN')}</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>
                    GST Applicable ({isInterstate ? 'Inter-state IGST 18%' : 'Intra-state CGST 9% + SGST 9%'}):
                  </span>
                  <span className="font-mono text-white">₹{taxAmount.toLocaleString('en-IN')}</span>
                </div>
                <div className="border-t border-slate-800 pt-1 flex justify-between font-semibold text-emerald-400">
                  <span>Invoice Grand Total:</span>
                  <span className="font-mono">₹{grandTotal.toLocaleString('en-IN')}</span>
                </div>
              </div>

              <div className="pt-2 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2 border border-slate-700 text-slate-300 rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-5 py-2 bg-sky-500 hover:bg-sky-600 text-white font-semibold rounded-lg"
                >
                  Issue Invoice & Post Journal
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

