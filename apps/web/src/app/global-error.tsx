'use client';

import React, { useEffect } from 'react';
import { ShieldAlert, RefreshCw } from 'lucide-react';

interface GlobalErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function GlobalError({ error, reset }: GlobalErrorProps) {
  useEffect(() => {
    console.error('[b00k5 Root Layout Fatal Crash Captured]:', error);
  }, [error]);

  return (
    <html lang="en">
      <body className="antialiased bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-slate-900/90 border border-slate-800 rounded-2xl p-8 shadow-2xl backdrop-blur-md">
          <div className="w-14 h-14 bg-rose-500/10 border border-rose-500/20 rounded-xl flex items-center justify-center text-rose-400 mx-auto mb-6">
            <ShieldAlert className="w-7 h-7" />
          </div>

          <h2 className="text-xl font-bold text-center text-white mb-2">
            Critical System Failure
          </h2>
          <p className="text-xs text-slate-400 text-center mb-6 leading-relaxed">
            A fatal error interrupted the core application root layout. Local ledger transactions and database records remain immutable and unaffected.
          </p>

          {error?.message && (
            <div className="p-3 bg-slate-950/80 border border-rose-900/40 rounded-lg text-xs font-mono text-rose-300 break-words mb-6 max-h-32 overflow-y-auto">
              {error.message}
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={() => reset()}
              className="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold rounded-lg transition-all shadow-lg shadow-emerald-950/40"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Reload Application
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}

