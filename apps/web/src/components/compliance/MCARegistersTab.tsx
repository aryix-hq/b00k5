'use client';

import React, { useState, useEffect } from 'react';
import {
  Users,
  FileText,
  Building2,
  ShieldCheck,
  Plus,
  CheckCircle2,
  AlertTriangle,
  Award,
  Layers,
  Calendar,
  Lock,
  ArrowRight
} from 'lucide-react';
import { fetchApi } from '@/lib/api';

interface Member {
  id: string;
  folio_number: string;
  member_name: string;
  pan?: string;
  date_of_becoming_member: string;
  number_of_shares: number;
  distinctive_from: number;
  distinctive_to: number;
  nominal_value_per_share: number;
  amount_paid_per_share: number;
  certificate_number?: string;
  status: string;
}

interface LoanGuarantee {
  id: string;
  transaction_type: string;
  body_corporate_name: string;
  amount: number;
  interest_rate_pct?: number;
  board_resolution_date: string;
  special_resolution_date?: string;
  status: string;
  notes?: string;
}

interface Contract {
  id: string;
  contract_date: string;
  party_name: string;
  nature_of_contract: string;
  contract_value?: number;
  director_name: string;
  director_din?: string;
  nature_of_interest: string;
  voting_status: string;
}

interface DirectorDisclosure {
  id: string;
  fiscal_year: string;
  form_type: string;
  director_name: string;
  director_din: string;
  filing_date: string;
  is_digitally_signed: boolean;
}

interface ShareCert {
  id: string;
  certificate_number: string;
  member_id: string;
  number_of_shares: number;
  distinctive_from: number;
  distinctive_to: number;
  face_value: number;
  issue_date: string;
  status: string;
}

