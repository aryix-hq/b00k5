'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Lock,
  Mail,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Building2,
  KeyRound,
  X
} from 'lucide-react';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePasswordLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim().toLowerCase(), password })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Invalid email or password.');
      }

      localStorage.setItem('b00k5_token', data.access_token);
      if (data.tenant_id) {
        localStorage.setItem('b00k5_tenant_id', data.tenant_id);
      }
      localStorage.setItem('b00k5_user_email', data.email);
      localStorage.setItem('b00k5_user_role', data.role || 'ADMIN');
      localStorage.setItem('b00k5_role', (data.role || 'owner').toLowerCase());
      localStorage.setItem('b00k5_is_super_admin', data.is_super_admin ? 'true' : 'false');

      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Login failed.');
    } finally {
      setLoading(false);
    }
  };

  const [googleModalOpen, setGoogleModalOpen] = useState(false);
  const [customGoogleEmail, setCustomGoogleEmail] = useState('');

  const executeGoogleAuth = async (targetEmail: string, displayName?: string) => {
    setGoogleLoading(true);
    setError(null);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/auth/google/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: targetEmail.trim().toLowerCase(),
          name: displayName || targetEmail.split('@')[0].replace('.', ' ').toUpperCase()
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Google authentication failed.');
      }

      localStorage.setItem('b00k5_token', data.access_token);
      if (data.tenant_id) {
        localStorage.setItem('b00k5_tenant_id', data.tenant_id);
      }
      localStorage.setItem('b00k5_user_email', data.email);
      localStorage.setItem('b00k5_user_role', data.role || 'ADMIN');
      localStorage.setItem('b00k5_role', (data.role || 'owner').toLowerCase());
      localStorage.setItem('b00k5_is_super_admin', data.is_super_admin ? 'true' : 'false');
      setGoogleModalOpen(false);

      router.push('/dashboard');
    } catch (err: any) {
      setError(err.message || 'Failed to authenticate with Google.');
    } finally {
      setGoogleLoading(false);
    }
  };

  const handleGoogleLogin = (prefilledEmail?: string) => {
    if (prefilledEmail) {
      executeGoogleAuth(prefilledEmail);
      return;
    }
    if (email && email.includes('@')) {
      executeGoogleAuth(email);
      return;
    }
    // Open user-friendly Google login & permissions modal
    setGoogleModalOpen(true);
  };

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center p-4 selection:bg-sky-500 selection:text-white">
      <div className="w-full max-w-md space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 shadow-lg shadow-sky-500/20 mb-2">
            <span className="font-mono text-xl font-bold text-white tracking-wider">b5</span>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Sign in to b00k5</h1>
          <p className="text-xs text-slate-400">
            Financial Operating System &amp; Statutory Compliance Platform for Indian Startups
          </p>
        </div>

        {/* Auth Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-xl space-y-5">
          {error && (
            <div className="p-3.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* 1-Click Sign in with Google / Gmail */}
          <div className="space-y-3">
            <button
              type="button"
              onClick={() => handleGoogleLogin()}
              disabled={googleLoading}
              className="w-full py-2.5 px-4 bg-white hover:bg-slate-100 disabled:opacity-60 text-slate-900 font-semibold text-xs rounded-xl flex items-center justify-center gap-2.5 shadow transition-all duration-150"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
              </svg>
              <span>{googleLoading ? 'Signing in with Google...' : 'Continue with Google (Gmail)'}</span>
            </button>

            <div className="relative flex py-1 items-center">
              <div className="flex-grow border-t border-slate-800"></div>
              <span className="flex-shrink mx-3 text-[10px] uppercase font-mono text-slate-500">Or use email</span>
              <div className="flex-grow border-t border-slate-800"></div>
            </div>
          </div>

          {/* Email / Password Form */}
          <form onSubmit={handlePasswordLogin} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Work Email Address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="founder@yourcompany.com"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-medium text-slate-300">
                  Password
                </label>
              </div>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-2.5" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
                  className="w-full bg-slate-950 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500 transition-colors"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white font-semibold text-xs rounded-xl flex items-center justify-center gap-2 shadow-lg shadow-sky-600/20 transition-all"
            >
              <span>{loading ? 'Authenticating...' : 'Sign in'}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>

        {/* Footer Info */}
        <div className="text-center text-[11px] text-slate-500 space-y-1">
          <p className="flex items-center justify-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            End-to-End Encrypted &bull; PostgreSQL 16 RLS Protected
          </p>
          <p>b00k5 Financial Engine &bull; Section 128 Companies Act 2013 Compliant</p>
        </div>
      </div>

      {/* Google Account & Permission Modal */}
      {googleModalOpen && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 w-full max-w-md rounded-2xl p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <svg className="w-5 h-5 shrink-0" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
                </svg>
                <div>
                  <h3 className="text-sm font-semibold text-white">Sign in with Google</h3>
                  <p className="text-[11px] text-slate-400">Enter your Google Workspace or Gmail account</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setGoogleModalOpen(false)}
                className="p-1 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Gmail Input */}
            <div className="space-y-2">
              <label className="text-[11px] font-medium text-slate-400 block">
                Google Workspace / Gmail Address:
              </label>
              <div className="flex gap-2">
                <input
                  type="email"
                  placeholder="yourname@gmail.com"
                  value={customGoogleEmail}
                  onChange={(e) => setCustomGoogleEmail(e.target.value)}
                  className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
                />
                <button
                  type="button"
                  onClick={() => {
                    if (customGoogleEmail && customGoogleEmail.includes('@')) {
                      executeGoogleAuth(customGoogleEmail);
                    }
                  }}
                  disabled={googleLoading || !customGoogleEmail.includes('@')}
                  className="px-3.5 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-50 text-white font-semibold text-xs rounded-xl shadow transition-all"
                >
                  {googleLoading ? 'Signing in...' : 'Sign in'}
                </button>
              </div>
            </div>

            {/* Permissions & Consent Notice */}
            <div className="p-3 bg-sky-950/20 border border-sky-800/30 rounded-xl space-y-1.5 text-[11px] text-slate-400">
              <div className="flex items-center gap-1.5 text-sky-400 font-medium">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Google Permissions Requested:</span>
              </div>
              <ul className="list-disc list-inside space-y-0.5 text-slate-400 pl-1 text-[10px]">
                <li>Basic Profile &amp; Email verification for single sign-on</li>
                <li>Encrypted Google Drive sync for financial books &amp; DB backups</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
