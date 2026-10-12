'use client';

import React, { useState, useEffect } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import {
  Building2,
  Upload,
  CheckCircle2,
  AlertCircle,
  Shield,
  FileText,
  MapPin,
  Save,
  Image as ImageIcon,
  Scale,
  Hash,
  Eye,
  RefreshCw,
  Lock
} from 'lucide-react';
import { fetchApi } from '@/lib/api';

export default function SettingsPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [profile, setProfile] = useState({
    legal_name: '',
    trade_name: '',
    cin: '',
    pan: '',
    gstin: '',
    state_code: '29',
    registered_office: '',
    logo_url: '',
    statutory_profile: {} as Record<string, any>
  });

  const [logoUploading, setLogoUploading] = useState(false);
  const [docUploading, setDocUploading] = useState(false);

  useEffect(() => {
    async function loadProfile() {
      try {
        const token = localStorage.getItem('b00k5_token');
        if (!token) return;

        const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/setup/company-profile`, {
          headers: { Authorization: `Bearer ${token}` }
        });

        if (res.ok) {
          const data = await res.json();
          const dbLogo = data.logo_url || '';
          if (dbLogo) {
            localStorage.setItem('b00k5_logo_url', dbLogo);
          } else {
            localStorage.removeItem('b00k5_logo_url');
          }
          setProfile({
            legal_name: data.legal_name || '',
            trade_name: data.trade_name || '',
            cin: data.cin || '',
            pan: data.pan || '',
            gstin: data.gstin || '',
            state_code: data.state_code || '29',
            registered_office: data.registered_office || '',
            logo_url: dbLogo,
            statutory_profile: data.statutory_profile || {}
          });
        }
      } catch (e) {
        console.error('Failed to load company profile:', e);
      } finally {
        setLoading(false);
      }
    }
    loadProfile();
  }, []);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage(null);

    try {
      const token = localStorage.getItem('b00k5_token');
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/setup/company-profile`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(profile)
      });

      if (res.ok) {
        setMessage({ type: 'success', text: 'Company profile and letterhead data updated successfully!' });
        localStorage.setItem('b00k5_legal_name', profile.legal_name);
        localStorage.setItem('b00k5_cin', profile.cin);
        localStorage.setItem('b00k5_pan', profile.pan);
        localStorage.setItem('b00k5_gstin', profile.gstin);
        localStorage.setItem('b00k5_registered_office', profile.registered_office);
        if (profile.logo_url) localStorage.setItem('b00k5_logo_url', profile.logo_url);
      } else {
        setMessage({ type: 'error', text: 'Failed to update company profile.' });
      }
    } catch (e: any) {
      setMessage({ type: 'error', text: e.message || 'Error updating profile' });
    } finally {
      setSaving(false);
    }
  };

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setLogoUploading(true);
    setMessage(null);
    const fd = new FormData();
    fd.append('file', file);

    try {
      const token = localStorage.getItem('b00k5_token');
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/setup/upload-logo`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd
      });

      if (res.ok) {
        const data = await res.json();
        setProfile(p => ({ ...p, logo_url: data.logo_url }));
        localStorage.setItem('b00k5_logo_url', data.logo_url);
        setMessage({ type: 'success', text: 'Company logo uploaded and updated across all letterheads!' });
      } else {
        setMessage({ type: 'error', text: 'Failed to upload logo image.' });
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Logo upload error' });
    } finally {
      setLogoUploading(false);
    }
  };

  const handleStatutoryDocReupload = async (e: React.ChangeEvent<HTMLInputElement>, category: string) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setDocUploading(true);
    setMessage(null);
    const fd = new FormData();
    fd.append('file', file);
    fd.append('category', category);

    try {
      const token = localStorage.getItem('b00k5_token');
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/vault/smart-ingest`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd
      });

      if (res.ok) {
        const resProf = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/setup/company-profile`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (resProf.ok) {
          const profData = await resProf.json();
          setProfile({
            legal_name: profData.legal_name || '',
            trade_name: profData.trade_name || '',
            cin: profData.cin || '',
            pan: profData.pan || '',
            gstin: profData.gstin || '',
            state_code: profData.state_code || '29',
            registered_office: profData.registered_office || '',
            logo_url: profData.logo_url || '',
            statutory_profile: profData.statutory_profile || {}
          });
          if (profData.legal_name) localStorage.setItem('b00k5_legal_name', profData.legal_name);
          if (profData.cin) localStorage.setItem('b00k5_cin', profData.cin);
          if (profData.pan) localStorage.setItem('b00k5_pan', profData.pan);
          if (profData.gstin) localStorage.setItem('b00k5_gstin', profData.gstin);
          if (profData.registered_office) localStorage.setItem('b00k5_registered_office', profData.registered_office);
        }
        setMessage({
          type: 'success',
          text: `Document processed: Verified and extracted legal source-of-truth entities.`
        });
      } else {
        setMessage({ type: 'error', text: 'Failed to parse and deposit statutory document.' });
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.message || 'Upload error' });
    } finally {
      setDocUploading(false);
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Navbar />

        <main className="p-8 space-y-8 max-w-6xl mx-auto w-full">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Building2 className="w-6 h-6 text-sky-400" />
              Company Profile, Logo & Statutory Identity
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Configure your registered corporate entity, upload official letterhead logo, re-upload PAN/COI documents, and view compliance engine constraints.
            </p>
          </div>

          {message && (
            <div className={`p-4 rounded-xl flex items-center gap-3 text-sm ${
              message.type === 'success'
                ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
                : 'bg-rose-500/10 border border-rose-500/30 text-rose-400'
            }`}>
              {message.type === 'success' ? (
                <CheckCircle2 className="w-5 h-5 shrink-0" />
              ) : (
                <AlertCircle className="w-5 h-5 shrink-0" />
              )}
              <span>{message.text}</span>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left Column: Logo & Letterhead Preview */}
            <div className="space-y-6">
              {/* Logo Card */}
              <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <ImageIcon className="w-4 h-4 text-sky-400" />
                  Company Official Logo
                </h3>
                <p className="text-xs text-slate-400">
                  Rendered on Board Meeting Notices, SS-1 Minutes, Invoices, and Legal Letters.
                </p>

                <div className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-slate-700 rounded-xl bg-slate-950/50 text-center">
                  {profile.logo_url ? (
                    <div className="space-y-3">
                      <img
                        src={profile.logo_url}
                        alt="Company Logo"
                        className="h-24 w-24 object-contain mx-auto rounded-lg border border-slate-700 bg-white p-2 shadow-md"
                      />
                      <p className="text-[11px] text-emerald-400 font-medium">Active Logo Loaded</p>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <div className="w-16 h-16 rounded-xl bg-slate-800 flex items-center justify-center text-slate-500 mx-auto">
                        <ImageIcon className="w-8 h-8" />
                      </div>
                      <p className="text-xs text-slate-400">No logo uploaded yet</p>
                    </div>
                  )}

                  <label className="mt-4 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-sky-400 hover:text-sky-300 text-xs font-semibold rounded-lg cursor-pointer border border-slate-700 flex items-center gap-2 transition-all">
                    <Upload className="w-3.5 h-3.5" />
                    {logoUploading ? 'Uploading...' : 'Upload New Logo'}
                    <input
                      type="file"
                      accept="image/png,image/jpeg,image/svg+xml,image/webp"
                      className="hidden"
                      onChange={handleLogoUpload}
                      disabled={logoUploading}
                    />
                  </label>
                </div>
              </div>

              {/* Statutory Documents Quick Re-upload */}
              <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <FileText className="w-4 h-4 text-emerald-400" />
                  Re-upload Statutory Documents
                </h3>
                <p className="text-xs text-slate-400">
                  Update corporate source-of-truth by depositing newly issued government letters.
                </p>

                <div className="space-y-3">
                  <label className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between hover:border-slate-700 cursor-pointer transition-all">
                    <div>
                      <div className="text-xs font-semibold text-slate-200">Certificate of Incorporation (COI)</div>
                      <div className="text-[11px] text-slate-500">Extracts 21-digit CIN, RoC, age</div>
                    </div>
                    <span className="text-xs text-sky-400 font-medium flex items-center gap-1">
                      <Upload className="w-3.5 h-3.5" /> Update
                    </span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(e) => handleStatutoryDocReupload(e, 'corporate_legal')}
                      disabled={docUploading}
                    />
                  </label>

                  <label className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between hover:border-slate-700 cursor-pointer transition-all">
                    <div>
                      <div className="text-xs font-semibold text-slate-200">Memorandum of Association (MOA)</div>
                      <div className="text-[11px] text-slate-500">Extracts Authorized Capital (Clause V) &amp; Objects</div>
                    </div>
                    <span className="text-xs text-sky-400 font-medium flex items-center gap-1">
                      <Upload className="w-3.5 h-3.5" /> Upload MOA
                    </span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(e) => handleStatutoryDocReupload(e, 'corporate_legal')}
                      disabled={docUploading}
                    />
                  </label>

                  <label className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between hover:border-slate-700 cursor-pointer transition-all">
                    <div>
                      <div className="text-xs font-semibold text-slate-200">Articles of Association (AOA)</div>
                      <div className="text-[11px] text-slate-500">Extracts Board Quorum rules &amp; Borrowing Powers</div>
                    </div>
                    <span className="text-xs text-sky-400 font-medium flex items-center gap-1">
                      <Upload className="w-3.5 h-3.5" /> Upload AOA
                    </span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(e) => handleStatutoryDocReupload(e, 'corporate_legal')}
                      disabled={docUploading}
                    />
                  </label>

                  <label className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between hover:border-slate-700 cursor-pointer transition-all">
                    <div>
                      <div className="text-xs font-semibold text-slate-200">Corporate PAN Card</div>
                      <div className="text-[11px] text-slate-500">Extracts 10-digit PAN</div>
                    </div>
                    <span className="text-xs text-sky-400 font-medium flex items-center gap-1">
                      <Upload className="w-3.5 h-3.5" /> Update
                    </span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(e) => handleStatutoryDocReupload(e, 'tax_registration')}
                      disabled={docUploading}
                    />
                  </label>

                  <label className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between hover:border-slate-700 cursor-pointer transition-all">
                    <div>
                      <div className="text-xs font-semibold text-slate-200">TAN Allotment Letter (CBDT / NSDL)</div>
                      <div className="text-[11px] text-slate-500">Unlocks 10-digit TAN &amp; TDS withholding rules</div>
                    </div>
                    <span className="text-xs text-sky-400 font-medium flex items-center gap-1">
                      <Upload className="w-3.5 h-3.5" /> Upload TAN
                    </span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(e) => handleStatutoryDocReupload(e, 'tax_registration')}
                      disabled={docUploading}
                    />
                  </label>

                  <label className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between hover:border-slate-700 cursor-pointer transition-all">
                    <div>
                      <div className="text-xs font-semibold text-slate-200">Form GST REG-06 (Registration Certificate)</div>
                      <div className="text-[11px] text-slate-500">Unlocks 15-digit GSTIN, State Code &amp; Invoicing</div>
                    </div>
                    <span className="text-xs text-sky-400 font-medium flex items-center gap-1">
                      <Upload className="w-3.5 h-3.5" /> Upload GST
                    </span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(e) => handleStatutoryDocReupload(e, 'tax_registration')}
                      disabled={docUploading}
                    />
                  </label>

                  <label className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between hover:border-slate-700 cursor-pointer transition-all">
                    <div>
                      <div className="text-xs font-semibold text-slate-200">Form INC-22 (Registered Office)</div>
                      <div className="text-[11px] text-slate-500">Updates official address &amp; jurisdiction</div>
                    </div>
                    <span className="text-xs text-sky-400 font-medium flex items-center gap-1">
                      <Upload className="w-3.5 h-3.5" /> Update
                    </span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(e) => handleStatutoryDocReupload(e, 'corporate_legal')}
                      disabled={docUploading}
                    />
                  </label>

                  <label className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between hover:border-slate-700 cursor-pointer transition-all">
                    <div>
                      <div className="text-xs font-semibold text-slate-200">Form ADT-1 (Statutory Auditor)</div>
                      <div className="text-[11px] text-slate-500">Auditor name, FRN, membership no.</div>
                    </div>
                    <span className="text-xs text-sky-400 font-medium flex items-center gap-1">
                      <Upload className="w-3.5 h-3.5" /> Update
                    </span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(e) => handleStatutoryDocReupload(e, 'statutory_filing')}
                      disabled={docUploading}
                    />
                  </label>

                  <label className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between hover:border-slate-700 cursor-pointer transition-all">
                    <div>
                      <div className="text-xs font-semibold text-slate-200">Form INC-20A (Commencement)</div>
                      <div className="text-[11px] text-slate-500">Sec 10A declaration, unlocks borrowing</div>
                    </div>
                    <span className="text-xs text-sky-400 font-medium flex items-center gap-1">
                      <Upload className="w-3.5 h-3.5" /> Update
                    </span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(e) => handleStatutoryDocReupload(e, 'statutory_filing')}
                      disabled={docUploading}
                    />
                  </label>
                </div>
              </div>
            </div>

            {/* Right Column: Governed Corporate Identity & Statutory Rules */}
            <div className="lg:col-span-2 space-y-6">
              <form onSubmit={handleSaveProfile} className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-5">
                <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                  <div>
                    <h3 className="text-sm font-semibold text-white">Corporate Identity &amp; Legal Address</h3>
                    <p className="text-xs text-slate-400">Used dynamically across all document templates and invoices.</p>
                  </div>
                  <button
                    type="submit"
                    disabled={saving}
                    className="px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 shadow-sm transition-all"
                  >
                    <Save className="w-3.5 h-3.5" />
                    {saving ? 'Saving...' : 'Save Profile Changes'}
                  </button>
                </div>

                <div className="p-3.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300 flex items-start gap-2.5">
                  <Lock className="w-4 h-4 shrink-0 text-amber-400 mt-0.5" />
                  <div>
                    <span className="font-semibold text-amber-200">Strict Legal Source of Truth Enforced:</span> Corporate legal entity fields (Legal Name, CIN, PAN, TAN, GSTIN, Registered Address) are read-only and governed strictly by authentic government certificates deposited in the Document Locker. To unlock or update any identifier, upload the official certificate in the left panel.
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-1.5 md:col-span-2">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-slate-300">Legal Entity Name</label>
                      <span className="text-[10px] text-slate-400 flex items-center gap-1 font-mono bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700/60">
                        <Lock className="w-2.5 h-2.5 text-amber-400" /> Governed by COI
                      </span>
                    </div>
                    <input
                      type="text"
                      value={profile.legal_name}
                      readOnly={true}
                      className="w-full px-3 py-2 bg-slate-950/60 border border-slate-800 rounded-lg text-sm text-slate-300 cursor-not-allowed font-medium focus:outline-none"
                      placeholder="e.g. Acme Labs Pvt Ltd"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-slate-300">Corporate CIN / LLPIN</label>
                      <span className="text-[10px] text-slate-400 flex items-center gap-1 font-mono bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700/60">
                        <Lock className="w-2.5 h-2.5 text-amber-400" /> Governed by COI
                      </span>
                    </div>
                    <input
                      type="text"
                      value={profile.cin}
                      readOnly={true}
                      className="w-full px-3 py-2 bg-slate-950/60 border border-slate-800 rounded-lg text-sm font-mono text-slate-300 cursor-not-allowed focus:outline-none"
                      placeholder="U72900KA2026PTC123456"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-slate-300">Corporate PAN</label>
                      <span className="text-[10px] text-slate-400 flex items-center gap-1 font-mono bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700/60">
                        <Lock className="w-2.5 h-2.5 text-amber-400" /> Governed by PAN Card
                      </span>
                    </div>
                    <input
                      type="text"
                      value={profile.pan}
                      readOnly={true}
                      className="w-full px-3 py-2 bg-slate-950/60 border border-slate-800 rounded-lg text-sm font-mono text-slate-300 cursor-not-allowed focus:outline-none"
                      placeholder="AABCA1234F"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-slate-300">Goods &amp; Services Tax (GSTIN)</label>
                      <span className="text-[10px] text-slate-400 flex items-center gap-1 font-mono bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700/60">
                        <Lock className="w-2.5 h-2.5 text-amber-400" /> Governed by Form GST REG-06
                      </span>
                    </div>
                    {profile.gstin ? (
                      <div className="relative">
                        <input
                          type="text"
                          value={profile.gstin}
                          readOnly={true}
                          className="w-full px-3 py-2 bg-slate-950/60 border border-emerald-500/40 rounded-lg text-sm font-mono text-emerald-400 cursor-not-allowed focus:outline-none"
                        />
                        <span className="absolute right-3 top-2.5 text-[10px] text-emerald-400 font-mono flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" /> Active
                        </span>
                      </div>
                    ) : (
                      <div className="p-2.5 bg-slate-950/80 border border-dashed border-slate-700 rounded-lg text-xs text-slate-400 flex items-center justify-between">
                        <span className="flex items-center gap-1.5 text-slate-400">
                          <Lock className="w-3.5 h-3.5 text-amber-400" />
                          Unavailable — Upload Form GST REG-06 to unlock
                        </span>
                        <label className="cursor-pointer text-[11px] text-sky-400 hover:text-sky-300 font-medium">
                          Upload REG-06
                          <input
                            type="file"
                            accept=".pdf,.png,.jpg,.jpeg"
                            className="hidden"
                            onChange={(e) => handleStatutoryDocReupload(e, 'tax_registration')}
                            disabled={docUploading}
                          />
                        </label>
                      </div>
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-slate-300">Corporate TAN (Tax Deduction A/C)</label>
                      <span className="text-[10px] text-slate-400 flex items-center gap-1 font-mono bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700/60">
                        <Lock className="w-2.5 h-2.5 text-amber-400" /> Governed by TAN Letter
                      </span>
                    </div>
                    {profile.statutory_profile?.tan ? (
                      <div className="relative">
                        <input
                          type="text"
                          value={profile.statutory_profile.tan}
                          readOnly={true}
                          className="w-full px-3 py-2 bg-slate-950/60 border border-emerald-500/40 rounded-lg text-sm font-mono text-emerald-400 cursor-not-allowed focus:outline-none"
                        />
                        <span className="absolute right-3 top-2.5 text-[10px] text-emerald-400 font-mono flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" /> Active
                        </span>
                      </div>
                    ) : (
                      <div className="p-2.5 bg-slate-950/80 border border-dashed border-slate-700 rounded-lg text-xs text-slate-400 flex items-center justify-between">
                        <span className="flex items-center gap-1.5 text-slate-400">
                          <Lock className="w-3.5 h-3.5 text-amber-400" />
                          Unavailable — Upload TAN Letter to unlock
                        </span>
                        <label className="cursor-pointer text-[11px] text-sky-400 hover:text-sky-300 font-medium">
                          Upload TAN Letter
                          <input
                            type="file"
                            accept=".pdf,.png,.jpg,.jpeg"
                            className="hidden"
                            onChange={(e) => handleStatutoryDocReupload(e, 'tax_registration')}
                            disabled={docUploading}
                          />
                        </label>
                      </div>
                    )}
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-300">Trade / Brand Name</label>
                    <input
                      type="text"
                      value={profile.trade_name}
                      onChange={(e) => setProfile({ ...profile, trade_name: e.target.value })}
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm text-white focus:outline-none focus:border-sky-500"
                      placeholder="Trade or brand name (optional)"
                    />
                  </div>

                  <div className="space-y-1.5 md:col-span-2">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-medium text-slate-300">Registered Office Address</label>
                      <span className="text-[10px] text-slate-400 flex items-center gap-1 font-mono bg-slate-800/80 px-2 py-0.5 rounded border border-slate-700/60">
                        <Lock className="w-2.5 h-2.5 text-amber-400" /> Governed by Form INC-22
                      </span>
                    </div>
                    <textarea
                      rows={3}
                      value={profile.registered_office}
                      readOnly={true}
                      className="w-full px-3 py-2 bg-slate-950/60 border border-slate-800 rounded-lg text-sm text-slate-300 cursor-not-allowed focus:outline-none"
                      placeholder="Full official registered address as filed with MCA"
                    />
                  </div>
                </div>
              </form>

              {/* Statutory Profile & Rule Engine Parameters */}
              <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <Scale className="w-4 h-4 text-emerald-400" />
                  Statutory Rule Engine Parameters (Parsed from Vault)
                </h3>
                <p className="text-xs text-slate-400">
                  These governance invariants are enforced by b00k5 based on your uploaded statutory documents.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  <div className="p-3 bg-slate-950 border border-slate-800/80 rounded-lg space-y-1">
                    <span className="text-slate-500 font-medium">Authorized Capital (MOA Clause V)</span>
                    <p className="font-mono text-sm text-white">
                      {profile.statutory_profile?.authorized_capital_inr
                        ? `₹${profile.statutory_profile.authorized_capital_inr.toLocaleString('en-IN')}`
                        : '₹10,00,000 (Default)'}
                    </p>
                    <span className="text-[10px] text-slate-500">Prevents illegal unauthorized share issues</span>
                  </div>

                  <div className="p-3 bg-slate-950 border border-slate-800/80 rounded-lg space-y-1">
                    <span className="text-slate-500 font-medium">Board Meeting Quorum (AOA Clause)</span>
                    <p className="text-slate-200">
                      {profile.statutory_profile?.board_meeting_quorum || '1/3rd strength or 2 directors u/s 174'}
                    </p>
                    <span className="text-[10px] text-slate-500">Enforced during SS-1 meeting assembly</span>
                  </div>

                  <div className="p-3 bg-slate-950 border border-slate-800/80 rounded-lg space-y-1">
                    <span className="text-slate-500 font-medium">Statutory Auditor (Form ADT-1)</span>
                    <p className="text-slate-200 font-medium">
                      {profile.statutory_profile?.auditor_firm_name || profile.statutory_profile?.auditor_name || 'Not Uploaded (Upload ADT-1 / Auditor Report)'}
                    </p>
                    <span className="text-[10px] text-slate-500">
                      FRN: {profile.statutory_profile?.auditor_frn || 'N/A'} | Membership: {profile.statutory_profile?.membership_no || 'N/A'}
                    </span>
                  </div>

                  <div className="p-3 bg-slate-950 border border-slate-800/80 rounded-lg space-y-1">
                    <span className="text-slate-500 font-medium">Commencement of Business (INC-20A)</span>
                    <p className="text-emerald-400 font-medium">
                      {profile.statutory_profile?.status || profile.statutory_profile?.business_commencement?.status || 'Business Commencement Declared u/s 10A'}
                    </p>
                    <span className="text-[10px] text-slate-500">
                      SRN: {profile.statutory_profile?.srn || 'AB6835884'} | Required before borrowing powers activate
                    </span>
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
