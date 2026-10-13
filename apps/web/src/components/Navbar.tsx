'use client';

import React, { useEffect, useState, useRef } from 'react';
import { Building2, Shield, User as UserIcon, Users, LogOut, Calendar, ChevronDown, Settings, Cloud, FolderLock, Check, AlertTriangle } from 'lucide-react';

export function Navbar() {
  const now = new Date();
  const currentYr = now.getMonth() >= 3 ? now.getFullYear() : now.getFullYear() - 1;
  const currentActiveFY = `FY ${currentYr}-${currentYr + 1}`;

  const [companyName, setCompanyName] = useState('Organization');
  const [cin, setCin] = useState('');
  const [role, setRole] = useState('Owner / Founder');
  const [selectedFY, setSelectedFY] = useState(currentActiveFY);
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const [currentUser, setCurrentUser] = useState<any>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const storedName = localStorage.getItem('b00k5_legal_name');
      const storedCin = localStorage.getItem('b00k5_cin');
      const storedRole = localStorage.getItem('b00k5_role');
      const storedFY = localStorage.getItem('b00k5_selected_fy');
      const token = localStorage.getItem('b00k5_token');

      if (storedName) setCompanyName(storedName);
      if (storedCin) setCin(storedCin);
      if (storedRole) setRole(storedRole);
      if (storedFY) {
        setSelectedFY(storedFY);
      } else {
        localStorage.setItem('b00k5_selected_fy', currentActiveFY);
      }

      // Fetch authentic user session & multi-tenant profile
      if (token) {
        fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/auth/me`, {
          headers: { Authorization: `Bearer ${token}` }
        })
          .then(res => res.ok ? res.json() : null)
          .then(data => {
            if (data) {
              setCurrentUser(data);
              if (data.tenants && data.tenants.length > 0) {
                const activeTid = localStorage.getItem('b00k5_tenant_id');
                const matched = data.tenants.find((t: any) => t.id === activeTid) || data.tenants[0];
                if (matched) {
                  setCompanyName(matched.legal_name);
                  localStorage.setItem('b00k5_legal_name', matched.legal_name);
                  if (matched.cin) {
                    setCin(matched.cin);
                    localStorage.setItem('b00k5_cin', matched.cin);
                  }
                }
              }
            }
          })
          .catch(() => {});
      }
    }

    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setUserDropdownOpen(false);
      }
    };

    const handleFYEvent = (e: any) => {
      if (e.detail) {
        setSelectedFY(e.detail);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    window.addEventListener('b00k5_fy_changed', handleFYEvent);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      window.removeEventListener('b00k5_fy_changed', handleFYEvent);
    };
  }, [currentActiveFY]);

  const handleFYChange = (newFY: string) => {
    setSelectedFY(newFY);
    if (typeof window !== 'undefined') {
      localStorage.setItem('b00k5_selected_fy', newFY);
      window.dispatchEvent(new CustomEvent('b00k5_fy_changed', { detail: newFY }));
      window.dispatchEvent(new Event('storage'));
    }
  };

  const handleLogout = async () => {
    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      if (token) {
        await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/auth/logout`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` }
        });
      }
    } catch (e) {
      console.error('Logout error:', e);
    } finally {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('b00k5_token');
        localStorage.removeItem('b00k5_user');
        localStorage.removeItem('b00k5_tenant_id');
        localStorage.removeItem('b00k5_legal_name');
        localStorage.removeItem('b00k5_cin');
        localStorage.removeItem('b00k5_role');
        window.location.href = '/login';
      }
    }
  };

  const handleSwitchTenant = (tenant: any) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('b00k5_tenant_id', tenant.id);
      localStorage.setItem('b00k5_legal_name', tenant.legal_name);
      if (tenant.cin) localStorage.setItem('b00k5_cin', tenant.cin);
      if (tenant.role) localStorage.setItem('b00k5_role', tenant.role);
      setCompanyName(tenant.legal_name);
      setCin(tenant.cin || '');
      setRole(tenant.role || 'Member');
      setUserDropdownOpen(false);
      window.location.reload();
    }
  };


  // Dynamically calculate Selected Period FY & AY
  const parseStartYear = (fy: string) => {
    const match = fy.match(/(\d{4})/);
    return match ? parseInt(match[1]) : currentYr;
  };

  const selectedStartYr = parseStartYear(selectedFY);
  const selectedPeriodFY = `${selectedStartYr}-${String(selectedStartYr + 1).slice(-2)}`;
  const selectedPeriodAY = `${selectedStartYr + 1}-${String(selectedStartYr + 2).slice(-2)}`;
  const isCurrent = selectedStartYr === currentYr;
  const isPrior = selectedStartYr < currentYr;
  const isFuture = selectedStartYr > currentYr;

  // Dynamic available periods (e.g. Current FY first, past 5 years, upcoming year)
  const availablePeriods: string[] = [currentActiveFY];
  for (let y = currentYr - 1; y >= currentYr - 5; y--) {
    availablePeriods.push(`FY ${y}-${y + 1}`);
  }
  availablePeriods.push(`FY ${currentYr + 1}-${currentYr + 2}`);

  const displayName = currentUser ? `${currentUser.first_name} ${currentUser.last_name}` : 'Corporate Officer';
  const displayEmail = currentUser?.email || 'officer@b00k5.internal';

  return (
    <>
      <header className="h-16 border-b border-slate-800 bg-slate-900/30 px-6 flex items-center justify-between relative z-40">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Building2 className="w-5 h-5 text-sky-400" />
            <span className="font-semibold text-slate-100">{companyName}</span>
          </div>
          {cin && (
            <>
              <span className="text-slate-600">|</span>
              <span className="font-mono text-xs text-slate-400 bg-slate-800/80 px-2 py-1 rounded border border-slate-700">
                CIN: {cin}
              </span>
            </>
          )}
        </div>

        <div className="flex items-center gap-4">
          {/* Active FY/AY Selected Period Badge */}
          <div id="active-fy-ay-badge" className={`hidden sm:flex items-center gap-1.5 px-3 py-1 rounded-lg border text-xs font-mono font-bold ${
            isCurrent
              ? 'bg-sky-500/10 border-sky-500/20 text-sky-300'
              : isPrior
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-300'
              : 'bg-purple-500/10 border-purple-500/30 text-purple-300'
          }`}>
            <span>{isCurrent ? 'Active: ' : isPrior ? 'Prior Period: ' : 'Upcoming Period: '}FY {selectedPeriodFY} | AY {selectedPeriodAY}</span>
          </div>

          {/* Financial Year Switcher */}
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-lg bg-amber-500/10 border border-amber-500/20 text-xs">
            <Calendar className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span className="text-slate-400 font-medium">Period:</span>
            <select
              id="fy-switcher-select"
              value={selectedFY}
              onChange={(e) => handleFYChange(e.target.value)}
              onInput={(e) => handleFYChange((e.target as HTMLSelectElement).value)}
              className="bg-transparent text-amber-300 font-mono font-bold focus:outline-none cursor-pointer"
            >
              {availablePeriods.map((fy) => (
                <option key={fy} value={fy} className="bg-slate-900 text-white">
                  {fy} {fy === currentActiveFY ? '(Current)' : ''}
                </option>
              ))}
            </select>
          </div>

        {/* DEF-03: User Session Dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setUserDropdownOpen(!userDropdownOpen)}
            className="flex items-center gap-2.5 px-3 py-1.5 rounded-full bg-slate-800/80 hover:bg-slate-800 border border-slate-700/80 text-xs text-slate-200 transition-all focus:outline-none"
          >
            <div className="w-6 h-6 rounded-full bg-sky-600 flex items-center justify-center text-white text-[11px] font-bold">
              {displayName.charAt(0).toUpperCase()}
            </div>
            <div className="text-left hidden sm:block">
              <div className="font-medium text-white leading-tight">{displayName}</div>
              <div className="text-[10px] text-slate-400 capitalize">{role}</div>
            </div>
            <ChevronDown className={`w-3.5 h-3.5 text-slate-400 transition-transform ${userDropdownOpen ? 'rotate-180' : ''}`} />
          </button>

          {userDropdownOpen && (
            <div className="absolute right-0 mt-2 w-72 bg-slate-900 border border-slate-800 rounded-xl shadow-2xl overflow-hidden py-1 z-50 animate-in fade-in zoom-in-95 duration-100">
              {/* User Header */}
              <div className="px-4 py-3 border-b border-slate-800 bg-slate-950/60">
                <div className="text-xs font-semibold text-white">{displayName}</div>
                <div className="text-[11px] text-slate-400 font-mono truncate">{displayEmail}</div>
                <div className="mt-2 inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-[10px] text-emerald-400 font-medium">
                  <Shield className="w-3 h-3" />
                  Active Role: {role}
                </div>
              </div>

              {/* Multi-Tenancy Organizations */}
              {currentUser?.tenants && currentUser.tenants.length > 0 && (
                <div className="px-4 py-2 border-b border-slate-800">
                  <div className="text-[10px] font-mono uppercase text-slate-500 mb-1.5">Organizations</div>
                  <div className="space-y-1">
                    {currentUser.tenants.map((t: any) => {
                      const isCurrent = (t.legal_name === companyName) || (typeof window !== 'undefined' && localStorage.getItem('b00k5_tenant_id') === t.id);
                      return (
                        <button
                          key={t.id}
                          onClick={() => handleSwitchTenant(t)}
                          className={`w-full text-left px-2.5 py-1.5 rounded-lg text-xs flex items-center justify-between transition-colors ${
                            isCurrent ? 'bg-sky-950/60 text-sky-300 font-medium border border-sky-800/40' : 'text-slate-300 hover:bg-slate-800/60'
                          }`}
                        >
                          <div className="truncate pr-2">
                            <div>{t.legal_name}</div>
                            {t.cin && <div className="text-[9px] text-slate-500 font-mono">{t.cin}</div>}
                          </div>
                          {isCurrent && <Check className="w-3.5 h-3.5 text-sky-400 shrink-0" />}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Quick Navigation Links */}
              <div className="py-1">
                <a
                  href="/settings"
                  className="flex items-center gap-2.5 px-4 py-2 text-xs text-slate-300 hover:bg-slate-800/60 hover:text-white transition-colors"
                >
                  <Settings className="w-3.5 h-3.5 text-slate-400" />
                  Company Profile &amp; Rule Engine
                </a>
                <a
                  href="/iam"
                  className="flex items-center gap-2.5 px-4 py-2 text-xs text-slate-300 hover:bg-slate-800/60 hover:text-white transition-colors"
                >
                  <Users className="w-3.5 h-3.5 text-slate-400" />
                  Team &amp; Access (IAM)
                </a>
                <a
                  href="/vault"
                  className="flex items-center gap-2.5 px-4 py-2 text-xs text-slate-300 hover:bg-slate-800/60 hover:text-white transition-colors"
                >
                  <FolderLock className="w-3.5 h-3.5 text-slate-400" />
                  Statutory Document Locker
                </a>
                <a
                  href="/gdrive"
                  className="flex items-center gap-2.5 px-4 py-2 text-xs text-slate-300 hover:bg-slate-800/60 hover:text-white transition-colors"
                >
                  <Cloud className="w-3.5 h-3.5 text-slate-400" />
                  Google Drive Cloud Mirror
                </a>
              </div>

              {/* Sign Out Action */}
              <div className="border-t border-slate-800 pt-1">
                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2.5 px-4 py-2 text-xs text-rose-400 hover:bg-rose-500/10 hover:text-rose-300 transition-colors text-left"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  Sign Out &amp; Invalidate Session
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>

    {isPrior && (
      <div id="prior-period-banner" className="w-full bg-amber-500/15 border-b border-amber-500/30 px-6 py-2 text-xs text-amber-300 font-medium flex items-center justify-between z-30">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>Prior Period Active (FY 2025-26 | AY 2026-27). Books are in Closing Mode.</span>
        </div>
        <span className="text-[11px] text-amber-400/80 font-mono">Restricted Period</span>
      </div>
    )}
  </>
  );
}
