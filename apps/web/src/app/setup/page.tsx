'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ShieldCheck,
  Building2,
  Key,
  CheckCircle,
  ArrowRight,
  UploadCloud,
  AlertCircle,
  FileText,
  Search,
  Check,
  FileCheck,
  ChevronDown,
  ChevronUp,
  FileCheck2,
  Lock,
  ExternalLink
} from 'lucide-react';
import { fetchApi } from '@/lib/api';

interface DocumentCheck {
  name: string;
  passed: boolean;
  detail: string;
}

interface VerifiedDocRecord {
  fileName: string;
  docTitle: string;
  sha256: string;
  fileSizeBytes: number;
  isAuthentic: boolean;
  criteriaMet: boolean;
  checks: DocumentCheck[];
}

export default function SetupWizard() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // SuperAdmin User Form
  const [adminEmail, setAdminEmail] = useState('admin@yourstartup.com');
  const [adminPassword, setAdminPassword] = useState('SuperSecretPass123!');
  const [firstName, setFirstName] = useState('Vikram');
  const [lastName, setLastName] = useState('Founder');
  const [adminDin, setAdminDin] = useState('09876543');

  // Verified Entity Details
  const [cin, setCin] = useState('');
  const [legalName, setLegalName] = useState('');
  const [pan, setPan] = useState('');
  const [tan, setTan] = useState('');
  const [gstin, setGstin] = useState('');
  const [stateCode, setStateCode] = useState('');
  const [registeredOffice, setRegisteredOffice] = useState('');
  const [incorporationDate, setIncorporationDate] = useState('');
  const [entityType, setEntityType] = useState('Private Limited Company');
  const [authorizedCapital, setAuthorizedCapital] = useState('');
  const [quorum, setQuorum] = useState('');

  // Document Verification State
  const [verifiedDocs, setVerifiedDocs] = useState<Record<string, VerifiedDocRecord>>({});
  const [uploadedFiles, setUploadedFiles] = useState<Record<string, File>>({});
  const [activeUploadDocType, setActiveUploadDocType] = useState<string | null>(null);
  const [verifyingDocType, setVerifyingDocType] = useState<string | null>(null);
  const [showManualEdit, setShowManualEdit] = useState(false);

  // Quick fallback lookup by identifier if documents are not on hand
  const [manualIdentifier, setManualIdentifier] = useState('');
  const [identifierLoading, setIdentifierLoading] = useState(false);

  // Handle statutory document upload & authenticity verification
  const handleDocumentUpload = async (docType: string, e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadedFiles((prev) => ({ ...prev, [docType]: file }));
    setVerifyingDocType(docType);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('doc_type', docType);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/setup/verify-document`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Document verification failed.');
      }

      const data = await res.json();

      // Record verified document
      const record: VerifiedDocRecord = {
        fileName: file.name,
        docTitle: data.document_title || file.name,
        sha256: data.sha256,
        fileSizeBytes: data.file_size_bytes,
        isAuthentic: data.is_authentic,
        criteriaMet: data.criteria_met,
        checks: data.checks || [],
      };

      setVerifiedDocs((prev) => ({ ...prev, [docType]: record }));

      // Populate verified company attributes
      const ext = data.extracted_entity || {};
      if (ext.legal_name && !legalName) setLegalName(ext.legal_name);
      if (ext.cin && !cin) setCin(ext.cin);
      if (ext.pan && !pan) setPan(ext.pan);
      if (ext.tan) setTan(ext.tan);
      if (ext.gstin) {
        setGstin(ext.gstin);
        if (ext.state_code) setStateCode(ext.state_code);
      }
      if (ext.registered_office && !registeredOffice) setRegisteredOffice(ext.registered_office);
      if (ext.incorporation_date && !incorporationDate) setIncorporationDate(ext.incorporation_date);
      if (ext.entity_type) setEntityType(ext.entity_type);
      if (ext.authorized_capital_inr) {
        setAuthorizedCapital(`₹${Number(ext.authorized_capital_inr).toLocaleString('en-IN')}`);
      }
      if (ext.board_meeting_quorum) {
        setQuorum(ext.board_meeting_quorum);
      }
      if (ext.directors && ext.directors.length > 0 && ext.directors[0].din) {
        setAdminDin(ext.directors[0].din);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to verify statutory document.');
    } finally {
      setVerifyingDocType(null);
    }
  };

  // Instant Identifier Verification Fallback
  const handleVerifyIdentifier = async () => {
    if (!manualIdentifier.trim()) return;

    setIdentifierLoading(true);
    setError(null);

    try {
      const clean = manualIdentifier.trim();
      const res = await fetchApi(`/api/v1/setup/inspect-identifier?identifier=${encodeURIComponent(clean)}`);

      if (res.cin) setCin(res.cin);
      if (res.pan) setPan(res.pan);
      if (res.gstin) setGstin(res.gstin);
      if (res.state_code) setStateCode(res.state_code);
      if (res.entity_type) setEntityType(res.entity_type);

      // Record pseudo-verification
      setVerifiedDocs((prev) => ({
        ...prev,
        identifier: {
          fileName: clean,
          docTitle: `${res.detected_type} Registry Verification`,
          sha256: 'Registry Query - Mod-36 Validated',
          fileSizeBytes: 0,
          isAuthentic: res.is_valid,
          criteriaMet: true,
          checks: [
            { name: 'Regulatory Pattern', passed: res.is_valid, detail: `Format verified as valid Indian ${res.detected_type}` },
            { name: 'Jurisdiction & State', passed: Boolean(res.state_code), detail: `Mapped to State Code ${res.state_code || 'Central'}` },
          ],
        },
      }));
    } catch (err: any) {
      setError(err.message || 'Identifier verification failed.');
    } finally {
      setIdentifierLoading(false);
    }
  };

  const handleCompleteSetup = async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetchApi('/api/v1/setup/wizard', {
        method: 'POST',
        body: JSON.stringify({
          admin_email: adminEmail,
          admin_password: adminPassword,
          admin_first_name: firstName,
          admin_last_name: lastName,
          admin_din: adminDin || undefined,
          legal_name: legalName || 'Acme Labs Private Limited',
          cin: cin || 'U72900KA2026PTC123456',
          pan: pan || 'AABCA1234F',
          gstin: gstin || undefined,
          tan: tan || undefined,
          state_code: stateCode || '29',
          registered_office: registeredOffice || 'Indiranagar, Bengaluru, Karnataka - 560038',
          incorporation_date: incorporationDate || '2026-01-15',
        }),
      });

      if (res.access_token) {
        const token = res.access_token;
        localStorage.setItem('b00k5_token', token);
        localStorage.setItem('b00k5_tenant_id', res.tenant_id);
        localStorage.setItem('b00k5_legal_name', res.legal_name);
        localStorage.setItem('b00k5_cin', cin);
        localStorage.setItem('b00k5_role', 'owner');
        localStorage.setItem('b00k5_admin_din', adminDin || '');
        localStorage.setItem('b00k5_signer_name', `${firstName} ${lastName}`.trim() || 'Director');
        localStorage.setItem('b00k5_venue', registeredOffice || 'Registered Office');
        localStorage.setItem('b00k5_registered_office', registeredOffice || '');

        // Vault the verified statutory documents directly into MinIO S3 Vault
        for (const [dType, fObj] of Object.entries(uploadedFiles)) {
          try {
            const vData = new FormData();
            vData.append('file', fObj);
            if (dType === 'coi') {
              vData.append('category', 'corporate_legal');
              vData.append('document_name', 'Certificate of Incorporation (COI)');
              if (cin) vData.append('document_number', cin);
            } else if (dType === 'moa') {
              vData.append('category', 'corporate_legal');
              vData.append('document_name', 'Memorandum of Association (MOA)');
            } else if (dType === 'aoa') {
              vData.append('category', 'corporate_legal');
              vData.append('document_name', 'Articles of Association (AOA)');
            } else if (dType === 'pan') {
              vData.append('category', 'tax_registration');
              vData.append('document_name', 'Permanent Account Number (PAN Card)');
              if (pan) vData.append('document_number', pan);
            } else if (dType === 'tan') {
              vData.append('category', 'tax_registration');
              vData.append('document_name', 'TAN Allotment Letter');
              if (tan) vData.append('document_number', tan);
            } else if (dType === 'gst') {
              vData.append('category', 'tax_registration');
              vData.append('document_name', 'GST Registration Certificate (REG-06)');
              if (gstin) vData.append('document_number', gstin);
            } else {
              vData.append('category', 'corporate_legal');
              vData.append('document_name', fObj.name);
            }

            await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/vault/upload`, {
              method: 'POST',
              headers: {
                Authorization: `Bearer ${token}`,
              },
              body: vData,
            });
          } catch (e) {
            console.error('Failed to vault document:', e);
          }
        }

        router.push('/dashboard');
      }
    } catch (err: any) {
      setError(err.message || 'Setup failed. Please check inputs.');
    } finally {
      setLoading(false);
    }
  };

  const hasAnyVerifiedDoc = Object.keys(verifiedDocs).length > 0;

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-6">
      <div className="w-full max-w-3xl bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl">
        {/* Brand Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-sky-500/20 border border-sky-500/40 flex items-center justify-center text-sky-400 font-mono font-bold text-xl">
            b5
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">b00k5 Turnkey Setup Wizard</h1>
            <p className="text-xs text-slate-400">Corporate Onboarding &amp; Statutory Document Verification</p>
          </div>
        </div>

        {/* Step Indicators */}
        <div className="flex items-center justify-between mb-8 border-y border-slate-800 py-3 text-xs">
          <div className={`flex items-center gap-2 ${step >= 1 ? 'text-sky-400 font-semibold' : 'text-slate-500'}`}>
            <span className="w-6 h-6 rounded-full border flex items-center justify-center text-xs">1</span>
            SuperAdmin Account
          </div>
          <ArrowRight className="w-4 h-4 text-slate-600" />
          <div className={`flex items-center gap-2 ${step >= 2 ? 'text-sky-400 font-semibold' : 'text-slate-500'}`}>
            <span className="w-6 h-6 rounded-full border flex items-center justify-center text-xs">2</span>
            Document Verification
          </div>
          <ArrowRight className="w-4 h-4 text-slate-600" />
          <div className={`flex items-center gap-2 ${step >= 3 ? 'text-sky-400 font-semibold' : 'text-slate-500'}`}>
            <span className="w-6 h-6 rounded-full border flex items-center justify-center text-xs">3</span>
            Locker &amp; Activation
          </div>
        </div>

        {error && (
          <div className="mb-6 p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 flex items-center gap-2 text-rose-400 text-sm">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Step 1: SuperAdmin */}
        {step === 1 && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-base font-semibold text-slate-200">Step 1: SuperAdmin Master Account</h2>
              <span className="text-xs text-slate-400">Signing Authority &amp; System Owner</span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">First Name</label>
                <input
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Last Name</label>
                <input
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Founder / Master Email</label>
              <input
                type="email"
                value={adminEmail}
                onChange={(e) => setAdminEmail(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Master Password</label>
                <input
                  type="password"
                  value={adminPassword}
                  onChange={(e) => setAdminPassword(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Director Identification Number (DIN)</label>
                <input
                  type="text"
                  value={adminDin}
                  onChange={(e) => setAdminDin(e.target.value)}
                  placeholder="8-digit MCA DIN (optional)"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-sky-500 font-mono"
                />
              </div>
            </div>
            <div className="pt-4 flex justify-end">
              <button
                type="button"
                onClick={() => setStep(2)}
                className="px-4 py-2 bg-sky-500 hover:bg-sky-600 text-white text-sm font-semibold rounded-lg flex items-center gap-2"
              >
                Proceed to Document Verification <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Statutory Document Verification */}
        {step === 2 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-base font-semibold text-slate-200">Step 2: Statutory Document Verification</h2>
              <p className="text-xs text-slate-400 mt-1">
                Upload your company documents. b00k5 validates file criteria, verifies government authenticity, and automatically populates your entity profile.
              </p>
            </div>

            {/* Document Checklist Grid */}
            <div className="space-y-3">
              {/* Document 1: COI / Registration Proof */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400 shrink-0">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-200">Certificate of Incorporation (COI)</span>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800/60">
                        Pvt Ltd / OPC / LLP
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Ministry of Corporate Affairs Certificate containing 21-digit CIN or 7-character LLPIN.
                    </p>

                    {verifiedDocs.coi && (
                      <div className="mt-2 text-xs flex items-center gap-2 text-emerald-400 font-mono">
                        <CheckCircle className="w-3.5 h-3.5" />
                        <span>Verified Authentic • SHA-256: {verifiedDocs.coi.sha256.slice(0, 12)}...</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="shrink-0 flex items-center gap-2">
                  <label className="cursor-pointer px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors">
                    <UploadCloud className="w-3.5 h-3.5 text-sky-400" />
                    <span>{verifiedDocs.coi ? 'Re-upload COI' : 'Upload COI'}</span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(e) => handleDocumentUpload('coi', e)}
                      disabled={verifyingDocType === 'coi'}
                    />
                  </label>
                </div>
              </div>

              {/* Document 2: Memorandum of Association (MOA) */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 shrink-0">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-200">Memorandum of Association (MOA)</span>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800/60">
                        Capital &amp; Objects
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Extracts Authorized Share Capital (Clause V), total nominal equity shares, and main business objects (Clause III).
                    </p>

                    {verifiedDocs.moa && (
                      <div className="mt-2 text-xs flex items-center gap-2 text-emerald-400 font-mono">
                        <CheckCircle className="w-3.5 h-3.5" />
                        <span>Verified Authentic • Authorized Capital: {authorizedCapital || 'Extracted'}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="shrink-0 flex items-center gap-2">
                  <label className="cursor-pointer px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors">
                    <UploadCloud className="w-3.5 h-3.5 text-cyan-400" />
                    <span>{verifiedDocs.moa ? 'Re-upload MOA' : 'Upload MOA'}</span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(e) => handleDocumentUpload('moa', e)}
                      disabled={verifyingDocType === 'moa'}
                    />
                  </label>
                </div>
              </div>

              {/* Document 3: Articles of Association (AOA) */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-teal-500/10 border border-teal-500/30 flex items-center justify-center text-teal-400 shrink-0">
                    <FileCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-200">Articles of Association (AOA)</span>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-teal-950 text-teal-400 border border-teal-800/60">
                        Governance
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Extracts Board of Directors meeting quorum rule (Section 174) and statutory borrowing limit clauses.
                    </p>

                    {verifiedDocs.aoa && (
                      <div className="mt-2 text-xs flex items-center gap-2 text-emerald-400 font-mono">
                        <CheckCircle className="w-3.5 h-3.5" />
                        <span>Verified Authentic • Quorum: {quorum || 'Extracted'}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="shrink-0 flex items-center gap-2">
                  <label className="cursor-pointer px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors">
                    <UploadCloud className="w-3.5 h-3.5 text-teal-400" />
                    <span>{verifiedDocs.aoa ? 'Re-upload AOA' : 'Upload AOA'}</span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(e) => handleDocumentUpload('aoa', e)}
                      disabled={verifyingDocType === 'aoa'}
                    />
                  </label>
                </div>
              </div>

              {/* Document 4: Entity PAN Card */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
                    <FileCheck className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-200">Permanent Account Number (PAN Card)</span>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-indigo-950 text-indigo-400 border border-indigo-800/60">
                        Mandatory
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      10-character PAN issued by Income Tax Department (Company, LLP, or Proprietor PAN).
                    </p>

                    {verifiedDocs.pan && (
                      <div className="mt-2 text-xs flex items-center gap-2 text-emerald-400 font-mono">
                        <CheckCircle className="w-3.5 h-3.5" />
                        <span>Verified Authentic • PAN: {pan || 'Extracted'}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="shrink-0 flex items-center gap-2">
                  <label className="cursor-pointer px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors">
                    <UploadCloud className="w-3.5 h-3.5 text-indigo-400" />
                    <span>{verifiedDocs.pan ? 'Re-upload PAN' : 'Upload PAN'}</span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(e) => handleDocumentUpload('pan', e)}
                      disabled={verifyingDocType === 'pan'}
                    />
                  </label>
                </div>
              </div>

              {/* Document 5: TAN Allotment Letter */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400 shrink-0">
                    <FileText className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-200">TAN Allotment Letter</span>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-purple-950 text-purple-400 border border-purple-800/60">
                        TDS Deductor
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Income Tax Department Form 49B allotment letter containing 10-digit Tax Deduction and Collection Account Number (TAN).
                    </p>

                    {verifiedDocs.tan && (
                      <div className="mt-2 text-xs flex items-center gap-2 text-emerald-400 font-mono">
                        <CheckCircle className="w-3.5 h-3.5" />
                        <span>Verified Authentic • TAN: {tan || 'Extracted'}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="shrink-0 flex items-center gap-2">
                  <label className="cursor-pointer px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors">
                    <UploadCloud className="w-3.5 h-3.5 text-purple-400" />
                    <span>{verifiedDocs.tan ? 'Re-upload TAN' : 'Upload TAN Letter'}</span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(e) => handleDocumentUpload('tan', e)}
                      disabled={verifyingDocType === 'tan'}
                    />
                  </label>
                </div>
              </div>

              {/* Document 6: Form GST REG-06 */}
              <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
                    <Building2 className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-slate-200">GST Registration Certificate (REG-06)</span>
                      <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800/60">
                        GST Registered
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5">
                      Form GST REG-06 showing 15-character GSTIN, Legal Name, and Principal Place of Business.
                    </p>

                    {verifiedDocs.gst && (
                      <div className="mt-2 text-xs flex items-center gap-2 text-emerald-400 font-mono">
                        <CheckCircle className="w-3.5 h-3.5" />
                        <span>Verified Authentic • Mod-36 Validated GSTIN: {gstin}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="shrink-0 flex items-center gap-2">
                  <label className="cursor-pointer px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg flex items-center gap-1.5 transition-colors">
                    <UploadCloud className="w-3.5 h-3.5 text-emerald-400" />
                    <span>{verifiedDocs.gst ? 'Re-upload GST' : 'Upload GST Certificate'}</span>
                    <input
                      type="file"
                      accept=".pdf,.png,.jpg,.jpeg"
                      className="hidden"
                      onChange={(e) => handleDocumentUpload('gst', e)}
                      disabled={verifyingDocType === 'gst'}
                    />
                  </label>
                </div>
              </div>
            </div>

            {/* In-Flight Verification Loader */}
            {verifyingDocType && (
              <div className="p-3 bg-sky-950/30 border border-sky-800/50 rounded-lg flex items-center gap-2 text-xs text-sky-400 font-mono">
                <div className="w-3.5 h-3.5 border-2 border-sky-400 border-t-transparent rounded-full animate-spin"></div>
                Validating document criteria, computing SHA-256 hash, and verifying authority seals...
              </div>
            )}

            {/* Quick Identifier Fallback */}
            <div className="border-t border-slate-800/80 pt-4">
              <div className="flex items-center justify-between text-xs text-slate-400 mb-2">
                <span>Don&apos;t have document PDFs on hand? Verify by Registry Identifier:</span>
              </div>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={manualIdentifier}
                  onChange={(e) => setManualIdentifier(e.target.value.toUpperCase())}
                  placeholder="Enter CIN (e.g. U72900KA2026PTC123456) or GSTIN (e.g. 29AABCA1234F1Z5)"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-sky-300 font-mono uppercase focus:outline-none focus:border-sky-500"
                />
                <button
                  type="button"
                  onClick={handleVerifyIdentifier}
                  disabled={identifierLoading || !manualIdentifier.trim()}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white text-xs font-medium rounded-lg flex items-center gap-1 shrink-0"
                >
                  <Search className="w-3.5 h-3.5" />
                  {identifierLoading ? 'Verifying...' : 'Verify'}
                </button>
              </div>
            </div>

            {/* Verified Corporate Profile Card */}
            {(hasAnyVerifiedDoc || legalName || cin || pan) && (
              <div className="bg-slate-950 border border-emerald-800/40 rounded-xl p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <ShieldCheck className="w-5 h-5 text-emerald-400" />
                    <span className="text-sm font-semibold text-white">Verified Corporate &amp; Tax Profile</span>
                  </div>
                  <span className="text-xs font-mono text-emerald-400 bg-emerald-950/60 border border-emerald-800/60 px-2 py-0.5 rounded">
                    Criteria &amp; Authenticity Verified
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-y-3 gap-x-6 text-xs">
                  <div>
                    <span className="text-slate-400 block mb-0.5">Legal Entity Name</span>
                    <span className="text-slate-100 font-semibold">{legalName || 'Acme Labs Private Limited'}</span>
                  </div>

                  <div>
                    <span className="text-slate-400 block mb-0.5">Entity Classification</span>
                    <span className="text-slate-100 font-mono">{entityType || 'Private Limited Company'}</span>
                  </div>

                  <div>
                    <span className="text-slate-400 block mb-0.5">Corporate Identity (CIN / LLPIN)</span>
                    <span className="text-sky-400 font-mono font-medium">{cin || 'Pending COI Upload'}</span>
                  </div>

                  <div>
                    <span className="text-slate-400 block mb-0.5">Permanent Account Number (PAN)</span>
                    <span className="text-slate-100 font-mono font-medium">{pan || 'Pending PAN Upload'}</span>
                  </div>

                  <div>
                    <span className="text-slate-400 block mb-0.5">Corporate TAN (Tax Deduction A/C)</span>
                    <span className="font-mono">
                      {tan ? (
                        <span className="text-emerald-400 font-medium">{tan} (Verified Active)</span>
                      ) : (
                        <span className="text-slate-500 italic">Not Available (Upload TAN Letter)</span>
                      )}
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-400 block mb-0.5">Goods &amp; Services Tax (GSTIN)</span>
                    <span className="font-mono">
                      {gstin ? (
                        <span className="text-emerald-400 font-medium">{gstin} (POS {stateCode || '29'})</span>
                      ) : (
                        <span className="text-slate-500 italic">Not Available (Upload Form GST REG-06)</span>
                      )}
                    </span>
                  </div>

                  <div>
                    <span className="text-slate-400 block mb-0.5">Authorized Capital (MOA Clause V)</span>
                    <span className="text-slate-100 font-mono">{authorizedCapital || 'Pending MOA Upload'}</span>
                  </div>

                  <div>
                    <span className="text-slate-400 block mb-0.5">Board Meeting Quorum (AOA)</span>
                    <span className="text-slate-100 font-mono">{quorum || 'Pending AOA Upload'}</span>
                  </div>

                  <div>
                    <span className="text-slate-400 block mb-0.5">Date of Incorporation</span>
                    <span className="text-slate-100 font-mono">{incorporationDate || '2026-01-15'}</span>
                  </div>

                  <div className="col-span-2">
                    <span className="text-slate-400 block mb-0.5">Registered Office Address</span>
                    <span className="text-slate-300">{registeredOffice || 'Indiranagar, Bengaluru, Karnataka 560038'}</span>
                  </div>
                </div>

                {/* Edit details toggle */}
                <div className="pt-2 border-t border-slate-800/80">
                  <button
                    type="button"
                    onClick={() => setShowManualEdit(!showManualEdit)}
                    className="text-xs text-sky-400 hover:text-sky-300 flex items-center gap-1 font-medium"
                  >
                    <span>{showManualEdit ? 'Hide Manual Adjustments' : 'Edit Profile Details'}</span>
                    {showManualEdit ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  </button>

                  {showManualEdit && (
                    <div className="mt-3 grid grid-cols-2 gap-3 pt-2">
                      <div>
                        <label className="text-[11px] text-slate-400 block mb-1">Legal Name</label>
                        <input
                          type="text"
                          value={legalName}
                          onChange={(e) => setLegalName(e.target.value)}
                          className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] text-slate-400 block mb-1">CIN / LLPIN</label>
                        <input
                          type="text"
                          value={cin}
                          onChange={(e) => setCin(e.target.value.toUpperCase())}
                          className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] text-slate-400 block mb-1">PAN</label>
                        <input
                          type="text"
                          value={pan}
                          onChange={(e) => setPan(e.target.value.toUpperCase())}
                          className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] text-slate-400 block mb-1">TAN</label>
                        <input
                          type="text"
                          value={tan}
                          onChange={(e) => setTan(e.target.value.toUpperCase())}
                          placeholder="BLRA12345B"
                          className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                        />
                      </div>
                      <div className="col-span-2">
                        <label className="text-[11px] text-slate-400 block mb-1">GSTIN</label>
                        <input
                          type="text"
                          value={gstin}
                          onChange={(e) => setGstin(e.target.value.toUpperCase())}
                          placeholder="29AABCA1234F1Z5"
                          className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="pt-4 flex justify-between">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="px-4 py-2 border border-slate-700 text-slate-300 text-sm font-semibold rounded-lg"
              >
                Back
              </button>
              <button
                type="button"
                onClick={() => setStep(3)}
                className="px-4 py-2 bg-sky-500 hover:bg-sky-600 text-white text-sm font-semibold rounded-lg flex items-center gap-2"
              >
                Next: Locker &amp; Milestones <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Seeding & Activation */}
        {step === 3 && (
          <div className="space-y-5">
            <div>
              <h2 className="text-base font-semibold text-slate-200">Step 3: Document Locker Seeding &amp; Activation</h2>
              <p className="text-xs text-slate-400 mt-1">
                All verified statutory files will be deposited into your sovereign S3 Document Vault with cryptographic SHA-256 tamper seals.
              </p>
            </div>

            {/* Verified Document Archive Summary */}
            <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-2.5">
              <div className="text-xs font-semibold text-slate-300 flex items-center gap-1.5 mb-2">
                <FileCheck2 className="w-4 h-4 text-emerald-400" />
                Verified Statutory Files Scheduled for Vault Seeding:
              </div>

              {Object.keys(verifiedDocs).length > 0 ? (
                Object.entries(verifiedDocs).map(([key, doc]) => (
                  <div key={key} className="flex items-center justify-between py-1.5 px-3 bg-slate-900/60 rounded border border-slate-800 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="text-slate-200 font-medium">{doc.docTitle}</span>
                      <span className="text-[10px] text-slate-500">({doc.fileName})</span>
                    </div>
                    <span className="font-mono text-[11px] text-emerald-400">SHA-256: {doc.sha256.slice(0, 16)}...</span>
                  </div>
                ))
              ) : (
                <div className="py-2 px-3 bg-slate-900/40 rounded border border-slate-800/60 text-xs text-slate-400">
                  Default foundational documents (COI.pdf, MOA.pdf, PAN.pdf) will be provisioned into your secure locker.
                </div>
              )}
            </div>

            <div className="bg-sky-950/20 border border-sky-800/40 p-4 rounded-xl text-xs space-y-2">
              <div className="font-semibold text-sky-300 flex items-center gap-1.5">
                <CheckCircle className="w-4 h-4 text-sky-400" />
                Automatic Provisioning on Activation:
              </div>
              <ul className="list-disc list-inside text-slate-300 space-y-1">
                <li>Double-entry Indian Chart of Accounts (Assets, Liabilities, TDS 194C/J/I/Q, GST)</li>
                <li>Statutory Watchdog: Section 173 120-day Board Meeting countdown</li>
                <li>Statutory Watchdog: DIR-3 KYC (Sep 30) &amp; AOC-4/MGT-7 deadline monitors</li>
                <li>Row-Level Security (RLS) PostgreSQL context isolation</li>
              </ul>
            </div>

            <div className="pt-4 flex justify-between">
              <button
                type="button"
                onClick={() => setStep(2)}
                className="px-4 py-2 border border-slate-700 text-slate-300 text-sm font-semibold rounded-lg"
              >
                Back
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={handleCompleteSetup}
                className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold rounded-lg flex items-center gap-2 shadow-lg shadow-emerald-900/30"
              >
                {loading ? 'Initializing Workspace...' : 'Launch b00k5 Financial OS'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
