'use client';

import React, { useEffect, useState, useRef } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import {
  Plus,
  Receipt,
  FileText,
  CheckCircle,
  UploadCloud,
  Loader2,
  RefreshCw,
  Sparkles,
  FileCheck,
  Download,
  Ban,
  Edit2,
  Users,
  Search,
  Check,
  ChevronDown,
  Building,
  Mail,
  Phone,
  MapPin,
  X,
  Trash2,
  QrCode,
  Copy,
  Shield,
  ShieldCheck,
  FolderLock,
  AlertTriangle
} from 'lucide-react';
import Link from 'next/link';
import { fetchApi } from '@/lib/api';

export default function InvoicesPage() {
  const [invoices, setInvoices] = useState<any[]>([]);
  const [contacts, setContacts] = useState<any[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [showRazorpayModal, setShowRazorpayModal] = useState(false);
  const [showContactModal, setShowContactModal] = useState(false);
  const [loading, setLoading] = useState(true);
  const [gstStatus, setGstStatus] = useState<any | null>(null);

  // E-Invoice State
  const [showEInvoiceModal, setShowEInvoiceModal] = useState(false);
  const [selectedEInvoice, setSelectedEInvoice] = useState<any | null>(null);
  const [generatingIrnInvId, setGeneratingIrnInvId] = useState<string | null>(null);
  const [copiedIrn, setCopiedIrn] = useState(false);

  // GSTR-1 Export State
  const [showGstr1Modal, setShowGstr1Modal] = useState(false);
  const [gstr1Year, setGstr1Year] = useState<number>(() => new Date().getFullYear());
  const [gstr1Month, setGstr1Month] = useState<number>(() => new Date().getMonth() + 1);
  const [exportingGstr1, setExportingGstr1] = useState(false);

  // Top-Level View Tab: 'invoices' | 'customers'
  const [mainTab, setMainTab] = useState<'invoices' | 'customers'>('invoices');
  const [customerSearchQuery, setCustomerSearchQuery] = useState('');

  // Search & Suggest Combobox states for New Invoice
  const [customerSearchText, setCustomerSearchText] = useState('');
  const [isCustomerComboboxOpen, setIsCustomerComboboxOpen] = useState(false);

  // Search & Suggest Combobox states for Edit Invoice
  const [editCustomerSearchText, setEditCustomerSearchText] = useState('');
  const [isEditCustomerComboboxOpen, setIsEditCustomerComboboxOpen] = useState(false);

  // New Customer Contact Modal state
  const [newContactName, setNewContactName] = useState('');
  const [newContactEmail, setNewContactEmail] = useState('');
  const [newContactPhone, setNewContactPhone] = useState('');
  const [newContactGstin, setNewContactGstin] = useState('');
  const [newContactState, setNewContactState] = useState('29');
  const [newContactAddress, setNewContactAddress] = useState('');

  // Edit Invoice states
  const [editingInvoice, setEditingInvoice] = useState<any | null>(null);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editInvNumber, setEditInvNumber] = useState('');
  const [editContactId, setEditContactId] = useState('');
  const [editIssueDate, setEditIssueDate] = useState('');
  const [editDueDate, setEditDueDate] = useState('');
  const [editPOS, setEditPOS] = useState('29');
  const [editItemDesc, setEditItemDesc] = useState('');
  const [editHsnCode, setEditHsnCode] = useState('998314');
  const [editQuantity, setEditQuantity] = useState('1');
  const [editUnitPrice, setEditUnitPrice] = useState('0');
  const [editGstRate, setEditGstRate] = useState('18.00');
  const [editSaving, setEditSaving] = useState(false);

  // Role and Mandatory Document Lock State
  const [userRole, setUserRole] = useState<string>('owner');
  const [isMandatoryDocsLocked, setIsMandatoryDocsLocked] = useState<boolean>(false);

  // Dynamic Multi-Line Items State for New Invoice
  const [lineItems, setLineItems] = useState<Array<{
    id: string;
    description: string;
    hsn: string;
    quantity: string;
    unitPrice: string;
    gstRate: string;
  }>>([
    {
      id: 'item-1',
      description: 'Software Design & Architecture Consulting',
      hsn: '998314',
      quantity: '1',
      unitPrice: '150000',
      gstRate: '18.00'
    }
  ]);

  // Standard New Invoice Form states
  const [contactId, setContactId] = useState('');
  const [invoiceNumber, setInvoiceNumber] = useState('INV-2026-001');
  const [placeOfSupply, setPlaceOfSupply] = useState('29'); // Karnataka

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

  // Real-time calculation across all dynamic line items
  const computedTotals = React.useMemo(() => {
    let sub = 0;
    let cgst = 0;
    let sgst = 0;
    let igst = 0;

    lineItems.forEach((it) => {
      const q = parseFloat(it.quantity || '0') || 0;
      const p = parseFloat(it.unitPrice || '0') || 0;
      const r = gstStatus?.has_gstin ? (parseFloat(it.gstRate || '0') || 0) : 0;
      const lineTaxable = q * p;
      sub += lineTaxable;

      const lineTax = (lineTaxable * r) / 100;
      if (placeOfSupply !== operatingState) {
        igst += lineTax;
      } else {
        cgst += lineTax / 2;
        sgst += lineTax / 2;
      }
    });

    const totalTax = cgst + sgst + igst;
    return {
      taxableValue: sub,
      cgstTotal: cgst,
      sgstTotal: sgst,
      igstTotal: igst,
      totalTax,
      grandTotal: sub + totalTax
    };
  }, [lineItems, placeOfSupply, operatingState, gstStatus]);

  const rzpIsInterstate = rzpPos !== operatingState;
  const rzpTaxable = parseFloat(rzpQty || '0') * parseFloat(rzpUnitPrice || '0');
  const rzpRateVal = parseFloat(rzpGstRate || '0');
  const rzpTaxAmt = (rzpTaxable * rzpRateVal) / 100;
  const rzpGrandTotal = rzpTaxable + rzpTaxAmt;
  const [selectedFY, setSelectedFY] = useState<string>('all');

  const filteredCreateContacts = contacts.filter((c) => {
    if (!customerSearchText) return true;
    const q = customerSearchText.toLowerCase();
    return (
      (c.name || '').toLowerCase().includes(q) ||
      (c.gstin || '').toLowerCase().includes(q) ||
      (c.email || '').toLowerCase().includes(q)
    );
  });

  const filteredEditContacts = contacts.filter((c) => {
    if (!editCustomerSearchText) return true;
    const q = editCustomerSearchText.toLowerCase();
    return (
      (c.name || '').toLowerCase().includes(q) ||
      (c.gstin || '').toLowerCase().includes(q) ||
      (c.email || '').toLowerCase().includes(q)
    );
  });

  const filteredCustomersList = contacts.filter((c) => {
    if (!customerSearchQuery) return true;
    const q = customerSearchQuery.toLowerCase();
    return (
      (c.name || '').toLowerCase().includes(q) ||
      (c.gstin || '').toLowerCase().includes(q) ||
      (c.email || '').toLowerCase().includes(q) ||
      (c.state_code || '').toLowerCase().includes(q) ||
      (c.billing_address || '').toLowerCase().includes(q)
    );
  });

  async function loadData() {
    try {
      const storedRole = typeof window !== 'undefined' ? (localStorage.getItem('b00k5_role') || 'owner').toLowerCase() : 'owner';
      setUserRole(storedRole);
      const isAuditor = storedRole.includes('auditor') || storedRole.includes('ca');

      const url = selectedFY && selectedFY !== 'all' ? `/api/v1/invoices/?fy=${encodeURIComponent(selectedFY)}` : '/api/v1/invoices/';
      const invRes = await fetchApi(url);
      setInvoices(invRes);
      const conRes = await fetchApi('/api/v1/invoices/contacts?is_customer=true');
      setContacts(conRes);
      if (conRes.length > 0 && !contactId) {
        setContactId(conRes[0].id);
        setCustomerSearchText(conRes[0].name);
      }

      // Only fetch next-number if authorized (non-auditor)
      if (!isAuditor) {
        try {
          const nextNum = await fetchApi('/api/v1/invoices/next-number');
          if (nextNum?.next_invoice_number) {
            setInvoiceNumber(nextNum.next_invoice_number);
          }
        } catch (err) {
          // fallback to default
        }
      }

      // Check Mandatory Document Gate Status
      try {
        const tenantProf = await fetchApi('/api/v1/vault/statutory-profile');
        if (tenantProf) {
          const statusVal = tenantProf.onboarding_status;
          const coiOk = Boolean(tenantProf.coi_verified);
          const panOk = Boolean(tenantProf.pan_verified);
          if (statusVal === 'PENDING_DOCUMENTS' && !(coiOk && panOk)) {
            setIsMandatoryDocsLocked(true);
          } else {
            setIsMandatoryDocsLocked(false);
          }
        }
      } catch (_) {}

      try {
        const gstThresholdRes = await fetchApi('/api/v1/invoices/gst-threshold-status');
        setGstStatus(gstThresholdRes);
        if (gstThresholdRes && !gstThresholdRes.has_gstin) {
          setEditGstRate('0.00');
          setRzpGstRate('0.00');
        }
      } catch (err) {
        console.error('Failed to load GST threshold status:', err);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [selectedFY]);

  const [downloadingInvId, setDownloadingInvId] = useState<string | null>(null);

  const handleGenerateIRN = async (invId: string) => {
    try {
      setGeneratingIrnInvId(invId);
      const res = await fetchApi(`/api/v1/invoices/${invId}/generate-irn`, {
        method: 'POST',
      });
      await loadData();
      setSelectedEInvoice(res);
      setShowEInvoiceModal(true);
    } catch (err: any) {
      alert(err?.detail || err?.message || 'Failed to generate IRN');
    } finally {
      setGeneratingIrnInvId(null);
    }
  };

  const handleViewEInvoice = (inv: any) => {
    setSelectedEInvoice({
      invoice_id: inv.id,
      invoice_number: inv.invoice_number,
      irn: inv.irn,
      ack_no: inv.ack_no,
      ack_date: inv.ack_date,
      signed_qr_code: inv.signed_qr_code,
      irn_status: inv.irn_status || 'ACT',
      einvoice_payload: inv.einvoice_payload,
      grand_total: inv.grand_total,
    });
    setShowEInvoiceModal(true);
  };

  const handleCopyIrn = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedIrn(true);
    setTimeout(() => setCopiedIrn(false), 2000);
  };

  const handleDownloadInvoicePdf = async (invId: string, invNum: string) => {
    try {
      setDownloadingInvId(invId);
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = typeof window !== 'undefined' ? (localStorage.getItem('b00k5_active_tenant_id') || localStorage.getItem('b00k5_tenant_id')) : null;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const url = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/invoices/${invId}/download${token ? `?token=${encodeURIComponent(token)}` : ''}`;
      const res = await fetch(url, { headers });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to download invoice PDF');
      }

      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = `${invNum || 'Tax_Invoice'}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch (err: any) {
      alert(err.message || 'Error downloading invoice PDF');
    } finally {
      setDownloadingInvId(null);
    }
  };

  const handleDownloadGstr1 = async () => {
    try {
      setExportingGstr1(true);
      const token = typeof window !== 'undefined' ? (localStorage.getItem('b00k5_token') || localStorage.getItem('token') || sessionStorage.getItem('token') || '') : '';
      const tenantId = typeof window !== 'undefined' ? (localStorage.getItem('b00k5_active_tenant_id') || localStorage.getItem('b00k5_tenant_id') || localStorage.getItem('active_tenant_id') || '') : '';
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const url = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/invoices/export/gstr-1?year=${gstr1Year}&month=${gstr1Month}`;
      const res = await fetch(url, { headers });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || 'Failed to generate GSTR-1 JSON');
      }

      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      const paddedMonth = String(gstr1Month).padStart(2, '0');
      a.download = `GSTR1_${gstStatus?.gstin || 'EXPORT'}_${paddedMonth}${gstr1Year}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);
      setShowGstr1Modal(false);
    } catch (err: any) {
      alert(err.message || 'Error exporting GSTR-1 JSON');
    } finally {
      setExportingGstr1(false);
    }
  };

  const handleStrikeOffInvoice = async (invId: string, invNum: string) => {
    if (!window.confirm(`Are you sure you want to strike off Invoice ${invNum}?\n\nThis will reverse the Double-Entry journal entries (Sales & Receivables) in your General Ledger and void the invoice.`)) {
      return;
    }
    try {
      const res = await fetchApi(`/api/v1/invoices/${invId}/strike-off`, {
        method: 'POST'
      });
      setRzpBanner(`Invoice ${invNum} successfully struck off and reversed in ledger (${res.reversal_journal || 'Reversal JV posted'}).`);
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Failed to strike off invoice');
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleDirectInvoicePdfUpload = async (invoiceId: string, file?: File | null) => {
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = typeof window !== 'undefined' ? (localStorage.getItem('b00k5_active_tenant_id') || localStorage.getItem('b00k5_tenant_id')) : null;
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
          email: newContactEmail.trim() || null,
          phone: newContactPhone.trim() || null,
          gstin: newContactGstin.trim() ? newContactGstin.trim().toUpperCase() : null,
          state_code: newContactState.trim() || '29',
          billing_address: newContactAddress.trim() || 'Registered Commercial Address',
        }),
      });
      await loadData();
      setContactId(c.id);
      setCustomerSearchText(c.name);
      if (c.state_code) setPlaceOfSupply(c.state_code);
      setEditContactId(c.id);
      setEditCustomerSearchText(c.name);
      if (c.state_code) setEditPOS(c.state_code);
      setShowContactModal(false);
      setNewContactName('');
      setNewContactEmail('');
      setNewContactPhone('');
      setNewContactGstin('');
      setNewContactAddress('');
    } catch (e: any) {
      alert(e.message || 'Failed to add customer');
    }
  };

  const handleDeleteCustomer = async (c: any, invCount: number) => {
    if (invCount > 0) {
      alert(`Cannot delete customer "${c.name}": ${invCount} tax invoice(s) are linked to this record.\n\nAccording to Companies Act Section 128 statutory rules, customer records with posted transactions must be preserved for audit trail immutability.`);
      return;
    }
    if (!window.confirm(`Are you sure you want to delete customer "${c.name}"?\n\nThis will permanently remove the contact from your customer directory.`)) {
      return;
    }
    try {
      await fetchApi(`/api/v1/invoices/contacts/${c.id}`, {
        method: 'DELETE'
      });
      setRzpBanner(`Customer "${c.name}" deleted successfully.`);
      if (contactId === c.id) {
        setContactId('');
        setCustomerSearchText('');
      }
      if (editContactId === c.id) {
        setEditContactId('');
        setEditCustomerSearchText('');
      }
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Failed to delete customer');
    }
  };

  const handleOpenEditInvoice = (inv: any) => {
    setEditingInvoice(inv);
    setEditInvNumber(inv.invoice_number);
    const cId = inv.contact_id || (inv.contact?.id ?? '');
    setEditContactId(cId);
    const matchedContact = contacts.find(c => c.id === cId);
    setEditCustomerSearchText(matchedContact ? matchedContact.name : (inv.contact?.name || ''));
    setIsEditCustomerComboboxOpen(false);
    setEditIssueDate(inv.issue_date || '');
    setEditDueDate(inv.due_date || '');
    setEditPOS(inv.place_of_supply || '29');
    const firstItem = (inv.items && inv.items.length > 0) ? inv.items[0] : null;
    setEditItemDesc(firstItem?.item_description || firstItem?.description || 'Software Consulting Services');
    setEditHsnCode(firstItem?.hsn_sac_code || '998314');
    setEditQuantity(String(firstItem?.quantity || '1'));
    setEditUnitPrice(String(firstItem?.unit_price || inv.subtotal || '0'));
    setEditGstRate(String(firstItem?.gst_rate_percent || '18.00'));
    setShowEditModal(true);
  };

  const handleSaveEditInvoice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingInvoice) return;
    try {
      setEditSaving(true);
      await fetchApi(`/api/v1/invoices/${editingInvoice.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          invoice_number: editInvNumber.trim(),
          contact_id: editContactId,
          issue_date: editIssueDate,
          due_date: editDueDate,
          place_of_supply: editPOS.trim(),
          items: [
            {
              item_description: editItemDesc.trim(),
              hsn_sac_code: editHsnCode.trim(),
              quantity: parseFloat(editQuantity || '1'),
              unit_price: parseFloat(editUnitPrice || '0'),
              gst_rate_percent: parseFloat(editGstRate || '0'),
            }
          ]
        })
      });
      setShowEditModal(false);
      setEditingInvoice(null);
      await loadData();
    } catch (err: any) {
      alert(err.message || 'Failed to update invoice');
    } finally {
      setEditSaving(false);
    }
  };

  const handleCreateInvoice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isMandatoryDocsLocked) {
      alert("Statutory Lock: Company Certificate of Incorporation (COI) and PAN must be uploaded in Statutory Vault before issuing invoices.");
      return;
    }
    try {
      await fetchApi('/api/v1/invoices/', {
        method: 'POST',
        body: JSON.stringify({
          contact_id: contactId,
          invoice_number: invoiceNumber,
          place_of_supply: placeOfSupply,
          due_date: new Date(Date.now() + 15 * 86400000).toISOString().split('T')[0],
          items: lineItems.map((item) => ({
            item_description: item.description.trim(),
            hsn_sac_code: item.hsn.trim(),
            quantity: parseFloat(item.quantity) || 1,
            unit_price: parseFloat(item.unitPrice) || 0,
            gst_rate_percent: gstStatus?.has_gstin ? (parseFloat(item.gstRate) || 0) : 0,
          })),
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
      const tenantId = typeof window !== 'undefined' ? (localStorage.getItem('b00k5_active_tenant_id') || localStorage.getItem('b00k5_tenant_id')) : null;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/invoices/import/parse`, {
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

      const res = await fetchApi('/api/v1/invoices/import', {
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
                onClick={() => setShowGstr1Modal(true)}
                className="px-3.5 py-2 border border-emerald-500/30 hover:border-emerald-500/60 bg-emerald-950/40 text-emerald-300 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition shadow-sm"
                title="Export official GSTN offline utility JSON (B2B, B2CL, B2CS, CDNR, EXP, HSN Table 12, Doc Issue Table 13) for direct upload to gst.gov.in"
              >
                <Download className="w-3.5 h-3.5 text-emerald-400" /> Export GSTR-1 JSON
              </button>
              {userRole.includes('auditor') || userRole.includes('ca') ? (
                <span className="px-3.5 py-2 rounded-xl bg-sky-950/60 border border-sky-500/30 text-sky-300 text-xs font-mono flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 text-sky-400" /> Statutory Audit Mode (Read-Only)
                </span>
              ) : isMandatoryDocsLocked ? (
                <div className="flex items-center gap-2">
                  <Link
                    href="/vault"
                    className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 shadow-sm"
                  >
                    <FolderLock className="w-3.5 h-3.5" /> Upload COI / PAN in Vault
                  </Link>
                  <button
                    disabled
                    title="Operations locked: Upload Certificate of Incorporation and PAN Card to unlock"
                    className="px-4 py-2 bg-slate-800 text-slate-500 text-xs font-semibold rounded-lg flex items-center gap-2 cursor-not-allowed border border-slate-700"
                  >
                    <Plus className="w-4 h-4" /> New Tax Invoice (Locked)
                  </button>
                </div>
              ) : (
                <>
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
                    <RefreshCw className="w-3.5 h-3.5" /> Import Tax Invoice
                  </button>
                  <button
                    onClick={() => setShowModal(true)}
                    className="px-4 py-2 bg-sky-500 hover:bg-sky-600 text-white text-xs font-semibold rounded-lg flex items-center gap-2"
                  >
                    <Plus className="w-4 h-4" /> New Tax Invoice
                  </button>
                </>
              )}
            </div>
          </div>

          {/* Statutory Mandatory Document Gate Banner */}
          {isMandatoryDocsLocked && (
            <div className="p-4 bg-rose-950/60 border border-rose-500/60 rounded-xl flex items-start gap-3 text-xs text-rose-200 shadow-xl">
              <div className="p-2 bg-rose-500/20 rounded-lg text-rose-400 shrink-0 mt-0.5">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <div className="space-y-1.5 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-white text-sm">
                    Company Operations Locked: Mandatory Statutory Documents Incomplete
                  </span>
                  <span className="px-2 py-0.5 bg-rose-500/20 text-rose-300 font-mono text-[10px] rounded border border-rose-500/30 font-semibold">
                    Section 10A Companies Act
                  </span>
                </div>
                <p className="text-rose-300 leading-relaxed">
                  Under Companies Act 2013 and Rule 9 of Companies (Incorporation) Rules, commercial operations and invoicing are strictly prohibited until the mandatory corporate documents (<strong>Certificate of Incorporation &apos;COI&apos;</strong> and <strong>Company PAN Card</strong>) have been deposited and verified in the Statutory Document Vault.
                </p>
                <div className="pt-1">
                  <Link
                    href="/vault"
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-rose-500 hover:bg-rose-600 text-white font-semibold text-xs rounded-lg transition"
                  >
                    <FolderLock className="w-3.5 h-3.5" /> Deposit Mandatory Documents in Vault →
                  </Link>
                </div>
              </div>
            </div>
          )}

          {rzpBanner && (
            <div className="p-3.5 bg-emerald-950/40 border border-emerald-500/40 rounded-xl flex items-center justify-between text-xs text-emerald-200">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{rzpBanner}</span>
              </div>
              <button onClick={() => setRzpBanner(null)} className="text-emerald-400 hover:text-white">✕</button>
            </div>
          )}

          {/* Statutory Section 22 CGST Act Turnover Threshold & Non-GST Guard Banner */}
          {gstStatus && (
            <>
              {gstStatus.threshold_exceeded ? (
                <div className="p-4 bg-rose-950/40 border border-rose-500/50 rounded-xl flex items-start justify-between gap-3 text-xs text-rose-200 shadow-lg">
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-rose-500/20 rounded-lg text-rose-400 shrink-0 mt-0.5">
                      <AlertTriangle className="w-5 h-5" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-sm">
                          Mandatory GST Registration Threshold Exceeded (Section 22 CGST Act)
                        </span>
                        <span className="px-2 py-0.5 bg-rose-500/20 text-rose-300 font-mono text-[10px] rounded border border-rose-500/30 font-semibold">
                          Action Required
                        </span>
                      </div>
                      <p className="text-rose-300 leading-relaxed">
                        Aggregate turnover for {gstStatus.current_fy} is <strong className="text-white font-mono">₹{gstStatus.turnover_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong>, crossing the statutory threshold limit of <strong className="text-white font-mono">₹{gstStatus.threshold_limit.toLocaleString('en-IN')}</strong>. Under Section 22(1) CGST Act, the entity is legally required to obtain GST registration within 30 days.
                      </p>
                      <p className="text-[11px] text-rose-400">
                        Until a verified GST registration certificate (GST REG-06) is uploaded to the Document Vault, all invoices are locked to Bill of Supply (0% GST) under Section 31(3)(c) &amp; Section 32 CGST Act.
                      </p>
                    </div>
                  </div>
                </div>
              ) : gstStatus.threshold_approaching ? (
                <div className="p-4 bg-amber-950/40 border border-amber-500/40 rounded-xl flex items-start justify-between gap-3 text-xs text-amber-200">
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-amber-500/20 rounded-lg text-amber-400 shrink-0 mt-0.5">
                      <AlertTriangle className="w-5 h-5" />
                    </div>
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white text-sm">
                          Approaching GST Exemption Limit (Section 22 Watchdog)
                        </span>
                        <span className="px-2 py-0.5 bg-amber-500/20 text-amber-300 font-mono text-[10px] rounded border border-amber-500/30">
                          Turnover Alert
                        </span>
                      </div>
                      <p className="text-amber-300 leading-relaxed">
                        Current FY aggregate turnover is <strong className="text-white font-mono">₹{gstStatus.turnover_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong> (75%+ of ₹20,00,000 threshold). Prepare registration documents in advance.
                      </p>
                    </div>
                  </div>
                </div>
              ) : !gstStatus.has_gstin ? (
                <div className="p-3 bg-sky-950/30 border border-sky-500/30 rounded-xl flex items-center justify-between text-xs text-sky-200">
                  <div className="flex items-center gap-2.5">
                    <Shield className="w-4 h-4 text-sky-400 shrink-0" />
                    <span>
                      <strong>Non-GST Entity Mode:</strong> No verified GST registration document on file. Invoices are issued as <strong>Bill of Supply (0% GST)</strong> under Section 31(3)(c) and Section 32 CGST Act. Current FY turnover: <strong className="font-mono text-white">₹{gstStatus.turnover_amount.toLocaleString('en-IN')}</strong> / ₹20,00,000.
                    </span>
                  </div>
                </div>
              ) : null}
            </>
          )}

          {/* Top-Level Navigation Tabs: Invoices vs Customers */}
          <div className="flex items-center gap-6 border-b border-slate-800">
            <button
              onClick={() => setMainTab('invoices')}
              className={`flex items-center gap-2 pb-3 text-sm font-semibold transition border-b-2 ${
                mainTab === 'invoices'
                  ? 'border-sky-500 text-sky-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Receipt className="w-4 h-4" />
              Tax Invoices &amp; AR
              <span className="ml-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono bg-slate-800 text-slate-300">
                {invoices.length}
              </span>
            </button>
            <button
              onClick={() => setMainTab('customers')}
              className={`flex items-center gap-2 pb-3 text-sm font-semibold transition border-b-2 ${
                mainTab === 'customers'
                  ? 'border-sky-500 text-sky-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Users className="w-4 h-4" />
              Customers Directory
              <span className="ml-1.5 px-2 py-0.5 rounded-full text-[10px] font-mono bg-slate-800 text-slate-300">
                {contacts.length}
              </span>
            </button>
          </div>

          {mainTab === 'invoices' ? (
            <>
              {/* Financial Year Switcher Tabs */}
              <div className="flex items-center gap-2 border-b border-slate-800 pb-3 overflow-x-auto">
                <span className="text-xs text-slate-400 font-medium">Financial Year:</span>
            {['all', '2026-27', '2025-26', '2024-25'].map((fy) => (
              <button
                key={fy}
                onClick={() => setSelectedFY(fy)}
                className={`px-3 py-1 rounded-lg text-xs font-mono transition ${
                  selectedFY === fy
                    ? 'bg-sky-500/20 text-sky-400 border border-sky-500/40 font-semibold'
                    : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-slate-200'
                }`}
              >
                {fy === 'all' ? 'All Fiscal Years' : `FY ${fy}`}
              </button>
            ))}
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
                  <th className="py-3.5 px-4 text-right">Actions / PDF</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {invoices.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-8 text-center text-slate-500">
                      No invoices issued yet. Click &quot;Import Tax Invoice&quot; or &quot;New Tax Invoice&quot; to synchronize your billing.
                    </td>
                  </tr>
                ) : (
                  invoices.map((inv) => (
                    <tr key={inv.id} className="hover:bg-slate-800/30">
                      <td className="py-3.5 px-4 font-mono font-medium text-white">
                        <div className="flex items-center gap-1.5">
                          <span>{inv.invoice_number}</span>
                          {inv.irn && (
                            <button
                              type="button"
                              onClick={() => handleViewEInvoice(inv)}
                              className="px-1.5 py-0.5 rounded bg-teal-500/20 text-teal-300 border border-teal-500/40 text-[9px] font-mono hover:bg-teal-500/30 transition flex items-center gap-1"
                              title={`NIC E-Invoice IRN: ${inv.irn}\nClick to view full signed payload`}
                            >
                              <Shield className="w-2.5 h-2.5 text-teal-400" />
                              <span>IRN</span>
                            </button>
                          )}
                        </div>
                      </td>
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
                          inv.status === 'cancelled' || inv.status === 'struck_off'
                            ? 'bg-rose-500/15 text-rose-300 border-rose-500/30'
                            : inv.status === 'paid'
                            ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
                            : 'bg-sky-500/10 text-sky-400 border-sky-500/20'
                        }`}>
                          {inv.status === 'cancelled' ? 'CANCELLED / VOID' : inv.status}
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-1.5 flex-wrap">
                          {inv.irn ? (
                            <button
                              type="button"
                              onClick={() => handleViewEInvoice(inv)}
                              className="px-2 py-1 rounded bg-teal-950/70 hover:bg-teal-900 border border-teal-700/60 text-teal-300 hover:text-white text-[10px] font-semibold inline-flex items-center gap-1 transition"
                              title="View Indian E-Invoice IRN & Signed QR Code"
                            >
                              <QrCode className="w-3 h-3 text-teal-400" />
                              <span>IRN</span>
                            </button>
                          ) : inv.status !== 'cancelled' && inv.status !== 'struck_off' ? (
                            <button
                              type="button"
                              onClick={() => handleGenerateIRN(inv.id)}
                              disabled={generatingIrnInvId === inv.id}
                              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-750 text-slate-300 hover:text-white text-[10px] font-semibold inline-flex items-center gap-1 transition disabled:opacity-50"
                              title="Generate Indian E-Invoice IRN & Signed QR Code (NIC Schema v1.03)"
                            >
                              {generatingIrnInvId === inv.id ? (
                                <Loader2 className="w-3 h-3 animate-spin text-sky-400" />
                              ) : (
                                <QrCode className="w-3 h-3 text-slate-400" />
                              )}
                              <span>E-Invoice</span>
                            </button>
                          ) : null}
                          {!userRole.includes('auditor') && !userRole.includes('ca') && (
                            <button
                              onClick={() => handleOpenEditInvoice(inv)}
                              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-750 text-slate-200 hover:text-white text-[10px] font-semibold inline-flex items-center gap-1 transition"
                              title="Edit Invoice details, customer, and line items"
                            >
                              <Edit2 className="w-3 h-3 text-amber-400" />
                              <span>Edit</span>
                            </button>
                          )}
                          <button
                            onClick={() => handleDownloadInvoicePdf(inv.id, inv.invoice_number)}
                            disabled={downloadingInvId === inv.id}
                            className="px-2 py-1 rounded bg-sky-950/70 hover:bg-sky-900 border border-sky-700/60 text-sky-300 hover:text-white text-[10px] font-semibold inline-flex items-center gap-1 transition disabled:opacity-50"
                            title="Download GST Tax Invoice PDF"
                          >
                            {downloadingInvId === inv.id ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <Download className="w-3 h-3" />
                            )}
                            <span>PDF</span>
                          </button>
                          {!inv.pdf_s3_key && !userRole.includes('auditor') && !userRole.includes('ca') && (
                            <label className="cursor-pointer px-2 py-1 rounded bg-indigo-950 text-indigo-300 border border-indigo-700 hover:bg-indigo-900 text-[10px] font-semibold inline-flex items-center gap-1 transition">
                              <UploadCloud className="w-3 h-3" /> Attach
                              <input
                                type="file"
                                accept=".pdf,.png,.jpg,.jpeg"
                                className="hidden"
                                onChange={(e) => handleDirectInvoicePdfUpload(inv.id, e.target.files?.[0])}
                              />
                            </label>
                          )}
                          {!userRole.includes('auditor') && !userRole.includes('ca') && inv.status !== 'cancelled' && inv.status !== 'struck_off' && (
                            <button
                              onClick={() => handleStrikeOffInvoice(inv.id, inv.invoice_number)}
                              className="px-2 py-1 rounded bg-rose-950/40 hover:bg-rose-900/70 border border-rose-800/60 text-rose-300 hover:text-white text-[10px] font-semibold inline-flex items-center gap-1 transition"
                              title="Strike off / Cancel invoice and reverse ledger postings"
                            >
                              <Ban className="w-3 h-3" /> Strike Off
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <div className="space-y-4">
          {/* Customer Directory Header & Search */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-900 border border-slate-800 p-4 rounded-xl">
            <div className="relative flex-1 max-w-md">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={customerSearchQuery}
                onChange={(e) => setCustomerSearchQuery(e.target.value)}
                placeholder="Search customers by name, GSTIN, email, state, or address..."
                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-8 py-2 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-sky-500"
              />
              {customerSearchQuery && (
                <button
                  onClick={() => setCustomerSearchQuery('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-slate-400 font-mono">
                Showing <strong className="text-slate-200">{filteredCustomersList.length}</strong> of {contacts.length} customers
              </span>
              <button
                onClick={() => {
                  setNewContactName('');
                  setNewContactEmail('');
                  setNewContactPhone('');
                  setNewContactGstin('');
                  setNewContactState('29');
                  setNewContactAddress('');
                  setShowContactModal(true);
                }}
                className="px-3 py-2 bg-sky-500 hover:bg-sky-600 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-sm transition"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Customer</span>
              </button>
            </div>
          </div>

          {/* Customers Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/60 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-mono">
                <tr>
                  <th className="py-3.5 px-4">Customer Name &amp; Entity</th>
                  <th className="py-3.5 px-4">GSTIN / Tax ID</th>
                  <th className="py-3.5 px-4">State / POS</th>
                  <th className="py-3.5 px-4">Contact Info</th>
                  <th className="py-3.5 px-4">Registered Address</th>
                  <th className="py-3.5 px-4 text-center">Invoices</th>
                  <th className="py-3.5 px-4 text-right">Quick Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {filteredCustomersList.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-500">
                      <Users className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                      <p className="font-medium text-slate-400">No customers found</p>
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        {customerSearchQuery
                          ? `No customers matched "${customerSearchQuery}". Try clearing search or add a new customer.`
                          : "No customers registered yet. Click 'Add Customer' to register your first billing contact."}
                      </p>
                    </td>
                  </tr>
                ) : (
                  filteredCustomersList.map((c) => {
                    const invCount = invoices.filter(
                      (inv) => inv.contact_id === c.id || inv.contact?.id === c.id
                    ).length;
                    return (
                      <tr key={c.id} className="hover:bg-slate-800/30">
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-2">
                            <div className="w-7 h-7 rounded-lg bg-sky-950/80 border border-sky-800/60 flex items-center justify-center text-sky-400 font-bold shrink-0">
                              {c.name ? c.name.charAt(0).toUpperCase() : 'C'}
                            </div>
                            <div>
                              <div className="font-semibold text-white">{c.name}</div>
                              <div className="text-[10px] text-slate-400 font-mono">
                                Customer ID: {c.id?.slice(0, 8)}...
                              </div>
                            </div>
                          </div>
                        </td>
                        <td className="py-3.5 px-4">
                          {c.gstin ? (
                            <span className="px-2 py-0.5 rounded bg-purple-500/10 text-purple-300 border border-purple-500/20 font-mono text-[11px] font-semibold">
                              {c.gstin}
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 text-[10px] font-mono">
                              Unregistered
                            </span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 font-mono">
                          <span className="text-slate-200">State {c.state_code || '29'}</span>
                        </td>
                        <td className="py-3.5 px-4 space-y-0.5">
                          {c.email && (
                            <div className="flex items-center gap-1.5 text-slate-300">
                              <Mail className="w-3 h-3 text-slate-500 shrink-0" />
                              <span className="truncate max-w-[180px]">{c.email}</span>
                            </div>
                          )}
                          {c.phone && (
                            <div className="flex items-center gap-1.5 text-slate-400 font-mono text-[11px]">
                              <Phone className="w-3 h-3 text-slate-500 shrink-0" />
                              <span>{c.phone}</span>
                            </div>
                          )}
                          {!c.email && !c.phone && (
                            <span className="text-slate-500 italic">No contact info</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-slate-300 max-w-sm">
                          <div className="text-[11px] leading-relaxed line-clamp-2" title={c.billing_address || ''}>
                            {c.billing_address || '—'}
                          </div>
                        </td>
                        <td className="py-3.5 px-4 text-center">
                          <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 text-[11px] font-mono">
                            {invCount}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <button
                              onClick={() => {
                                setContactId(c.id);
                                setCustomerSearchText(c.name);
                                if (c.state_code) setPlaceOfSupply(c.state_code);
                                else if (c.gstin && c.gstin.length >= 2 && /^\d{2}$/.test(c.gstin.slice(0, 2))) {
                                  setPlaceOfSupply(c.gstin.slice(0, 2));
                                }
                                setShowModal(true);
                              }}
                              className="px-2.5 py-1 rounded bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 border border-sky-500/30 text-[11px] font-semibold inline-flex items-center gap-1 transition"
                              title={`Issue new invoice for ${c.name}`}
                            >
                              <Plus className="w-3 h-3" />
                              <span>New Invoice</span>
                            </button>
                            <button
                              onClick={() => handleDeleteCustomer(c, invCount)}
                              className={`p-1.5 rounded text-[11px] font-semibold inline-flex items-center justify-center transition border ${
                                invCount > 0
                                  ? 'text-slate-600 border-slate-800 cursor-not-allowed opacity-40'
                                  : 'text-rose-400 hover:text-white bg-rose-950/20 hover:bg-rose-900 border-rose-900/40'
                              }`}
                              title={invCount > 0 ? `Cannot delete: ${invCount} linked invoice(s)` : `Delete customer "${c.name}"`}
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </main>
  </div>

      {/* Add Customer Modal */}
      {showContactModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="font-bold text-white text-base">Add Customer Contact</h3>
                <p className="text-[11px] text-slate-400 mt-0.5">Register a billing client with valid GSTIN and registered business address.</p>
              </div>
              <button onClick={() => setShowContactModal(false)} className="text-slate-400 hover:text-white text-sm">✕</button>
            </div>
            <form onSubmit={handleCreateContact} className="space-y-3.5 text-xs">
              <div>
                <label className="block text-slate-400 mb-1 font-medium">Customer Legal / Trade Name *</label>
                <input
                  type="text"
                  value={newContactName}
                  onChange={(e) => setNewContactName(e.target.value)}
                  placeholder="e.g. Acme Technologies Pvt Ltd"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-sky-500"
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Customer Email ID</label>
                  <input
                    type="email"
                    value={newContactEmail}
                    onChange={(e) => setNewContactEmail(e.target.value)}
                    placeholder="billing@customer.com"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 focus:outline-none focus:border-sky-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Customer Phone Number</label>
                  <input
                    type="tel"
                    value={newContactPhone}
                    onChange={(e) => setNewContactPhone(e.target.value)}
                    placeholder="+91 98765 43210"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono focus:outline-none focus:border-sky-500"
                  />
                </div>
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
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono uppercase focus:outline-none focus:border-sky-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">State Code (POS) *</label>
                  <input
                    type="text"
                    value={newContactState}
                    onChange={(e) => setNewContactState(e.target.value)}
                    placeholder="29"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono focus:outline-none focus:border-sky-500"
                    required
                  />
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-slate-400 font-medium">Registered Billing Address</label>
                  <span className="text-[10px] text-slate-500">Accommodates full multi-line statutory address</span>
                </div>
                <textarea
                  rows={3}
                  value={newContactAddress}
                  onChange={(e) => setNewContactAddress(e.target.value)}
                  placeholder="Enter full registered commercial address (Unit/Flat No, Building, Street, Area/Locality, City, State, PIN Code)..."
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-sky-500 resize-y leading-relaxed text-xs"
                />
              </div>
              <div className="pt-2 flex justify-end gap-2 border-t border-slate-800">
                <button type="button" onClick={() => setShowContactModal(false)} className="px-4 py-2 border border-slate-700 text-slate-300 rounded-lg hover:bg-slate-800 transition">
                  Cancel
                </button>
                <button type="submit" className="px-5 py-2 bg-sky-500 hover:bg-sky-600 text-white font-semibold rounded-lg shadow-sm transition">
                  Save Customer
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Tax Invoice Modal */}
      {showEditModal && editingInvoice && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl p-6 shadow-2xl space-y-4 my-8">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="font-bold text-white text-base flex items-center gap-2">
                  <Edit2 className="w-4 h-4 text-amber-400" />
                  Edit Tax Invoice — {editingInvoice.invoice_number}
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Update customer, line items, and pricing. General Ledger journal entries and invoice PDF will automatically re-balance.
                </p>
              </div>
              <button onClick={() => setShowEditModal(false)} className="text-slate-400 hover:text-white text-sm">✕</button>
            </div>

            <form onSubmit={handleSaveEditInvoice} className="space-y-4 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1 font-medium">Invoice Number *</label>
                  <input
                    type="text"
                    value={editInvNumber}
                    onChange={(e) => setEditInvNumber(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono font-bold"
                    required
                  />
                </div>
                <div className="relative">
                  <label className="block text-slate-400 mb-1 font-medium">Customer Contact *</label>
                  <div className="relative">
                    <input
                      type="text"
                      value={editCustomerSearchText}
                      onChange={(e) => {
                        setEditCustomerSearchText(e.target.value);
                        setIsEditCustomerComboboxOpen(true);
                      }}
                      onFocus={() => setIsEditCustomerComboboxOpen(true)}
                      placeholder="Type customer name, GSTIN or email..."
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-3 pr-8 py-2 text-slate-200 placeholder:text-slate-500 text-xs focus:outline-none focus:border-sky-500"
                      required
                    />
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                      {editCustomerSearchText && (
                        <button
                          type="button"
                          onClick={() => {
                            setEditCustomerSearchText('');
                            setEditContactId('');
                            setIsEditCustomerComboboxOpen(true);
                          }}
                          className="text-slate-500 hover:text-slate-300 p-0.5"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => setIsEditCustomerComboboxOpen(!isEditCustomerComboboxOpen)}
                        className="text-slate-500 hover:text-slate-300 p-0.5"
                      >
                        <ChevronDown className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Dropdown suggestions */}
                  {isEditCustomerComboboxOpen && (
                    <>
                      <div
                        className="fixed inset-0 z-40"
                        onClick={() => setIsEditCustomerComboboxOpen(false)}
                      />
                      <div className="absolute left-0 right-0 top-full mt-1 bg-slate-900 border border-slate-700 rounded-lg shadow-2xl max-h-56 overflow-y-auto z-50 divide-y divide-slate-800">
                        {filteredEditContacts.length === 0 ? (
                          <div className="p-3 text-center space-y-2">
                            <p className="text-slate-400 text-xs">No matching customers found</p>
                            <button
                              type="button"
                              onClick={() => {
                                setNewContactName(editCustomerSearchText);
                                setNewContactEmail('');
                                setNewContactPhone('');
                                setNewContactGstin('');
                                setNewContactState('29');
                                setNewContactAddress('');
                                setIsEditCustomerComboboxOpen(false);
                                setShowContactModal(true);
                              }}
                              className="w-full px-3 py-1.5 bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 border border-sky-500/30 rounded text-xs font-semibold flex items-center justify-center gap-1"
                            >
                              <Plus className="w-3 h-3" />
                              Add &quot;{editCustomerSearchText}&quot; as New Customer
                            </button>
                          </div>
                        ) : (
                          filteredEditContacts.map((c) => {
                            const isSelected = editContactId === c.id;
                            return (
                              <button
                                key={c.id}
                                type="button"
                                onClick={() => {
                                  setEditContactId(c.id);
                                  setEditCustomerSearchText(c.name);
                                  if (c.state_code) {
                                    setEditPOS(c.state_code);
                                  } else if (c.gstin && c.gstin.length >= 2 && /^\d{2}$/.test(c.gstin.slice(0, 2))) {
                                    setEditPOS(c.gstin.slice(0, 2));
                                  }
                                  setIsEditCustomerComboboxOpen(false);
                                }}
                                className={`w-full text-left px-3 py-2.5 flex items-center justify-between hover:bg-slate-800/80 transition text-xs ${
                                  isSelected ? 'bg-sky-950/40 text-sky-300' : 'text-slate-300'
                                }`}
                              >
                                <div className="space-y-0.5">
                                  <div className="font-semibold text-slate-100 flex items-center gap-2">
                                    <span>{c.name}</span>
                                    {c.state_code && (
                                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-400">
                                        State {c.state_code}
                                      </span>
                                    )}
                                  </div>
                                  <div className="text-[11px] text-slate-400 font-mono">
                                    {c.gstin ? `GSTIN: ${c.gstin}` : 'Unregistered'}
                                    {c.email ? ` • ${c.email}` : ''}
                                  </div>
                                </div>
                                {isSelected && <Check className="w-4 h-4 text-sky-400 shrink-0 ml-2" />}
                              </button>
                            );
                          })
                        )}
                        <div className="p-2 bg-slate-950/60 border-t border-slate-800">
                          <button
                            type="button"
                            onClick={() => {
                              setNewContactName(editCustomerSearchText);
                              setIsEditCustomerComboboxOpen(false);
                              setShowContactModal(true);
                            }}
                            className="w-full text-left px-2 py-1 text-[11px] text-sky-400 hover:text-sky-300 font-medium flex items-center gap-1.5"
                          >
                            <Plus className="w-3 h-3" />
                            Create new customer contact
                          </button>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-slate-400 mb-1">Issue Date *</label>
                  <input
                    type="date"
                    value={editIssueDate}
                    onChange={(e) => setEditIssueDate(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                    required
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Due Date *</label>
                  <input
                    type="date"
                    value={editDueDate}
                    onChange={(e) => setEditDueDate(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                    required
                  />
                </div>
                <div>
                  <label className="block text-slate-400 mb-1">Place of Supply (POS) *</label>
                  <input
                    type="text"
                    value={editPOS}
                    onChange={(e) => setEditPOS(e.target.value)}
                    placeholder="29"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                    required
                  />
                </div>
              </div>

              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-xl space-y-3">
                <div className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider font-mono">
                  Line Item Details &amp; Pricing
                </div>
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-slate-400 font-medium">Service / Item Description *</label>
                    <span className="text-[10px] text-slate-500">Multi-line description</span>
                  </div>
                  <textarea
                    rows={3}
                    value={editItemDesc}
                    onChange={(e) => setEditItemDesc(e.target.value)}
                    placeholder="Enter detailed scope of work or item deliverables..."
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 text-xs leading-relaxed resize-y focus:outline-none focus:border-sky-500"
                    required
                  />
                </div>
                <div className="grid grid-cols-4 gap-2">
                  <div>
                    <label className="block text-slate-400 mb-1">HSN/SAC</label>
                    <input
                      type="text"
                      value={editHsnCode}
                      onChange={(e) => setEditHsnCode(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Qty</label>
                    <input
                      type="number"
                      step="any"
                      min="0.01"
                      value={editQuantity}
                      onChange={(e) => setEditQuantity(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">Unit Price (₹)</label>
                    <input
                      type="number"
                      step="any"
                      min="0"
                      value={editUnitPrice}
                      onChange={(e) => setEditUnitPrice(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-slate-400 mb-1">
                      GST Rate {!gstStatus?.has_gstin && <span className="text-[10px] text-amber-400 font-mono">(0% Bill of Supply)</span>}
                    </label>
                    <select
                      value={editGstRate}
                      onChange={(e) => setEditGstRate(e.target.value)}
                      disabled={!gstStatus?.has_gstin}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      {!gstStatus?.has_gstin ? (
                        <option value="0.00">0% (Bill of Supply - No GSTIN)</option>
                      ) : (
                        <>
                          <option value="0.00">0% (Nil)</option>
                          <option value="5.00">5%</option>
                          <option value="12.00">12%</option>
                          <option value="18.00">18%</option>
                          <option value="28.00">28%</option>
                        </>
                      )}
                    </select>
                  </div>
                </div>

                {/* Real-time Subtotal & Tax Preview */}
                {(() => {
                  const sub = (parseFloat(editQuantity || '0') * parseFloat(editUnitPrice || '0'));
                  const r = parseFloat(editGstRate || '0');
                  const tax = (sub * r) / 100;
                  const tot = sub + tax;
                  const isInter = editPOS.trim() !== '29';
                  return (
                    <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
                      <span>Subtotal: ₹{sub.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                      <span>
                        {isInter ? `IGST (${r}%): ` : `CGST+SGST (${r}%): `}
                        ₹{tax.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                      <span className="font-bold text-emerald-400 text-xs">
                        Grand Total: ₹{tot.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                  );
                })()}
              </div>

              <div className="pt-2 flex justify-end gap-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowEditModal(false)}
                  className="px-4 py-2 border border-slate-700 text-slate-300 rounded-lg hover:bg-slate-800"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={editSaving}
                  className="px-5 py-2 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold rounded-lg flex items-center gap-1.5 shadow-md shadow-amber-500/20 disabled:opacity-50"
                >
                  {editSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileCheck className="w-4 h-4" />}
                  <span>{editSaving ? 'Updating Invoice...' : 'Save & Re-balance Ledger'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Import Tax Invoice Modal */}
      {showRazorpayModal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl p-6 shadow-2xl space-y-4 my-8">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="font-bold text-white text-base flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-indigo-400" />
                  Import Tax Invoice
                </h3>
                <p className="text-[11px] text-slate-400">
                  Universal Invoice Parser: Upload any Tax Invoice (PDF, PNG, JPG, or Razorpay CSV/JSON export) to auto-extract details and sync with General Ledger.
                </p>
              </div>
              <button onClick={() => setShowRazorpayModal(false)} className="text-slate-400 hover:text-white text-sm">
                ✕
              </button>
            </div>

            {/* File Dropzone for Tax Invoice PDF / CSV / JSON */}
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
                    ? 'Extracting Invoice Details...'
                    : rzpUploadedFile
                      ? `Loaded: ${rzpUploadedFile} (${rzpBatchItems.length} invoice${rzpBatchItems.length === 1 ? '' : 's'} detected)`
                      : 'Click to upload Tax Invoice PDF / Image or Invoices CSV / JSON Export'}
                </div>
                <div className="text-[10px] text-slate-400 font-mono">
                  Auto-extracts Invoice #, Date, Customer GSTIN, Place of Supply, Line Items & Tax Breakdown
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
                      <label className="block text-slate-400 mb-1">
                        GST Rate % {!gstStatus?.has_gstin && <span className="text-[10px] text-amber-400 font-mono">(0% Non-GST)</span>}
                      </label>
                      <select
                        value={rzpGstRate}
                        onChange={(e) => setRzpGstRate(e.target.value)}
                        disabled={!gstStatus?.has_gstin}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 disabled:opacity-60 disabled:cursor-not-allowed"
                      >
                        {!gstStatus?.has_gstin ? (
                          <option value="0.00">0% (Bill of Supply - No GSTIN)</option>
                        ) : (
                          <>
                            <option value="18.00">18% GST</option>
                            <option value="12.00">12% GST</option>
                            <option value="5.00">5% GST</option>
                            <option value="0.00">0% (Exempt / Export)</option>
                          </>
                        )}
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
                <div className="relative">
                  <label className="block text-slate-400 mb-1 font-medium">Customer / Billed To *</label>
                  <div className="relative">
                    <input
                      type="text"
                      value={customerSearchText}
                      onChange={(e) => {
                        setCustomerSearchText(e.target.value);
                        setIsCustomerComboboxOpen(true);
                      }}
                      onFocus={() => setIsCustomerComboboxOpen(true)}
                      placeholder="Type customer name, GSTIN or email..."
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-3 pr-8 py-2 text-slate-200 placeholder:text-slate-500 text-xs focus:outline-none focus:border-sky-500"
                      required
                    />
                    <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                      {customerSearchText && (
                        <button
                          type="button"
                          onClick={() => {
                            setCustomerSearchText('');
                            setContactId('');
                            setIsCustomerComboboxOpen(true);
                          }}
                          className="text-slate-500 hover:text-slate-300 p-0.5"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => setIsCustomerComboboxOpen(!isCustomerComboboxOpen)}
                        className="text-slate-500 hover:text-slate-300 p-0.5"
                      >
                        <ChevronDown className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Dropdown suggestions */}
                  {isCustomerComboboxOpen && (
                    <>
                      <div
                        className="fixed inset-0 z-40"
                        onClick={() => setIsCustomerComboboxOpen(false)}
                      />
                      <div className="absolute left-0 right-0 top-full mt-1 bg-slate-900 border border-slate-700 rounded-lg shadow-2xl max-h-56 overflow-y-auto z-50 divide-y divide-slate-800">
                        {filteredCreateContacts.length === 0 ? (
                          <div className="p-3 text-center space-y-2">
                            <p className="text-slate-400 text-xs">No matching customers found</p>
                            <button
                              type="button"
                              onClick={() => {
                                setNewContactName(customerSearchText);
                                setNewContactEmail('');
                                setNewContactPhone('');
                                setNewContactGstin('');
                                setNewContactState('29');
                                setNewContactAddress('');
                                setIsCustomerComboboxOpen(false);
                                setShowContactModal(true);
                              }}
                              className="w-full px-3 py-1.5 bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 border border-sky-500/30 rounded text-xs font-semibold flex items-center justify-center gap-1"
                            >
                              <Plus className="w-3 h-3" />
                              Add &quot;{customerSearchText}&quot; as New Customer
                            </button>
                          </div>
                        ) : (
                          filteredCreateContacts.map((c) => {
                            const isSelected = contactId === c.id;
                            return (
                              <button
                                key={c.id}
                                type="button"
                                onClick={() => {
                                  setContactId(c.id);
                                  setCustomerSearchText(c.name);
                                  if (c.state_code) {
                                    setPlaceOfSupply(c.state_code);
                                  } else if (c.gstin && c.gstin.length >= 2 && /^\d{2}$/.test(c.gstin.slice(0, 2))) {
                                    setPlaceOfSupply(c.gstin.slice(0, 2));
                                  }
                                  setIsCustomerComboboxOpen(false);
                                }}
                                className={`w-full text-left px-3 py-2.5 flex items-center justify-between hover:bg-slate-800/80 transition text-xs ${
                                  isSelected ? 'bg-sky-950/40 text-sky-300' : 'text-slate-300'
                                }`}
                              >
                                <div className="space-y-0.5">
                                  <div className="font-semibold text-slate-100 flex items-center gap-2">
                                    <span>{c.name}</span>
                                    {c.state_code && (
                                      <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-400">
                                        State {c.state_code}
                                      </span>
                                    )}
                                  </div>
                                  <div className="text-[11px] text-slate-400 font-mono">
                                    {c.gstin ? `GSTIN: ${c.gstin}` : 'Unregistered'}
                                    {c.email ? ` • ${c.email}` : ''}
                                  </div>
                                </div>
                                {isSelected && <Check className="w-4 h-4 text-sky-400 shrink-0 ml-2" />}
                              </button>
                            );
                          })
                        )}
                        <div className="p-2 bg-slate-950/60 border-t border-slate-800">
                          <button
                            type="button"
                            onClick={() => {
                              setNewContactName(customerSearchText);
                              setIsCustomerComboboxOpen(false);
                              setShowContactModal(true);
                            }}
                            className="w-full text-left px-2 py-1 text-[11px] text-sky-400 hover:text-sky-300 font-medium flex items-center gap-1.5"
                          >
                            <Plus className="w-3 h-3" />
                            Create new customer contact
                          </button>
                        </div>
                      </div>
                    </>
                  )}
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
              </div>
              {/* Dynamic Line Items Section */}
              <div className="space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                  <div className="text-xs font-semibold text-slate-300 font-mono uppercase tracking-wider flex items-center gap-2">
                    <Receipt className="w-3.5 h-3.5 text-sky-400" />
                    Service / Line Items ({lineItems.length})
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      setLineItems([
                        ...lineItems,
                        {
                          id: `item-${Date.now()}`,
                          description: '',
                          hsn: '998314',
                          quantity: '1',
                          unitPrice: '0',
                          gstRate: gstStatus?.has_gstin ? '18.00' : '0.00'
                        }
                      ]);
                    }}
                    className="px-2.5 py-1 bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 border border-sky-500/30 rounded text-[11px] font-semibold flex items-center gap-1 transition"
                  >
                    <Plus className="w-3 h-3" /> Add Item / Line
                  </button>
                </div>

                {lineItems.map((item, idx) => {
                  const lineTaxable = (parseFloat(item.quantity || '0') || 0) * (parseFloat(item.unitPrice || '0') || 0);
                  const lineRate = gstStatus?.has_gstin ? (parseFloat(item.gstRate || '0') || 0) : 0;
                  const lineTax = (lineTaxable * lineRate) / 100;
                  const lineTotal = lineTaxable + lineTax;

                  return (
                    <div key={item.id} className="p-3.5 bg-slate-950/80 border border-slate-800 rounded-xl space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-mono font-semibold text-slate-300 flex items-center gap-1.5">
                          <span className="w-4 h-4 rounded-full bg-slate-800 text-slate-300 text-[10px] flex items-center justify-center">
                            {idx + 1}
                          </span>
                          Item #{idx + 1}
                        </span>
                        {lineItems.length > 1 && (
                          <button
                            type="button"
                            onClick={() => setLineItems(lineItems.filter((_, i) => i !== idx))}
                            className="text-slate-500 hover:text-rose-400 p-1 transition"
                            title="Remove this line item"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>

                      {/* Large Multi-Line Description Box */}
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <label className="block text-slate-400 font-medium">Service / Deliverable Description *</label>
                          <span className="text-[10px] text-slate-500">Multi-line service scope / deliverables</span>
                        </div>
                        <textarea
                          rows={3}
                          value={item.description}
                          onChange={(e) => {
                            const updated = [...lineItems];
                            updated[idx].description = e.target.value;
                            setLineItems(updated);
                          }}
                          placeholder="Enter comprehensive scope of work, technical deliverables, milestone description, or product specifications..."
                          className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 placeholder:text-slate-600 focus:outline-none focus:border-sky-500 text-xs leading-relaxed resize-y"
                          required
                        />
                      </div>

                      <div className="grid grid-cols-4 gap-2.5">
                        <div>
                          <label className="block text-slate-400 mb-1">HSN / SAC *</label>
                          <input
                            type="text"
                            value={item.hsn}
                            onChange={(e) => {
                              const updated = [...lineItems];
                              updated[idx].hsn = e.target.value;
                              setLineItems(updated);
                            }}
                            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200 font-mono text-xs"
                            required
                          />
                        </div>
                        <div>
                          <label className="block text-slate-400 mb-1">Quantity *</label>
                          <input
                            type="number"
                            step="any"
                            min="0.01"
                            value={item.quantity}
                            onChange={(e) => {
                              const updated = [...lineItems];
                              updated[idx].quantity = e.target.value;
                              setLineItems(updated);
                            }}
                            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200 font-mono text-xs"
                            required
                          />
                        </div>
                        <div>
                          <label className="block text-slate-400 mb-1">Unit Price (₹) *</label>
                          <input
                            type="number"
                            step="any"
                            min="0"
                            value={item.unitPrice}
                            onChange={(e) => {
                              const updated = [...lineItems];
                              updated[idx].unitPrice = e.target.value;
                              setLineItems(updated);
                            }}
                            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200 font-mono text-xs"
                            required
                          />
                        </div>
                        <div>
                          <label className="block text-slate-400 mb-1">
                            GST Rate {!gstStatus?.has_gstin && <span className="text-[10px] text-amber-400 font-mono">(0%)</span>}
                          </label>
                          <select
                            value={item.gstRate}
                            onChange={(e) => {
                              const updated = [...lineItems];
                              updated[idx].gstRate = e.target.value;
                              setLineItems(updated);
                            }}
                            disabled={!gstStatus?.has_gstin}
                            className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1.5 text-slate-200 font-mono text-xs disabled:opacity-60 disabled:cursor-not-allowed"
                          >
                            {!gstStatus?.has_gstin ? (
                              <option value="0.00">0% (Bill of Supply)</option>
                            ) : (
                              <>
                                <option value="18.00">18% (Standard)</option>
                                <option value="12.00">12%</option>
                                <option value="5.00">5%</option>
                                <option value="28.00">28%</option>
                                <option value="0.00">0% (Nil / Exempt)</option>
                              </>
                            )}
                          </select>
                        </div>
                      </div>

                      <div className="flex justify-between items-center text-[11px] pt-1 text-slate-400 border-t border-slate-900">
                        <span>Taxable: <strong className="font-mono text-slate-200">₹{lineTaxable.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></span>
                        <span>Tax ({lineRate}%): <strong className="font-mono text-slate-200">₹{lineTax.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></span>
                        <span>Line Total: <strong className="font-mono text-sky-300">₹{lineTotal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Dynamic Tax & Double-Entry Summary */}
              <div className="p-4 bg-slate-950 rounded-xl border border-slate-800 space-y-2 text-xs">
                <div className="flex justify-between text-slate-400">
                  <span>Aggregate Taxable Value:</span>
                  <span className="font-mono text-white font-semibold">
                    ₹{computedTotals.taxableValue.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>
                    GST ({isInterstate ? `Inter-state IGST` : `Intra-state CGST + SGST`}):
                  </span>
                  <span className="font-mono text-white font-semibold">
                    ₹{computedTotals.totalTax.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="border-t border-slate-800 pt-2 flex justify-between font-bold text-emerald-400 text-sm">
                  <span>Invoice Grand Total:</span>
                  <span className="font-mono">
                    ₹{computedTotals.grandTotal.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </span>
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

      {/* E-Invoice IRN & Signed QR Modal */}
      {showEInvoiceModal && selectedEInvoice && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-5 animate-in fade-in duration-200">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-teal-500/10 rounded-lg border border-teal-500/30">
                  <QrCode className="w-5 h-5 text-teal-400" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white flex items-center gap-2">
                    NIC E-Invoice Details
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                      {selectedEInvoice.irn_status || 'ACT'} — Active
                    </span>
                  </h3>
                  <p className="text-xs text-slate-400">
                    Rule 48(4) CGST Rules — 64-character SHA-256 Invoice Reference Number
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowEInvoiceModal(false)}
                className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs">
              {/* Invoice & Ack Meta */}
              <div className="grid grid-cols-3 gap-3 p-3.5 bg-slate-950 rounded-xl border border-slate-800 font-mono">
                <div>
                  <span className="text-slate-500 block text-[10px]">Invoice Number</span>
                  <span className="text-white font-bold">{selectedEInvoice.invoice_number}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Ack Number</span>
                  <span className="text-sky-400 font-bold">{selectedEInvoice.ack_no || '112610145892001'}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Ack Timestamp</span>
                  <span className="text-slate-300">
                    {selectedEInvoice.ack_date ? new Date(selectedEInvoice.ack_date).toLocaleString('en-IN') : 'Just now'}
                  </span>
                </div>
              </div>

              {/* 64-char IRN Hash */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-slate-300 font-semibold flex items-center gap-1.5">
                    <Shield className="w-3.5 h-3.5 text-teal-400" />
                    Invoice Reference Number (IRN)
                  </span>
                  <button
                    type="button"
                    onClick={() => handleCopyIrn(selectedEInvoice.irn)}
                    className="text-[11px] text-sky-400 hover:text-sky-300 flex items-center gap-1 font-mono"
                  >
                    {copiedIrn ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                    {copiedIrn ? 'Copied' : 'Copy IRN'}
                  </button>
                </div>
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl font-mono text-[11px] text-teal-300 break-all select-all">
                  {selectedEInvoice.irn}
                </div>
              </div>

              {/* B2B Signed QR Code Payload */}
              <div className="space-y-1.5">
                <span className="text-slate-300 font-semibold block">
                  B2B Signed QR Code Payload (Offline Statutory Verification)
                </span>
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl font-mono text-[10px] text-slate-400 max-h-24 overflow-y-auto break-all select-all">
                  {selectedEInvoice.signed_qr_code}
                </div>
              </div>

              {/* Raw NIC Schema JSON */}
              {selectedEInvoice.einvoice_payload && (
                <div className="space-y-1.5">
                  <span className="text-slate-300 font-semibold block">
                    NIC Schema v1.03 Payload (GSTN Standard)
                  </span>
                  <pre className="p-3 bg-slate-950 border border-slate-800 rounded-xl font-mono text-[10px] text-slate-300 max-h-36 overflow-y-auto select-all">
                    {JSON.stringify(selectedEInvoice.einvoice_payload, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            <div className="flex justify-end pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setShowEInvoiceModal(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-xs font-semibold transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Export GSTR-1 JSON Modal */}
      {showGstr1Modal && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-4 my-8">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="font-bold text-white text-base flex items-center gap-2">
                  <Download className="w-4 h-4 text-emerald-400" />
                  Export GSTR-1 Portal JSON
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Official GSTN Offline Utility format for direct upload on gst.gov.in
                </p>
              </div>
              <button
                onClick={() => setShowGstr1Modal(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4 text-xs">
              <div className="p-3 bg-emerald-950/30 border border-emerald-500/30 rounded-xl space-y-1.5">
                <div className="flex items-center gap-2 text-emerald-300 font-semibold">
                  <CheckCircle className="w-4 h-4" />
                  <span>Statutory Coverage</span>
                </div>
                <p className="text-slate-400 text-[11px] leading-relaxed">
                  Generates schema-compliant tables: <strong>B2B (4)</strong>, <strong>B2CL (5)</strong>, <strong>B2CS (7)</strong>, <strong>CDNR (9B)</strong>, <strong>EXP (6A)</strong>, <strong>HSN Summary (12)</strong>, and <strong>Doc Issue (13)</strong>.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-400 text-[11px] mb-1 font-medium">Return Year</label>
                  <select
                    value={gstr1Year}
                    onChange={(e) => setGstr1Year(parseInt(e.target.value))}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-emerald-500"
                  >
                    {[2024, 2025, 2026, 2027, 2028].map((y) => (
                      <option key={y} value={y}>{y}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-slate-400 text-[11px] mb-1 font-medium">Return Month</label>
                  <select
                    value={gstr1Month}
                    onChange={(e) => setGstr1Month(parseInt(e.target.value))}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-emerald-500"
                  >
                    {[
                      { num: 1, name: 'January' },
                      { num: 2, name: 'February' },
                      { num: 3, name: 'March' },
                      { num: 4, name: 'April' },
                      { num: 5, name: 'May' },
                      { num: 6, name: 'June' },
                      { num: 7, name: 'July' },
                      { num: 8, name: 'August' },
                      { num: 9, name: 'September' },
                      { num: 10, name: 'October' },
                      { num: 11, name: 'November' },
                      { num: 12, name: 'December' }
                    ].map((m) => (
                      <option key={m.num} value={m.num}>{m.num.toString().padStart(2, '0')} - {m.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="p-3 bg-slate-800/60 rounded-xl border border-slate-700/50 space-y-1">
                <span className="text-[11px] text-slate-400">Target File:</span>
                <p className="font-mono text-emerald-400 font-semibold text-xs">
                  GSTR1_{gstStatus?.gstin || 'EXPORT'}_{String(gstr1Month).padStart(2, '0')}{gstr1Year}.json
                </p>
                <p className="text-[10px] text-slate-500">
                  Ready for direct upload under GSTR-1 &gt; Prepare Offline &gt; Upload on GST Portal.
                </p>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowGstr1Modal(false)}
                  className="px-3.5 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition text-xs font-medium"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={exportingGstr1}
                  onClick={handleDownloadGstr1}
                  className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs flex items-center gap-2 transition disabled:opacity-50"
                >
                  {exportingGstr1 ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Generating JSON...</span>
                    </>
                  ) : (
                    <>
                      <Download className="w-3.5 h-3.5" />
                      <span>Download GSTR-1 JSON</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

