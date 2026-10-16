'use client';

import React, { useEffect } from 'react';
import { Receipt, RefreshCw, LayoutDashboard } from 'lucide-react';
import Link from 'next/link';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function InvoicesErrorBoundary({ error, reset }: ErrorProps) {
  useEffect(() => {
    console.error('[b00k5 Invoices Error Boundary Caught]:', error);
  }, [error]);

  return (
    <div className="min-h-[400px] flex items-center justify-center p-6 text-slate-100">
      <div className="max-w-md w-full bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-2xl text-center">
        <div className="w-12 h-12 bg-sky-500/10 border border-sky-500/20 rounded-xl flex items-center justify-center text-sky-400 mx-auto mb-4">
          <Receipt className="w-6 h-6" />
        </div>

        <h2 className="text-lg font-bold text-white mb-1.5">
          Invoicing & Accounts Receivable Error
        </h2>
        <p className="text-xs text-slate-400 mb-4 leading-relaxed">
          An error occurred while loading tax invoices or contact lists. Your posted customer balances and GSTR-1 ledgers remain preserved.
        </p>

        {error?.message && (
          <div className="p-3 bg-slate-950/80 border border-rose-900/40 rounded-lg text-xs font-mono text-rose-300 break-words mb-4 max-h-24 overflow-y-auto text-left">
            {error.message}
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={() => reset()}
            className="flex-1 flex items-center justify-center gap-2 py-2 px-3 bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold rounded-lg transition-all"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Reload Invoices
          </button>
          <Link
            href="/dashboard"
            className="flex-1 flex items-center justify-center gap-2 py-2 px-3 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg transition-all border border-slate-700"
          >
            <LayoutDashboard className="w-3.5 h-3.5" />
            Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}

