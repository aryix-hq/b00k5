'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Building2, ChevronDown, Check, Shield, User, Briefcase, Plus, Loader2 } from 'lucide-react';
import { fetchApi } from '@/lib/api';

export interface CompanySummary {
  id: string;
  legal_name: string;
  trade_name?: string;
  cin?: string;
  pan: string;
  gstin?: string;
  entity_type: string;
  role: string;
  is_primary: boolean;
  logo_url?: string;
}

export function TenantSwitcher() {
  const [companies, setCompanies] = useState<CompanySummary[]>([]);
  const [activeCompany, setActiveCompany] = useState<CompanySummary | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [switching, setSwitching] = useState<boolean>(false);
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const formatRoleBadge = (role: string) => {
    const r = (role || '').toLowerCase();
    if (r.includes('owner')) {
      return { label: 'Owner', color: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' };
    }
    if (r.includes('ca') || r.includes('auditor')) {
      return { label: 'CA / Auditor', color: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20' };
    }
    if (r.includes('finance')) {
      return { label: 'Finance Mgr', color: 'bg-sky-500/10 text-sky-400 border-sky-500/20' };
    }
    return { label: 'Employee', color: 'bg-amber-500/10 text-amber-400 border-amber-500/20' };
  };

  const loadCompanies = async () => {
    try {
      const data = await fetchApi('/api/v1/tenants/my-companies');
      if (Array.isArray(data)) {
        setCompanies(data);
        const storedTid = typeof window !== 'undefined'
          ? (localStorage.getItem('b00k5_active_tenant_id') || localStorage.getItem('b00k5_tenant_id'))
          : null;

        let current = data.find((c: CompanySummary) => c.id === storedTid);
        if (!current && data.length > 0) {
          current = data[0];
          if (typeof window !== 'undefined') {
            localStorage.setItem('b00k5_active_tenant_id', current.id);
            localStorage.setItem('b00k5_tenant_id', current.id);
            localStorage.setItem('b00k5_legal_name', current.legal_name);
            localStorage.setItem('b00k5_role', current.role);
            if (current.cin) localStorage.setItem('b00k5_cin', current.cin);
          }
        }
        setActiveCompany(current || null);
      }
    } catch (err) {
      console.error('Failed to load companies:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCompanies();

    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelectCompany = async (company: CompanySummary) => {
    if (activeCompany?.id === company.id) {
      setIsOpen(false);
      return;
    }

    setSwitching(true);
    try {
      const res = await fetchApi('/api/v1/auth/switch-tenant', {
        method: 'POST',
        body: JSON.stringify({ tenant_id: company.id }),
      });

      if (res && res.access_token) {
        localStorage.setItem('b00k5_token', res.access_token);
        localStorage.setItem('b00k5_active_tenant_id', res.tenant_id);
        localStorage.setItem('b00k5_tenant_id', res.tenant_id);
        localStorage.setItem('b00k5_legal_name', res.legal_name);
        localStorage.setItem('b00k5_role', res.role);
        if (res.cin) localStorage.setItem('b00k5_cin', res.cin);
        if (res.is_super_admin) localStorage.setItem('b00k5_is_super_admin', 'true');

        window.dispatchEvent(new CustomEvent('b00k5_tenant_changed', { detail: res }));
        window.location.reload();
      }
    } catch (err: any) {
      console.error('Failed to switch company:', err);
      alert(err.message || 'Could not switch company context');
      setSwitching(false);
    }
  };

  const activeBadge = activeCompany ? formatRoleBadge(activeCompany.role) : null;

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        disabled={loading || switching}
        className="flex items-center gap-3 px-3.5 py-1.5 rounded-xl bg-slate-800/90 hover:bg-slate-800 border border-slate-700/80 text-left transition-all focus:outline-none focus:ring-1 focus:ring-amber-400/50"
      >
        <div className="p-1.5 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/20 shrink-0">
          <Building2 className="w-4 h-4" />
        </div>

        <div className="flex flex-col min-w-0 pr-1">
          <div className="flex items-center gap-2">
            <span
              className="text-xs font-bold text-white truncate max-w-[280px] sm:max-w-[340px]"
              title={activeCompany?.legal_name || 'Select Company'}
            >
              {loading ? 'Loading...' : (activeCompany?.legal_name || 'Select Company')}
            </span>
            {activeBadge && (
              <span className={`px-1.5 py-0.2 rounded text-[10px] font-semibold border shrink-0 ${activeBadge.color}`}>
                {activeBadge.label}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 text-[10px] text-slate-400">
            <span className="truncate max-w-[200px]">{activeCompany?.entity_type || 'Private Limited'}</span>
            {activeCompany?.cin && (
              <>
                <span className="text-slate-600">•</span>
                <span className="font-mono text-slate-500">{activeCompany.cin.slice(0, 10)}...</span>
              </>
            )}
          </div>
        </div>

        {switching ? (
          <Loader2 className="w-4 h-4 text-amber-400 animate-spin shrink-0" />
        ) : (
          <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${isOpen ? 'rotate-180' : ''} shrink-0`} />
        )}
      </button>

      {isOpen && (
        <div className="absolute left-0 mt-2 w-96 min-w-[320px] max-w-md bg-slate-900 border border-slate-800 rounded-xl shadow-2xl overflow-hidden py-1.5 z-50 animate-in fade-in zoom-in-95 duration-100">
          <div className="px-3.5 py-2 border-b border-slate-800 flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400 font-semibold">
              Select Entity ({companies.length})
            </span>
            <span className="text-[10px] text-slate-500 font-mono">Multi-Tenant IAM</span>
          </div>

          <div className="max-h-64 overflow-y-auto py-1 divide-y divide-slate-800/40">
            {companies.map((comp) => {
              const isSelected = activeCompany?.id === comp.id;
              const roleBadge = formatRoleBadge(comp.role);

              return (
                <button
                  key={comp.id}
                  onClick={() => handleSelectCompany(comp)}
                  className={`w-full text-left px-3.5 py-2.5 flex items-start justify-between gap-3 transition-colors ${
                    isSelected
                      ? 'bg-sky-950/50 text-white border-l-2 border-sky-400'
                      : 'hover:bg-slate-800/70 text-slate-300'
                  }`}
                >
                  <div className="flex-1 min-w-0 space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-white break-words">{comp.legal_name}</span>
                      <span className={`px-1.5 py-0.2 rounded text-[9px] font-semibold border shrink-0 ${roleBadge.color}`}>
                        {roleBadge.label}
                      </span>
                    </div>
                    <div className="text-[10px] text-slate-400 flex items-center gap-2">
                      <span>{comp.entity_type}</span>
                      {comp.cin && (
                        <>
                          <span className="text-slate-600">•</span>
                          <span className="font-mono text-slate-500">{comp.cin}</span>
                        </>
                      )}
                    </div>
                    <div className="text-[9px] text-slate-500 font-mono">
                      PAN: {comp.pan} {comp.gstin ? `| GSTIN: ${comp.gstin}` : ''}
                    </div>
                  </div>

                  {isSelected && (
                    <div className="mt-1 p-0.5 rounded-full bg-sky-500/20 text-sky-400">
                      <Check className="w-3.5 h-3.5" />
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          <div className="px-3 py-2 border-t border-slate-800 bg-slate-950/60 flex items-center justify-between text-[11px]">
            <a
              href="/settings/team"
              className="text-amber-400 hover:text-amber-300 font-medium flex items-center gap-1.5"
            >
              <Plus className="w-3 h-3" />
              <span>Team &amp; Invitations</span>
            </a>
            <span className="text-[10px] text-slate-500">Companies Act §128</span>
          </div>
        </div>
      )}
    </div>
  );
}

