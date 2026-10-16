'use client';

import React, { useEffect } from 'react';
import { ShieldAlert, RefreshCw, LayoutDashboard } from 'lucide-react';
import Link from 'next/link';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function AdminErrorBoundary({ error, reset }: ErrorProps) {
  useEffect(() => {
    console.error('[b00k5 Admin Error Boundary Caught]:', error);
  }, [error]);

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6 text-slate-100">
      <div className="max-w-md w-full bg-slate-900/90 border border-slate-800 rounded-2xl p-8 shadow-2xl backdrop-blur-md">
        <div className="w-14 h-14 bg-rose-500/10 border border-rose-500/20 rounded-xl flex items-center justify-center text-rose-400 mx-auto mb-6">
          <ShieldAlert className="w-7 h-7" />
        </div>

        <h2 className="text-xl font-bold text-center text-white mb-2">
          Platform Administration Error
        </h2>
        <p className="text-xs text-slate-400 text-center mb-6 leading-relaxed">
          An error occurred while loading administrative system telemetry or tenant directory. System ledger invariants and cryptographic databases remain unharmed.
        </p>

        {error?.message && (
          <div className="p-3 bg-slate-950/80 border border-rose-900/40 rounded-lg text-xs font-mono text-rose-300 break-words mb-6 max-h-32 overflow-y-auto">
            {error.message}
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={() => reset()}
            className="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold rounded-lg transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Retry
          </button>
          <Link
            href="/dashboard"
            className="flex-1 flex items-center justify-center gap-2 py-2.5 px-4 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg transition-all border border-slate-700"
          >
            <LayoutDashboard className="w-3.5 h-3.5" />
            Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}

