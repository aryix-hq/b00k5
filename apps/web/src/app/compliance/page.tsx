'use client';

import React, { useEffect, useState } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import {
  Scale,
  AlertTriangle,
  Clock,
  CheckCircle,
  AlertCircle,
  FileCheck,
  Calendar,
  DollarSign
} from 'lucide-react';
import { fetchApi } from '@/lib/api';

export default function CompliancePage() {
  const [dashboard, setDashboard] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  async function loadData() {
    try {
      const res = await fetchApi('/api/v1/compliance/dashboard');
      setDashboard(res);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  const handleMarkComplete = async (eventId: string) => {
    try {
      await fetchApi(`/api/v1/compliance/${eventId}/complete`, { method: 'POST' });
      await loadData();
    } catch (e: any) {
      alert(e.message || 'Error updating status');
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Navbar />

        <main className="p-8 space-y-6 max-w-7xl mx-auto w-full">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Scale className="w-6 h-6 text-sky-400" />
              Statutory Compliance & MCA Penalty Watchdog
            </h2>
            <p className="text-xs text-slate-400">
              Active tracking under the Companies Act 2013 and CGST Act to prevent ₹100/day compounding liabilities
            </p>
          </div>

          {/* Stats Bar */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
              <span className="text-xs text-slate-400">Total Obligations</span>
              <p className="text-2xl font-bold text-white mt-1">{dashboard?.total_events || 0}</p>
            </div>
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
              <span className="text-xs text-amber-400">Due Soon (&le;15 Days)</span>
              <p className="text-2xl font-bold text-amber-400 mt-1">{dashboard?.due_soon_count || 0}</p>
            </div>
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
              <span className="text-xs text-rose-400">Overdue Filings</span>
              <p className="text-2xl font-bold text-rose-400 mt-1">{dashboard?.overdue_count || 0}</p>
            </div>
            <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
              <span className="text-xs text-rose-400">Compounding MCA Fines</span>
              <p className="text-2xl font-bold text-rose-400 font-mono mt-1">
                ₹{dashboard?.total_penalty_accruing_inr || '0.00'}
              </p>
            </div>
          </div>

          {/* Obligations List */}
          <div className="space-y-4">
            <h3 className="text-sm font-semibold text-slate-300">Statutory Calendar & Countdown Timers</h3>
            <div className="space-y-3">
              {dashboard?.upcoming_events?.map((ev: any) => {
                const isOverdue = ev.status === 'overdue';
                const isDueSoon = ev.status === 'due_soon';
                const isDone = ev.status === 'completed';

                return (
                  <div
                    key={ev.id}
                    className={`p-5 rounded-xl border flex items-center justify-between transition-all ${
                      isDone
                        ? 'bg-slate-900/40 border-slate-800/50 opacity-60'
                        : isOverdue
                        ? 'bg-rose-950/20 border-rose-800/40'
                        : isDueSoon
                        ? 'bg-amber-950/20 border-amber-800/40'
                        : 'bg-slate-900 border-slate-800'
                    }`}
                  >
                    <div className="space-y-1.5 max-w-2xl">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                          {ev.category.replace('_', ' ')}
                        </span>
                        {ev.statutory_reference && (
                          <span className="text-[11px] text-slate-400 font-mono">
                            {ev.statutory_reference}
                          </span>
                        )}
                      </div>
                      <h4 className="font-semibold text-white text-sm">{ev.title}</h4>
                      <p className="text-xs text-slate-400">{ev.description}</p>
                    </div>

                    <div className="flex items-center gap-6">
                      <div className="text-right">
                        <span className="text-xs text-slate-400 block font-mono">Due: {ev.due_date}</span>
                        {isDone ? (
                          <span className="text-xs text-emerald-400 font-medium flex items-center gap-1 justify-end mt-1">
                            <CheckCircle className="w-3.5 h-3.5" /> Filed & Completed
                          </span>
                        ) : isOverdue ? (
                          <span className="text-xs font-bold text-rose-400 flex items-center gap-1 justify-end mt-1">
                            <AlertCircle className="w-3.5 h-3.5" /> Overdue (+₹{ev.accumulated_penalty_inr} fine)
                          </span>
                        ) : (
                          <span className="text-xs text-sky-400 font-medium mt-1 block">
                            {ev.days_remaining} days remaining
                          </span>
                        )}
                      </div>

                      {!isDone && (
                        <button
                          onClick={() => handleMarkComplete(ev.id)}
                          className="px-3.5 py-1.5 rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 font-medium"
                        >
                          Mark Completed
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
