'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem('b00k5_token');
    if (!token) {
      router.push('/setup');
    } else {
      router.push('/dashboard');
    }
  }, [router]);

  return (
    <div className="flex h-screen items-center justify-center bg-slate-950">
      <div className="flex items-center gap-3">
        <div className="w-5 h-5 border-2 border-sky-400 border-t-transparent rounded-full animate-spin"></div>
        <p className="text-slate-400 text-sm font-mono">Initializing b00k5 local workspace...</p>
      </div>
    </div>
  );
}
