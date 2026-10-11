'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import {
  Scale,
  Receipt,
  FolderLock,
  KeyRound,
  AlertTriangle,
  Clock,
  CheckCircle2,
  TrendingUp,
  FileText,
  ShieldCheck,
  Building
} from 'lucide-react';
import { fetchApi } from '@/lib/api';
import { checkBridgeStatus, BridgeStatus } from '@/lib/dsc-bridge';

export default function Dashboard() {
  const [complianceData, setComplianceData] = useState<any>(null);
  const [bridgeStatus, setBridgeStatus] = useState<BridgeStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const comp = await fetchApi('/api/v1/compliance/dashboard');
        setComplianceData(comp);
      } catch (e) {
        console.error(e);
      }

      try {
        const b = await checkBridgeStatus();
        setBridgeStatus(b);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Navbar />

        <main className="p-8 space-y-8 max-w-7xl mx-auto w-full">
          {/* Top Banner: Corporate Financial Operating System */}
          <div className="flex items-center justify-between p-4 bg-slate-900 border border-slate-800 rounded-xl">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-sky-500/10 border border-sky-500/20 text-sky-400">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">Corporate Financial Operating System</h3>
                <p className="text-xs text-slate-400">PostgreSQL RLS Active • MinIO Encrypted Storage • Schedule III Balanced</p>
              </div>
            </div>

            <div className="flex items-center gap-3 text-xs">
              <span className="px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-medium flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                System Operational
              </span>
            </div>
          </div>

          {/* Statutory Compliance Watchdog Hero */}
          <section className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-white flex items-center gap-2">
                  <Scale className="w-5 h-5 text-sky-400" />
                  Statutory Compliance Watchdog (MCA & GST)
                </h2>
                <p className="text-xs text-slate-400">Section 173 Board Meeting 120-Day Rule, Director KYC & Filing Monitor</p>
              </div>
              {complianceData?.total_penalty_accruing_inr > 0 && (
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs font-semibold">
                  <AlertTriangle className="w-4 h-4" />
                  ₹{complianceData.total_penalty_accruing_inr} Compound MCA Late Fees Accruing!
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              {complianceData?.upcoming_events?.slice(0, 4).map((event: any) => {
                const isCompleted = event.status === 'completed' || event.status === 'filed' || event.status === 'verified';
                const isOverdue = !isCompleted && event.status === 'overdue';
                const isDueSoon = !isCompleted && event.status === 'due_soon';
                return (
                  <div
                    key={event.id}
                    className={`p-4 rounded-xl border flex flex-col justify-between ${
                      isCompleted
                        ? 'bg-emerald-950/20 border-emerald-800/40 text-emerald-200'
                        : isOverdue
                        ? 'bg-rose-950/20 border-rose-800/40 text-rose-200'
                        : isDueSoon
                        ? 'bg-amber-950/20 border-amber-800/40 text-amber-200'
                        : 'bg-slate-900 border-slate-800 text-slate-200'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                          {event.category.replace('_', ' ')}
                        </span>
                        {isCompleted ? (
                          <span className="text-[10px] font-bold text-emerald-400">FILED / COMPLETED</span>
                        ) : isOverdue ? (
                          <span className="text-[10px] font-bold text-rose-400">OVERDUE</span>
                        ) : (
                          <span className="text-[10px] text-slate-400">{event.days_remaining}d remaining</span>
                        )}
                      </div>
                      <h4 className="text-sm font-semibold mb-1 line-clamp-1">{event.title}</h4>
                      <p className="text-xs text-slate-400 mb-2 line-clamp-2">{event.description}</p>
                    </div>

                    <div className="border-t border-slate-800/80 pt-2 flex items-center justify-between text-xs">
                      <span className="text-slate-400 font-mono">Due: {event.due_date}</span>
                      {isOverdue && (
                        <span className="font-bold text-rose-400">
                          +₹{event.accumulated_penalty_inr}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Quick Actions Grid */}
          <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Link
              href="/invoices"
              className="p-6 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-900/60 border border-slate-800 hover:border-sky-500/50 transition-all group"
            >
              <div className="w-12 h-12 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400 flex items-center justify-center mb-4 group-hover:scale-105 transition-transform">
                <Receipt className="w-6 h-6" />
              </div>
              <h3 className="font-semibold text-white mb-1">Issue GST Tax Invoice</h3>
              <p className="text-xs text-slate-400">
                Dynamic Place of Supply (POS) engine, HSN master lookup, and auto double-entry posting.
              </p>
            </Link>

            <Link
              href="/vault"
              className="p-6 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-900/60 border border-slate-800 hover:border-emerald-500/50 transition-all group"
            >
              <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mb-4 group-hover:scale-105 transition-transform">
                <FolderLock className="w-6 h-6" />
              </div>
              <h3 className="font-semibold text-white mb-1">Legal Document Locker</h3>
              <p className="text-xs text-slate-400">
                Encrypted repository for COI, MOA, AOA, PAN, and Cap Table certificates with SHA-256 integrity.
              </p>
            </Link>

            <Link
              href="/dsc"
              className="p-6 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-900/60 border border-slate-800 hover:border-purple-500/50 transition-all group"
            >
              <div className="w-12 h-12 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400 flex items-center justify-center mb-4 group-hover:scale-105 transition-transform">
                <KeyRound className="w-6 h-6" />
              </div>
              <h3 className="font-semibold text-white mb-1">Hardware DSC Signer</h3>
              <p className="text-xs text-slate-400">
                Cryptographic signing for Board Minutes, MCA filings, and Secretarial Standards.
              </p>
            </Link>
          </section>
        </main>
      </div>
    </div>
  );
}
