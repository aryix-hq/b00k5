'use client';

import React, { useEffect, useState } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import {
  Building2,
  Search,
  CheckCircle2,
  ExternalLink,
  Plus,
  ShieldAlert,
  ArrowRight,
  Loader2,
  Hash,
  FileText,
  Calendar,
  Users,
  Archive,
  RotateCcw,
  Trash2,
  X,
  Filter
} from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { fetchApi } from '@/lib/api';

interface Company {
  id: string;
  legal_name: string;
  entity_type: string;
  cin?: string;
  pan?: string;
  gstin?: string;
  role: string;
  is_primary?: boolean;
  is_archived?: boolean;
  registered_office?: string;
}

export default function TenantDirectoryPage() {
  const router = useRouter();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [switchingId, setSwitchingId] = useState<string | null>(null);
  const [actionId, setActionId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>('');
  const [successMsg, setSuccessMsg] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'archived'>('active');

  // Create Modal State
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [newCompany, setNewCompany] = useState({
    legal_name: '',
    trade_name: '',
    entity_type: 'Private Limited Company',
    pan: '',
    cin: '',
    gstin: '',
    state_code: '29',
    registered_office: '',
    admin_din: ''
  });

  const loadTenants = async () => {
    setLoading(true);
    setErrorMsg('');
    try {
      const data = await fetchApi('/api/v1/tenants/my-companies');
      if (Array.isArray(data)) {
        setCompanies(data);
      }
    } catch (err: any) {
      console.error('Failed to load tenants:', err);
      setErrorMsg(err.message || 'Unable to retrieve company directory. Ensure you are logged in as Super Admin.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTenants();
  }, []);

  const handleSwitchTenant = async (company: Company) => {
    setSwitchingId(company.id);
    try {
      const res = await fetchApi('/api/v1/tenants/switch-tenant', {
        method: 'POST',
        body: JSON.stringify({ tenant_id: company.id }),
      });

      if (res && res.access_token) {
        localStorage.setItem('b00k5_token', res.access_token);
        localStorage.setItem('b00k5_active_tenant_id', res.active_tenant_id);
        localStorage.setItem('b00k5_legal_name', company.legal_name);
        if (company.cin) localStorage.setItem('b00k5_cin', company.cin);
        document.cookie = `b00k5_active_tenant_id=${res.active_tenant_id}; path=/; max-age=2592000; SameSite=Lax`;
        document.cookie = `b00k5_token=${res.access_token}; path=/; max-age=2592000; SameSite=Lax`;
        router.push('/dashboard');
        router.refresh();
      }
    } catch (err: any) {
      console.error('Tenant switch failed:', err);
      alert(err.message || 'Failed to switch company.');
    } finally {
      setSwitchingId(null);
    }
  };

  const handleToggleArchive = async (company: Company) => {
    const isArchived = Boolean(company.is_archived);
    const actionWord = isArchived ? 'restore' : 'archive';
    if (!window.confirm(`Are you sure you want to ${actionWord} "${company.legal_name}"?`)) {
      return;
    }

    setActionId(company.id);
    try {
      const res = await fetchApi(`/api/v1/tenants/admin/${company.id}/archive`, {
        method: 'POST'
      });
      setSuccessMsg(res.message || `Entity "${company.legal_name}" has been updated.`);
      await loadTenants();
    } catch (err: any) {
      setErrorMsg(err.message || `Failed to ${actionWord} company.`);
    } finally {
      setActionId(null);
    }
  };

  const handleDeleteTenant = async (company: Company) => {
    const promptConfirm = window.prompt(
      `PERMANENT DESTRUCTION WARNING:\n\nYou are about to permanently delete the company "${company.legal_name}".\nAll Chart of Accounts, Invoices, Journal Entries, and Vault documents for this workspace will be deleted.\n\nType the company's legal name below to confirm:`,
      ''
    );
    if (promptConfirm !== company.legal_name) {
      if (promptConfirm !== null) {
        alert('Company name did not match. Deletion cancelled.');
      }
      return;
    }

    setActionId(company.id);
    try {
      const res = await fetchApi(`/api/v1/tenants/admin/${company.id}`, {
        method: 'DELETE'
      });
      setSuccessMsg(res.message || `Entity "${company.legal_name}" permanently deleted.`);
      await loadTenants();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to delete company.');
    } finally {
      setActionId(null);
    }
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCompany.legal_name || !newCompany.pan) {
      alert('Legal Name and PAN are mandatory.');
      return;
    }

    setSubmitting(true);
    setErrorMsg('');
    setSuccessMsg('');
    try {
      const res = await fetchApi('/api/v1/tenants/admin/create-tenant', {
        method: 'POST',
        body: JSON.stringify(newCompany)
      });
      setSuccessMsg(`Entity "${res.legal_name}" successfully provisioned with Chart of Accounts.`);
      setCreateModalOpen(false);
      setNewCompany({
        legal_name: '',
        trade_name: '',
        entity_type: 'Private Limited Company',
        pan: '',
        cin: '',
        gstin: '',
        state_code: '29',
        registered_office: '',
        admin_din: ''
      });
      await loadTenants();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to create new entity.');
    } finally {
      setSubmitting(false);
    }
  };

  const filteredCompanies = companies.filter((c) => {
    const isArchived = Boolean(c.is_archived);
    if (statusFilter === 'active' && isArchived) return false;
    if (statusFilter === 'archived' && !isArchived) return false;

    const q = searchQuery.toLowerCase();
    return (
      c.legal_name?.toLowerCase().includes(q) ||
      c.cin?.toLowerCase().includes(q) ||
      c.pan?.toLowerCase().includes(q) ||
      c.entity_type?.toLowerCase().includes(q)
    );
  });

  const activeCount = companies.filter((c) => !c.is_archived).length;
  const archivedCount = companies.filter((c) => c.is_archived).length;

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 antialiased overflow-hidden">
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Navbar />

        <main className="flex-1 p-6 lg:p-8 max-w-7xl w-full mx-auto space-y-6">
          {/* Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
            <div>
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-sky-500/10 text-sky-400 border border-sky-500/20">
                  <Building2 className="w-6 h-6" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h1 className="text-xl font-bold text-white tracking-tight">Tenant &amp; Company Directory</h1>
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                      Super Admin
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Provision new corporate entities, archive obsolete workspaces, and switch active tenant context.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                id="add-company-btn"
                data-testid="add-company-btn"
                onClick={() => setCreateModalOpen(true)}
                className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow-lg shadow-sky-950/40 transition-all"
              >
                <Plus className="w-4 h-4" />
                Add New Company
              </button>
            </div>
          </div>

          {/* Filter Bar & Search */}
          <div className="flex flex-col sm:flex-row gap-3">
            {/* Search Bar */}
            <div className="flex-1 flex items-center gap-3 p-2 bg-slate-900/90 border border-slate-800 rounded-xl">
              <div className="p-2 text-slate-500">
                <Search className="w-4 h-4" />
              </div>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search companies by Legal Name, CIN, or PAN..."
                className="flex-1 bg-transparent text-xs text-white placeholder-slate-500 focus:outline-none"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery('')}
                  className="text-xs text-slate-400 hover:text-white px-2"
                >
                  Clear
                </button>
              )}
            </div>

            {/* Status Filter Tabs */}
            <div className="flex items-center gap-1.5 p-1 bg-slate-900 border border-slate-800 rounded-xl shrink-0">
              <button
                onClick={() => setStatusFilter('active')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  statusFilter === 'active'
                    ? 'bg-sky-600 text-white font-semibold shadow'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Active ({activeCount})
              </button>
              <button
                onClick={() => setStatusFilter('archived')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  statusFilter === 'archived'
                    ? 'bg-amber-600 text-white font-semibold shadow'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                Archived ({archivedCount})
              </button>
              <button
                onClick={() => setStatusFilter('all')}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  statusFilter === 'all'
                    ? 'bg-slate-800 text-white font-semibold'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                All ({companies.length})
              </button>
            </div>
          </div>

          {/* Success Message */}
          {successMsg && (
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>{successMsg}</span>
              </div>
              <button onClick={() => setSuccessMsg('')} className="text-slate-400 hover:text-white">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Error Message */}
          {errorMsg && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
              <button onClick={() => setErrorMsg('')} className="text-slate-400 hover:text-white">
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Loading State */}
          {loading ? (
            <div className="flex flex-col items-center justify-center py-16 text-slate-400 space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-sky-400" />
              <p className="text-xs">Loading registered companies...</p>
            </div>
          ) : filteredCompanies.length === 0 ? (
            <div className="p-12 text-center bg-slate-900/40 border border-slate-800 rounded-2xl space-y-3">
              <Building2 className="w-10 h-10 text-slate-600 mx-auto" />
              <h3 className="text-sm font-semibold text-white">No companies found</h3>
              <p className="text-xs text-slate-400 max-w-sm mx-auto">
                {searchQuery
                  ? 'No registered companies match your search query.'
                  : statusFilter === 'archived'
                  ? 'No companies are currently in the archive.'
                  : 'No active companies registered on this platform yet.'}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredCompanies.map((comp) => {
                const isCurrentActive =
                  typeof window !== 'undefined' &&
                  localStorage.getItem('b00k5_active_tenant_id') === comp.id;
                const isArchived = Boolean(comp.is_archived);

                return (
                  <div
                    key={comp.id}
                    className={`p-5 rounded-2xl border transition-all ${
                      isArchived
                        ? 'bg-slate-900/40 border-amber-500/20 opacity-80'
                        : isCurrentActive
                        ? 'bg-sky-950/20 border-sky-500/40 shadow-lg shadow-sky-950/20'
                        : 'bg-slate-900/80 border-slate-800/80 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <h2 className="text-sm font-bold text-white break-words">
                            {comp.legal_name}
                          </h2>
                          {isCurrentActive && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                              <CheckCircle2 className="w-3 h-3" /> Active Session
                            </span>
                          )}
                          {isArchived && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20 flex items-center gap-1">
                              <Archive className="w-3 h-3" /> Archived
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-400">{comp.entity_type || 'Private Limited Company'}</p>
                      </div>

                      <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold uppercase bg-slate-800 text-slate-300 border border-slate-700">
                        {comp.role}
                      </span>
                    </div>

                    {/* Metadata Grid */}
                    <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/60 text-[11px] font-mono space-y-1.5 mb-4">
                      {comp.cin && (
                        <div className="flex justify-between items-center">
                          <span className="text-slate-500">CIN:</span>
                          <span className="text-slate-300 font-semibold">{comp.cin}</span>
                        </div>
                      )}
                      {comp.pan && (
                        <div className="flex justify-between items-center">
                          <span className="text-slate-500">PAN:</span>
                          <span className="text-slate-300">{comp.pan}</span>
                        </div>
                      )}
                      {comp.gstin && (
                        <div className="flex justify-between items-center">
                          <span className="text-slate-500">GSTIN:</span>
                          <span className="text-slate-300">{comp.gstin}</span>
                        </div>
                      )}
                    </div>

                    {/* Action Bar */}
                    <div className="flex items-center justify-between gap-2 pt-2 border-t border-slate-800/60 flex-wrap">
                      <div className="flex items-center gap-2">
                        {/* Archive / Restore Button */}
                        <button
                          onClick={() => handleToggleArchive(comp)}
                          disabled={actionId === comp.id || isCurrentActive}
                          title={isArchived ? 'Restore company workspace' : 'Archive company'}
                          className={`p-1.5 rounded-lg text-xs font-semibold transition-all border ${
                            isArchived
                              ? 'bg-amber-500/10 border-amber-500/30 text-amber-300 hover:bg-amber-500/20'
                              : 'bg-slate-800/80 border-slate-700 text-slate-400 hover:text-white'
                          } ${isCurrentActive ? 'opacity-40 cursor-not-allowed' : ''}`}
                        >
                          {actionId === comp.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : isArchived ? (
                            <span className="flex items-center gap-1 text-[11px]">
                              <RotateCcw className="w-3 h-3" /> Restore
                            </span>
                          ) : (
                            <span className="flex items-center gap-1 text-[11px]">
                              <Archive className="w-3 h-3" /> Archive
                            </span>
                          )}
                        </button>

                        {/* Permanent Delete Button */}
                        <button
                          onClick={() => handleDeleteTenant(comp)}
                          disabled={actionId === comp.id || isCurrentActive}
                          title="Permanently delete company"
                          className="p-1.5 rounded-lg text-xs text-rose-400 hover:text-rose-300 bg-rose-500/10 border border-rose-500/20 hover:bg-rose-500/20 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>

                      <div className="flex items-center gap-2">
                        <Link
                          href="/settings/company-profile"
                          className="text-xs text-slate-400 hover:text-white flex items-center gap-1.5 transition-colors px-2"
                        >
                          <FileText className="w-3.5 h-3.5" />
                          Profile
                        </Link>

                        <button
                          onClick={() => handleSwitchTenant(comp)}
                          disabled={switchingId === comp.id || isCurrentActive}
                          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                            isCurrentActive
                              ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                              : 'bg-sky-600 hover:bg-sky-500 text-white shadow-md shadow-sky-950/40'
                          }`}
                        >
                          {switchingId === comp.id ? (
                            <>
                              <Loader2 className="w-3.5 h-3.5 animate-spin" />
                              Switching...
                            </>
                          ) : isCurrentActive ? (
                            'Currently Open'
                          ) : (
                            <>
                              Switch to Entity
                              <ArrowRight className="w-3.5 h-3.5" />
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </main>
      </div>

      {/* CREATE NEW COMPANY MODAL */}
      {createModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg shadow-2xl p-6 space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-sky-500/10 text-sky-400">
                  <Building2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Add New Corporate Entity</h3>
                  <p className="text-[11px] text-slate-400">Provisions isolated multi-tenant ledger and seeds Chart of Accounts</p>
                </div>
              </div>
              <button
                onClick={() => setCreateModalOpen(false)}
                className="text-slate-400 hover:text-white p-1"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateSubmit} className="space-y-4 text-xs">
              <div className="space-y-1">
                <label className="text-slate-300 font-semibold">Legal Company Name *</label>
                <input
                  id="new-company-legal-name"
                  data-testid="new-company-legal-name"
                  type="text"
                  required
                  placeholder="e.g. ARYIX TECHNOLOGIES PRIVATE LIMITED"
                  value={newCompany.legal_name}
                  onChange={(e) => setNewCompany({ ...newCompany, legal_name: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 focus:outline-none focus:border-sky-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-slate-300 font-semibold">Entity Type *</label>
                  <select
                    id="new-company-entity-type"
                    value={newCompany.entity_type}
                    onChange={(e) => setNewCompany({ ...newCompany, entity_type: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-sky-500"
                  >
                    <option value="Private Limited Company">Private Limited Company</option>
                    <option value="One Person Company (OPC)">One Person Company (OPC)</option>
                    <option value="Limited Liability Partnership (LLP)">Limited Liability Partnership (LLP)</option>
                    <option value="Public Limited Company">Public Limited Company</option>
                    <option value="Proprietorship">Proprietorship</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-slate-300 font-semibold">Company PAN (10-char) *</label>
                  <input
                    id="new-company-pan"
                    data-testid="new-company-pan"
                    type="text"
                    required
                    maxLength={10}
                    placeholder="e.g. AABCA5297J"
                    value={newCompany.pan}
                    onChange={(e) => setNewCompany({ ...newCompany, pan: e.target.value.toUpperCase() })}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 uppercase font-mono focus:outline-none focus:border-sky-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-slate-300 font-semibold">CIN / LLPIN (Optional)</label>
                  <input
                    id="new-company-cin"
                    data-testid="new-company-cin"
                    type="text"
                    maxLength={21}
                    placeholder="e.g. U70200KA2025OPC206792"
                    value={newCompany.cin}
                    onChange={(e) => setNewCompany({ ...newCompany, cin: e.target.value.toUpperCase() })}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 uppercase font-mono focus:outline-none focus:border-sky-500"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-slate-300 font-semibold">GSTIN (Optional)</label>
                  <input
                    type="text"
                    maxLength={15}
                    placeholder="e.g. 29ABDCA5297J1Z5"
                    value={newCompany.gstin}
                    onChange={(e) => setNewCompany({ ...newCompany, gstin: e.target.value.toUpperCase() })}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 uppercase font-mono focus:outline-none focus:border-sky-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className="text-slate-300 font-semibold">State Code (GST State)</label>
                  <input
                    type="text"
                    maxLength={2}
                    placeholder="29"
                    value={newCompany.state_code}
                    onChange={(e) => setNewCompany({ ...newCompany, state_code: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white font-mono focus:outline-none focus:border-sky-500"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-slate-300 font-semibold">Director DIN (8-digit)</label>
                  <input
                    type="text"
                    maxLength={8}
                    placeholder="11249061"
                    value={newCompany.admin_din}
                    onChange={(e) => setNewCompany({ ...newCompany, admin_din: e.target.value })}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white font-mono focus:outline-none focus:border-sky-500"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-slate-300 font-semibold">Registered Office Address</label>
                <textarea
                  rows={2}
                  placeholder="Full registered office address as per MCA..."
                  value={newCompany.registered_office}
                  onChange={(e) => setNewCompany({ ...newCompany, registered_office: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-white placeholder-slate-600 focus:outline-none focus:border-sky-500"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setCreateModalOpen(false)}
                  className="px-4 py-2 rounded-xl bg-slate-800 text-slate-300 hover:text-white font-semibold transition-all"
                >
                  Cancel
                </button>
                <button
                  id="provision-company-submit-btn"
                  data-testid="provision-company-submit-btn"
                  type="submit"
                  disabled={submitting}
                  className="flex items-center gap-2 px-5 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-semibold shadow-lg shadow-sky-950/40 transition-all disabled:opacity-50"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Provisioning...
                    </>
                  ) : (
                    'Provision Organization'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
