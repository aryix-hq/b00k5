'use client';

import React, { useState, useEffect } from 'react';
import { Cloud, Shield, Database, CheckCircle2, RefreshCw, AlertCircle, ArrowLeft, Lock, HardDrive, Server, Archive, RotateCcw, X, ShieldAlert } from 'lucide-react';
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

        <div className="flex items-center gap-2">
          {gdriveConfigured ? (
            <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 rounded-full flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Google Drive Connected
            </span>
          ) : (
            <Link href="/gdrive" className="text-xs font-mono text-amber-400 bg-amber-500/10 border border-amber-500/30 px-3 py-1 rounded-full flex items-center gap-1.5 hover:bg-amber-500/20 transition">
              <AlertCircle className="w-3.5 h-3.5" />
              Google Drive: Not Configured (Upload Key)
            </Link>
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
