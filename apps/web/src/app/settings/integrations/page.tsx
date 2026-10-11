'use client';

import React, { useState, useEffect } from 'react';
import { Cloud, Shield, Database, CheckCircle2, RefreshCw, AlertCircle, ArrowLeft, Lock, HardDrive } from 'lucide-react';
import Link from 'next/link';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';

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

export default function IntegrationsSettingsPage() {
  const [backingUp, setBackingUp] = useState<boolean>(false);
  const [backupStatus, setBackupStatus] = useState<string | null>(null);
  const [logs, setLogs] = useState<BackupLog[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [gdriveConfigured, setGdriveConfigured] = useState<boolean>(false);

  const fetchLogs = async () => {
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = typeof window !== 'undefined' ? localStorage.getItem('b00k5_tenant_id') : null;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/system/backup-logs`, { headers });
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
      }

      const cfgRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/storage/gdrive-config`, { headers });
      if (cfgRes.ok) {
        const cfg = await cfgRes.json();
        setGdriveConfigured(Boolean(cfg?.configured));
      }
    } catch (e) {
      console.warn('Failed to fetch backup logs:', e);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const handleRunBackup = async () => {
    setBackingUp(true);
    setBackupStatus('Executing pg_dump & AES-256-GCM encryption...');
    setErrorMsg(null);

    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const tenantId = typeof window !== 'undefined' ? localStorage.getItem('b00k5_tenant_id') : null;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      if (tenantId) headers['X-Tenant-ID'] = tenantId;

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/system/backup-database`, {
        method: 'POST',
        headers
      });

      if (!res.ok) {
        throw new Error('Database backup failed');
      }

      const newLog = await res.json();
      setBackupStatus('Success');
      setLogs(prev => [newLog, ...prev]);
    } catch (err: any) {
      setErrorMsg(err.message || 'Backup failed');
      setBackupStatus('Failed');
    } finally {
      setBackingUp(false);
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
        </main>
      </div>
    </div>
  );
}
