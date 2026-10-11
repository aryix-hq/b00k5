'use client';

import React, { useEffect, useState } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import { Plus, Receipt, FileText, CheckCircle, ArrowRight, ArrowDownLeft, ArrowUpRight } from 'lucide-react';
import { fetchApi } from '@/lib/api';

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<any[]>([]);
  const [contacts, setContacts] = useState<any[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(true);

  // Form states
  const [contactId, setContactId] = useState('');
  const [invoiceNumber, setInvoiceNumber] = useState('INV-2026-001');
  const [placeOfSupply, setPlaceOfSupply] = useState('29'); // Karnataka
  const [itemDesc, setItemDesc] = useState('Software Design & Architecture Consulting');
  const [hsnCode, setHsnCode] = useState('998314');
  const [quantity, setQuantity] = useState('1');
  const [unitPrice, setUnitPrice] = useState('150000');
  const [gstRate, setGstRate] = useState('18.00');

  const operatingState = '29'; // Default Karnataka
  const isInterstate = placeOfSupply !== operatingState;
  const taxable = parseFloat(quantity || '0') * parseFloat(unitPrice || '0');
  const rate = parseFloat(gstRate || '0');
  const taxAmount = (taxable * rate) / 100;
  const grandTotal = taxable + taxAmount;

  async function loadData() {
    try {
      const invRes = await fetchApi('/api/v1/invoices/');
      setInvoices(invRes);
      const conRes = await fetchApi('/api/v1/invoices/contacts?is_customer=true');
      setContacts(conRes);
      if (conRes.length > 0) {
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

  const handleCreateContact = async () => {
    try {
      const c = await fetchApi('/api/v1/invoices/contacts', {
        method: 'POST',
        body: JSON.stringify({
          name: 'Zomato Media Pvt Ltd',
          is_customer: true,
          gstin: '07AABCA9876F1Z2',
          state_code: '07', // Delhi
          billing_address: 'Ground Floor, 12A, DLF Cyber City, Gurugram, Haryana',
        }),
      });
      await loadData();
      setContactId(c.id);
    } catch (e) {
      console.error(e);
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

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Navbar />

        <main className="p-8 space-y-6 max-w-7xl mx-auto w-full">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Receipt className="w-6 h-6 text-sky-400" />
                Invoices & Accounts Receivable (AR)
              </h2>
              <p className="text-xs text-slate-400">
                Indian GST Engine with automatic double-entry journal postings & HSN codes
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleCreateContact}
                className="px-3 py-2 border border-slate-800 hover:border-slate-700 bg-slate-900 text-xs rounded-lg text-slate-300"
              >
                + Quick Add Customer
              </button>
              <button
                onClick={() => setShowModal(true)}
                className="px-4 py-2 bg-sky-500 hover:bg-sky-600 text-white text-xs font-semibold rounded-lg flex items-center gap-2"
              >
                <Plus className="w-4 h-4" /> New Tax Invoice
              </button>
            </div>
          </div>

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
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {invoices.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-8 text-center text-slate-500">
                      No invoices issued yet. Click &quot;New Tax Invoice&quot; to issue your first GST invoice.
                    </td>
                  </tr>
                ) : (
                  invoices.map((inv) => (
                    <tr key={inv.id} className="hover:bg-slate-800/30">
                      <td className="py-3.5 px-4 font-mono font-medium text-white">{inv.invoice_number}</td>
                      <td className="py-3.5 px-4 text-slate-400">{inv.issue_date}</td>
                      <td className="py-3.5 px-4 font-mono">State {inv.place_of_supply}</td>
                      <td className="py-3.5 px-4">
                        {inv.is_interstate ? (
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
                        <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[10px] uppercase font-mono">
                          {inv.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </main>
      </div>

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
