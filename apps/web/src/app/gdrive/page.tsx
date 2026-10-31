'use client';

import React, { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Cloud, ArrowRight } from 'lucide-react';
import Link from 'next/link';

export default function GDriveRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/settings/integrations?tab=cloud&provider=gdrive');
  }, [router]);

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 items-center justify-center p-4">
      <div className="p-8 rounded-2xl bg-slate-900 border border-slate-800 max-w-md w-full text-center space-y-4">
        <div className="w-12 h-12 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400 flex items-center justify-center mx-auto">
          <Cloud className="w-6 h-6 animate-pulse" />
        </div>
        <h2 className="text-lg font-bold text-white">Google Drive Sync Relocated</h2>
        <p className="text-xs text-slate-400 leading-relaxed">
          Google Drive sync, database backups, and point-in-time recovery are now consolidated under the unified <span className="font-semibold text-slate-200">Cloud Storage & Backups</span> console.
        </p>
        <div className="pt-2">
          <Link
            href="/settings/integrations?tab=cloud&provider=gdrive"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-medium text-xs transition-colors"
          >
            Go to Cloud Storage & Backups
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </div>
  );
}
