'use client';

import React, { useEffect, useState } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import {
  FolderLock,
  Upload,
  FileCheck2,
  ShieldCheck,
  Calendar,
  Hash,
  Download,
  ExternalLink,
  Plus,
  Scale,
  Sparkles,
  Lock,
  AlertTriangle,
  CheckCircle2,
  Eye,
  FileText,
  Building2,
  Coins,
  Users
} from 'lucide-react';
import { fetchApi } from '@/lib/api';

const categories = [
  { id: 'all', label: 'All Vault Items' },
  { id: 'corporate_legal', label: 'Corporate Legal (COI, MOA, AOA)' },
  { id: 'tax_registration', label: 'Tax Registrations (PAN, GST, PT)' },
  { id: 'operational_license', label: 'Operational (MSME, DPIIT)' },
  { id: 'equity_governance', label: 'Equity & Governance (MOM, Cap Table)' },
  { id: 'statutory_filing', label: 'Statutory Filings (ADT-1, AOC-4, MGT-7)' },
];

export default function DocumentLockerPage() {
  const [selectedCat, setSelectedCat] = useState('all');
  const [documents, setDocuments] = useState<any[]>([]);
  const [statutoryProfile, setStatutoryProfile] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  // Deposit Modal State
  const [depositModalOpen, setDepositModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedCategory, setSelectedCategory] = useState('corporate_legal');
  const [pdfPassword, setPdfPassword] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [extractionResult, setExtractionResult] = useState<any | null>(null);

  // Detail Modal State
  const [viewDoc, setViewDoc] = useState<any | null>(null);

  async function loadData() {
    try {
      const endpoint = selectedCat === 'all' ? '/api/v1/vault/' : `/api/v1/vault/?category=${selectedCat}`;
      const docs = await fetchApi(endpoint);
      if (Array.isArray(docs)) setDocuments(docs);

      const profileRes = await fetchApi('/api/v1/vault/statutory-profile');
      if (profileRes?.statutory_profile) {
        setStatutoryProfile(profileRes.statutory_profile);
      }
    } catch (e) {
      console.error('Failed to load vault data:', e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [selectedCat]);

  const handleDepositSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;

    setUploading(true);
    setUploadError('');
    setExtractionResult(null);

    const fd = new FormData();
    fd.append('file', selectedFile);
    fd.append('category', selectedCategory);
    if (pdfPassword) fd.append('pdf_password', pdfPassword);

    try {
      const token = localStorage.getItem('b00k5_token');
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/vault/smart-ingest`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: fd
      });

      if (res.status === 422) {
        const err = await res.json();
        if (err?.detail?.needs_password) {
          setUploadError('This PDF document is encrypted. Please enter the PDF password below to unlock.');
          setUploading(false);
          return;
        }
      }

      if (res.ok) {
        const data = await res.json();
        setExtractionResult(data);
        if (data.statutory_profile) setStatutoryProfile(data.statutory_profile);
        if (data.extracted_fields?.gstin) {
          localStorage.setItem('b00k5_extracted_gstin', data.extracted_fields.gstin);
        }
        if (data.extracted_fields?.state_code) {
          localStorage.setItem('b00k5_extracted_state', data.extracted_fields.state_code);
        }
        if (data.extracted_fields?.legal_name) {
          localStorage.setItem('b00k5_legal_name', data.extracted_fields.legal_name);
        }
        loadData();
      } else {
        const err = await res.json();
        setUploadError(err.detail?.message || err.detail || 'Failed to ingest document.');
      }
    } catch (err: any) {
      setUploadError(err.message || 'Ingestion error');
    } finally {
      setUploading(false);
    }
  };

  const [downloadingPack, setDownloadingPack] = useState(false);

  const handleExportAuditorPack = async () => {
    setDownloadingPack(true);
    try {
      const token = localStorage.getItem('b00k5_token');
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/vault/export-auditor-pack`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Auditor_Permanent_File_FY2025-26.zip`;
        document.body.appendChild(a);
        a.click();
        a.remove();
      } else {
        alert('Failed to generate auditor pack');
      }
    } catch (e: any) {
      alert(e.message || 'Error downloading auditor pack');
    } finally {
      setDownloadingPack(false);
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Navbar />

        <main className="p-8 space-y-6 max-w-7xl mx-auto w-full">
          {/* Header */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <FolderLock className="w-6 h-6 text-emerald-400" />
                Statutory Document Vault &amp; Legal Rule Engine
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Cryptographically sealed MinIO repository. Documents serve as the active legal source of truth, parsed into the compliance engine.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleExportAuditorPack}
                disabled={downloadingPack}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-sky-400 hover:text-sky-300 text-xs font-semibold rounded-lg flex items-center gap-2 border border-slate-700 shadow-sm transition-all"
              >
                <Download className={`w-4 h-4 ${downloadingPack ? 'animate-bounce' : ''}`} />
                {downloadingPack ? 'Generating Audit Pack...' : 'Export Auditor Pack (ZIP)'}
              </button>

              <button
                onClick={() => {
                  setDepositModalOpen(true);
                  setExtractionResult(null);
                  setSelectedFile(null);
                  setUploadError('');
                  setPdfPassword('');
                }}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 shadow-sm transition-all"
              >
                <Upload className="w-4 h-4" /> Deposit Governance Document
              </button>
            </div>
          </div>

          {/* Statutory Source of Truth Banner */}
          <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                <Scale className="w-4 h-4 text-emerald-400" />
                Active Statutory Profile & Rule Engine
              </h3>
              <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                Companies Act, 2013 Verified
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1">
                <span className="text-slate-500 flex items-center gap-1.5">
                  <Coins className="w-3.5 h-3.5 text-amber-400" /> Authorized Capital (MOA)
                </span>
                <p className="font-mono text-sm font-bold text-white">
                  {statutoryProfile.authorized_capital_inr
                    ? `₹${statutoryProfile.authorized_capital_inr.toLocaleString('en-IN')}`
                    : 'Pending MOA Upload'}
                </p>
                <p className="text-[10px] text-slate-500">
                  {statutoryProfile.total_equity_shares
                    ? `${statutoryProfile.total_equity_shares.toLocaleString('en-IN')} shares of ₹${statutoryProfile.face_value_inr || 10}`
                    : 'Upload MOA to extract'}
                </p>
              </div>

              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1">
                <span className="text-slate-500 flex items-center gap-1.5">
                  <Users className="w-3.5 h-3.5 text-sky-400" /> Board Meeting Quorum (AOA)
                </span>
                <p className="font-semibold text-slate-200 truncate">
                  {statutoryProfile.board_meeting_quorum || 'Pending AOA Upload'}
                </p>
                <p className="text-[10px] text-slate-500">Sec 174 Compliance Rule</p>
              </div>

              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1">
                <span className="text-slate-500 flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> Statutory Auditor (ADT-1)
                </span>
                <p className="font-semibold text-slate-200 truncate">
                  {statutoryProfile.auditor_firm_name || statutoryProfile.auditor_name || 'Pending ADT-1 Upload'}
                </p>
                <p className="text-[10px] font-mono text-slate-400">
                  FRN: {statutoryProfile.auditor_frn || 'Not Uploaded'}
                </p>
              </div>

              <div className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1">
                <span className="text-slate-500 flex items-center gap-1.5">
                  <Building2 className="w-3.5 h-3.5 text-purple-400" /> Business Commencement
                </span>
                <p className={`font-semibold ${statutoryProfile.business_commencement?.status || statutoryProfile.inc20a_verified ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {statutoryProfile.business_commencement?.status || (statutoryProfile.inc20a_verified ? 'INC-20A Declared' : 'Pending Form INC-20A')}
                </p>
                <p className="text-[10px] text-slate-500">
                  SRN: {statutoryProfile.srn || 'Not Uploaded'}
                </p>
              </div>
            </div>
          </div>

          {/* Category Tabs */}
          <div className="flex items-center gap-2 overflow-x-auto pb-2 border-b border-slate-800 text-xs">
            {categories.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setSelectedCat(cat.id)}
                className={`px-3 py-1.5 rounded-lg whitespace-nowrap transition-all ${
                  selectedCat === cat.id
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40'
                }`}
              >
                {cat.label}
              </button>
            ))}
          </div>

          {/* Document Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {documents.length === 0 ? (
              <div className="col-span-full py-16 text-center text-slate-500 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
                <FileCheck2 className="w-12 h-12 mx-auto text-slate-600" />
                <h4 className="text-sm font-semibold text-slate-300">Vault Empty in this Category</h4>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  Deposit statutory documents (COI, MOA, AOA, PAN, ADT-1, INC-20A) to trigger active corporate entity extraction.
                </p>
                <button
                  onClick={() => setDepositModalOpen(true)}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg inline-flex items-center gap-1.5"
                >
                  <Plus className="w-3.5 h-3.5" /> Deposit First Document
                </button>
              </div>
            ) : (
              documents.map((doc) => (
                <div
                  key={doc.id}
                  onClick={() => setViewDoc(doc)}
                  className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-3 hover:border-emerald-500/40 transition-all cursor-pointer group"
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400 uppercase">
                        {doc.category.replace('_', ' ')}
                      </span>
                      <h4 className="font-semibold text-white text-sm mt-1.5 group-hover:text-emerald-300 transition-colors">
                        {doc.document_name}
                      </h4>
                      {doc.document_number && (
                        <p className="text-xs text-slate-400 font-mono mt-0.5">Ref: {doc.document_number}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5">
                      <a
                        href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/vault/${doc.id}/download`}
                        target="_blank"
                        rel="noreferrer"
                        download
                        onClick={(e) => e.stopPropagation()}
                        className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition"
                        title="Download Document"
                      >
                        <Download className="w-4 h-4" />
                      </a>
                      <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
                        <ShieldCheck className="w-5 h-5" />
                      </div>
                    </div>
                  </div>

                  <div className="space-y-1.5 text-xs text-slate-400 pt-2 border-t border-slate-800/80">
                    <div className="flex items-center gap-1.5 font-mono text-[11px]">
                      <Hash className="w-3.5 h-3.5 text-slate-500 shrink-0" />
                      <span className="truncate" title={doc.sha256_hash}>
                        SHA-256: {doc.sha256_hash.substring(0, 16)}...
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px]">
                      <span>Size: {(doc.file_size_bytes / 1024).toFixed(1)} KB</span>
                      <span>Added: {doc.created_at.split('T')[0]}</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </main>
      </div>

      {/* DEPOSIT DOCUMENT MODAL & LIVE EXTRACTION MATRIX */}
      {depositModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 space-y-5 shadow-2xl overflow-y-auto max-h-[90vh]">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Upload className="w-5 h-5 text-emerald-400" />
                  Deposit Governance Document
                </h3>
                <p className="text-xs text-slate-400">Active Legal Extraction Pipeline: Parses and updates statutory rule engine</p>
              </div>
              <button
                onClick={() => setDepositModalOpen(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            {uploadError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-400 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}

            {!extractionResult ? (
              <form onSubmit={handleDepositSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-300">Document Category</label>
                  <select
                    value={selectedCategory}
                    onChange={(e) => setSelectedCategory(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-white"
                  >
                    <option value="corporate_legal">Corporate Legal (COI, MOA, AOA, INC-22)</option>
                    <option value="tax_registration">Tax Registrations (PAN Card, GST REG-06, TAN)</option>
                    <option value="statutory_filing">Statutory MCA Filings (ADT-1, AOC-4, MGT-7A, INC-20A)</option>
                    <option value="equity_governance">Equity & Governance (Minutes of Meeting, Cap Table)</option>
                    <option value="operational_license">Operational Licenses (MSME, DPIIT Startup)</option>
                  </select>
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-300">Select Document File</label>
                  <div className="p-6 border-2 border-dashed border-slate-700 rounded-xl bg-slate-950/60 text-center space-y-2">
                    <FileText className="w-8 h-8 text-slate-500 mx-auto" />
                    {selectedFile ? (
                      <div>
                        <p className="text-xs font-semibold text-white">{selectedFile.name}</p>
                        <p className="text-[11px] text-slate-400">{(selectedFile.size / 1024).toFixed(1)} KB</p>
                      </div>
                    ) : (
                      <div>
                        <p className="text-xs text-slate-300 font-medium">Click to select PDF or image</p>
                        <p className="text-[10px] text-slate-500">Supports COI, MOA, AOA, PAN, ADT-1, INC-20A, AOC-4, MGT-7A</p>
                      </div>
                    )}
                    <label className="inline-block mt-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-sky-400 text-xs font-medium rounded-lg cursor-pointer transition-all">
                      Browse Files
                      <input
                        type="file"
                        accept=".pdf,.png,.jpg,.jpeg"
                        className="hidden"
                        onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                      />
                    </label>
                  </div>
                </div>

                {/* Password field for encrypted PDFs */}
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
                    <Lock className="w-3.5 h-3.5 text-slate-400" />
                    PDF Password (Only if file is encrypted)
                  </label>
                  <input
                    type="password"
                    value={pdfPassword}
                    onChange={(e) => setPdfPassword(e.target.value)}
                    placeholder="Enter password if required"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-white font-mono"
                  />
                </div>

                <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                  <button
                    type="button"
                    onClick={() => setDepositModalOpen(false)}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={!selectedFile || uploading}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 shadow-sm transition-all"
                  >
                    {uploading ? (
                      <>Parsing Legal Entities...</>
                    ) : (
                      <>
                        <Sparkles className="w-3.5 h-3.5" /> Deposit & Parse Document
                      </>
                    )}
                  </button>
                </div>
              </form>
            ) : (
              /* LIVE EXTRACTION MATRIX INSPECTOR */
              <div className="space-y-5">
                <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex items-center gap-3">
                  <CheckCircle2 className="w-6 h-6 text-emerald-400 shrink-0" />
                  <div>
                    <h4 className="text-xs font-bold text-white">Document Ingested & Verified</h4>
                    <p className="text-[11px] text-emerald-300">{extractionResult.message}</p>
                  </div>
                </div>

                {/* Extracted Matrix Details */}
                <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-3">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                    <span className="text-xs font-semibold text-white">Extracted Legal Entities</span>
                    <span className="text-[10px] font-mono text-slate-400 uppercase">
                      Type: {extractionResult.extracted_matrix?.document_type}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {Object.entries(extractionResult.extracted_matrix?.extracted_fields || {}).map(([key, val]) => (
                      <div key={key} className="p-2 bg-slate-900 border border-slate-800/80 rounded">
                        <div className="text-[10px] text-slate-400 font-mono capitalize">{key.replace(/_/g, ' ')}</div>
                        <div className="text-white font-medium truncate mt-0.5">
                          {typeof val === 'object' ? JSON.stringify(val) : String(val)}
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="pt-2 text-[10px] font-mono text-slate-400 flex items-center gap-1.5">
                    <Hash className="w-3 h-3 text-slate-500 shrink-0" />
                    <span>Cryptographic Hash: {extractionResult.document?.sha256_hash}</span>
                  </div>
                </div>

                <div className="flex justify-end gap-3 pt-2">
                  <button
                    onClick={() => {
                      setDepositModalOpen(false);
                      setExtractionResult(null);
                    }}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg"
                  >
                    Done
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* VIEW DOCUMENT DETAIL MODAL */}
      {viewDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-xl w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-sm font-bold text-white">{viewDoc.document_name}</h3>
                <span className="text-[10px] font-mono text-slate-400 uppercase">{viewDoc.category}</span>
              </div>
              <button onClick={() => setViewDoc(null)} className="text-slate-400 hover:text-white text-xs">
                ✕
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-1">
                <span className="text-[10px] text-slate-500 uppercase font-mono">Cryptographic SHA-256 Hash</span>
                <p className="font-mono text-slate-300 break-all">{viewDoc.sha256_hash}</p>
              </div>

              {viewDoc.metadata_json?.extracted_fields && (
                <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-2">
                  <span className="text-[10px] text-slate-500 uppercase font-mono">Extracted Corporate Entities</span>
                  <div className="grid grid-cols-2 gap-2">
                    {Object.entries(viewDoc.metadata_json.extracted_fields).map(([k, v]) => (
                      <div key={k} className="p-2 bg-slate-900 rounded border border-slate-800/80">
                        <div className="text-[10px] text-slate-400 font-mono capitalize">{k.replace(/_/g, ' ')}</div>
                        <div className="text-slate-200 font-medium truncate mt-0.5">
                          {typeof v === 'object' ? JSON.stringify(v) : String(v)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-slate-800">
              <a
                href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/vault/${viewDoc.id}/download`}
                target="_blank"
                rel="noreferrer"
                download
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 transition shadow-md shadow-emerald-600/20"
              >
                <Download className="w-4 h-4" />
                <span>Download Document</span>
              </a>
              <div className="flex items-center gap-2">
                <a
                  href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/vault/${viewDoc.id}/download`}
                  target="_blank"
                  rel="noreferrer"
                  className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition border border-slate-700"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Open in Tab</span>
                </a>
                <button
                  onClick={() => setViewDoc(null)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
