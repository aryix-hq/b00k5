'use client';

import React, { useEffect, useState } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import {
  Users,
  UserPlus,
  ShieldCheck,
  Shield,
  KeyRound,
  FileCheck2,
  Trash2,
  Edit2,
  Lock,
  Mail,
  Building2,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Hash,
  UploadCloud
} from 'lucide-react';
import { fetchApi } from '@/lib/api';

interface IAMUser {
  membership_id: string;
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: 'owner' | 'auditor_ca' | 'finance_manager' | 'employee';
  din?: string;
  is_primary: boolean;
  created_at: string;
}

export default function IAMPage() {
  const [users, setUsers] = useState<IAMUser[]>([]);
  const [rolesMatrix, setRolesMatrix] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Active Tenant & Multi-Tenant Scoping State
  const [activeTenantName, setActiveTenantName] = useState<string>('');
  const [activeCin, setActiveCin] = useState<string>('');
  const [activeTenantId, setActiveTenantId] = useState<string>('');
  const [isSuperAdmin, setIsSuperAdmin] = useState<boolean>(false);
  const [availableTenants, setAvailableTenants] = useState<any[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState<string>('');

  // Invite Modal
  const [inviteModalOpen, setInviteModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  const [newUser, setNewUser] = useState({
    email: '',
    first_name: '',
    last_name: '',
    role: 'finance_manager',
    password: '',
    din: ''
  });
  const [uploadingDinDoc, setUploadingDinDoc] = useState(false);

  const handleUploadDinDoc = async (file: File) => {
    setUploadingDinDoc(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('doc_type', 'din_approval');
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/setup/verify-document`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd
      });
      if (res.ok) {
        const data = await res.json();
        const ext = data.extracted_entity || {};
        if (ext.din) {
          setNewUser(prev => ({ ...prev, din: ext.din }));
        } else {
          alert('No 8-digit DIN found in uploaded document.');
        }
      } else {
        alert('Could not verify DIN approval letter.');
      }
    } catch (e: any) {
      alert(e.message || 'Upload error');
    } finally {
      setUploadingDinDoc(false);
    }
  };

  async function loadUsers() {
    try {
      if (typeof window !== 'undefined') {
        const tName = localStorage.getItem('b00k5_legal_name') || 'Current Organization';
        const tCin = localStorage.getItem('b00k5_cin') || '';
        const tId = localStorage.getItem('b00k5_active_tenant_id') || localStorage.getItem('b00k5_tenant_id') || '';
        const isSuper = localStorage.getItem('b00k5_is_super_admin') === 'true';

        setActiveTenantName(tName);
        setActiveCin(tCin);
        setActiveTenantId(tId);
        setIsSuperAdmin(isSuper);
        if (!selectedTenantId && tId) setSelectedTenantId(tId);

        if (isSuper) {
          try {
            const tList = await fetchApi('/api/v1/tenants/admin/list-tenants');
            if (Array.isArray(tList)) setAvailableTenants(tList);
          } catch (_) {}
        }
      }

      const data = await fetchApi('/api/v1/iam/users');
      if (Array.isArray(data)) setUsers(data);

      const matrix = await fetchApi('/api/v1/iam/roles-matrix');
      if (Array.isArray(matrix)) setRolesMatrix(matrix);
    } catch (e) {
      console.error('Failed to load IAM data:', e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUsers();
  }, []);

  const handleInviteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMsg('');
    setSuccessMsg('');

    try {
      const payload: any = { ...newUser };
      if (payload.role !== 'owner') {
        delete payload.din;
      }
      if (selectedTenantId) {
        payload.tenant_id = selectedTenantId;
      }
      await fetchApi('/api/v1/iam/users', {
        method: 'POST',
        body: JSON.stringify(payload)
      });

      setSuccessMsg(`User ${newUser.email} successfully scoped to ${activeTenantName} with role ${newUser.role}!`);
      setInviteModalOpen(false);
      setNewUser({
        email: '',
        first_name: '',
        last_name: '',
        role: 'finance_manager',
        password: '',
        din: ''
      });
      loadUsers();
    } catch (e: any) {
      setErrorMsg(e.message || 'Error creating user');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRevoke = async (membershipId: string) => {
    if (!confirm('Are you sure you want to revoke this user access from your organization?')) return;

    try {
      await fetchApi(`/api/v1/iam/users/${membershipId}`, {
        method: 'DELETE'
      });
      loadUsers();
    } catch (e: any) {
      alert(e.message || 'Error revoking access');
    }
  };

  const getRoleBadge = (role: string) => {
    switch (role) {
      case 'owner':
        return (
          <span className="px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium text-xs flex items-center gap-1.5 w-fit">
            <ShieldCheck className="w-3.5 h-3.5 text-amber-400" /> Director (Owner)
          </span>
        );
      case 'auditor_ca':
        return (
          <span className="px-2.5 py-1 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20 font-medium text-xs flex items-center gap-1.5 w-fit">
            <FileCheck2 className="w-3.5 h-3.5 text-sky-400" /> Statutory Auditor (CA)
          </span>
        );
      case 'finance_manager':
        return (
          <span className="px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium text-xs flex items-center gap-1.5 w-fit">
            <Shield className="w-3.5 h-3.5 text-emerald-400" /> Finance Manager / CFO
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700 text-xs w-fit">
            Staff / Employee
          </span>
        );
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Navbar />

        <main className="p-4 sm:p-6 md:p-8 space-y-6 md:space-y-8 max-w-7xl mx-auto w-full">
          {/* Header */}
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-6">
            <div className="min-w-0 flex-1">
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                <Users className="w-6 h-6 text-sky-400 shrink-0" />
                <span>Identity &amp; Access Management (IAM)</span>
              </h2>
              <p className="text-xs text-slate-400 mt-1 max-w-2xl">
                Statutory role-based access control for Directors (DIN / DSC signing), Statutory Auditors (CA read-only file), and Finance Managers.
              </p>
            </div>

            <button
              id="add-member-modal-btn"
              data-testid="add-member-modal-btn"
              onClick={() => setInviteModalOpen(true)}
              className="px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold rounded-lg flex items-center gap-2 shadow-sm transition-all shrink-0"
            >
              <UserPlus className="w-4 h-4" /> Add Team Member / Auditor
            </button>
          </div>

          {successMsg && (
            <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-xs text-emerald-400 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Members Table */}
          <div className="overflow-x-auto border border-slate-800 rounded-xl bg-slate-900">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/70 border-b border-slate-800 text-slate-400 uppercase font-mono">
                <tr>
                  <th className="p-4">Member Name</th>
                  <th className="p-4">Email</th>
                  <th className="p-4">Designated Role</th>
                  <th className="p-4">Director DIN</th>
                  <th className="p-4">Added On</th>
                  <th className="p-4 text-center">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {users.map((u) => (
                  <tr key={u.membership_id} className="hover:bg-slate-800/40">
                    <td className="p-4 font-sans font-semibold text-white">
                      {u.first_name} {u.last_name}
                      {u.is_primary && (
                        <span className="ml-2 text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          Founder
                        </span>
                      )}
                    </td>
                    <td className="p-4 text-slate-300 font-sans">{u.email}</td>
                    <td className="p-4">{getRoleBadge(u.role)}</td>
                    <td className="p-4 text-slate-400">
                      {u.din ? (
                        <span className="text-white font-mono bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
                          DIN: {u.din}
                        </span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                    <td className="p-4 text-slate-400 font-sans">{u.created_at.split('T')[0]}</td>
                    <td className="p-4 text-center">
                      {!u.is_primary && (
                        <button
                          onClick={() => handleRevoke(u.membership_id)}
                          className="p-1.5 hover:bg-rose-500/10 text-slate-400 hover:text-rose-400 rounded transition-all"
                          title="Revoke Access"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Statutory Authorization Matrix */}
          <div className="p-6 bg-slate-900 border border-slate-800 rounded-xl space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Shield className="w-4 h-4 text-sky-400" />
                Statutory Permissions & Governance Rights Matrix
              </h3>
              <span className="text-[10px] text-slate-400 font-mono">
                Companies Act, 2013 &amp; IT Act, 2000
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 text-xs">
              <div className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2">
                <div className="flex items-center gap-2 font-semibold text-amber-400">
                  <ShieldCheck className="w-4 h-4" /> Director / Sovereign Founder
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Full administrative authority. Authorized to sign Board Meeting Minutes (SS-1) and MCA statutory filings using hardware DSC tokens under Section 173.
                </p>
                <div className="pt-2 border-t border-slate-800 text-[10px] font-mono text-emerald-400">
                  ✓ DSC Signer • Full Ledger Control
                </div>
              </div>

              <div className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2">
                <div className="flex items-center gap-2 font-semibold text-sky-400">
                  <FileCheck2 className="w-4 h-4" /> Statutory Auditor (CA)
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Strictly read-only isolation. Accesses Schedule III Trial Balance, Bank Reconciliations, and 1-Click download of Permanent Audit File &amp; Current Year audit evidence.
                </p>
                <div className="pt-2 border-t border-slate-800 text-[10px] font-mono text-sky-400">
                  ✓ 1-Click Auditor Pack • Zero-Edit Isolation
                </div>
              </div>

              <div className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2">
                <div className="flex items-center gap-2 font-semibold text-emerald-400">
                  <Building2 className="w-4 h-4" /> Finance Manager / CFO
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Executes 3-Tier Bank Reconciliation, allocates Suspense Account (Code 2099), issues GST tax invoices, and logs vendor bills with ITC validation.
                </p>
                <div className="pt-2 border-t border-slate-800 text-[10px] font-mono text-emerald-400">
                  ✓ Reconciliation • Invoicing • ITC
                </div>
              </div>

              <div className="p-4 bg-slate-950/70 border border-slate-800 rounded-xl space-y-2">
                <div className="flex items-center gap-2 font-semibold text-slate-300">
                  <Users className="w-4 h-4" /> Staff / Employees
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Deposits expense receipts and scans corporate bills with SmartScan OCR. No access to general ledger or sensitive corporate governance records.
                </p>
                <div className="pt-2 border-t border-slate-800 text-[10px] font-mono text-slate-400">
                  ✓ Receipts Only • Sandboxed Scope
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>

      {/* INVITE USER MODAL */}
      {inviteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <form
            onSubmit={handleInviteSubmit}
            className="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-4 shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <UserPlus className="w-4 h-4 text-sky-400" />
                Add Organization Member / Auditor
              </h3>
              <button
                type="button"
                onClick={() => setInviteModalOpen(false)}
                className="text-slate-400 hover:text-white text-xs"
              >
                ✕
              </button>
            </div>

            {/* Target Organization Scope Badge */}
            <div className="p-3.5 bg-slate-950/80 border border-sky-500/30 rounded-xl space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono uppercase tracking-wider text-sky-400 font-semibold flex items-center gap-1.5">
                  <Building2 className="w-3.5 h-3.5" /> Target Organization Scope
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/30 flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3 text-sky-400" /> Scoped Workspace
                </span>
              </div>

              {isSuperAdmin && availableTenants.length > 0 ? (
                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Select Target Entity (Super Admin)</label>
                  <select
                    value={selectedTenantId}
                    onChange={(e) => {
                      setSelectedTenantId(e.target.value);
                      const t = availableTenants.find((item: any) => item.id === e.target.value);
                      if (t) {
                        setActiveTenantName(t.legal_name);
                        setActiveCin(t.cin || '');
                      }
                    }}
                    className="w-full px-2.5 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-white text-xs font-medium focus:outline-none focus:border-sky-500"
                  >
                    {availableTenants.map((t: any) => (
                      <option key={t.id} value={t.id}>
                        {t.legal_name} {t.cin ? `(${t.cin})` : ''}
                      </option>
                    ))}
                  </select>
                </div>
              ) : (
                <div>
                  <div className="font-bold text-white text-xs flex items-center gap-1.5">
                    <span>{activeTenantName || 'Current Organization'}</span>
                  </div>
                  <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                    {activeCin ? `CIN: ${activeCin}` : 'Sovereign Corporate Workspace'} • ID: {activeTenantId ? activeTenantId.slice(0, 8) + '...' : 'Active'}
                  </div>
                </div>
              )}
            </div>

            {errorMsg && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg text-xs text-rose-400">
                {errorMsg}
              </div>
            )}

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="space-y-1">
                <label className="text-slate-300 font-medium">First Name</label>
                <input
                  id="invite-member-first-name"
                  data-testid="invite-member-first-name"
                  type="text"
                  required
                  value={newUser.first_name}
                  onChange={(e) => setNewUser({ ...newUser, first_name: e.target.value })}
                  placeholder="e.g. Ramesh"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                />
              </div>

              <div className="space-y-1">
                <label className="text-slate-300 font-medium">Last Name</label>
                <input
                  id="invite-member-last-name"
                  data-testid="invite-member-last-name"
                  type="text"
                  required
                  value={newUser.last_name}
                  onChange={(e) => setNewUser({ ...newUser, last_name: e.target.value })}
                  placeholder="e.g. Kumar"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                />
              </div>

              <div className="col-span-2 space-y-1">
                <label className="text-slate-300 font-medium">Email Address</label>
                <input
                  id="invite-member-email"
                  data-testid="invite-member-email"
                  type="email"
                  required
                  value={newUser.email}
                  onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                  placeholder="auditor@ca-firm.com"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                />
              </div>

              <div className="col-span-2 space-y-1">
                <label className="text-slate-300 font-medium">Designated Role</label>
                <select
                  id="invite-member-role"
                  data-testid="invite-member-role"
                  value={newUser.role}
                  onChange={(e) => setNewUser({ ...newUser, role: e.target.value as any })}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                >
                  <option value="owner">Director / Sovereign Founder (Full Admin + DSC)</option>
                  <option value="auditor_ca">Statutory Auditor (CA - Read-Only Audit File)</option>
                  <option value="finance_manager">Finance Manager / CFO (Bookkeeping &amp; Reconcile)</option>
                  <option value="employee">Staff / Employee (Receipts Only)</option>
                </select>
              </div>

              {newUser.role === 'owner' && (
                <div className="col-span-2 space-y-1">
                  <label className="text-slate-300 font-medium flex items-center justify-between">
                    <span>Director Identification Number (DIN)</span>
                    <span className={`text-[10px] font-mono ${newUser.din ? 'text-emerald-400 font-semibold' : 'text-slate-400'}`}>
                      {newUser.din ? '✓ Verified via DIR-3' : '🔒 Upload DIR-3 to verify'}
                    </span>
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={newUser.din}
                      readOnly
                      placeholder="Upload DIN Approval Letter"
                      className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white font-mono cursor-not-allowed opacity-90"
                    />
                    <label className="cursor-pointer px-3 py-2 bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 shrink-0 transition">
                      <UploadCloud className="w-3.5 h-3.5" />
                      <span>{uploadingDinDoc ? 'Extracting...' : 'Upload DIR-3'}</span>
                      <input
                        type="file"
                        accept=".pdf,.png,.jpg,.jpeg"
                        className="hidden"
                        onChange={(e) => e.target.files?.[0] && handleUploadDinDoc(e.target.files[0])}
                        disabled={uploadingDinDoc}
                      />
                    </label>
                  </div>
                </div>
              )}

              <div className="col-span-2 space-y-1">
                <label className="text-slate-300 font-medium">Temporary Password</label>
                <input
                  id="invite-member-password"
                  data-testid="invite-member-password"
                  type="password"
                  required
                  value={newUser.password}
                  onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                  placeholder="Minimum 8 characters"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setInviteModalOpen(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg"
              >
                Cancel
              </button>
              <button
                id="invite-member-submit-btn"
                data-testid="invite-member-submit-btn"
                type="submit"
                disabled={submitting}
                className="px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold rounded-lg"
              >
                {submitting ? 'Creating Member...' : 'Grant Access'}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
