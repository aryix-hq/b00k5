'use client';

import React, { useState, useEffect } from 'react';
import { Cloud, Shield, Database, CheckCircle2, RefreshCw, AlertCircle, ArrowLeft, Lock, HardDrive, Server, Archive, RotateCcw, X, ShieldAlert, Eye, EyeOff, Check, ExternalLink, Layers, ArrowUpRight, FileText, Receipt, ShieldCheck, Building } from 'lucide-react';
import Link from 'next/link';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import { fetchApi } from '@/lib/api';

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

export default function IntegrationsSettingsPage() {
  const [backingUp, setBackingUp] = useState<boolean>(false);
  const [backupStatus, setBackupStatus] = useState<string | null>(null);
  const [logs, setLogs] = useState<BackupLog[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [gdriveConfigured, setGdriveConfigured] = useState<boolean>(false);

  // MinIO S3 Checkpoints State
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
        message: err.message || 'Failed to synchronize files to S3.'
      });
    } finally {
      setSyncingS3(false);
    }
  };

  const handleDisconnectS3 = async () => {
    if (!window.confirm('Are you sure you want to disconnect this remote S3 / Cloudflare R2 bucket?')) return;
    try {
      await fetchApi('/api/v1/storage/s3-disconnect', { method: 'POST' });
      setS3Config(null);
      setS3Endpoint('');
      setS3Bucket('');
      setS3AccessKey('');
      setS3SecretKey('');
      setS3TestStatus(null);
      setS3SyncStatus(null);
      await fetchS3Config();
    } catch (err: any) {
      alert(err.message || 'Failed to disconnect.');
    }
  };

  const fetchLogs = async () => {
    try {
      const data = await fetchApi('/api/v1/system/backup-logs');
      if (Array.isArray(data)) {
        setLogs(data);
      }

      const cfg = await fetchApi('/api/v1/storage/gdrive-config');
      if (cfg) {
        setGdriveConfigured(Boolean(cfg?.configured));
      }
    } catch (e) {
      console.warn('Failed to fetch backup logs:', e);
    }
  };

  const fetchMinioSnapshots = async () => {
    try {
      const data = await fetchApi('/api/v1/system/backup/snapshots');
      if (Array.isArray(data)) {
        setMinioSnapshots(data);
      }
    } catch (e) {
      console.warn('Failed to fetch MinIO snapshots:', e);
    }
  };

  useEffect(() => {
    fetchLogs();
    fetchMinioSnapshots();
    fetchS3Config();
  }, []);

  const handleRunBackup = async () => {
    setBackingUp(true);
    setBackupStatus('Executing pg_dump & AES-256-GCM encryption...');
    setErrorMsg(null);

    try {
      const newLog = await fetchApi('/api/v1/system/backup-database', {
        method: 'POST',
      });

      setBackupStatus('Success');
      setLogs(prev => [newLog, ...prev]);
      await fetchMinioSnapshots();
    } catch (err: any) {
      setErrorMsg(err.message || 'Backup failed');
      setBackupStatus('Failed');
    } finally {
      setBackingUp(false);
    }
  };

  const handleCreateMinioCheckpoint = async () => {
    setCreatingCheckpoint(true);
    setCheckpointStatus('Creating encrypted pg_dump checkpoint & streaming to MinIO...');
    setErrorMsg(null);

    try {
      await fetchApi('/api/v1/system/backup/checkpoint', {
        method: 'POST'
      });
      setCheckpointStatus('Checkpoint Created Successfully');
      await Promise.all([fetchMinioSnapshots(), fetchLogs()]);
    } catch (err: any) {
      setErrorMsg(err.message || 'MinIO checkpoint failed');
      setCheckpointStatus('Failed');
    } finally {
      setCreatingCheckpoint(false);
    }
  };

  const handleRestoreCheckpoint = async () => {
    if (!targetSnapshot) return;
    setRestoringKey(targetSnapshot.object_key);
    setErrorMsg(null);
    setRestoreResult(null);

    try {
      const res = await fetchApi('/api/v1/system/backup/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          object_key: targetSnapshot.object_key,
          decryption_secret: restoreSecret.trim() || undefined
        })
      });

      setRestoreResult(res);
      if (res.restore_approved) {
        setCheckpointStatus('Database restored successfully from MinIO checkpoint!');
      } else {
        setErrorMsg(`Restore rejected by 7-Point Staging Gate: ${res.reason || res.stage_status}`);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to restore MinIO checkpoint');
    } finally {
      setRestoringKey(null);
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Navbar />
        <main className="flex-1 overflow-y-auto p-8 max-w-6xl mx-auto w-full space-y-6">
          <div className="flex items-center justify-between border-b border-slate-800 pb-4">
            <div className="flex items-center gap-3">
          <Link href="/settings" className="p-2 rounded-lg bg-slate-800 text-slate-400 hover:text-white transition">
            <ArrowLeft className="w-5 h-5" />
          </Link>
          <div>
            <h1 className="text-xl font-bold text-white flex items-center gap-2">
              <Cloud className="w-5 h-5 text-sky-400" />
              Cloud Integrations & Database Archival
            </h1>
            <p className="text-xs text-slate-400">
              AES-256-GCM Encrypted PostgreSQL Backups Streamed to Google Drive (/b00k5_Statutory_Archive/DB_Backups/)
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {gdriveConfigured ? (
            <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 rounded-full flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Google Drive Connected
            </span>
          ) : (
            <Link href="/gdrive" className="text-xs font-mono text-slate-400 bg-slate-800/60 border border-slate-700 px-3 py-1 rounded-full flex items-center gap-1.5 hover:bg-slate-700 transition">
              <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
              Google Drive: Not Configured
            </Link>
          )}

          {s3Config?.configured ? (
            <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 rounded-full flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5" />
              {s3Config.provider === 'cloudflare_r2' ? 'Cloudflare R2' : s3Config.provider === 'aws_s3' ? 'AWS S3' : 'S3 Bucket'} Connected
            </span>
          ) : (
            <span className="text-xs font-mono text-amber-400 bg-amber-500/10 border border-amber-500/30 px-3 py-1 rounded-full flex items-center gap-1.5">
              <AlertCircle className="w-3.5 h-3.5" />
              Cloudflare R2 / S3: Setup Required
            </span>
          )}

          <span className="text-xs font-mono text-sky-400 bg-sky-500/10 border border-sky-500/20 px-3 py-1 rounded-full flex items-center gap-1.5">
            <Lock className="w-3.5 h-3.5" />
            AES-256-GCM Encryption
          </span>
        </div>
      </div>

      {/* Backup Action Banner */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900/90 to-slate-950 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <h2 className="text-base font-semibold text-white flex items-center gap-2">
            <Database className="w-4 h-4 text-sky-400" />
            PostgreSQL Database Dump & Google Drive Sync
          </h2>
          <p className="text-xs text-slate-400">
            Nightly scheduled dump at 02:00 AM IST. On-demand streaming with 30-day snapshot pruning.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            id="run-db-backup-btn"
            onClick={handleRunBackup}
            disabled={backingUp}
            className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 font-semibold text-white text-xs shadow-lg shadow-sky-600/30 transition disabled:opacity-50"
          >
            {backingUp ? <RefreshCw className="w-4 h-4 animate-spin" /> : <HardDrive className="w-4 h-4" />}
            Run Full Database Backup to Google Drive
          </button>
        </div>
      </div>

      {/* Progress & Status Modal/Banner */}
      {backupStatus && (
        <div
          id="backup-status-badge"
          className={`p-4 rounded-xl border flex items-center gap-3 text-xs font-medium transition-all ${
            backupStatus === 'Success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
              : backupStatus === 'Failed'
              ? 'bg-rose-500/10 border-rose-500/30 text-rose-400'
              : 'bg-sky-500/10 border-sky-500/30 text-sky-300'
          }`}
        >
          {backupStatus === 'Success' ? (
            <CheckCircle2 className="w-5 h-5 shrink-0" />
          ) : backupStatus === 'Failed' ? (
            <AlertCircle className="w-5 h-5 shrink-0" />
          ) : (
            <RefreshCw className="w-5 h-5 shrink-0 animate-spin" />
          )}
          <span>Status: {backupStatus}</span>
        </div>
      )}

      {/* Cloudflare R2 & AWS S3 Off-Site Cloud Mirror Card */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900/90 to-slate-950 border border-slate-800 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/30">
                Option 2: Cloudflare R2 / AWS S3
              </span>
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                Zero OAuth / Zero Quota Limits
              </span>
            </div>
            <h2 className="text-base font-semibold text-white flex items-center gap-2 mt-1">
              <Cloud className="w-4 h-4 text-sky-400" />
              Cloudflare R2 &amp; AWS S3 Off-Site Cloud Mirror
            </h2>
            <p className="text-xs text-slate-400">
              Enterprise set-and-forget archival. Completely bypasses Google's personal 0-byte Service Account quota and 7-day token expirations.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {s3Config?.configured && (
              <button
                id="sync-s3-mirror-btn"
                onClick={handleSyncS3}
                disabled={syncingS3}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 font-semibold text-white text-xs shadow-lg shadow-emerald-600/30 transition disabled:opacity-50"
              >
                {syncingS3 ? <RefreshCw className="w-4 h-4 animate-spin" /> : <HardDrive className="w-4 h-4" />}
                Sync All Vault &amp; Backups to S3
              </button>
            )}
          </div>
        </div>

        {s3TestStatus && (
          <div
            className={`p-3.5 rounded-xl border flex items-center gap-3 text-xs font-medium ${
              s3TestStatus.success
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
            }`}
          >
            {s3TestStatus.success ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            )}
            <div className="flex-1">
              <span>{s3TestStatus.message}</span>
              {s3TestStatus.latency_ms && (
                <span className="text-[11px] font-mono opacity-75 ml-2">({s3TestStatus.latency_ms}ms)</span>
              )}
            </div>
          </div>
        )}

        {s3SyncStatus && (
          <div
            className={`p-3.5 rounded-xl border flex items-center gap-3 text-xs font-medium ${
              s3SyncStatus.success
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
                : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
            }`}
          >
            {s3SyncStatus.success ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            )}
            <span>{s3SyncStatus.message}</span>
          </div>
        )}

        {/* Provider Selector Tabs */}
        <div className="flex items-center gap-2 pt-1">
          <button
            type="button"
            onClick={() => {
              setS3Provider('cloudflare_r2');
              setS3Region('auto');
              if (!s3Endpoint || s3Endpoint.includes('amazonaws.com')) {
                setS3Endpoint('https://<ACCOUNT_ID>.r2.cloudflarestorage.com');
              }
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              s3Provider === 'cloudflare_r2'
                ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 font-semibold'
                : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            Cloudflare R2 (10GB Free Forever)
          </button>
          <button
            type="button"
            onClick={() => {
              setS3Provider('aws_s3');
              setS3Region('ap-south-1');
              if (!s3Endpoint || s3Endpoint.includes('r2.cloudflarestorage.com')) {
                setS3Endpoint('https://s3.ap-south-1.amazonaws.com');
              }
            }}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              s3Provider === 'aws_s3'
                ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 font-semibold'
                : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            AWS S3 (Global Standard)
          </button>
          <button
            type="button"
            onClick={() => setS3Provider('custom_s3')}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
              s3Provider === 'custom_s3'
                ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 font-semibold'
                : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            Custom S3 (MinIO / Wasabi / B2)
          </button>
        </div>

        {/* S3 Credentials Form */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div>
            <label className="text-slate-300 font-medium block mb-1">
              S3 Endpoint URL:
              {s3Provider === 'cloudflare_r2' && (
                <span className="text-[11px] text-sky-400 font-normal ml-2">https://&lt;account_id&gt;.r2.cloudflarestorage.com</span>
              )}
            </label>
            <input
              type="text"
              value={s3Endpoint}
              onChange={(e) => setS3Endpoint(e.target.value)}
              placeholder="e.g. https://abc12345.r2.cloudflarestorage.com"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono text-xs focus:border-sky-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="text-slate-300 font-medium block mb-1">Bucket Name:</label>
            <input
              type="text"
              value={s3Bucket}
              onChange={(e) => setS3Bucket(e.target.value)}
              placeholder="e.g. aryix-b00k5-vault"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono text-xs focus:border-sky-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="text-slate-300 font-medium block mb-1">Access Key ID:</label>
            <input
              type="text"
              value={s3AccessKey}
              onChange={(e) => setS3AccessKey(e.target.value)}
              placeholder="e.g. 7f4a... or AKIA..."
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono text-xs focus:border-sky-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="text-slate-300 font-medium block mb-1 flex items-center justify-between">
              <span>Secret Access Key:</span>
              {s3Config?.has_secret && (
                <span className="text-[10px] text-emerald-400 font-mono">Secret saved (leave blank to keep)</span>
              )}
            </label>
            <div className="relative">
              <input
                type={showSecret ? 'text' : 'password'}
                value={s3SecretKey}
                onChange={(e) => setS3SecretKey(e.target.value)}
                placeholder={s3Config?.has_secret ? '••••••••••••••••' : 'Paste S3 Secret Key'}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 pr-10 text-white font-mono text-xs focus:border-sky-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setShowSecret(!showSecret)}
                className="absolute right-2.5 top-2.5 text-slate-500 hover:text-slate-300"
              >
                {showSecret ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
              </button>
            </div>
          </div>

          <div>
            <label className="text-slate-300 font-medium block mb-1">Region:</label>
            <input
              type="text"
              value={s3Region}
              onChange={(e) => setS3Region(e.target.value)}
              placeholder="auto (for Cloudflare R2) or ap-south-1"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono text-xs focus:border-sky-500 focus:outline-none"
            />
          </div>

          <div>
            <label className="text-slate-300 font-medium block mb-1">Root Folder / Prefix (Optional):</label>
            <input
              type="text"
              value={s3Prefix}
              onChange={(e) => setS3Prefix(e.target.value)}
              placeholder="e.g. b00k5_ARYIX"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono text-xs focus:border-sky-500 focus:outline-none"
            />
          </div>
        </div>

        {/* Scope of Mirroring: Invoices, Bills, Vault, Statements & Backups */}
        <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800/80 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5 text-sky-400" />
              Complete Off-Site Backup Scope (All Invoices, Bills, Documents &amp; DB)
            </span>
            <span className="text-[10px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
              MCA Sec 128 Compliant
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
              <div className="flex items-center gap-2 text-sky-400 mb-1">
                <FileText className="w-4 h-4" />
                <span className="text-xs font-medium text-white">Sales Invoices</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-tight">
                All client tax invoices, debit/credit notes archived as PDF documents with SHA-256 hashes.
              </p>
            </div>

            <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
              <div className="flex items-center gap-2 text-emerald-400 mb-1">
                <Receipt className="w-4 h-4" />
                <span className="text-xs font-medium text-white">Vendor Bills</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-tight">
                All vendor bills, OCR receipt attachments, and statutory expense vouchers.
              </p>
            </div>

            <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
              <div className="flex items-center gap-2 text-purple-400 mb-1">
                <ShieldCheck className="w-4 h-4" />
                <span className="text-xs font-medium text-white">Legal &amp; Tax Vault</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-tight">
                Certificate of Incorporation (COI), MOA, AOA, PAN, GST, and ROC filings.
              </p>
            </div>

            <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
              <div className="flex items-center gap-2 text-amber-400 mb-1">
                <Building className="w-4 h-4" />
                <span className="text-xs font-medium text-white">Bank Statements</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-tight">
                Reconciled bank statements and monthly financial institution transaction records.
              </p>
            </div>

            <div className="p-3 rounded-lg bg-slate-900 border border-slate-800">
              <div className="flex items-center gap-2 text-rose-400 mb-1">
                <Database className="w-4 h-4" />
                <span className="text-xs font-medium text-white">Database Dumps</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-tight">
                Encrypted PostgreSQL archives (AES-256-GCM) with double-entry integrity checks.
              </p>
            </div>
          </div>
        </div>

        {/* Cloudflare R2 Storage Quota & Retention Policy Card */}
        <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
            <div>
              <h3 className="text-xs font-semibold text-white uppercase tracking-wider flex items-center gap-2">
                <Archive className="w-3.5 h-3.5 text-amber-400" />
                Storage Quota &amp; Database Backup Retention Policy
              </h3>
              <p className="text-[11px] text-slate-400">
                Prevents running out of space by automatically pruning older database snapshots while permanently preserving statutory invoices and bills.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono text-slate-300">
                {s3Config?.storage_usage?.total_mb ?? 0} MB / 10 GB Free Tier
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                {s3Config?.storage_usage?.remaining_free_gb ?? 10.0} GB Free Remaining
              </span>
            </div>
          </div>

          {/* Quota Progress Bar */}
          <div className="space-y-1.5">
            <div className="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
              <div
                className={`h-full transition-all duration-500 ${
                  (s3Config?.storage_usage?.used_percentage ?? 0) > 80
                    ? 'bg-rose-500'
                    : (s3Config?.storage_usage?.used_percentage ?? 0) > 50
                    ? 'bg-amber-500'
                    : 'bg-emerald-500'
                }`}
                style={{ width: `${Math.max(1, Math.min(100, s3Config?.storage_usage?.used_percentage ?? 0.5))}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
              <span>Used: {s3Config?.storage_usage?.used_percentage ?? 0}%</span>
              <span>{s3Config?.storage_usage?.file_count ?? 0} Total Objects in Bucket</span>
              <span>10 GB Free Forever Limit</span>
            </div>
          </div>

          {/* Retention Controls */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1 items-end">
            <div>
              <label className="text-slate-300 text-xs font-medium block mb-1">
                Keep Database Snapshots:
              </label>
              <select
                value={retentionKeepCount}
                onChange={(e) => setRetentionKeepCount(Number(e.target.value))}
                className="w-full bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono text-xs focus:border-amber-500 focus:outline-none cursor-pointer"
              >
                <option value={5}>Keep 5 Most Recent Backups (~50 MB)</option>
                <option value={7}>Keep 7 Daily Backups (~70 MB - Default)</option>
                <option value={14}>Keep 14 Backups (~140 MB)</option>
                <option value={30}>Keep 30 Backups (~300 MB)</option>
              </select>
            </div>

            <div className="flex items-center gap-2 pb-2">
              <input
                type="checkbox"
                id="auto-prune-toggle"
                checked={retentionAutoPrune}
                onChange={(e) => setRetentionAutoPrune(e.target.checked)}
                className="rounded border-slate-700 bg-slate-900 text-amber-500 focus:ring-0 w-4 h-4 cursor-pointer"
              />
              <label htmlFor="auto-prune-toggle" className="text-xs text-slate-300 cursor-pointer select-none">
                Auto-prune older snapshots during backups
              </label>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleSaveRetention}
                disabled={savingRetention || !s3Config?.configured}
                className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 text-xs font-semibold rounded-lg transition"
              >
                {savingRetention ? 'Saving...' : 'Save Policy'}
              </button>
              <button
                type="button"
                onClick={handlePruneBackups}
                disabled={pruningBackups || !s3Config?.configured}
                className="px-3.5 py-2 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-300 text-xs font-semibold rounded-lg transition"
              >
                {pruningBackups ? 'Pruning...' : 'Prune Now'}
              </button>
            </div>
          </div>

          {pruneResult && (
            <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-center gap-2 font-mono">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
              <span>Pruned {pruneResult.pruned_count} old snapshot(s). Reclaimed {pruneResult.reclaimed_mb} MB space.</span>
            </div>
          )}

          <p className="text-[10px] text-slate-500 italic pt-1">
            * Statutory Invariant: Sales invoices, vendor expense bills, and MCA legal filings are protected by Companies Act 2013 Section 128 (8-year audit mandate) and will never be deleted by the retention engine.
          </p>
        </div>

        {/* S3 Action Buttons */}
        <div className="flex flex-wrap items-center gap-3 pt-2">
          <button
            type="button"
            onClick={handleTestS3}
            disabled={testingS3 || !s3Endpoint || !s3Bucket || !s3AccessKey || (!s3SecretKey && !s3Config?.has_secret)}
            className="flex items-center gap-1.5 px-4 py-2 bg-slate-800 hover:bg-slate-700 disabled:opacity-50 text-slate-200 text-xs font-semibold rounded-lg transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${testingS3 ? 'animate-spin' : ''}`} />
            {testingS3 ? 'Testing S3 Bucket...' : 'Test Connection'}
          </button>

          <button
            type="button"
            onClick={handleSaveS3}
            disabled={savingS3 || !s3Endpoint || !s3Bucket || !s3AccessKey || (!s3SecretKey && !s3Config?.has_secret)}
            className="flex items-center gap-1.5 px-5 py-2 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-800 disabled:text-slate-500 text-white text-xs font-semibold rounded-lg shadow-md shadow-sky-600/20 transition"
          >
            <Check className="w-3.5 h-3.5" />
            {savingS3 ? 'Saving...' : 'Save & Connect Cloud Bucket'}
          </button>

          {s3Config?.configured && (
            <button
              type="button"
              onClick={handleDisconnectS3}
              className="px-3.5 py-2 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-400 text-xs font-semibold rounded-lg transition"
            >
              Disconnect S3
            </button>
          )}

          {s3Config?.last_synced_at && (
            <span className="text-[11px] text-slate-400 font-mono ml-auto">
              Last Synced: {new Date(s3Config.last_synced_at).toLocaleString('en-IN')}
            </span>
          )}
        </div>
      </div>

      {/* MinIO S3 Immutable Checkpoints & Disaster Recovery Card */}
      <div className="p-6 rounded-2xl bg-gradient-to-r from-slate-900/90 to-slate-950 border border-slate-800 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30">
                Sovereign S3 Storage / MinIO
              </span>
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                7-Point Staging Gate Verified
              </span>
            </div>
            <h2 className="text-base font-semibold text-white flex items-center gap-2 mt-1">
              <Server className="w-4 h-4 text-amber-400" />
              MinIO S3 Immutable Database Checkpoints
            </h2>
            <p className="text-xs text-slate-400">
              On-premise / private cloud disaster recovery fallback when Google Drive is unconfigured or unreachable.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              id="run-minio-checkpoint-btn"
              onClick={handleCreateMinioCheckpoint}
              disabled={creatingCheckpoint}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 font-semibold text-white text-xs shadow-lg shadow-amber-600/30 transition disabled:opacity-50"
            >
              {creatingCheckpoint ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Archive className="w-4 h-4" />}
              Create MinIO S3 Checkpoint
            </button>
          </div>
        </div>

        {checkpointStatus && (
          <div
            id="checkpoint-status-badge"
            className={`p-3.5 rounded-xl border flex items-center gap-3 text-xs font-medium transition-all ${
              checkpointStatus.includes('Successfully')
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                : checkpointStatus === 'Failed'
                ? 'bg-rose-500/10 border-rose-500/30 text-rose-400'
                : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
            }`}
          >
            {checkpointStatus.includes('Successfully') ? (
              <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
            ) : checkpointStatus === 'Failed' ? (
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            ) : (
              <RefreshCw className="w-4 h-4 shrink-0 animate-spin text-amber-400" />
            )}
            <span>Status: {checkpointStatus}</span>
          </div>
        )}

        {/* MinIO Checkpoints Table */}
        <div className="pt-2">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-xs font-semibold text-slate-300">Available MinIO Snapshots ({minioSnapshots.length})</h4>
            <button onClick={fetchMinioSnapshots} className="text-[11px] text-slate-400 hover:text-white flex items-center gap-1">
              <RefreshCw className="w-3 h-3" /> Refresh Snapshots
            </button>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table id="minio-snapshots-table" className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950 text-slate-400 font-mono uppercase text-[11px] border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Snapshot File</th>
                  <th className="py-2.5 px-3">Size (KB)</th>
                  <th className="py-2.5 px-3">MinIO URI</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3 text-right">Disaster Recovery</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {minioSnapshots.length > 0 ? (
                  minioSnapshots.map((snap) => (
                    <tr key={snap.object_key} className="hover:bg-slate-800/30">
                      <td className="py-2.5 px-3 font-medium text-white max-w-[200px] truncate" title={snap.filename}>
                        {snap.filename}
                      </td>
                      <td className="py-2.5 px-3 text-slate-300">
                        {(snap.size_bytes / 1024).toFixed(1)} KB
                      </td>
                      <td className="py-2.5 px-3 text-amber-300 font-mono text-[11px] max-w-[220px] truncate" title={snap.uri}>
                        {snap.uri}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">
                        {snap.last_modified ? new Date(snap.last_modified).toLocaleString('en-IN') : 'N/A'}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <button
                          onClick={() => {
                            setTargetSnapshot(snap);
                            setRestoreModalOpen(true);
                            setRestoreResult(null);
                          }}
                          className="px-3 py-1 bg-rose-950/60 hover:bg-rose-900/60 text-rose-300 border border-rose-800/60 rounded text-[11px] font-semibold transition"
                        >
                          Restore Snapshot
                        </button>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-slate-500 text-xs">
                      No MinIO checkpoints found. Click &quot;Create MinIO S3 Checkpoint&quot; above to take an instant snapshot.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Backup Audit Table */}
      <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-white">Database Backup Audit Ledger</h3>
          <button onClick={fetchLogs} className="text-xs text-slate-400 hover:text-white flex items-center gap-1">
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
        </div>

        <div className="overflow-x-auto">
          <table id="backup-logs-table" className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950 text-slate-400 font-mono uppercase text-[11px] border-b border-slate-800">
              <tr>
                <th className="py-3 px-3">Backup Filename</th>
                <th className="py-3 px-3">Size (KB)</th>
                <th className="py-3 px-3">SHA-256 Checksum</th>
                <th className="py-3 px-3">Google Drive File ID</th>
                <th className="py-3 px-3">Status</th>
                <th className="py-3 px-3 text-right">Timestamp</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {logs.length > 0 ? (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-800/30">
                    <td className="py-3 px-3 font-medium text-white max-w-[200px] truncate" title={log.filename}>
                      {log.filename}
                    </td>
                    <td className="py-3 px-3 text-slate-300">
                      {(log.file_size_bytes / 1024).toFixed(1)} KB
                    </td>
                    <td className="py-3 px-3 text-slate-400 max-w-[150px] truncate" title={log.sha256_checksum}>
                      {log.sha256_checksum}
                    </td>
                    <td className="py-3 px-3 text-sky-400 font-bold max-w-[150px] truncate" title={log.gdrive_file_id}>
                      {log.gdrive_file_id || 'Virtual Sync'}
                    </td>
                    <td className="py-3 px-3">
                      <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                        {log.status}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right text-slate-400">
                      {new Date(log.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-slate-500">
                    No backup records found. Click above to execute full backup.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 7-Point Staging Gate Restore Confirmation Modal */}
      {restoreModalOpen && targetSnapshot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-rose-500/40 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden p-6 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2 text-rose-400 font-bold text-sm">
                <ShieldAlert className="w-5 h-5" />
                <span>Disaster Recovery: 7-Point Staging Gate Restore</span>
              </div>
              <button
                onClick={() => {
                  setRestoreModalOpen(false);
                  setTargetSnapshot(null);
                }}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-slate-300">
              You are about to restore database snapshot: <strong className="text-white font-mono">{targetSnapshot.filename}</strong>
            </p>

            <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 text-[11px] space-y-1.5 text-slate-300 font-sans">
              <div className="font-semibold text-amber-300">Automated 7-Point Staging Verification:</div>
              <ul className="list-disc list-inside space-y-1 text-slate-400">
                <li>Gate 1: SHA-256 binary checksum validation</li>
                <li>Gate 2: Authenticated AES-256-GCM decryption &amp; gzip integrity</li>
                <li>Gate 3: RPO stale-snapshot protection (overwrites checked)</li>
                <li>Gate 4: Document Vault archive completeness</li>
                <li>Gate 5: Staged multi-point accounting check (zero-sum debits/credits)</li>
                <li>Gate 6: Cross-tenant foreign key isolation</li>
                <li>Gate 7: Atomic cutover with automated rollback on failure</li>
              </ul>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1">
                Decryption Master Secret (Optional, defaults to system SECRET_KEY)
              </label>
              <input
                type="password"
                value={restoreSecret}
                onChange={(e) => setRestoreSecret(e.target.value)}
                placeholder="Leave blank to use system vault key"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono text-xs focus:outline-none focus:border-rose-500"
              />
            </div>

            {restoreResult && (
              <div className={`p-3 rounded-xl border text-xs ${
                restoreResult.restore_approved ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
              }`}>
                <div className="font-semibold">{restoreResult.restore_approved ? 'Verification Passed!' : 'Restore Verification Failed'}</div>
                <div className="text-[11px] text-slate-300 mt-0.5">{restoreResult.reason || restoreResult.stage_status}</div>
              </div>
            )}

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => {
                  setRestoreModalOpen(false);
                  setTargetSnapshot(null);
                }}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleRestoreCheckpoint}
                disabled={Boolean(restoringKey)}
                className="px-5 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-semibold shadow-lg shadow-rose-600/30 transition disabled:opacity-50 flex items-center gap-2"
              >
                {restoringKey ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
                {restoringKey ? 'Executing 7-Point Staging Gate...' : 'Confirm Restore & Overwrite'}
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
