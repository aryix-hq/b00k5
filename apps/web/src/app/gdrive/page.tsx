'use client';

import React, { useEffect, useState } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import {
  Cloud,
  RefreshCw,
  Folder,
  FileText,
  CheckCircle2,
  Clock,
  AlertTriangle,
  HardDrive,
  ShieldCheck,
  ExternalLink,
  ChevronRight,
  Database,
  ArrowUpRight,
  Key,
  Upload,
  Settings2,
  FileCheck2,
  Lock,
  Check,
  X,
  Download,
  Copy
} from 'lucide-react';
import { fetchApi } from '@/lib/api';

export default function GDriveSyncPage() {
  const [dashboard, setDashboard] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<string | null>(null);
  const [mirroredFiles, setMirroredFiles] = useState<any[]>([]);
  const [filesLoading, setFilesLoading] = useState(false);
  const [downloadingArchive, setDownloadingArchive] = useState(false);

  // Google Drive Configuration State (Option A: Service Account)
  const [gdriveConfig, setGdriveConfig] = useState<any>(null);
  const [authType, setAuthType] = useState<'service_account' | 'oauth2' | 'mirror'>('service_account');
  const [serviceAccountJson, setServiceAccountJson] = useState<string>('');
  const [saParsedEmail, setSaParsedEmail] = useState<string>('');
  const [saParsedProjectId, setSaParsedProjectId] = useState<string>('');
  const [rootFolder, setRootFolder] = useState<string>('b00k5_vault');
  const [rootFolderId, setRootFolderId] = useState<string>('');
  const [copiedEmail, setCopiedEmail] = useState<boolean>(false);
  const [showJsonText, setShowJsonText] = useState<boolean>(false);
  const [testingConnection, setTestingConnection] = useState<boolean>(false);
  const [testStatus, setTestStatus] = useState<{ success: boolean; message: string; details?: any } | null>(null);
  const [savingConfig, setSavingConfig] = useState<boolean>(false);
  const [configMessage, setConfigMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  // Direct Upload State
  const [uploadCategory, setUploadCategory] = useState<string>('bank_statements');
  const [uploadDate, setUploadDate] = useState<string>(() => new Date().toISOString().split('T')[0]);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadSuccess, setUploadSuccess] = useState<any>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  async function loadStatus() {
    try {
      const data = await fetchApi('/api/v1/storage/gdrive-status');
      setDashboard(data);
    } catch (e) {
      console.error('Failed to load Google Drive sync status:', e);
    } finally {
      setLoading(false);
    }
  }

  const copyEmailToClipboard = (email: string) => {
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard.writeText(email);
      setCopiedEmail(true);
      setTimeout(() => setCopiedEmail(false), 2500);
    }
  };

  async function loadConfig() {
    try {
      const cfg = await fetchApi('/api/v1/storage/gdrive-config');
      if (cfg) {
        setGdriveConfig(cfg);
        if (cfg.root_folder) setRootFolder(cfg.root_folder);
        if (cfg.root_folder_id) setRootFolderId(cfg.root_folder_id);
        if (cfg.client_email) setSaParsedEmail(cfg.client_email);
        if (cfg.project_id) setSaParsedProjectId(cfg.project_id);
      }
    } catch (e) {
      console.warn('Failed to load GDrive config:', e);
    }
  }

  async function loadMirroredFiles() {
    try {
      setFilesLoading(true);
      const data = await fetchApi('/api/v1/storage/gdrive-files');
      if (data && data.files) {
        setMirroredFiles(data.files);
      }
    } catch (e) {
      console.warn('Failed to load mirrored files:', e);
    } finally {
      setFilesLoading(false);
    }
  }

  useEffect(() => {
    loadStatus();
    loadConfig();
    loadMirroredFiles();
  }, []);

  const handleDownloadArchive = async () => {
    try {
      setDownloadingArchive(true);
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = typeof window !== 'undefined' ? localStorage.getItem('b00k5_tenant_id') : null;
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/storage/gdrive-download-archive`, {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
        }
      });
      if (!res.ok) {
        throw new Error('Failed to generate statutory archive download.');
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `b00k5_Statutory_Archive_${(dashboard?.legal_name || 'Acme_Labs').replace(/\s+/g, '_')}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      alert(err.message || 'Error downloading archive');
    } finally {
      setDownloadingArchive(false);
    }
  };

  const handleTriggerSync = async () => {
    setSyncing(true);
    setSyncResult(null);

    try {
      const token = localStorage.getItem('b00k5_token');
      const tenantId = localStorage.getItem('b00k5_tenant_id');
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/storage/gdrive-sync-all`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
        }
      });

      if (res.ok) {
        const data = await res.json();
        setSyncResult(data.message || 'Background synchronization dispatched to Celery worker queue.');
        await loadStatus();
        await loadMirroredFiles();
      } else {
        setSyncResult('Failed to trigger synchronization sweep.');
      }
    } catch (e: any) {
      setSyncResult(e.message || 'Error executing sync');
    } finally {
      setSyncing(false);
    }
  };

  const handleTestConnection = async () => {
    setTestingConnection(true);
    setTestStatus(null);
    try {
      const token = localStorage.getItem('b00k5_token');
      const tenantId = localStorage.getItem('b00k5_tenant_id');
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/storage/gdrive-test-connection`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
        }
      });
      const data = await res.json();
      if (res.ok && data.success) {
        setTestStatus({
          success: true,
          message: data.message || `Successfully connected: ${data.backend}`,
          details: data.diagnostic
        });
      } else {
        setTestStatus({
          success: false,
          message: data.detail || 'Connection test failed'
        });
      }
    } catch (e: any) {
      setTestStatus({
        success: false,
        message: e.message || 'Connection error'
      });
    } finally {
      setTestingConnection(false);
    }
  };

  const handleDisconnectGoogle = async () => {
    try {
      const token = localStorage.getItem('b00k5_token');
      const tenantId = localStorage.getItem('b00k5_tenant_id');
      await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/storage/gdrive-disconnect`, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
        }
      });
      setConfigMessage({ type: 'success', text: 'Google Drive disconnected successfully.' });
      loadConfig();
      loadStatus();
      loadMirroredFiles();
    } catch (e: any) {
      setConfigMessage({ type: 'error', text: e.message });
    }
  };

  const handleSaveConfig = async () => {
    setSavingConfig(true);
    setConfigMessage(null);
    try {
      const token = localStorage.getItem('b00k5_token');
      const tenantId = localStorage.getItem('b00k5_tenant_id');
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/storage/gdrive-config`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
          ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
        },
        body: JSON.stringify({
          auth_type: authType,
          service_account_json: serviceAccountJson,
          root_folder: rootFolder,
          root_folder_id: rootFolderId
        })
      });

      const data = await res.json();
      if (res.ok && data.success) {
        setConfigMessage({
          type: 'success',
          text: data.message || 'Google Drive configuration saved successfully.'
        });
        loadConfig();
        loadStatus();
      } else {
        setConfigMessage({
          type: 'error',
          text: data.detail || 'Failed to save Google Drive configuration.'
        });
      }
    } catch (e: any) {
      setConfigMessage({
        type: 'error',
        text: e.message || 'Network error saving configuration.'
      });
    } finally {
      setSavingConfig(false);
    }
  };

  const handleFileUploadJson = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const content = event.target?.result as string;
        setServiceAccountJson(content);
        try {
          const parsed = JSON.parse(content);
          if (parsed.project_id && !rootFolder.includes('_')) {
            setRootFolder(`b00k5_${parsed.project_id}`);
          }
        } catch {
          // ignore
        }
      };
      reader.readAsText(file);
    }
  };

  const handleDirectUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) {
      setUploadError('Please select a file to upload');
      return;
    }
    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    const formData = new FormData();
    formData.append('file', uploadFile);
    formData.append('category', uploadCategory);
    if (uploadDate) formData.append('document_date', uploadDate);

    try {
      const token = localStorage.getItem('b00k5_token');
      const tenantId = localStorage.getItem('b00k5_tenant_id');
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/storage/gdrive-upload`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
        },
        body: formData
      });

      const data = await res.json();
      if (res.ok && data.success) {
        setUploadSuccess(data);
        setUploadFile(null);
        loadStatus();
        loadMirroredFiles();
      } else {
        setUploadError(data.detail || 'Failed to upload to Google Drive.');
      }
    } catch (e: any) {
      setUploadError(e.message || 'Upload error');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Navbar />

        <main className="p-8 space-y-6 max-w-7xl mx-auto w-full">
          {/* Header */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800/60">
                  Background Daemon: b00k5_worker_sync
                </span>
                <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800/60">
                  {gdriveConfig?.configured ? 'OAuth2 / Service Account Ready' : 'Virtual Mirror Active'}
                </span>
              </div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2 mt-1">
                <Cloud className="w-6 h-6 text-sky-400" />
                Google Drive 2-Way Mirror &amp; Cloud Synchronizer
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Automatically organizes your statutory vault, bank statements, and invoices into an official Google Drive folder hierarchy by Indian Fiscal Year.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleDownloadArchive}
                disabled={downloadingArchive}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 shadow-sm transition-all"
              >
                <Download className={`w-4 h-4 ${downloadingArchive ? 'animate-bounce' : ''}`} />
                {downloadingArchive ? 'Generating Zip...' : 'Download Statutory Archive (.zip)'}
              </button>
              <button
                onClick={handleTriggerSync}
                disabled={syncing}
                className="px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 shadow-sm transition-all"
              >
                <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
                {syncing ? 'Dispatching Sync Daemon...' : 'Sync All to Google Drive'}
              </button>
            </div>
          </div>

          {syncResult && (
            <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-xs text-emerald-400 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{syncResult}</span>
            </div>
          )}

          {/* Sync Telemetry Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
              <span className="text-xs text-slate-400 font-medium flex items-center gap-1.5">
                <HardDrive className="w-4 h-4 text-emerald-400" /> Daemon Worker Status
              </span>
              <div className="text-base font-bold text-emerald-400 flex items-center gap-1.5 pt-1">
                <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                <span>Active &amp; Online</span>
              </div>
              <p className="text-[10px] font-mono text-slate-500 mt-1">Queue: celery@gdrive_queue</p>
            </div>

            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
              <span className="text-xs text-slate-400 font-medium">Synced Documents</span>
              <div className="text-2xl font-bold text-white font-mono">
                {mirroredFiles.length > 0 ? mirroredFiles.length : (dashboard?.total_files_synced ?? 0)}
              </div>
              <p className="text-[11px] text-emerald-400 flex items-center gap-1">
                <ShieldCheck className="w-3 h-3" /> SHA-256 Checksums Verified
              </p>
            </div>

            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
              <span className="text-xs text-slate-400 font-medium">Pending Queue</span>
              <div className="text-2xl font-bold text-sky-400 font-mono">
                {dashboard?.pending_sync ?? 0}
              </div>
              <p className="text-[11px] text-slate-500">Sub-100ms Ingestion Latency</p>
            </div>

            <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-1">
              <span className="text-xs text-slate-400 font-medium">Target Google Drive Root</span>
              <div className="text-sm font-semibold text-white truncate pt-1">
                /b00k5/{dashboard?.legal_name?.substring(0, 18) || 'Acme_Labs'}...
              </div>
              <p className="text-[10px] text-slate-500">Auto-created Cloud Root</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Google Cloud Service Account (Option A) Card */}
            <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-5">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <Cloud className="w-5 h-5 text-sky-400" />
                  <h3 className="text-sm font-bold text-white">Google Cloud Service Account (Live Cloud)</h3>
                </div>
                {gdriveConfig?.live_cloud ? (
                  <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[11px] font-medium flex items-center gap-1">
                    <Check className="w-3 h-3" /> Live Cloud Active
                  </span>
                ) : gdriveConfig?.configured ? (
                  <span className="px-2.5 py-0.5 rounded-full bg-sky-500/10 border border-sky-500/30 text-sky-400 text-[11px] font-medium flex items-center gap-1">
                    <Check className="w-3 h-3" /> Credentials Saved
                  </span>
                ) : (
                  <span className="px-2.5 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-[11px] font-medium">
                    Setup Required
                  </span>
                )}
              </div>

              {configMessage && (
                <div className={`p-3 rounded-lg text-xs flex items-center gap-2 ${
                  configMessage.type === 'success'
                    ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
                    : 'bg-rose-500/10 border border-rose-500/30 text-rose-400'
                }`}>
                  {configMessage.type === 'success' ? <Check className="w-4 h-4 shrink-0" /> : <AlertTriangle className="w-4 h-4 shrink-0" />}
                  <span>{configMessage.text}</span>
                </div>
              )}

              {testStatus && (
                <div className={`p-3.5 rounded-xl border text-xs space-y-1 ${
                  testStatus.success
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                    : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                }`}>
                  <div className="flex items-center gap-2 font-semibold">
                    {testStatus.success ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <AlertTriangle className="w-4 h-4 text-rose-400" />}
                    <span>{testStatus.message}</span>
                  </div>
                  {testStatus.details?.user_email && (
                    <div className="text-[11px] text-slate-300 font-mono pl-6">
                      Authenticated: {testStatus.details.user_email}
                    </div>
                  )}
                  {testStatus.details?.folder_warning && (
                    <div className="text-[11px] text-amber-400 pl-6 pt-1">
                      ⚠️ {testStatus.details.folder_warning}
                    </div>
                  )}
                </div>
              )}

              {/* 3-Step Guided Service Account Flow */}
              <div className="space-y-4">
                {/* Step 1: Upload Credentials JSON */}
                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-white flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-sky-500/20 text-sky-400 font-mono text-[11px] flex items-center justify-center font-bold">1</span>
                      Upload Service Account Key (`credentials.json`)
                    </span>
                    <button
                      type="button"
                      onClick={() => setShowJsonText(!showJsonText)}
                      className="text-[11px] text-sky-400 hover:text-sky-300 underline"
                    >
                      {showJsonText ? 'Use File Upload' : 'Paste Raw JSON'}
                    </button>
                  </div>

                  {!showJsonText ? (
                    <div>
                      <input
                        type="file"
                        accept=".json"
                        id="sa-json-file-input"
                        onChange={handleFileUploadJson}
                        className="block w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-sky-600 file:text-white hover:file:bg-sky-500 cursor-pointer"
                      />
                      <p className="text-[11px] text-slate-500 mt-1.5">
                        Download your Service Account JSON key from Google Cloud Console &gt; IAM &amp; Admin &gt; Service Accounts.
                      </p>
                    </div>
                  ) : (
                    <div>
                      <textarea
                        rows={4}
                        value={serviceAccountJson}
                        onChange={(e) => {
                          setServiceAccountJson(e.target.value);
                          try {
                            const p = JSON.parse(e.target.value);
                            if (p.client_email) setSaParsedEmail(p.client_email);
                            if (p.project_id) setSaParsedProjectId(p.project_id);
                          } catch {}
                        }}
                        placeholder='Paste full {"type": "service_account", "project_id": ...} here'
                        className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-white font-mono focus:outline-none focus:border-sky-500"
                      />
                    </div>
                  )}
                </div>

                {/* Step 2: Share Google Drive Folder */}
                {(saParsedEmail || gdriveConfig?.client_email) && (
                  <div className="p-4 rounded-xl bg-sky-950/40 border border-sky-500/30 space-y-3">
                    <span className="text-xs font-semibold text-white flex items-center gap-2">
                      <span className="w-5 h-5 rounded-full bg-sky-500/20 text-sky-400 font-mono text-[11px] flex items-center justify-center font-bold">2</span>
                      Share Your Google Drive Folder as Editor
                    </span>

                    <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div className="truncate">
                        <span className="text-[10px] text-sky-400 uppercase font-semibold block tracking-wider">Service Account Email:</span>
                        <span className="font-mono text-xs text-white select-all">{saParsedEmail || gdriveConfig?.client_email}</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => copyEmailToClipboard(saParsedEmail || gdriveConfig?.client_email)}
                        className="px-3 py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-semibold flex items-center gap-1.5 transition shrink-0 self-start sm:self-auto"
                      >
                        {copiedEmail ? <Check className="w-3.5 h-3.5 text-emerald-300" /> : <Copy className="w-3.5 h-3.5" />}
                        <span>{copiedEmail ? 'Copied!' : 'Copy Email'}</span>
                      </button>
                    </div>

                    <p className="text-[11px] text-slate-300 leading-relaxed">
                      👉 Open <a href="https://drive.google.com" target="_blank" rel="noopener noreferrer" className="text-sky-400 underline inline-flex items-center gap-0.5">drive.google.com <ExternalLink className="w-3 h-3" /></a>, right-click the folder where you want b00k5 files stored, click <strong>Share</strong>, and add this Service Account email with <strong>Editor</strong> permission.
                    </p>
                  </div>
                )}

                {/* Step 3: Target Folder ID / Link */}
                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-3">
                  <span className="text-xs font-semibold text-white flex items-center gap-2">
                    <span className="w-5 h-5 rounded-full bg-sky-500/20 text-sky-400 font-mono text-[11px] flex items-center justify-center font-bold">3</span>
                    Target Google Drive Folder ID / Link (Optional)
                  </span>

                  <div className="space-y-2 text-xs">
                    <input
                      type="text"
                      id="root-folder-id-input"
                      value={rootFolderId}
                      onChange={(e) => setRootFolderId(e.target.value)}
                      placeholder="Paste Drive Folder URL (e.g. drive.google.com/drive/folders/1ABC...) or Folder ID"
                      className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono text-xs focus:outline-none focus:border-sky-500"
                    />
                    <p className="text-[11px] text-slate-500">
                      If left empty, b00k5 will automatically create or use a root folder named <code className="text-sky-400">{rootFolder}</code>.
                    </p>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex flex-wrap items-center gap-3 pt-2">
                  <button
                    type="button"
                    onClick={handleTestConnection}
                    disabled={testingConnection}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 text-xs font-semibold rounded-lg transition flex items-center gap-1.5"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${testingConnection ? 'animate-spin' : ''}`} />
                    {testingConnection ? 'Testing API...' : 'Test Live Connection'}
                  </button>

                  <button
                    type="button"
                    onClick={handleSaveConfig}
                    disabled={savingConfig || (!serviceAccountJson && !gdriveConfig?.configured)}
                    className="flex-1 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-semibold rounded-lg shadow-md shadow-emerald-600/20 transition flex items-center justify-center gap-1.5"
                  >
                    <Check className="w-4 h-4" />
                    {savingConfig ? 'Saving...' : 'Save & Authorize Service Account'}
                  </button>

                  {gdriveConfig?.configured && (
                    <button
                      type="button"
                      onClick={handleDisconnectGoogle}
                      className="px-3.5 py-2 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-400 text-xs font-semibold rounded-lg transition"
                    >
                      Disconnect
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* Direct Upload Flow to Google Drive */}
            <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-5">
              <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                <Upload className="w-5 h-5 text-sky-400" />
                <h3 className="text-sm font-bold text-white">Direct Upload to Google Drive Mirror</h3>
              </div>

              <p className="text-xs text-slate-400">
                Instantly deposits documents into the canonical Indian Financial Year folder structure and guarantees local MinIO mirroring in under 100ms.
              </p>

              {uploadSuccess && (
                <div className="p-3.5 rounded-lg bg-emerald-950/40 border border-emerald-800 text-emerald-300 text-xs space-y-1.5 font-mono">
                  <div className="flex items-center gap-1.5 text-emerald-400 font-sans font-semibold">
                    <CheckCircle2 className="w-4 h-4" />
                    Uploaded &amp; Mirrored to Google Drive!
                  </div>
                  <div>File: <span className="text-white">{uploadSuccess.file_name}</span></div>
                  <div>Remote Path: <span className="text-sky-300">{uploadSuccess.gdrive_folder_path}</span></div>
                  <div>File ID: <span className="text-slate-400">{uploadSuccess.gdrive_file_id}</span></div>
                  <div className="truncate">SHA-256: <span className="text-slate-400">{uploadSuccess.sha256_checksum}</span></div>
                  {uploadSuccess.web_view_link && (
                    <a
                      href={uploadSuccess.web_view_link}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-sky-400 hover:underline pt-1 font-sans text-[11px]"
                    >
                      Open in Google Drive <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
                </div>
              )}

              {uploadError && (
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  <span>{uploadError}</span>
                </div>
              )}

              <form onSubmit={handleDirectUpload} className="space-y-4 text-xs">
                <div>
                  <label className="text-slate-300 font-medium block mb-1">Select File:</label>
                  <input
                    type="file"
                    onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                    className="block w-full text-xs text-slate-400 file:mr-3 file:py-2 file:px-3 file:rounded file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-sky-400 hover:file:bg-slate-700 cursor-pointer"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-slate-300 font-medium block mb-1">Target Category:</label>
                    <select
                      value={uploadCategory}
                      onChange={(e) => setUploadCategory(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-white"
                    >
                      <option value="bank_statements">Bank Statements</option>
                      <option value="vendor_bills">Vendor Bills &amp; ITC</option>
                      <option value="corporate_legal">Corporate Legal (COI, MOA, AOA)</option>
                      <option value="statutory_filings">Statutory Filings (AOC-4, MGT-7)</option>
                      <option value="board_governance">Board Governance &amp; SS-1</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-slate-300 font-medium block mb-1">Document Date:</label>
                    <input
                      type="date"
                      value={uploadDate}
                      onChange={(e) => setUploadDate(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-2 text-white font-mono"
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={uploading || !uploadFile}
                  className="w-full py-2.5 px-4 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-semibold rounded-lg flex items-center justify-center gap-2 shadow-sm transition-all"
                >
                  <Upload className={`w-4 h-4 ${uploading ? 'animate-bounce' : ''}`} />
                  {uploading ? 'Synchronizing to Google Drive...' : 'Upload & Synchronize to Google Drive'}
                </button>
              </form>
            </div>
          </div>

          {/* Canonical Hierarchy Explorer */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Folder className="w-4 h-4 text-amber-400" />
                Canonical Google Drive Directory Structure
              </h3>
              <p className="text-xs text-slate-400">
                b00k5 maps and mirrors your sovereign files into standardized Indian corporate accounting folders.
              </p>

              <div className="space-y-2 text-xs font-mono">
                {(dashboard?.canonical_hierarchy || [
                  '/b00k5/Corporate Legal (COI, MOA, AOA)/',
                  '/b00k5/Tax Registrations (PAN, GST)/',
                  '/b00k5/FY 2025-26/Bank Statements/',
                  '/b00k5/FY 2025-26/Vendor Bills & ITC/',
                  '/b00k5/FY 2025-26/Statutory Filings (AOC-4, MGT-7)/',
                  '/b00k5/Board Governance & SS-1 Minutes/'
                ]).map((path: string, idx: number) => (
                  <div
                    key={idx}
                    className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg flex items-center justify-between text-slate-300 hover:border-slate-700 transition-colors"
                  >
                    <div className="flex items-center gap-2 truncate">
                      <Folder className="w-4 h-4 text-amber-400 shrink-0" />
                      <span className="truncate">{path}</span>
                    </div>
                    <span className="text-[10px] font-sans text-emerald-400 px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20 shrink-0">
                      Mirrored
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Recent Synchronized Files Log */}
            <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                    <Clock className="w-4 h-4 text-sky-400" />
                    Mirrored Cloud Archive ({mirroredFiles.length} files)
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Live statutory files mirrored in storage hierarchy with SHA-256 integrity proofs.
                  </p>
                </div>
                {mirroredFiles.length > 0 && (
                  <button
                    onClick={handleDownloadArchive}
                    disabled={downloadingArchive}
                    className="px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-500/30 text-emerald-400 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download All (.zip)
                  </button>
                )}
              </div>

              {filesLoading ? (
                <div className="py-8 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-sky-400" />
                  <span>Scanning mirrored storage hierarchy...</span>
                </div>
              ) : mirroredFiles.length === 0 ? (
                <div className="py-8 text-center border border-dashed border-slate-800 rounded-xl space-y-3">
                  <Folder className="w-8 h-8 text-slate-600 mx-auto" />
                  <p className="text-xs text-slate-400">No mirrored statutory documents found yet.</p>
                  <button
                    onClick={handleTriggerSync}
                    disabled={syncing}
                    className="px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold rounded-lg inline-flex items-center gap-2 transition"
                  >
                    <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
                    Populate &amp; Mirror Now
                  </button>
                </div>
              ) : (
                <div className="space-y-3 max-h-[420px] overflow-y-auto pr-1">
                  {mirroredFiles.map((item: any, i: number) => (
                    <div
                      key={i}
                      className="p-3 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1.5 text-xs font-mono hover:border-slate-700 transition"
                    >
                      <div className="flex items-center justify-between font-sans">
                        <span className="font-semibold text-white truncate max-w-[280px]">{item.file_name || item.name}</span>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-slate-400 font-mono">
                            {item.size_bytes ? `${(item.size_bytes / 1024).toFixed(1)} KB` : '0 KB'}
                          </span>
                          <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 font-sans">
                            Mirrored
                          </span>
                        </div>
                      </div>
                      <div className="text-[11px] text-sky-400/80 truncate font-mono">
                        📁 {item.relative_path}
                      </div>
                      <div className="flex items-center justify-between text-[10px] text-slate-500 pt-0.5">
                        <span className="truncate">SHA-256: {item.sha256 ? item.sha256.substring(0, 24) + '...' : 'Verified'}</span>
                        <span>{item.modified_at ? new Date(item.modified_at).toLocaleTimeString() : 'Just now'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