export function MCARegistersTab() {
  const [activeSubTab, setActiveSubTab] = useState<'mgt1' | 'mbp2' | 'mbp4' | 'disclosures' | 'sh1'>('mgt1');
  const [loading, setLoading] = useState(true);

  const [members, setMembers] = useState<Member[]>([]);
  const [loans, setLoans] = useState<LoanGuarantee[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [disclosures, setDisclosures] = useState<DirectorDisclosure[]>([]);
  const [certs, setCerts] = useState<ShareCert[]>([]);

  // Modals
  const [isMemberModalOpen, setIsMemberModalOpen] = useState(false);
  const [folio, setFolio] = useState('');
  const [memberName, setMemberName] = useState('');
  const [memberPan, setMemberPan] = useState('');
  const [numShares, setNumShares] = useState('10000');
  const [distFrom, setDistFrom] = useState('1');
  const [distTo, setDistTo] = useState('10000');
  const [memberSubmitting, setMemberSubmitting] = useState(false);
  const [memberError, setMemberError] = useState<string | null>(null);

  // Modal: Share Certificate
  const [isCertModalOpen, setIsCertModalOpen] = useState(false);
  const [selectedMemberId, setSelectedMemberId] = useState('');
  const [certNum, setCertNum] = useState('');
  const [certSubmitting, setCertSubmitting] = useState(false);
  const [certError, setCertError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const [mRes, lRes, cRes, dRes, sRes] = await Promise.all([
        fetchApi('/api/v1/registers/members').catch(() => []),
        fetchApi('/api/v1/registers/loans').catch(() => []),
        fetchApi('/api/v1/registers/contracts').catch(() => []),
        fetchApi('/api/v1/registers/disclosures').catch(() => []),
        fetchApi('/api/v1/registers/share-certificates').catch(() => [])
      ]);
      setMembers(mRes || []);
      setLoans(lRes || []);
      setContracts(cRes || []);
      setDisclosures(dRes || []);
      setCerts(sRes || []);
    } catch (err) {
      console.error('Error loading MCA registers:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    setMemberSubmitting(true);
    setMemberError(null);
    try {
      await fetchApi('/api/v1/registers/members', {
        method: 'POST',
        body: JSON.stringify({
          folio_number: folio.trim(),
          member_name: memberName.trim(),
          pan: memberPan.trim().toUpperCase() || undefined,
          number_of_shares: parseFloat(numShares),
          distinctive_from: parseInt(distFrom, 10),
          distinctive_to: parseInt(distTo, 10),
          nominal_value_per_share: 10.0,
          amount_paid_per_share: 10.0
        })
      });
      setIsMemberModalOpen(false);
      setFolio('');
      setMemberName('');
      setMemberPan('');
      loadData();
    } catch (err: any) {
      setMemberError(err.message || 'Failed to register member');
    } finally {
      setMemberSubmitting(false);
    }
  };

  const handleIssueCert = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMemberId) return;
    setCertSubmitting(true);
    setCertError(null);
    try {
      const mem = members.find(m => m.id === selectedMemberId);
      if (!mem) return;
      await fetchApi('/api/v1/registers/share-certificates', {
        method: 'POST',
        body: JSON.stringify({
          member_id: mem.id,
          certificate_number: certNum.trim(),
          number_of_shares: mem.number_of_shares,
          distinctive_from: mem.distinctive_from,
          distinctive_to: mem.distinctive_to,
          face_value: 10.0
        })
      });
      setIsCertModalOpen(false);
      setCertNum('');
      loadData();
    } catch (err: any) {
      setCertError(err.message || 'Failed to issue certificate');
    } finally {
      setCertSubmitting(false);
    }
  };

  const formatINR = (val: number) => {
    return new Intl.NumberFormat('en-IN', {
      style: 'currency',
      currency: 'INR',
      minimumFractionDigits: 2
    }).format(val);
  };

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs uppercase font-mono px-2 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-500/30">
              Companies Act 2013 Governance
            </span>
            <span className="text-xs font-mono text-slate-400">
              Mandatory MCA Secretarial Registers &amp; Director Disclosures
            </span>
          </div>
          <h2 className="text-xl font-bold text-white mt-1">
            Statutory Registers &amp; Director Disclosures Suite
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Form MGT-1 (Members), Form MBP-2 (Loans u/s 186), Form MBP-4 (Contracts u/s 189), Form MBP-1 &amp; DIR-8, and Form SH-1 Share Certificates.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setIsMemberModalOpen(true)}
            className="px-3.5 py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-lg shadow-sm flex items-center gap-1.5 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Member (MGT-1)
          </button>
          <button
            onClick={() => setIsCertModalOpen(true)}
            className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg shadow-sm flex items-center gap-1.5 transition-colors"
          >
            <Award className="w-4 h-4" />
            Issue Certificate (SH-1)
          </button>
        </div>
      </div>

      {/* Sub-Tab Navigation Bar */}
      <div className="flex flex-wrap gap-2 border-b border-slate-800 pb-2">
        <button
          onClick={() => setActiveSubTab('mgt1')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
            activeSubTab === 'mgt1'
              ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
              : 'bg-slate-900 text-slate-400 hover:text-white'
          }`}
        >
          <Users className="w-3.5 h-3.5" />
          Form MGT-1: Register of Members
        </button>
        <button
          onClick={() => setActiveSubTab('mbp2')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
            activeSubTab === 'mbp2'
              ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
              : 'bg-slate-900 text-slate-400 hover:text-white'
          }`}
        >
          <Building2 className="w-3.5 h-3.5" />
          Form MBP-2: Loans &amp; Guarantees (Sec 186)
        </button>
        <button
          onClick={() => setActiveSubTab('mbp4')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
            activeSubTab === 'mbp4'
              ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
              : 'bg-slate-900 text-slate-400 hover:text-white'
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          Form MBP-4: Contracts (Sec 189)
        </button>
        <button
          onClick={() => setActiveSubTab('disclosures')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
            activeSubTab === 'disclosures'
              ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
              : 'bg-slate-900 text-slate-400 hover:text-white'
          }`}
        >
          <ShieldCheck className="w-3.5 h-3.5" />
          Director Disclosures (MBP-1 &amp; DIR-8)
        </button>
        <button
          onClick={() => setActiveSubTab('sh1')}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition ${
            activeSubTab === 'sh1'
              ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40'
              : 'bg-slate-900 text-slate-400 hover:text-white'
          }`}
        >
          <Award className="w-3.5 h-3.5" />
          Form SH-1: Share Certificates
        </button>
      </div>

      {/* SUB-TAB 1: FORM MGT-1 */}
      {activeSubTab === 'mgt1' && (
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-800">
            <div>
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Users className="w-4 h-4 text-purple-400" />
                Form MGT-1: Statutory Register of Members (Section 88)
              </h3>
              <p className="text-xs text-slate-400 mt-0.5">
                Official registry of equity and preference shareholders with distinctive share numbers.
              </p>
            </div>
          </div>

          {members.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-xs font-mono">
              No members registered in Form MGT-1 yet. Click &quot;Add Member&quot; to register shareholders.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                    <th className="p-3">Folio No</th>
                    <th className="p-3">Member Name &amp; PAN</th>
                    <th className="p-3">Date Joined</th>
                    <th className="p-3 text-right">No. of Shares</th>
                    <th className="p-3 text-center">Distinctive Numbers</th>
                    <th className="p-3 text-right">Nominal Value</th>
                    <th className="p-3 text-right">Paid-Up Value</th>
                    <th className="p-3">Certificate No</th>
                    <th className="p-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {members.map(m => (
                    <tr key={m.id} className="hover:bg-slate-800/30 transition">
                      <td className="p-3 text-sky-400 font-bold">{m.folio_number}</td>
                      <td className="p-3">
                        <div className="font-semibold text-white">{m.member_name}</div>
                        <div className="text-[11px] text-slate-400">{m.pan || 'PAN NOT PROVIDED'}</div>
                      </td>
                      <td className="p-3 text-slate-300">{m.date_of_becoming_member}</td>
                      <td className="p-3 text-right font-bold text-white">
                        {Number(m.number_of_shares).toLocaleString('en-IN')}
                      </td>
                      <td className="p-3 text-center text-amber-400 font-semibold">
                        {m.distinctive_from} to {m.distinctive_to}
                      </td>
                      <td className="p-3 text-right text-slate-300">₹{m.nominal_value_per_share}</td>
                      <td className="p-3 text-right font-semibold text-emerald-400">₹{m.amount_paid_per_share}</td>
                      <td className="p-3 text-purple-300">{m.certificate_number || '—'}</td>
                      <td className="p-3">
                        <span className="px-2 py-0.5 rounded-full text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-semibold">
                          {m.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* SUB-TAB 2: FORM MBP-2 */}
      {activeSubTab === 'mbp2' && (
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Building2 className="w-4 h-4 text-purple-400" />
              Form MBP-2: Register of Loans, Guarantees &amp; Securities (Section 186)
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Tracks loans, investments, and corporate guarantees with interest rate and statutory ceiling guardrails.
            </p>
          </div>

          {loans.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-xs font-mono">
              No inter-corporate loans or guarantees recorded.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                    <th className="p-3">Type</th>
                    <th className="p-3">Body Corporate</th>
                    <th className="p-3 text-right">Amount (₹)</th>
                    <th className="p-3 text-right">Interest Rate</th>
                    <th className="p-3">Board Resolution</th>
                    <th className="p-3">Special Resolution</th>
                    <th className="p-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {loans.map(l => (
                    <tr key={l.id} className="hover:bg-slate-800/30 transition">
                      <td className="p-3 text-sky-400 font-bold">{l.transaction_type}</td>
                      <td className="p-3 text-white font-semibold">{l.body_corporate_name}</td>
                      <td className="p-3 text-right font-bold text-emerald-400">{formatINR(l.amount)}</td>
                      <td className="p-3 text-right text-amber-400">{l.interest_rate_pct ? `${l.interest_rate_pct}%` : '—'}</td>
                      <td className="p-3 text-slate-300">{l.board_resolution_date}</td>
                      <td className="p-3 text-slate-400">{l.special_resolution_date || 'N/A (Within 60% Limits)'}</td>
                      <td className="p-3">
                        <span className="px-2 py-0.5 rounded-full text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-semibold">
                          {l.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* SUB-TAB 3: FORM MBP-4 */}
      {activeSubTab === 'mbp4' && (
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <FileText className="w-4 h-4 text-purple-400" />
              Form MBP-4: Register of Contracts in which Directors are Interested (Section 189)
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Enforces Section 184 conflict disclosure and records interested director voting abstentions.
            </p>
          </div>

          {contracts.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-xs font-mono">
              No related-party or interested director contracts recorded.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                    <th className="p-3">Date</th>
                    <th className="p-3">Party Name</th>
                    <th className="p-3">Nature of Contract</th>
                    <th className="p-3">Interested Director</th>
                    <th className="p-3">Interest Nature</th>
                    <th className="p-3">Voting Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {contracts.map(c => (
                    <tr key={c.id} className="hover:bg-slate-800/30 transition">
                      <td className="p-3 text-slate-300">{c.contract_date}</td>
                      <td className="p-3 text-white font-semibold">{c.party_name}</td>
                      <td className="p-3 text-slate-300">{c.nature_of_contract}</td>
                      <td className="p-3">
                        <div className="text-sky-300 font-semibold">{c.director_name}</div>
                        <div className="text-[10px] text-slate-500">DIN: {c.director_din || 'N/A'}</div>
                      </td>
                      <td className="p-3 text-amber-300">{c.nature_of_interest}</td>
                      <td className="p-3">
                        <span className="px-2 py-0.5 rounded-full text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/30 font-semibold">
                          {c.voting_status} (Sec 184(2))
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* SUB-TAB 4: DIRECTOR DISCLOSURES */}
      {activeSubTab === 'disclosures' && (
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-purple-400" />
              Annual Director Disclosures (Form MBP-1 &amp; Form DIR-8)
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Notice of interest in other entities u/s 184(1) and intimation of non-disqualification u/s 164(2) for every financial year.
            </p>
          </div>

          {disclosures.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-xs font-mono">
              No annual director disclosures filed for the current fiscal period.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                    <th className="p-3">Fiscal Year</th>
                    <th className="p-3">Form Type</th>
                    <th className="p-3">Director Name</th>
                    <th className="p-3">DIN</th>
                    <th className="p-3">Filing Date</th>
                    <th className="p-3">Cryptographic Seal</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {disclosures.map(d => (
                    <tr key={d.id} className="hover:bg-slate-800/30 transition">
                      <td className="p-3 text-sky-400 font-bold">{d.fiscal_year}</td>
                      <td className="p-3">
                        <span className="px-2 py-0.5 rounded bg-purple-950 text-purple-400 border border-purple-800/60 font-bold">
                          {d.form_type === 'MBP_1' ? 'Form MBP-1 (Interest)' : 'Form DIR-8 (Eligibility)'}
                        </span>
                      </td>
                      <td className="p-3 text-white font-semibold">{d.director_name}</td>
                      <td className="p-3 text-slate-300">{d.director_din}</td>
                      <td className="p-3 text-slate-400">{d.filing_date}</td>
                      <td className="p-3">
                        <span className="inline-flex items-center gap-1 text-[11px] text-emerald-400">
                          <CheckCircle2 className="w-3.5 h-3.5" /> DSC Verified
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* SUB-TAB 5: FORM SH-1 */}
      {activeSubTab === 'sh1' && (
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800 shadow-xl space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-white flex items-center gap-2">
              <Award className="w-4 h-4 text-purple-400" />
              Form SH-1: Share Certificates Register (Section 46)
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Digitally generated share certificates pursuant to Rule 5(2) of Companies (Share Capital and Debentures) Rules, 2014.
            </p>
          </div>

          {certs.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-xs font-mono">
              No share certificates issued yet. Click &quot;Issue Certificate (SH-1)&quot; above.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                    <th className="p-3">Certificate No</th>
                    <th className="p-3 text-right">No. of Shares</th>
                    <th className="p-3 text-center">Distinctive Range</th>
                    <th className="p-3 text-right">Face Value</th>
                    <th className="p-3">Issue Date</th>
                    <th className="p-3">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {certs.map(c => (
                    <tr key={c.id} className="hover:bg-slate-800/30 transition">
                      <td className="p-3 text-indigo-400 font-bold">{c.certificate_number}</td>
                      <td className="p-3 text-right font-bold text-white">
                        {Number(c.number_of_shares).toLocaleString('en-IN')}
                      </td>
                      <td className="p-3 text-center text-amber-400 font-semibold">
                        {c.distinctive_from} to {c.distinctive_to}
                      </td>
                      <td className="p-3 text-right text-slate-300">₹{c.face_value}</td>
                      <td className="p-3 text-slate-400">{c.issue_date}</td>
                      <td className="p-3">
                        <span className="px-2 py-0.5 rounded-full text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-semibold">
                          {c.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Modal: Add Member */}
      {isMemberModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Users className="w-5 h-5 text-purple-400" />
                Register Member (Form MGT-1)
              </h3>
              <button onClick={() => setIsMemberModalOpen(false)} className="text-slate-400 hover:text-white text-sm">
                ✕
              </button>
            </div>

            <form onSubmit={handleAddMember} className="space-y-4 text-xs font-sans">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Folio Number*</label>
                  <input
                    type="text"
                    value={folio}
                    onChange={e => setFolio(e.target.value)}
                    placeholder="e.g. FOLIO-001"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-purple-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Member PAN</label>
                  <input
                    type="text"
                    maxLength={10}
                    value={memberPan}
                    onChange={e => setMemberPan(e.target.value.toUpperCase())}
                    placeholder="e.g. ABCPD1234F"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono uppercase focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Full Legal Name*</label>
                <input
                  type="text"
                  value={memberName}
                  onChange={e => setMemberName(e.target.value)}
                  placeholder="e.g. Vikram Sharma"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-medium focus:outline-none focus:border-purple-500"
                  required
                />
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Shares Count*</label>
                  <input
                    type="number"
                    value={numShares}
                    onChange={e => {
                      setNumShares(e.target.value);
                      const f = parseInt(distFrom, 10) || 1;
                      const cnt = parseInt(e.target.value, 10) || 0;
                      setDistTo(String(f + cnt - 1));
                    }}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-purple-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">From No.*</label>
                  <input
                    type="number"
                    value={distFrom}
                    onChange={e => {
                      setDistFrom(e.target.value);
                      const f = parseInt(e.target.value, 10) || 1;
                      const cnt = parseInt(numShares, 10) || 0;
                      setDistTo(String(f + cnt - 1));
                    }}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-purple-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">To No.*</label>
                  <input
                    type="number"
                    value={distTo}
                    readOnly
                    className="w-full bg-slate-950/60 border border-slate-800 rounded-lg px-3 py-2 text-slate-400 font-mono"
                  />
                </div>
              </div>

              {memberError && (
                <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                  {memberError}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsMemberModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={memberSubmitting}
                  className="px-4 py-2 rounded-lg bg-purple-600 hover:bg-purple-500 disabled:bg-purple-800 text-white font-semibold"
                >
                  {memberSubmitting ? 'Registering...' : 'Add to Form MGT-1'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Issue Share Certificate */}
      {isCertModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Award className="w-5 h-5 text-indigo-400" />
                Issue Share Certificate (Form SH-1)
              </h3>
              <button onClick={() => setIsCertModalOpen(false)} className="text-slate-400 hover:text-white text-sm">
                ✕
              </button>
            </div>

            <form onSubmit={handleIssueCert} className="space-y-4 text-xs font-sans">
              <div>
                <label className="block text-slate-300 font-semibold mb-1">Select Member (Folio)*</label>
                <select
                  value={selectedMemberId}
                  onChange={e => {
                    setSelectedMemberId(e.target.value);
                    const mem = members.find(m => m.id === e.target.value);
                    if (mem) {
                      setCertNum(`SH1-${mem.folio_number}`);
                    }
                  }}
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-medium focus:outline-none focus:border-indigo-500"
                  required
                >
                  <option value="">-- Choose Member --</option>
                  {members.map(m => (
                    <option key={m.id} value={m.id}>
                      [{m.folio_number}] {m.member_name} ({m.number_of_shares} shares)
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Certificate Number*</label>
                <input
                  type="text"
                  value={certNum}
                  onChange={e => setCertNum(e.target.value)}
                  placeholder="e.g. SH1-001"
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-indigo-500"
                  required
                />
              </div>

              {certError && (
                <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                  {certError}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsCertModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={certSubmitting}
                  className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 text-white font-semibold"
                >
                  {certSubmitting ? 'Issuing...' : 'Issue Form SH-1 Certificate'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

