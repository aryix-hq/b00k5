'use client';

import React, { useState, useEffect } from 'react';
import {
  Building2,
  ShieldCheck,
  CheckCircle2,
  ArrowLeft,
  Save,
  Download,
  FileText,
  UploadCloud,
  Check,
  AlertCircle,
  ExternalLink,
  Layers,
  Image as ImageIcon
} from 'lucide-react';
import Link from 'next/link';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';

interface StatutoryDoc {
  code: string;
  name: string;
  authority: string;
  purpose: string;
  category: string;
  status: 'verified' | 'pending';
  is_uploaded: boolean;
  file_size_bytes?: number;
  sha256_hash?: string;
  extracted_entities: Record<string, any>;
  can_download: boolean;
  download_url: string;
}

export default function CompanyProfileSettingsPage() {
  const [legalName, setLegalName] = useState('');
  const [tradeName, setTradeName] = useState('');
  const [cin, setCin] = useState('');
  const [pan, setPan] = useState('');
  const [tan, setTan] = useState('');
  const [gstin, setGstin] = useState('');
  const [stateCode, setStateCode] = useState('29');
  const [registeredOffice, setRegisteredOffice] = useState('');
  const [directorName, setDirectorName] = useState('');
  const [directorDin, setDirectorDin] = useState('');
  const [logoPreview, setLogoPreview] = useState<string | null>(null);

  const [logoUploading, setLogoUploading] = useState(false);
  const [statutoryDocs, setStatutoryDocs] = useState<StatutoryDoc[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [uploadingDoc, setUploadingDoc] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const getEffectiveTenantId = () => {
    if (typeof window === 'undefined') return null;
    return (
      localStorage.getItem('b00k5_active_tenant_id') ||
      localStorage.getItem('b00k5_tenant_id') ||
      localStorage.getItem('tenant_id')
    );
  };

  async function loadStatutoryStatus() {
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = getEffectiveTenantId();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/compliance/statutory-documents-status`, { headers });
      if (res.ok) {
        const data = await res.json();
        if (data.documents) setStatutoryDocs(data.documents);
        if (data.legal_name) setLegalName(data.legal_name);
        if (data.cin) setCin(data.cin);
        if (data.pan) setPan(data.pan);
        setGstin(data.gstin || '');
        setTan(data.tan || '');
        if (data.logo_url) {
          setLogoPreview(data.logo_url);
          if (typeof window !== 'undefined') {
            try { localStorage.setItem('b00k5_logo_url', data.logo_url); } catch (e) {}
          }
        }
        const dinDoc = (data.documents || []).find((d: any) => d.code === 'DIN_APPROVAL');
        if (dinDoc?.extracted_entities?.din && !String(dinDoc.extracted_entities.din).startsWith('Pending')) {
          setDirectorDin(dinDoc.extracted_entities.din);
        }
        if (dinDoc?.extracted_entities?.director_name) {
          setDirectorName(dinDoc.extracted_entities.director_name);
        }
      }
    } catch (e) {
      console.error('Failed to load statutory documents status:', e);
    } finally {
      setLoadingDocs(false);
    }
  }

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('b00k5_token');
      const tenantId = getEffectiveTenantId();
      if (token) {
        const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
        if (tenantId) headers['X-Tenant-ID'] = tenantId;

        fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/setup/company-profile`, {
          headers
        })
          .then(res => res.ok ? res.json() : null)
          .then(data => {
            if (data) {
              setGstin(data.gstin && !data.gstin.startsWith('29AABCA') ? data.gstin : '');
              setStateCode(data.state_code || '29');
              setLegalName(data.legal_name || '');
              setTradeName(data.trade_name || '');
              setCin(data.cin || '');
              setPan(data.pan || '');
              setTan(data.statutory_profile?.tan && !data.statutory_profile.tan.startsWith('BLRA12345') ? data.statutory_profile.tan : '');
              setRegisteredOffice(data.registered_office || '');

              const prof = data.statutory_profile || {};
              const pDin = prof.primary_director_din || prof.director_din || (prof.directors?.[0]?.din !== 'N/A' ? prof.directors?.[0]?.din : '');
              const pName = prof.primary_director_name || prof.director_name || prof.directors?.[0]?.name || '';
              if (pDin) setDirectorDin(pDin);
              if (pName) setDirectorName(pName);

              const dbLogo = data.logo_url || data.statutory_profile?.logo_url || null;
              if (dbLogo) {
                setLogoPreview(dbLogo);
                try { localStorage.setItem('b00k5_logo_url', dbLogo); } catch (e) {}
              } else {
                setLogoPreview(null);
                localStorage.removeItem('b00k5_logo_url');
              }

              if (data.legal_name) localStorage.setItem('b00k5_legal_name', data.legal_name);
              if (data.cin) localStorage.setItem('b00k5_cin', data.cin);
              if (data.pan) localStorage.setItem('b00k5_pan', data.pan);
              if (data.registered_office) localStorage.setItem('b00k5_registered_office', data.registered_office);
            }
          })
          .catch(() => {});
      }
    }

    loadStatutoryStatus();
  }, []);

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 2 * 1024 * 1024) {
      alert('Logo file size must be less than 2MB');
      return;
    }

    setLogoUploading(true);
    setStatusMsg(null);
    const fd = new FormData();
    fd.append('file', file);

    try {
      const token = typeof window !== 'undefined' ? (localStorage.getItem('b00k5_token') || localStorage.getItem('token')) : null;
      const tenantId = getEffectiveTenantId();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const url = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/setup/upload-logo${token ? `?token=${encodeURIComponent(token)}` : ''}${tenantId ? `&tenant_id=${encodeURIComponent(tenantId)}` : ''}`;
      const res = await fetch(url, {
        method: 'POST',
        headers,
        body: fd
      });

      if (res.ok) {
        const data = await res.json();
        setLogoPreview(data.logo_url);
        if (typeof window !== 'undefined') {
          try { localStorage.setItem('b00k5_logo_url', data.logo_url); } catch (e) {}
        }
        setStatusMsg('Company logo uploaded and updated across all letterheads and invoices!');
      } else {
        const errJson = await res.json().catch(() => null);
        alert(errJson?.detail || 'Failed to upload company logo');
      }
    } catch (err: any) {
      alert(err.message || 'Logo upload error');
    } finally {
      setLogoUploading(false);
    }
  };

  const handleRemoveLogo = async () => {
    if (!confirm('Are you sure you want to remove the company logo?')) return;
    try {
      const token = typeof window !== 'undefined' ? (localStorage.getItem('b00k5_token') || localStorage.getItem('token')) : null;
      const tenantId = getEffectiveTenantId();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const url = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/setup/remove-logo${token ? `?token=${encodeURIComponent(token)}` : ''}${tenantId ? `&tenant_id=${encodeURIComponent(tenantId)}` : ''}`;
      await fetch(url, {
        method: 'DELETE',
        headers
      });

      setLogoPreview(null);
      if (typeof window !== 'undefined') {
        localStorage.removeItem('b00k5_logo_url');
      }
      setStatusMsg('Company logo removed successfully.');
    } catch (err: any) {
      console.error('Error removing logo:', err);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setStatusMsg(null);

    try {
      const token = typeof window !== 'undefined' ? (localStorage.getItem('b00k5_token') || localStorage.getItem('token')) : null;
      const tenantId = getEffectiveTenantId();

      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const bodyPayload: Record<string, any> = {
        legal_name: legalName,
        trade_name: tradeName,
        cin,
        pan,
        gstin,
        state_code: stateCode,
        registered_office: registeredOffice,
      };
      if (logoPreview) {
        bodyPayload.logo_url = logoPreview;
      }

      await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/compliance/update-company-profile`, {
        method: 'POST',
        headers,
        body: JSON.stringify(bodyPayload)
      });

      if (typeof window !== 'undefined') {
        localStorage.setItem('b00k5_extracted_gstin', gstin);
        localStorage.setItem('b00k5_extracted_state', stateCode);
        localStorage.setItem('b00k5_legal_name', legalName);
        localStorage.setItem('b00k5_cin', cin);
      }

      setStatusMsg('Company profile and statutory master register updated successfully.');
      loadStatutoryStatus();
    } catch (err: any) {
      setStatusMsg('Profile updated locally.');
    } finally {
      setSaving(false);
    }
  };

  const handleReuploadDoc = async (docType: string, file: File) => {
    setUploadingDoc(docType);
    setStatusMsg(null);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('doc_type', docType.toLowerCase());
    
    const categoryMap: Record<string, string> = {
      'COI': 'corporate_legal',
      'MOA': 'corporate_legal',
      'AOA': 'corporate_legal',
      'INC_22': 'corporate_legal',
      'PAN': 'tax_registration',
      'TAN': 'tax_registration',
      'GST_REG06': 'tax_registration',
      'ADT_1': 'statutory_filing',
      'INC_20A': 'statutory_filing',
      'MGT_7A': 'statutory_filing',
      'AOC_4': 'statutory_filing',
      'AUDITOR_REPORT': 'statutory_filing',
      'BOARD_REPORT': 'equity_governance',
      'DIR_12': 'equity_governance',
      'DIN_APPROVAL': 'equity_governance',
      'DIR_3': 'equity_governance',
    };
    const cat = categoryMap[docType.toUpperCase()] || 'corporate_legal';
    fd.append('category', cat);

    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = getEffectiveTenantId();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/vault/smart-ingest`, {
        method: 'POST',
        headers,
        body: fd
      });

      const data = await res.json();
      if (res.ok && data.success) {
        setStatusMsg(`Successfully extracted data from ${file.name} and updated profile!`);
        loadStatutoryStatus();
      } else {
        alert(data.detail?.message || data.detail || 'Failed to parse document');
      }
    } catch (e: any) {
      alert(e.message || 'Upload error');
    } finally {
      setUploadingDoc(null);
    }
  };

  const handleDownloadLetterhead = async () => {
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = getEffectiveTenantId();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/compliance/generate-letterhead`, {
        method: 'POST',
        headers
      });

      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${legalName.replace(/\s+/g, '_')}_OFFICIAL_LETTERHEAD.pdf`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      }
    } catch (e) {
      console.error('Error generating letterhead:', e);
    }
  };

  const handleDownloadDoc = async (code: string, isExtract: boolean = false) => {
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = getEffectiveTenantId();
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/compliance/download-document/${code}?allow_extract=${isExtract ? 'true' : 'false'}`, {
        headers
      });

      if (res.ok) {
        const disposition = res.headers.get('content-disposition');
        let filename = `${legalName.replace(/\s+/g, '_')}_${code}${isExtract ? '_EXTRACT' : ''}.pdf`;
        if (disposition && disposition.includes('filename=')) {
          const match = disposition.match(/filename="?([^";]+)"?/);
          if (match && match[1]) filename = match[1];
        }
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
      } else {
        const err = await res.json().catch(() => null);
        alert(err?.detail || 'No authentic original document uploaded yet. Please upload the official certificate.');
      }
    } catch (e: any) {
      console.error('Error downloading document:', e);
      alert(e.message || 'Download error');
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Navbar />
        <main className="flex-1 overflow-y-auto p-8 max-w-6xl mx-auto w-full space-y-8">
          {/* Header */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
            <div className="flex items-center gap-3">
              <Link href="/dashboard" className="p-2 rounded-lg bg-slate-800 text-slate-400 hover:text-white transition">
                <ArrowLeft className="w-5 h-5" />
              </Link>
              <div>
                <h1 className="text-xl font-bold text-white flex items-center gap-2">
                  <Building2 className="w-5 h-5 text-sky-400" />
                  Company Statutory Master Profile &amp; Document Hub
                </h1>
                <p className="text-xs text-slate-400">
                  Legal Source of Truth with all 14 statutory filings, entity extraction, and 1-click letterhead generation
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                id="generate-letterhead-btn"
                onClick={handleDownloadLetterhead}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium shadow-sm transition text-xs font-sans"
              >
                <Download className="w-3.5 h-3.5" />
                Generate Company Letterhead (PDF)
              </button>
            </div>
          </div>

          {statusMsg && (
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{statusMsg}</span>
            </div>
          )}

          {/* Master Profile Form Card */}
          <form onSubmit={handleSave} className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <Layers className="w-4 h-4 text-sky-400" />
                1. Corporate Identity &amp; Statutory Registration Data
              </h2>
              <span className="text-[11px] font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-0.5 rounded-full flex items-center gap-1">
                <ShieldCheck className="w-3 h-3" /> Source of Truth Active
              </span>
            </div>

            {/* Company Logo Section */}
            <div className="flex flex-col sm:flex-row items-center gap-6 p-4 rounded-xl bg-slate-950/60 border border-slate-800">
              <div className="relative group shrink-0">
                {logoPreview ? (
                  <div className="relative">
                    <img
                      src={logoPreview}
                      alt="Company Logo"
                      className="w-20 h-20 object-contain rounded-xl border border-slate-700 bg-white p-1 shadow-md"
                    />
                    <button
                      type="button"
                      onClick={handleRemoveLogo}
                      className="absolute -top-2 -right-2 p-1 rounded-full bg-rose-600 hover:bg-rose-500 text-white text-[10px] shadow"
                      title="Remove Logo"
                    >
                      ✕
                    </button>
                  </div>
                ) : (
                  <div className="w-20 h-20 rounded-xl bg-slate-900 border-2 border-dashed border-slate-700 flex flex-col items-center justify-center text-slate-500 hover:border-sky-500 transition">
                    <ImageIcon className="w-6 h-6 text-slate-400" />
                    <span className="text-[10px] text-slate-400 mt-1">No Logo</span>
                  </div>
                )}
              </div>

              <div className="flex-1 space-y-1 text-center sm:text-left">
                <div className="flex items-center justify-center sm:justify-start gap-2">
                  <h3 className="text-xs font-semibold text-white">Company Logo</h3>
                  <span className="text-[10px] text-sky-400 bg-sky-950/60 border border-sky-800/50 px-2 py-0.5 rounded">
                    Included on Official Letterhead &amp; Invoices
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">
                  Accepts PNG, JPG, JPEG, SVG or WebP formats up to 2MB. Automatically rendered on letterhead and document templates.
                </p>
                <div className="pt-1 flex items-center justify-center sm:justify-start gap-2">
                  <label className={`cursor-pointer px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-medium flex items-center gap-1.5 transition ${logoUploading ? 'opacity-50 pointer-events-none' : ''}`}>
                    <UploadCloud className="w-3.5 h-3.5" />
                    <span>{logoUploading ? 'Uploading...' : (logoPreview ? 'Change Logo' : 'Upload Company Logo')}</span>
                    <input
                      type="file"
                      id="logo-upload-input"
                      accept="image/*"
                      className="hidden"
                      disabled={logoUploading}
                      onChange={handleLogoUpload}
                    />
                  </label>
                  {logoPreview && !logoUploading && (
                    <button
                      type="button"
                      onClick={handleRemoveLogo}
                      className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition"
                    >
                      Remove
                    </button>
                  )}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center justify-between">
                  <span>Legal Entity Name</span>
                  <span className="text-[10px] text-sky-400 font-mono">🔒 Upload COI to edit</span>
                </label>
                <input
                  type="text"
                  id="legal-name-input"
                  value={legalName}
                  readOnly
                  title="Legal Entity Name is bound to Certificate of Incorporation. Upload COI to update."
                  onChange={(e) => setLegalName(e.target.value)}
                  className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-white text-xs font-medium focus:outline-none cursor-not-allowed opacity-90"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Trade Name / Brand</label>
                <input
                  type="text"
                  id="trade-name-input"
                  value={tradeName}
                  onChange={(e) => setTradeName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white text-xs font-medium focus:outline-none focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center justify-between">
                  <span>CIN (21 Digits)</span>
                  <span className="text-[10px] text-sky-400 font-mono">🔒 Upload COI to edit</span>
                </label>
                <input
                  type="text"
                  id="cin-input"
                  value={cin}
                  readOnly
                  title="CIN is bound to Certificate of Incorporation. Upload COI to update."
                  onChange={(e) => setCin(e.target.value)}
                  className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono text-xs font-bold text-sky-400 focus:outline-none cursor-not-allowed opacity-90"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center justify-between">
                  <span>PAN (10 Characters)</span>
                  <span className="text-[10px] text-amber-400 font-mono">🔒 Upload PAN to edit</span>
                </label>
                <input
                  type="text"
                  id="pan-input"
                  value={pan}
                  readOnly
                  title="PAN is bound to Permanent Account Number Card. Upload PAN Card to update."
                  onChange={(e) => setPan(e.target.value)}
                  className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono text-xs font-bold text-amber-300 focus:outline-none cursor-not-allowed opacity-90"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center justify-between">
                  <span>TAN (10 Characters)</span>
                  <span className={`text-[10px] font-mono ${statutoryDocs.some(d => d.code === 'TAN' && d.status === 'verified') ? 'text-purple-400 font-semibold' : 'text-slate-500'}`}>
                    {statutoryDocs.some(d => d.code === 'TAN' && d.status === 'verified') ? '✓ Verified' : '🔒 Upload TAN Certificate to activate'}
                  </span>
                </label>
                <input
                  type="text"
                  id="tan-input"
                  value={tan}
                  placeholder="Upload TAN Certificate to activate"
                  onChange={(e) => setTan(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono text-xs font-bold text-purple-300 focus:outline-none focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center justify-between">
                  <span>GSTIN (15 Digits)</span>
                  <span className={`text-[10px] font-mono ${statutoryDocs.some(d => d.code === 'GST_REG06' && d.status === 'verified') ? 'text-emerald-400 font-semibold' : 'text-slate-500'}`}>
                    {statutoryDocs.some(d => d.code === 'GST_REG06' && d.status === 'verified') ? '✓ Verified' : '🔒 Upload Form REG-06 to activate'}
                  </span>
                </label>
                <input
                  type="text"
                  id="gstin-input"
                  value={gstin}
                  placeholder="Upload Form REG-06 to activate"
                  onChange={(e) => setGstin(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono text-xs font-bold text-emerald-400 focus:outline-none focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center justify-between">
                  <span>Authorized Director Name</span>
                  <span className="text-[10px] text-sky-400 font-mono">🔒 Upload SPICe+ Part B / DIR-3 to verify</span>
                </label>
                <input
                  type="text"
                  id="director-name-input"
                  value={directorName}
                  readOnly
                  placeholder="Upload SPICe+ Part B / DIR-3 DIN Approval Letter"
                  title="Director Name is bound to official MCA SPICe+ Part B (INC-32) or Form DIR-3 DIN Approval Letter."
                  className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-white text-xs font-medium focus:outline-none cursor-not-allowed opacity-90"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center justify-between">
                  <span>Director Identification Number (DIN)</span>
                  <span className={`text-[10px] font-mono ${directorDin ? 'text-emerald-400 font-semibold' : 'text-slate-500'}`}>
                    {directorDin ? '✓ Verified via SPICe+ Part B / DIR-3' : '🔒 Upload SPICe+ Part B / DIR-3 to verify'}
                  </span>
                </label>
                <input
                  type="text"
                  id="director-din-input"
                  value={directorDin}
                  readOnly
                  placeholder="Upload SPICe+ Part B / DIR-3 DIN Approval Letter"
                  title="DIN is verified from official MCA SPICe+ Part B (INC-32) or Form DIR-3 DIN Approval Letter."
                  className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono text-xs font-bold text-sky-400 focus:outline-none cursor-not-allowed opacity-90"
                />
              </div>

              <div className="sm:col-span-2">
                <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center justify-between">
                  <span>Registered Office Address</span>
                  <span className="text-[10px] text-sky-400 font-mono">🔒 Upload INC-22 to edit</span>
                </label>
                <input
                  type="text"
                  id="address-input"
                  value={registeredOffice}
                  readOnly
                  title="Registered Office Address is bound to Form INC-22. Upload Form INC-22 to update."
                  onChange={(e) => setRegisteredOffice(e.target.value)}
                  className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-white text-xs font-medium focus:outline-none cursor-not-allowed opacity-90"
                  placeholder="Street, City, PIN Code, State"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">State &amp; RoC Jurisdiction</label>
                <select
                  id="state-code-select"
                  value={stateCode}
                  onChange={(e) => setStateCode(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-medium text-xs focus:outline-none cursor-pointer"
                >
                  <option value="29">29 - Karnataka (RoC Bangalore)</option>
                  <option value="27">27 - Maharashtra (RoC Mumbai/Pune)</option>
                  <option value="07">07 - Delhi (RoC Delhi)</option>
                  <option value="33">33 - Tamil Nadu (RoC Chennai)</option>
                  <option value="36">36 - Telangana (RoC Hyderabad)</option>
                </select>
              </div>
            </div>

            {/* Quick Re-upload Document Pills */}
            <div className="pt-2 border-t border-slate-800/80 space-y-2">
              <span className="text-xs text-slate-400 font-medium block">
                Update Master Details via Official Statutory Document Extraction:
              </span>
              <div className="flex flex-wrap gap-2.5">
                <label className="cursor-pointer px-3 py-1.5 rounded-lg bg-sky-950/80 hover:bg-sky-900/80 border border-sky-800/60 text-xs font-medium text-sky-200 flex items-center gap-1.5 transition">
                  <UploadCloud className="w-3.5 h-3.5 text-sky-400" />
                  <span>{uploadingDoc === 'DIN_APPROVAL' ? 'Extracting...' : 'Upload SPICe+ Part B / DIR-3 DIN Approval Letter'}</span>
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && handleReuploadDoc('DIN_APPROVAL', e.target.files[0])}
                  />
                </label>

                <label className="cursor-pointer px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-medium text-slate-200 flex items-center gap-1.5 transition">
                  <UploadCloud className="w-3.5 h-3.5 text-sky-400" />
                  <span>{uploadingDoc === 'PAN' ? 'Extracting...' : 'Re-upload PAN Card'}</span>
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && handleReuploadDoc('PAN', e.target.files[0])}
                  />
                </label>

                <label className="cursor-pointer px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-medium text-slate-200 flex items-center gap-1.5 transition">
                  <UploadCloud className="w-3.5 h-3.5 text-sky-400" />
                  <span>{uploadingDoc === 'COI' ? 'Extracting...' : 'Re-upload COI (CIN & Name)'}</span>
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && handleReuploadDoc('COI', e.target.files[0])}
                  />
                </label>

                <label className="cursor-pointer px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-medium text-slate-200 flex items-center gap-1.5 transition">
                  <UploadCloud className="w-3.5 h-3.5 text-sky-400" />
                  <span>{uploadingDoc === 'INC_22' ? 'Extracting...' : 'Re-upload Form INC-22 (Address)'}</span>
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && handleReuploadDoc('INC_22', e.target.files[0])}
                  />
                </label>

                <label className="cursor-pointer px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-medium text-slate-200 flex items-center gap-1.5 transition">
                  <UploadCloud className="w-3.5 h-3.5 text-sky-400" />
                  <span>{uploadingDoc === 'ADT_1' ? 'Extracting...' : 'Upload Form ADT-1 (Auditor)'}</span>
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && handleReuploadDoc('ADT_1', e.target.files[0])}
                  />
                </label>

                <label className="cursor-pointer px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-medium text-slate-200 flex items-center gap-1.5 transition">
                  <UploadCloud className="w-3.5 h-3.5 text-sky-400" />
                  <span>{uploadingDoc === 'INC_20A' ? 'Extracting...' : 'Upload Form INC-20A (Commencement)'}</span>
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && handleReuploadDoc('INC_20A', e.target.files[0])}
                  />
                </label>

                <label className="cursor-pointer px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-medium text-slate-200 flex items-center gap-1.5 transition">
                  <UploadCloud className="w-3.5 h-3.5 text-sky-400" />
                  <span>{uploadingDoc === 'GST_REG06' ? 'Extracting...' : 'Upload GST REG-06'}</span>
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg"
                    className="hidden"
                    onChange={(e) => e.target.files?.[0] && handleReuploadDoc('GST_REG06', e.target.files[0])}
                  />
                </label>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="submit"
                id="save-profile-btn"
                disabled={saving}
                className="flex items-center gap-2 px-6 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 font-semibold text-white text-xs shadow-lg shadow-sky-600/30 transition disabled:opacity-50"
              >
                <Save className="w-4 h-4" />
                {saving ? 'Saving Profile...' : 'Save Profile Changes'}
              </button>
            </div>
          </form>

          {/* Section 2: Statutory Documents Matrix (All 14 Documents) */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-base font-bold text-white flex items-center gap-2">
                  <FileText className="w-5 h-5 text-sky-400" />
                  2. Mandatory Statutory Documents Matrix (14 Corporate Filings)
                </h2>
                <p className="text-xs text-slate-400">
                  Live verification status, extracted entities, and one-click downloadable extracts
                </p>
              </div>
              <span className="text-xs font-mono text-slate-400">
                Verified: {statutoryDocs.filter(d => d.status === 'verified').length} / {statutoryDocs.length || 14}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {statutoryDocs.map((doc) => (
                <div
                  key={doc.code}
                  className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3 hover:border-slate-700 transition"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-sky-400 bg-sky-950/60 px-2 py-0.5 rounded border border-sky-800/50">
                          {doc.code}
                        </span>
                        <h3 className="font-semibold text-white text-xs">{doc.name}</h3>
                      </div>
                      <p className="text-[11px] text-slate-500 mt-1 font-sans">{doc.authority}</p>
                    </div>

                    <span
                      className={`text-[10px] font-mono uppercase px-2 py-0.5 rounded-full font-semibold flex items-center gap-1 ${
                        doc.status === 'verified'
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                          : 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                      }`}
                    >
                      {doc.status === 'verified' ? (
                        <>
                          <Check className="w-3 h-3" /> Verified
                        </>
                      ) : (
                        'Pending'
                      )}
                    </span>
                  </div>

                  <p className="text-xs text-slate-400 line-clamp-2">{doc.purpose}</p>

                  {/* Extracted Key Metadata */}
                  {Object.keys(doc.extracted_entities || {}).length > 0 && (
                    <div className="p-2.5 rounded-lg bg-slate-950/80 border border-slate-800/80 font-mono text-[11px] text-slate-300 space-y-1">
                      {Object.entries(doc.extracted_entities).map(([k, v]) => (
                        <div key={k} className="flex justify-between items-start gap-2">
                          <span className="text-slate-500 capitalize shrink-0">{k.replace(/_/g, ' ')}:</span>
                          <span className="text-white font-semibold text-right break-words max-w-[260px]">{String(v)}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[11px] text-slate-500 font-mono">
                      {doc.sha256_hash ? `SHA: ${doc.sha256_hash.substring(0, 8)}...` : 'Format: MCA / PDF'}
                    </span>

                    <div className="flex items-center gap-2">
                      <label className="cursor-pointer flex items-center gap-1 px-2.5 py-1.5 rounded-lg bg-sky-950/80 hover:bg-sky-900/80 text-sky-300 text-xs font-medium border border-sky-800/60 transition">
                        <UploadCloud className="w-3.5 h-3.5 text-sky-400" />
                        <span>{uploadingDoc === doc.code ? 'Extracting...' : 'Upload'}</span>
                        <input
                          type="file"
                          accept=".pdf,.png,.jpg,.jpeg"
                          className="hidden"
                          onChange={(e) => e.target.files?.[0] && handleReuploadDoc(doc.code, e.target.files[0])}
                        />
                      </label>

                      {doc.sha256_hash ? (
                        <button
                          type="button"
                          onClick={() => handleDownloadDoc(doc.code, false)}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold border border-sky-500 shadow-sm transition"
                          title="Download authentic original uploaded binary file from MinIO"
                        >
                          <Download className="w-3.5 h-3.5" />
                          Download Original
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => handleDownloadDoc(doc.code, true)}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium border border-slate-700 transition"
                          title="Original not uploaded. Click to generate certified statutory extract."
                        >
                          <Download className="w-3.5 h-3.5 text-slate-400" />
                          Download Extract
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
