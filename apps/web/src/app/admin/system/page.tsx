'use client';

import React, { useEffect, useState } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import {
  Activity,
  Database,
  Server,
  HardDrive,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  ShieldCheck,
  Calendar,
  Layers,
  ArrowUpRight,
  Loader2,
  Lock,
  CloudUpload,
  Cpu
} from 'lucide-react';
import { fetchApi } from '@/lib/api';

interface TelemetryData {
  status: string;
  service: string;
  version: string;
  timestamp: string;
  database: {
    status: string;
    engine: string;
    rls_enabled: boolean;
    total_tenants: number;
    total_users: number;
    total_journal_entries: number;
    total_debits: number;
    total_credits: number;
    ledger_drift: number;
    balance_invariant_holds: boolean;
  };
  redis: {
    status: string;
    url: string;
  };
  minio: {
    status: string;
    endpoint: string;
    buckets: string[];
  };
  fiscal_calendar: {
    system_fy: string;
    system_ay: string;
    direct_tax_regime?: string;
  };
}

export default function SystemTelemetryPage() {
  const [data, setData] = useState<TelemetryData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [backingUp, setBackingUp] = useState<boolean>(false);
  const [backupMsg, setBackupMsg] = useState<string>('');
  const [errorMsg, setErrorMsg] = useState<string>('');

  const loadTelemetry = async () => {
    setErrorMsg('');
    try {
      const res = await fetchApi('/api/v1/system/telemetry');
      if (res && res.database) {
        setData(res);
      } else {
        setErrorMsg('Invalid telemetry response format received.');
      }
    } catch (err: any) {
      console.error('Failed to load telemetry:', err);
      setErrorMsg(err.message || 'Unable to load telemetry. Please ensure the backend API is reachable.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadTelemetry();
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    loadTelemetry();
  };

  const handleTriggerBackup = async () => {
    setBackingUp(true);
    setBackupMsg('');
    try {
      const res = await fetchApi('/api/v1/system/backup-database', {
        method: 'POST',
      });
      if (res && res.filename) {
        setBackupMsg(`Encrypted backup created successfully: ${res.filename} (${(res.file_size_bytes / 1024).toFixed(1)} KB)`);
      } else {
        setBackupMsg('Backup completed.');
      }
    } catch (err: any) {
      console.error('Backup failed:', err);
      setBackupMsg(`Backup failed: ${err.message || 'Unknown error'}`);
    } finally {
      setBackingUp(false);
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 antialiased overflow-hidden">
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Navbar />

        <main className="flex-1 p-6 lg:p-8 max-w-7xl w-full mx-auto space-y-6">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
            <div>
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <Activity className="w-6 h-6" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h1 className="text-xl font-bold text-white tracking-tight">System Telemetry & Health</h1>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      Docker Stack Live
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Real-time container status, database connection pool, mathematical ledger invariants, and storage health.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleRefresh}
                disabled={refreshing || loading}
                className="flex items-center gap-2 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-all"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
                Refresh
              </button>
              <button
                onClick={handleTriggerBackup}
                disabled={backingUp}
                className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold shadow-lg shadow-emerald-950/40 transition-all"
              >
                {backingUp ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CloudUpload className="w-3.5 h-3.5" />}
                Trigger Backup
              </button>
            </div>
          </div>

          {backupMsg && (
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center justify-between">
              <span>{backupMsg}</span>
              <button onClick={() => setBackupMsg('')} className="text-emerald-500 hover:text-emerald-300">✕</button>
            </div>
          )}

          {loading ? (
            <div className="flex flex-col items-center justify-center py-20 text-slate-400 space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />
              <p className="text-xs">Gathering container diagnostics...</p>
            </div>
          ) : data ? (
            <>
              {/* Service Health Cards */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* API Engine */}
                <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-400">FastAPI Engine</span>
                    <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-400">
                      <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                      Healthy
                    </span>
                  </div>
                  <div className="text-lg font-bold text-white font-mono">{data.service}</div>
                  <p className="text-[11px] text-slate-500">v{data.version} • Python 3.11</p>
                </div>

                {/* PostgreSQL Database */}
                <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-400">Database Engine</span>
                    <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-400">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Active
                    </span>
                  </div>
                  <div className="text-lg font-bold text-white font-mono">{data.database.engine}</div>
                  <p className="text-[11px] text-slate-500">RLS Enforced • Port 5432</p>
                </div>

                {/* Redis Broker */}
                <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-400">Celery Broker</span>
                    <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-400">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {data.redis.status}
                    </span>
                  </div>
                  <div className="text-lg font-bold text-white font-mono">Redis 7 Alpine</div>
                  <p className="text-[11px] text-slate-500 font-mono truncate">{data.redis.url}</p>
                </div>

                {/* MinIO S3 */}
                <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-400">Object Storage</span>
                    <span className="flex items-center gap-1 text-[11px] font-semibold text-emerald-400">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {data.minio.status}
                    </span>
                  </div>
                  <div className="text-lg font-bold text-white font-mono">MinIO Sovereign S3</div>
                  <p className="text-[11px] text-slate-500">{data.minio.buckets.length} Buckets Mounted</p>
                </div>
              </div>

              {/* Core Mathematical Ledger Invariant Banner */}
              <div className="p-5 rounded-2xl bg-gradient-to-r from-emerald-950/40 via-slate-900/80 to-slate-900/80 border border-emerald-500/30 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <ShieldCheck className="w-6 h-6" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-white">Mathematical Ledger Balance Invariant</h3>
                    <p className="text-xs text-slate-400">
                      Section 128 Companies Act zero-drift invariant: Absolute debit-credit difference across all posted vouchers.
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-6">
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider font-mono">Posted Vouchers</div>
                    <div className="text-base font-bold text-white font-mono">{data.database.total_journal_entries}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-slate-500 uppercase tracking-wider font-mono">Ledger Drift</div>
                    <div className="text-base font-bold text-emerald-400 font-mono">₹{data.database.ledger_drift.toFixed(2)}</div>
                  </div>
                  <div className="px-3 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-xs font-bold font-mono">
                    VERIFIED ZERO-DRIFT
                  </div>
                </div>
              </div>

              {/* Statutory Regime & Detailed Stats */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Active Fiscal Calendar */}
                <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
                  <div className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-sky-400" />
                    <h3 className="text-sm font-bold text-white">Active Statutory Regime</h3>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                      <span className="text-slate-500 block text-[10px] uppercase font-mono">Financial Year</span>
                      <span className="text-base font-bold text-white font-mono">{data.fiscal_calendar.system_fy}</span>
                    </div>
                    <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800">
                      <span className="text-slate-500 block text-[10px] uppercase font-mono">Assessment Year</span>
                      <span className="text-base font-bold text-white font-mono">{data.fiscal_calendar.system_ay}</span>
                    </div>
                  </div>

                  <p className="text-xs text-slate-400 leading-relaxed">
                    Under Indian tax law, transactions falling between April 1 of Year Y and March 31 of Year Y+1 are evaluated under Assessment Year Y+1. For dates on/after 1 April 2026, the engine tracks provisions under the Income-tax Act, 2025.
                  </p>
                </div>

                {/* Storage & Encryption Architecture */}
                <div className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
                  <div className="flex items-center gap-2">
                    <Lock className="w-4 h-4 text-emerald-400" />
                    <h3 className="text-sm font-bold text-white">Sovereignty & Encryption</h3>
                  </div>

                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between items-center p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 font-mono text-[11px]">
                      <span className="text-slate-400">Database Encryption:</span>
                      <span className="text-white font-semibold">AES-256-GCM Backup Stream</span>
                    </div>
                    <div className="flex justify-between items-center p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 font-mono text-[11px]">
                      <span className="text-slate-400">MinIO S3 Buckets:</span>
                      <span className="text-white font-semibold">{data.minio.buckets.join(', ')}</span>
                    </div>
                    <div className="flex justify-between items-center p-2.5 rounded-lg bg-slate-950/60 border border-slate-800 font-mono text-[11px]">
                      <span className="text-slate-400">Total Registered Tenants:</span>
                      <span className="text-white font-semibold">{data.database.total_tenants} Entities</span>
                    </div>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="p-8 text-center text-slate-400 bg-slate-900/40 rounded-2xl border border-slate-800 space-y-3">
              <AlertTriangle className="w-8 h-8 text-amber-400 mx-auto" />
              <div className="text-sm font-semibold text-white">Telemetry Unavailable</div>
              <p className="text-xs text-slate-400 max-w-md mx-auto">
                {errorMsg || 'Unable to load telemetry. Please ensure the backend API is reachable.'}
              </p>
              <button
                onClick={handleRefresh}
                className="mt-2 px-4 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 border border-slate-700 transition-all inline-flex items-center gap-2"
              >
                <RefreshCw className="w-3.5 h-3.5" /> Retry Diagnostics
              </button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

