'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import {
  Cloud,
  Shield,
  Database,
  CheckCircle2,
  RefreshCw,
  AlertCircle,
  ArrowLeft,
  Lock,
  HardDrive,
  Server,
  Archive,
  RotateCcw,
  X,
  ShieldAlert,
  Eye,
  EyeOff,
  Check,
  ExternalLink,
  Layers,
  ArrowUpRight,
  FileText,
  Receipt,
  ShieldCheck,
  Building,
  Sliders,
  ChevronRight,
  AlertTriangle
} from 'lucide-react';
import Link from 'next/link';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import { fetchApi } from '@/lib/api';
import { GoogleDriveSyncView } from '@/components/storage/GoogleDriveSyncView';

interface BackupLog {
  id: string;
  filename: string;
  file_size_bytes: number;
  sha256_checksum: string;
  gdrive_file_id: string;
  gdrive_folder_path: string;
  status: string;
  duration_seconds: number;
  created_at: string;
}

interface MinioSnapshot {
  object_key: string;
  filename: string;
  size_bytes: number;
  last_modified: string | null;
  uri: string;
}

interface S3MirrorConfig {
  configured: boolean;
  provider: 'cloudflare_r2' | 'aws_s3' | 'custom_s3';
  endpoint: string;
  bucket_name: string;
  region: string;
  root_prefix: string;
  access_key_id: string;
  has_secret: boolean;
  secret_access_key_masked: string;
  status: string;
  retention_policy?: {
    keep_backups_count: number;
    auto_prune_backups: boolean;
    max_backup_age_days: number;
  };
  storage_usage?: {
    total_bytes: number;
    total_mb: number;
    total_gb: number;
    free_tier_gb: number;
    used_percentage: number;
    remaining_free_gb: number;
    categories?: Record<string, { bytes: number; count: number }>;
    file_count: number;
  };
  last_tested_at?: string | null;
  last_synced_at?: string | null;
}

function IntegrationsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // URL state sync
  const initialTab = (searchParams.get('tab') as 'cloud' | 'backups' | 'restore') || 'cloud';
  const initialProvider = (searchParams.get('provider') as 'gdrive' | 's3') || 'gdrive';

  const [activeTab, setActiveTab] = useState<'cloud' | 'backups' | 'restore'>(initialTab);
  const [cloudProvider, setCloudProvider] = useState<'gdrive' | 's3'>(initialProvider);

  // Backup & DB Log state
  const [backingUp, setBackingUp] = useState<boolean>(false);
  const [backupStatus, setBackupStatus] = useState<string | null>(null);
  const [logs, setLogs] = useState<BackupLog[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [gdriveConfigured, setGdriveConfigured] = useState<boolean>(false);

  // MinIO S3 Checkpoints & Restore State
  const [minioSnapshots, setMinioSnapshots] = useState<MinioSnapshot[]>([]);
  const [creatingCheckpoint, setCreatingCheckpoint] = useState<boolean>(false);
  const [checkpointStatus, setCheckpointStatus] = useState<string | null>(null);
  const [restoringKey, setRestoringKey] = useState<string | null>(null);
  const [restoreModalOpen, setRestoreModalOpen] = useState<boolean>(false);
  const [targetSnapshot, setTargetSnapshot] = useState<MinioSnapshot | null>(null);
  const [restoreSecret, setRestoreSecret] = useState<string>('');
  const [restoreResult, setRestoreResult] = useState<any | null>(null);

  // S3 / Cloudflare R2 Remote Mirror State
  const [s3Config, setS3Config] = useState<S3MirrorConfig | null>(null);
  const [s3Provider, setS3Provider] = useState<'cloudflare_r2' | 'aws_s3' | 'custom_s3'>('cloudflare_r2');
  const [s3Endpoint, setS3Endpoint] = useState<string>('');
  const [s3Bucket, setS3Bucket] = useState<string>('');
  const [s3Region, setS3Region] = useState<string>('auto');
  const [s3Prefix, setS3Prefix] = useState<string>('');
  const [s3AccessKey, setS3AccessKey] = useState<string>('');
  const [s3SecretKey, setS3SecretKey] = useState<string>('');
  const [showSecret, setShowSecret] = useState<boolean>(false);
  const [testingS3, setTestingS3] = useState<boolean>(false);
  const [savingS3, setSavingS3] = useState<boolean>(false);
  const [syncingS3, setSyncingS3] = useState<boolean>(false);
  const [s3TestStatus, setS3TestStatus] = useState<{ success: boolean; message: string; latency_ms?: number } | null>(null);
  const [s3SyncStatus, setS3SyncStatus] = useState<{ success: boolean; message: string; count?: number; retention?: any } | null>(null);

  // Retention & Storage Quota State
  const [retentionKeepCount, setRetentionKeepCount] = useState<number>(7);
  const [retentionAutoPrune, setRetentionAutoPrune] = useState<boolean>(true);
  const [savingRetention, setSavingRetention] = useState<boolean>(false);
  const [pruningBackups, setPruningBackups] = useState<boolean>(false);
  const [pruneResult, setPruneResult] = useState<{ pruned_count: number; reclaimed_mb: number } | null>(null);

  // Update URL on tab/provider switch
  const handleTabChange = (tab: 'cloud' | 'backups' | 'restore') => {
    setActiveTab(tab);
    const params = new URLSearchParams(window.location.search);
    params.set('tab', tab);
    router.replace(`/settings/integrations?${params.toString()}`);
  };

  const handleProviderChange = (provider: 'gdrive' | 's3') => {
    setCloudProvider(provider);
    const params = new URLSearchParams(window.location.search);
    params.set('provider', provider);
    router.replace(`/settings/integrations?${params.toString()}`);
  };

  const fetchS3Config = async () => {
    try {
      const data = await fetchApi('/api/v1/storage/s3-config');
      if (data) {
        setS3Config(data);
        if (data.provider) setS3Provider(data.provider);
        if (data.endpoint) setS3Endpoint(data.endpoint);
        if (data.bucket_name) setS3Bucket(data.bucket_name);
        if (data.region) setS3Region(data.region);
        if (data.root_prefix) setS3Prefix(data.root_prefix);
        if (data.access_key_id) setS3AccessKey(data.access_key_id);
        if (data.retention_policy) {
          if (data.retention_policy.keep_backups_count) setRetentionKeepCount(data.retention_policy.keep_backups_count);
          if (typeof data.retention_policy.auto_prune_backups === 'boolean') setRetentionAutoPrune(data.retention_policy.auto_prune_backups);
        }
      }
    } catch (e) {
      console.warn('Failed to load S3 mirror config:', e);
    }
  };

  const handleSaveRetention = async () => {
    setSavingRetention(true);
    try {
      const res = await fetchApi('/api/v1/storage/s3-retention-policy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          keep_backups_count: retentionKeepCount,
          auto_prune_backups: retentionAutoPrune,
          max_backup_age_days: 30
        })
      });
      alert(res.message || 'Retention policy saved.');
      await fetchS3Config();
    } catch (err: any) {
      alert(err.message || 'Failed to save retention policy.');
    } finally {
      setSavingRetention(false);
    }
  };

  const handlePruneBackups = async () => {
    if (!window.confirm(`Prune older database snapshots on Cloudflare R2 / S3, retaining the ${retentionKeepCount} newest? (Invoices, bills, and tax filings will NOT be deleted).`)) return;
    setPruningBackups(true);
    try {
      const res = await fetchApi('/api/v1/storage/s3-prune-backups', {
        method: 'POST'
      });
      setPruneResult(res.prune_details || { pruned_count: 0, reclaimed_mb: 0 });
      alert(res.message || 'Backups pruned successfully.');
      await fetchS3Config();
    } catch (err: any) {
      alert(err.message || 'Failed to prune backups.');
    } finally {
      setPruningBackups(false);
    }
  };

  const handleTestS3 = async () => {
    setTestingS3(true);
    setS3TestStatus(null);
    try {
      const res = await fetchApi('/api/v1/storage/s3-test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: s3Provider,
          endpoint: s3Endpoint.trim(),
          bucket_name: s3Bucket.trim(),
          region: s3Region.trim(),
          root_prefix: s3Prefix.trim() || undefined,
          access_key_id: s3AccessKey.trim(),
          secret_access_key: s3SecretKey.trim() || undefined
        })
      });

      if (res.success) {
        setS3TestStatus({
          success: true,
          message: res.message || 'Connection verified successfully!',
          latency_ms: res.latency_ms
        });
      } else {
        setS3TestStatus({
          success: false,
          message: res.error || res.message || 'Connection test failed.'
        });
      }
    } catch (err: any) {
      setS3TestStatus({
        success: false,
        message: err.message || 'Connection check failed.'
      });
    } finally {
      setTestingS3(false);
    }
  };

  const handleSaveS3 = async () => {
    setSavingS3(true);
    setS3TestStatus(null);
    try {
      const res = await fetchApi('/api/v1/storage/s3-config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: s3Provider,
          endpoint: s3Endpoint.trim(),
          bucket_name: s3Bucket.trim(),
          region: s3Region.trim(),
          root_prefix: s3Prefix.trim() || undefined,
          access_key_id: s3AccessKey.trim(),
          secret_access_key: s3SecretKey.trim() || undefined
        })
      });

      setS3TestStatus({
        success: true,
        message: res.message || 'S3 Cloud Mirror configuration saved and verified!',
        latency_ms: res.latency_ms
      });
      setS3SecretKey('');
      await fetchS3Config();
    } catch (err: any) {
      setS3TestStatus({
        success: false,
        message: err.message || 'Failed to save S3 configuration.'
      });
    } finally {
      setSavingS3(false);
    }
  };

  const handleSyncS3 = async () => {
    setSyncingS3(true);
    setS3SyncStatus(null);
    try {
      const res = await fetchApi('/api/v1/storage/s3-sync-all', {
        method: 'POST'
      });
      setS3SyncStatus({
        success: true,
        message: res.message || `Successfully synced ${res.synced_count} items.`,
        count: res.synced_count
      });
      await fetchS3Config();
      await fetchLogs();
    } catch (err: any) {
      setS3SyncStatus({
        success: false,
        message: err.message || 'S3 Sync failed.'
      });
    } finally {
      setSyncingS3(false);
    }
  };

  const fetchLogs = async () => {
    try {
      const data = await fetchApi('/api/v1/backup/logs');
      setLogs(data);
    } catch (e) {
      console.warn('Failed to fetch backup logs:', e);
    }
  };

  const checkGDriveConfig = async () => {
    try {
      const config = await fetchApi('/api/v1/storage/gdrive-config');
      if (config && config.configured) {
        setGdriveConfigured(true);
      }
    } catch (e) {
      console.warn('Failed to fetch gdrive config:', e);
    }
  };

  const fetchMinioSnapshots = async () => {
    try {
      const res = await fetchApi('/api/v1/backup/minio-snapshots');
      if (res && res.snapshots) {
        setMinioSnapshots(res.snapshots);
      }
    } catch (e) {
      console.warn('Failed to fetch minio snapshots:', e);
    }
  };

  const handleCreateCheckpoint = async () => {
    setCreatingCheckpoint(true);
    setCheckpointStatus(null);
    try {
      const res = await fetchApi('/api/v1/backup/minio-checkpoint', {
        method: 'POST'
      });
      setCheckpointStatus(res.message || 'Local MinIO Checkpoint snapshot created successfully.');
      await fetchMinioSnapshots();
    } catch (err: any) {
      setCheckpointStatus(`Failed: ${err.message || 'Error creating checkpoint.'}`);
    } finally {
      setCreatingCheckpoint(false);
    }
  };

  const handleTriggerBackup = async () => {
    setBackingUp(true);
    setBackupStatus(null);
    setErrorMsg(null);
    try {
      const res = await fetchApi('/api/v1/backup/trigger', {
        method: 'POST'
      });
      setBackupStatus(`Database backup snapshot successfully created: ${res.filename} (${(res.file_size_bytes / 1024).toFixed(1)} KB)`);
      await fetchLogs();
      await fetchMinioSnapshots();
      await fetchS3Config();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to trigger backup.');
    } finally {
      setBackingUp(false);
    }
  };

  const openRestoreModal = (snapshot: MinioSnapshot) => {
    setTargetSnapshot(snapshot);
    setRestoreSecret('');
    setRestoreResult(null);
    setRestoreModalOpen(true);
  };

  const handleExecuteRestore = async () => {
    if (!targetSnapshot) return;
    if (!restoreSecret.trim()) {
      alert('Administrator password is required to authorize database restore.');
      return;
    }

    setRestoringKey(targetSnapshot.object_key);
    try {
      const res = await fetchApi('/api/v1/backup/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          snapshot_key: targetSnapshot.object_key,
          admin_secret: restoreSecret.trim(),
          create_safety_checkpoint: true
        })
      });

      setRestoreResult({
        success: true,
        message: res.message || 'Database restored successfully!',
        details: res
      });
      await fetchMinioSnapshots();
    } catch (err: any) {
      setRestoreResult({
        success: false,
        message: err.message || 'Restore execution failed.'
      });
    } finally {
      setRestoringKey(null);
    }
  };

  useEffect(() => {
    fetchLogs();
    checkGDriveConfig();
    fetchMinioSnapshots();
    fetchS3Config();
  }, []);

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 antialiased overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Navbar />

        <main className="p-8 max-w-7xl mx-auto w-full space-y-8">
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
            <div>
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
                  <HardDrive className="w-6 h-6" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                    Cloud Storage & Database Backups
                    <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono font-medium">
                      Unified Console
                    </span>
                  </h1>
                  <p className="text-sm text-slate-400 mt-0.5">
                    Offsite cloud sync (Google Drive & Cloudflare R2 / S3), on-demand database snapshots, and point-in-time recovery.
                  </p>
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="flex items-center gap-3">
              <button
                onClick={handleTriggerBackup}
                disabled={backingUp}
                className="px-4 py-2.5 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white font-medium text-sm flex items-center gap-2 transition-colors shadow-sm"
              >
                <Database className={`w-4 h-4 ${backingUp ? 'animate-spin' : ''}`} />
                {backingUp ? 'Creating Snapshot...' : 'Run Instant DB Backup'}
              </button>
            </div>
          </div>

          {/* Top-Level Tabs Navigation */}
          <div className="flex border-b border-slate-800 gap-2">
            <button
              onClick={() => handleTabChange('cloud')}
              className={`px-4 py-3 font-medium text-sm border-b-2 flex items-center gap-2 transition-colors ${
                activeTab === 'cloud'
                  ? 'border-sky-500 text-sky-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Cloud className="w-4 h-4" />
              Cloud Storage & Sync
              <span className="px-1.5 py-0.5 text-[10px] rounded bg-slate-800 text-slate-400 border border-slate-700">
                GDrive / R2 / S3
              </span>
            </button>

            <button
              onClick={() => handleTabChange('backups')}
              className={`px-4 py-3 font-medium text-sm border-b-2 flex items-center gap-2 transition-colors ${
                activeTab === 'backups'
                  ? 'border-sky-500 text-sky-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Database className="w-4 h-4" />
              Database Backups & Snapshots
              <span className="px-1.5 py-0.5 text-[10px] rounded bg-slate-800 text-slate-400 border border-slate-700">
                {logs.length}
              </span>
            </button>

            <button
              onClick={() => handleTabChange('restore')}
              className={`px-4 py-3 font-medium text-sm border-b-2 flex items-center gap-2 transition-colors ${
                activeTab === 'restore'
                  ? 'border-sky-500 text-sky-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <RotateCcw className="w-4 h-4" />
              Restore & Checkpoints
              <span className="px-1.5 py-0.5 text-[10px] rounded bg-slate-800 text-slate-400 border border-slate-700">
                {minioSnapshots.length}
              </span>
            </button>
          </div>

          {/* Global Status Banners */}
          {backupStatus && (
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 shrink-0" />
              <span className="text-sm font-medium">{backupStatus}</span>
            </div>
          )}

          {errorMsg && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center gap-3">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <span className="text-sm font-medium">{errorMsg}</span>
            </div>
          )}

          {/* TAB 1: CLOUD STORAGE & SYNC */}
          {activeTab === 'cloud' && (
            <div className="space-y-6">
              {/* Provider Sub-selector Switch */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-slate-900 border border-slate-800">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 px-2">
                    Storage Provider:
                  </span>
                  <button
                    onClick={() => handleProviderChange('gdrive')}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors ${
                      cloudProvider === 'gdrive'
                        ? 'bg-sky-500/20 text-sky-300 border border-sky-500/30'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    <Cloud className="w-4 h-4 text-sky-400" />
                    Google Drive
                    {gdriveConfigured && (
                      <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                    )}
                  </button>

                  <button
                    onClick={() => handleProviderChange('s3')}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors ${
                      cloudProvider === 's3'
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    <Server className="w-4 h-4 text-amber-400" />
                    Cloudflare R2 / S3
                    {s3Config?.configured && (
                      <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                    )}
                  </button>
                </div>

                <div className="text-xs text-slate-500 font-mono">
                  {cloudProvider === 'gdrive' ? 'Free 15 GB via Google Workspace' : 'Free 10 GB/mo via Cloudflare R2'}
                </div>
              </div>

              {/* View 1: Google Drive */}
              {cloudProvider === 'gdrive' && (
                <div>
                  <GoogleDriveSyncView />
                </div>
              )}

              {/* View 2: Cloudflare R2 / AWS S3 */}
              {cloudProvider === 's3' && (
                <div className="space-y-6">
                  {/* Quota & Capacity Usage Card */}
                  {s3Config?.storage_usage && (
                    <div className="p-6 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-amber-950/20 border border-amber-500/20 space-y-4">
                      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div>
                          <div className="flex items-center gap-2">
                            <Layers className="w-5 h-5 text-amber-400" />
                            <h3 className="text-lg font-bold text-white">Cloudflare R2 Storage Quota</h3>
                            <span className="px-2 py-0.5 text-xs font-mono font-medium rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                              Free Tier (10 GB/month)
                            </span>
                          </div>
                          <p className="text-xs text-slate-400 mt-1">
                            Zero egress fees on Cloudflare R2. Monitors remote bucket usage across all categories.
                          </p>
                        </div>

                        <div className="flex items-center gap-4 text-right">
                          <div>
                            <div className="text-2xl font-mono font-bold text-amber-300">
                              {s3Config.storage_usage.total_mb.toFixed(2)} <span className="text-sm font-normal text-slate-400">MB</span>
                            </div>
                            <div className="text-xs text-slate-500 font-mono">
                              of {s3Config.storage_usage.free_tier_gb} GB used ({s3Config.storage_usage.used_percentage.toFixed(2)}%)
                            </div>
                          </div>
                          <div className="h-10 w-[1px] bg-slate-800"></div>
                          <div>
                            <div className="text-2xl font-mono font-bold text-emerald-400">
                              {s3Config.storage_usage.remaining_free_gb.toFixed(2)} <span className="text-sm font-normal text-slate-400">GB</span>
                            </div>
                            <div className="text-xs text-slate-500 font-mono">Remaining Free Allowance</div>
                          </div>
                        </div>
                      </div>

                      {/* Progress Bar */}
                      <div className="space-y-1.5">
                        <div className="w-full h-3 rounded-full bg-slate-800 overflow-hidden p-0.5">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              s3Config.storage_usage.used_percentage > 85 ? 'bg-rose-500' : s3Config.storage_usage.used_percentage > 60 ? 'bg-amber-500' : 'bg-emerald-500'
                            }`}
                            style={{ width: `${Math.max(s3Config.storage_usage.used_percentage, 0.5)}%` }}
                          ></div>
                        </div>
                        <div className="flex justify-between text-[11px] text-slate-500 font-mono">
                          <span>0 GB</span>
                          <span>{s3Config.storage_usage.file_count} total remote objects</span>
                          <span>{s3Config.storage_usage.free_tier_gb} GB</span>
                        </div>
                      </div>

                      {/* Category Breakdown */}
                      {s3Config.storage_usage.categories && (
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                            <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-1">
                              <Receipt className="w-3.5 h-3.5 text-sky-400" />
                              <span>Tax Invoices</span>
                            </div>
                            <div className="text-sm font-bold font-mono text-white">
                              {((s3Config.storage_usage.categories['invoices']?.bytes || 0) / (1024 * 1024)).toFixed(2)} MB
                            </div>
                            <div className="text-[10px] text-slate-500">
                              {s3Config.storage_usage.categories['invoices']?.count || 0} files
                            </div>
                          </div>

                          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                            <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-1">
                              <FileText className="w-3.5 h-3.5 text-indigo-400" />
                              <span>Vendor Bills</span>
                            </div>
                            <div className="text-sm font-bold font-mono text-white">
                              {((s3Config.storage_usage.categories['bills']?.bytes || 0) / (1024 * 1024)).toFixed(2)} MB
                            </div>
                            <div className="text-[10px] text-slate-500">
                              {s3Config.storage_usage.categories['bills']?.count || 0} files
                            </div>
                          </div>

                          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                            <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-1">
                              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                              <span>Statutory Vault</span>
                            </div>
                            <div className="text-sm font-bold font-mono text-white">
                              {((s3Config.storage_usage.categories['statutory']?.bytes || 0) / (1024 * 1024)).toFixed(2)} MB
                            </div>
                            <div className="text-[10px] text-slate-500">
                              {s3Config.storage_usage.categories['statutory']?.count || 0} files
                            </div>
                          </div>

                          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                            <div className="flex items-center gap-1.5 text-xs text-slate-400 mb-1">
                              <Database className="w-3.5 h-3.5 text-amber-400" />
                              <span>DB Backups</span>
                            </div>
                            <div className="text-sm font-bold font-mono text-white">
                              {((s3Config.storage_usage.categories['backups']?.bytes || 0) / (1024 * 1024)).toFixed(2)} MB
                            </div>
                            <div className="text-[10px] text-slate-500">
                              {s3Config.storage_usage.categories['backups']?.count || 0} snapshots
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Retention Policy Configuration Card */}
                  <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <Sliders className="w-5 h-5 text-sky-400" />
                          <h3 className="text-lg font-bold text-white">Backup Retention & Auto-Pruning Policy</h3>
                        </div>
                        <p className="text-xs text-slate-400 mt-1">
                          Protect against quota exhaustion by automatically retaining only the newest N database snapshots. Documents and invoices are permanent.
                        </p>
                      </div>

                      <div className="flex items-center gap-3">
                        <button
                          onClick={handlePruneBackups}
                          disabled={pruningBackups || !s3Config?.configured}
                          className="px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-300 font-medium text-xs flex items-center gap-2 transition-colors border border-slate-700"
                        >
                          <Archive className={`w-3.5 h-3.5 ${pruningBackups ? 'animate-spin' : ''}`} />
                          {pruningBackups ? 'Pruning...' : 'Prune Older Backups Now'}
                        </button>

                        <button
                          onClick={handleSaveRetention}
                          disabled={savingRetention}
                          className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white font-medium text-xs flex items-center gap-2 transition-colors shadow-sm"
                        >
                          {savingRetention ? 'Saving...' : 'Save Retention Policy'}
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                      <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2">
                        <label className="text-xs font-medium text-slate-300 flex items-center justify-between">
                          <span>Keep Most Recent Database Snapshots:</span>
                          <span className="font-mono text-sky-400 font-bold">{retentionKeepCount} backups</span>
                        </label>
                        <input
                          type="range"
                          min="3"
                          max="30"
                          value={retentionKeepCount}
                          onChange={(e) => setRetentionKeepCount(parseInt(e.target.value))}
                          className="w-full accent-sky-500 cursor-pointer"
                        />
                        <p className="text-[11px] text-slate-500">
                          Recommended: 7 snapshots (keeps 1 week of daily backups under 50 MB total).
                        </p>
                      </div>

                      <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                        <div>
                          <div className="text-sm font-medium text-white">Auto-Prune on Every Sync</div>
                          <div className="text-xs text-slate-500 mt-0.5">
                            Automatically removes snapshots beyond the retention threshold during scheduled backups.
                          </div>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input
                            type="checkbox"
                            checked={retentionAutoPrune}
                            onChange={(e) => setRetentionAutoPrune(e.target.checked)}
                            className="sr-only peer"
                          />
                          <div className="w-11 h-6 bg-slate-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-sky-600"></div>
                        </label>
                      </div>
                    </div>

                    {pruneResult && (
                      <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center gap-2">
                        <Check className="w-4 h-4 shrink-0" />
                        <span>Pruned {pruneResult.pruned_count} old backups, reclaimed {pruneResult.reclaimed_mb.toFixed(2)} MB on Cloudflare R2.</span>
                      </div>
                    )}
                  </div>

                  {/* Remote S3 Configuration Form */}
                  <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-6">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <Server className="w-5 h-5 text-sky-400" />
                          <h3 className="text-lg font-bold text-white">Cloudflare R2 / S3 Remote Configuration</h3>
                          {s3Config?.configured ? (
                            <span className="px-2 py-0.5 text-xs font-mono font-medium rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                              Active & Connected
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 text-xs font-mono font-medium rounded bg-slate-800 text-slate-400 border border-slate-700">
                              Not Configured
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-400 mt-1">
                          Configure S3-compatible credentials to mirror documents, bills, invoices, and database snapshots offsite.
                        </p>
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={handleSyncS3}
                          disabled={syncingS3 || !s3Config?.configured}
                          className="px-3.5 py-2 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 disabled:opacity-50 text-xs font-medium flex items-center gap-2 transition-colors"
                        >
                          <RefreshCw className={`w-3.5 h-3.5 ${syncingS3 ? 'animate-spin' : ''}`} />
                          {syncingS3 ? 'Syncing...' : 'Sync All Files Now'}
                        </button>
                      </div>
                    </div>

                    {s3TestStatus && (
                      <div className={`p-4 rounded-xl border text-sm flex items-center justify-between gap-3 ${
                        s3TestStatus.success
                          ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                          : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                      }`}>
                        <div className="flex items-center gap-2">
                          {s3TestStatus.success ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
                          <span>{s3TestStatus.message}</span>
                        </div>
                        {s3TestStatus.latency_ms && (
                          <span className="text-xs font-mono opacity-80">
                            Latency: {s3TestStatus.latency_ms} ms
                          </span>
                        )}
                      </div>
                    )}

                    {s3SyncStatus && (
                      <div className={`p-4 rounded-xl border text-sm flex items-center gap-3 ${
                        s3SyncStatus.success
                          ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                          : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                      }`}>
                        {s3SyncStatus.success ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
                        <span>{s3SyncStatus.message}</span>
                      </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <label className="text-xs font-medium text-slate-300">Provider Service</label>
                        <select
                          value={s3Provider}
                          onChange={(e) => setS3Provider(e.target.value as any)}
                          className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white focus:outline-none focus:border-sky-500"
                        >
                          <option value="cloudflare_r2">Cloudflare R2 (10 GB Free Tier, Zero Egress)</option>
                          <option value="aws_s3">Amazon Web Services (AWS S3)</option>
                          <option value="custom_s3">Custom S3 / Wasabi / Backblaze B2</option>
                        </select>
                      </div>

                      <div className="space-y-2">
                        <label className="text-xs font-medium text-slate-300">
                          S3 Endpoint URL
                          {s3Provider === 'cloudflare_r2' && (
                            <span className="text-[10px] text-slate-500 ml-2 font-mono">
                              (e.g. https://&lt;account_id&gt;.r2.cloudflarestorage.com)
                            </span>
                          )}
                        </label>
                        <input
                          type="text"
                          value={s3Endpoint}
                          onChange={(e) => setS3Endpoint(e.target.value)}
                          placeholder="https://<account_id>.r2.cloudflarestorage.com"
                          className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white font-mono placeholder:text-slate-600 focus:outline-none focus:border-sky-500"
                        />
                      </div>

                      <div className="space-y-2">
                        <label className="text-xs font-medium text-slate-300">Bucket Name</label>
                        <input
                          type="text"
                          value={s3Bucket}
                          onChange={(e) => setS3Bucket(e.target.value)}
                          placeholder="b00k5-offsite-vault"
                          className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white font-mono placeholder:text-slate-600 focus:outline-none focus:border-sky-500"
                        />
                      </div>

                      <div className="space-y-2">
                        <label className="text-xs font-medium text-slate-300">Region</label>
                        <input
                          type="text"
                          value={s3Region}
                          onChange={(e) => setS3Region(e.target.value)}
                          placeholder="auto (for Cloudflare R2) or us-east-1"
                          className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white font-mono placeholder:text-slate-600 focus:outline-none focus:border-sky-500"
                        />
                      </div>

                      <div className="space-y-2">
                        <label className="text-xs font-medium text-slate-300">Access Key ID</label>
                        <input
                          type="text"
                          value={s3AccessKey}
                          onChange={(e) => setS3AccessKey(e.target.value)}
                          placeholder="R2 API Token Access Key"
                          className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white font-mono placeholder:text-slate-600 focus:outline-none focus:border-sky-500"
                        />
                      </div>

                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <label className="text-xs font-medium text-slate-300">Secret Access Key</label>
                          {s3Config?.has_secret && (
                            <span className="text-[10px] text-emerald-400 font-mono">
                              Secret stored securely ({s3Config.secret_access_key_masked})
                            </span>
                          )}
                        </div>
                        <div className="relative">
                          <input
                            type={showSecret ? 'text' : 'password'}
                            value={s3SecretKey}
                            onChange={(e) => setS3SecretKey(e.target.value)}
                            placeholder={s3Config?.has_secret ? 'Leave blank to preserve existing secret' : 'Paste Secret Access Key'}
                            className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white font-mono placeholder:text-slate-600 focus:outline-none focus:border-sky-500 pr-10"
                          />
                          <button
                            type="button"
                            onClick={() => setShowSecret(!showSecret)}
                            className="absolute right-3 top-3 text-slate-500 hover:text-slate-300"
                          >
                            {showSecret ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-col sm:flex-row items-center justify-end gap-3 pt-4 border-t border-slate-800">
                      <button
                        type="button"
                        onClick={handleTestS3}
                        disabled={testingS3 || !s3Endpoint || !s3Bucket || !s3AccessKey}
                        className="w-full sm:w-auto px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 font-medium text-sm flex items-center justify-center gap-2 transition-colors border border-slate-700"
                      >
                        <Check className={`w-4 h-4 ${testingS3 ? 'animate-spin' : ''}`} />
                        {testingS3 ? 'Testing Connection...' : 'Test S3 Connection'}
                      </button>

                      <button
                        type="button"
                        onClick={handleSaveS3}
                        disabled={savingS3 || !s3Endpoint || !s3Bucket || !s3AccessKey}
                        className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white font-medium text-sm flex items-center justify-center gap-2 transition-colors shadow-sm"
                      >
                        {savingS3 ? 'Saving...' : 'Save & Verify S3 Mirror'}
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: DATABASE BACKUPS & SNAPSHOTS */}
          {activeTab === 'backups' && (
            <div className="space-y-6">
              {/* Backups Summary Bar */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800">
                  <div className="text-xs text-slate-400 font-medium">Total Backups Recorded</div>
                  <div className="text-2xl font-bold font-mono text-white mt-1">{logs.length}</div>
                  <div className="text-[11px] text-slate-500 mt-1">Logged across all operations</div>
                </div>

                <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800">
                  <div className="text-xs text-slate-400 font-medium">Offsite Mirrors Active</div>
                  <div className="text-lg font-bold text-white mt-1 flex items-center gap-2">
                    {gdriveConfigured ? (
                      <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        Google Drive
                      </span>
                    ) : null}
                    {s3Config?.configured ? (
                      <span className="text-xs px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                        Cloudflare R2
                      </span>
                    ) : null}
                    {!gdriveConfigured && !s3Config?.configured ? (
                      <span className="text-xs text-slate-500">Local Only (MinIO)</span>
                    ) : null}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">Automated mirror on backup</div>
                </div>

                <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800">
                  <div className="text-xs text-slate-400 font-medium">Latest Checkpoint</div>
                  <div className="text-sm font-mono text-sky-400 font-semibold truncate mt-1">
                    {logs[0]?.filename || 'No recent backup'}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">
                    {logs[0]?.created_at ? new Date(logs[0].created_at).toLocaleString() : 'N/A'}
                  </div>
                </div>
              </div>

              {/* Backup Audit Log Table */}
              <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Database className="w-5 h-5 text-sky-400" />
                    <h3 className="text-lg font-bold text-white">Database Backup & Sync History</h3>
                  </div>
                  <button
                    onClick={fetchLogs}
                    className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
                    title="Refresh logs"
                  >
                    <RefreshCw className="w-4 h-4" />
                  </button>
                </div>

                {logs.length === 0 ? (
                  <div className="text-center py-12 text-slate-500 text-sm">
                    No backup logs recorded yet. Click "Run Instant DB Backup" to create your first snapshot.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm text-slate-300">
                      <thead className="text-xs uppercase bg-slate-950/60 text-slate-500 border-b border-slate-800 font-mono">
                        <tr>
                          <th className="px-4 py-3">Snapshot Name</th>
                          <th className="px-4 py-3">Size</th>
                          <th className="px-4 py-3">SHA-256 Checksum</th>
                          <th className="px-4 py-3">GDrive ID</th>
                          <th className="px-4 py-3">Duration</th>
                          <th className="px-4 py-3">Status</th>
                          <th className="px-4 py-3 text-right">Created At</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800 font-mono text-xs">
                        {logs.map((log) => (
                          <tr key={log.id} className="hover:bg-slate-800/40 transition-colors">
                            <td className="px-4 py-3 font-semibold text-white">
                              {log.filename}
                            </td>
                            <td className="px-4 py-3 text-slate-300">
                              {(log.file_size_bytes / 1024).toFixed(1)} KB
                            </td>
                            <td className="px-4 py-3 text-slate-400 truncate max-w-[120px]" title={log.sha256_checksum}>
                              {log.sha256_checksum ? log.sha256_checksum.substring(0, 12) + '...' : 'N/A'}
                            </td>
                            <td className="px-4 py-3 text-slate-400 truncate max-w-[120px]">
                              {log.gdrive_file_id || 'Local/S3'}
                            </td>
                            <td className="px-4 py-3 text-slate-400">
                              {log.duration_seconds ? `${log.duration_seconds.toFixed(2)}s` : 'N/A'}
                            </td>
                            <td className="px-4 py-3">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                                log.status === 'success' || log.status === 'completed'
                                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                  : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                              }`}>
                                {log.status}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-right text-slate-400">
                              {new Date(log.created_at).toLocaleString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 3: RESTORE & CHECKPOINTS */}
          {activeTab === 'restore' && (
            <div className="space-y-6">
              {/* Critical Safety Warning */}
              <div className="p-5 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-200 space-y-2">
                <div className="flex items-center gap-2 font-bold text-amber-400">
                  <ShieldAlert className="w-5 h-5 shrink-0" />
                  <span>Point-in-Time Database Restoration Protocol</span>
                </div>
                <p className="text-xs leading-relaxed text-amber-300/90">
                  Restoring a snapshot replaces the current transactional PostgreSQL database with the exact state from the selected checkpoint.
                  As a zero-risk safeguard, the system automatically creates an immediate safety snapshot before executing any restore operation.
                </p>
              </div>

              {/* Checkpoints Actions */}
              <div className="flex items-center justify-between p-4 rounded-xl bg-slate-900 border border-slate-800">
                <div>
                  <h4 className="text-sm font-semibold text-white">Local MinIO S3 Checkpoints</h4>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Immutable snapshots stored in the isolated <span className="font-mono text-sky-400">b00k5-backups</span> bucket.
                  </p>
                </div>

                <button
                  onClick={handleCreateCheckpoint}
                  disabled={creatingCheckpoint}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 font-medium text-xs flex items-center gap-2 transition-colors border border-slate-700"
                >
                  <Archive className={`w-3.5 h-3.5 ${creatingCheckpoint ? 'animate-spin' : ''}`} />
                  {creatingCheckpoint ? 'Creating Checkpoint...' : 'Create Instant Safety Checkpoint'}
                </button>
              </div>

              {checkpointStatus && (
                <div className="p-3 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400 text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>{checkpointStatus}</span>
                </div>
              )}

              {/* Snapshots Table */}
              <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <RotateCcw className="w-5 h-5 text-amber-400" />
                    <h3 className="text-lg font-bold text-white">Available Recovery Checkpoints</h3>
                  </div>
                  <button
                    onClick={fetchMinioSnapshots}
                    className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
                    title="Refresh snapshots"
                  >
                    <RefreshCw className="w-4 h-4" />
                  </button>
                </div>

                {minioSnapshots.length === 0 ? (
                  <div className="text-center py-12 text-slate-500 text-sm">
                    No local MinIO checkpoints found. Click "Create Instant Safety Checkpoint" above.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm text-slate-300">
                      <thead className="text-xs uppercase bg-slate-950/60 text-slate-500 border-b border-slate-800 font-mono">
                        <tr>
                          <th className="px-4 py-3">Snapshot File</th>
                          <th className="px-4 py-3">Size</th>
                          <th className="px-4 py-3">Object Key</th>
                          <th className="px-4 py-3">Modified</th>
                          <th className="px-4 py-3 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800 font-mono text-xs">
                        {minioSnapshots.map((snap) => (
                          <tr key={snap.object_key} className="hover:bg-slate-800/40 transition-colors">
                            <td className="px-4 py-3 font-semibold text-white">
                              {snap.filename}
                            </td>
                            <td className="px-4 py-3 text-slate-300">
                              {(snap.size_bytes / 1024).toFixed(1)} KB
                            </td>
                            <td className="px-4 py-3 text-slate-400 truncate max-w-[200px]" title={snap.object_key}>
                              {snap.object_key}
                            </td>
                            <td className="px-4 py-3 text-slate-400">
                              {snap.last_modified ? new Date(snap.last_modified).toLocaleString() : 'N/A'}
                            </td>
                            <td className="px-4 py-3 text-right">
                              <button
                                onClick={() => openRestoreModal(snap)}
                                className="px-3 py-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border border-amber-500/30 text-xs font-semibold transition-colors flex items-center gap-1.5 ml-auto"
                              >
                                <RotateCcw className="w-3.5 h-3.5" />
                                Restore
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Restore Confirmation Modal */}
          {restoreModalOpen && targetSnapshot && (
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-150">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 space-y-6 shadow-2xl relative">
                <button
                  onClick={() => setRestoreModalOpen(false)}
                  className="absolute right-4 top-4 text-slate-400 hover:text-slate-200"
                >
                  <X className="w-5 h-5" />
                </button>

                <div className="flex items-center gap-3">
                  <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
                    <RotateCcw className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-lg font-bold text-white">Authorize Database Restore</h3>
                    <p className="text-xs text-slate-400">Point-in-time state recovery authorization</p>
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Target Snapshot:</span>
                    <span className="font-mono text-white font-semibold">{targetSnapshot.filename}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Snapshot Size:</span>
                    <span className="font-mono text-slate-300">{(targetSnapshot.size_bytes / 1024).toFixed(1)} KB</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Timestamp:</span>
                    <span className="font-mono text-slate-400">
                      {targetSnapshot.last_modified ? new Date(targetSnapshot.last_modified).toLocaleString() : 'N/A'}
                    </span>
                  </div>
                </div>

                <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs space-y-1">
                  <div className="font-bold flex items-center gap-1.5 text-rose-400">
                    <AlertTriangle className="w-4 h-4" />
                    <span>Irreversible State Mutation Warning</span>
                  </div>
                  <p>
                    All database rows updated after this snapshot was created will be reverted to this point in time. An automated pre-restore safety checkpoint will be preserved.
                  </p>
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-medium text-slate-300">Administrator Password</label>
                  <input
                    type="password"
                    value={restoreSecret}
                    onChange={(e) => setRestoreSecret(e.target.value)}
                    placeholder="Enter AdminPass2026! to authorize"
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-sm text-white font-mono placeholder:text-slate-600 focus:outline-none focus:border-amber-500"
                  />
                </div>

                {restoreResult && (
                  <div className={`p-3.5 rounded-xl border text-xs ${
                    restoreResult.success
                      ? 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                      : 'bg-rose-500/10 border-rose-500/20 text-rose-400'
                  }`}>
                    {restoreResult.message}
                  </div>
                )}

                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    onClick={() => setRestoreModalOpen(false)}
                    className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium text-xs transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleExecuteRestore}
                    disabled={restoringKey !== null || !restoreSecret.trim()}
                    className="px-5 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-semibold text-xs flex items-center gap-2 transition-colors shadow-sm"
                  >
                    <RotateCcw className={`w-3.5 h-3.5 ${restoringKey !== null ? 'animate-spin' : ''}`} />
                    {restoringKey !== null ? 'Restoring Database...' : 'Confirm & Restore'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default function IntegrationsSettingsPage() {
  return (
    <Suspense fallback={
      <div className="flex h-screen bg-slate-950 items-center justify-center text-slate-400 text-sm">
        Loading Cloud & Backup Settings...
      </div>
    }>
      <IntegrationsContent />
    </Suspense>
  );
}
