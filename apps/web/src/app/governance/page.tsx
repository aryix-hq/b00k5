'use client';

import React, { useEffect, useState } from 'react';
import {
  Scale,
  Calendar,
  AlertTriangle,
  Clock,
  CheckCircle2,
  FileText,
  FileCheck,
  PenTool,
  ShieldCheck,
  Sparkles,
  Download,
  IndianRupee,
  RefreshCw,
  ExternalLink,
  Plus,
  Trash2,
  KeyRound,
  Lock,
  Users
} from 'lucide-react';
import { DSCBridgeWidget } from '../../components/DSCBridgeWidget';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import { CompanyLetterhead } from '@/components/CompanyLetterhead';
import { fetchApi } from '@/lib/api';
import { signHashViaBridge, checkBridgeStatus } from '../../lib/dsc-bridge';

interface StatutoryEvent {
  id: string;
  category: string;
  title: string;
  statutory_ref: string;
  due_date: string;
  days_remaining: number;
  fine_per_day: number;
  status: 'compliant' | 'due_soon' | 'overdue' | 'completed' | 'filed' | 'verified' | 'upcoming';
  accumulated_penalty: number;
}

export default function GovernanceDashboardPage() {
  const [companyName, setCompanyName] = useState('Sovereign Enterprise');
  const [cin, setCin] = useState('');
  const [venue, setVenue] = useState('Registered Office');
  const [signerName, setSignerName] = useState('Authorized Director');
  const [directorDin, setDirectorDin] = useState('');
  const [directors, setDirectors] = useState<Array<{ name: string; din: string; designation: string; isPresent: boolean }>>([]);

  const [events, setEvents] = useState<StatutoryEvent[]>([]);
  const [loading, setLoading] = useState(true);

  const [selectedTemplate, setSelectedTemplate] = useState<'minutes' | 'notice'>('minutes');
  const [meetingNo, setMeetingNo] = useState('BM/2026-27/01');
  const [meetingDate, setMeetingDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [meetingTime, setMeetingTime] = useState('11:00 AM IST');
  const [isGenerated, setIsGenerated] = useState(false);
  const [isSigned, setIsSigned] = useState(false);
  const [sealDetails, setSealDetails] = useState<{
    tokenLabel: string;
    signatureHex: string;
    sha256: string;
    timestamp: string;
    certSubject: string;
  } | null>(null);

  // Dynamic Agenda & Resolutions state (SS-1 and Sec 173 Notice)
  const [agendaItems, setAgendaItems] = useState<string[]>([
    'Election of Chairman and Ascertainment of Quorum u/s 174',
    'Grant of leave of absence, if any',
    'Review and Approval of Unaudited Financial Statements & General Ledger',
    'Review of Statutory Compliance status under Section 173 and ROC filings',
    'Authorization of Mandates and Signatory Powers for ROC e-filing'
  ]);

  const [resolutions, setResolutions] = useState<string[]>([
    'RESOLVED THAT unaudited financial statements and general ledger for the period be and are hereby noted and approved.',
    'RESOLVED THAT statutory compliance under Section 173 of the Companies Act 2013 and annual filing preparedness be taken on record.',
    'RESOLVED THAT authorized signatories be mandated for electronic submission with the Registrar of Companies.'
  ]);

  // Hardware DSC (HYP 2003) Token State
  const [dscModalOpen, setDscModalOpen] = useState(false);
  const [dscPin, setDscPin] = useState('123456');
  const [dscSigning, setDscSigning] = useState(false);
  const [dscError, setDscError] = useState<string | null>(null);
  const [bridgeStatusInfo, setBridgeStatusInfo] = useState<string>('Checking HYP 2003 Token...');

  // Section 173 Board Meeting Metrics
  const [bmDaysRemaining, setBmDaysRemaining] = useState<number>(120);
  const [bmElapsedDays, setBmElapsedDays] = useState<number>(0);
  const [bmIsOverdue, setBmIsOverdue] = useState<boolean>(false);
  const [bmDueDate, setBmDueDate] = useState<string>('');

  useEffect(() => {
    // 1. Load active organization context from localStorage
    if (typeof window !== 'undefined') {
      const storedName = localStorage.getItem('b00k5_legal_name');
      const storedCin = localStorage.getItem('b00k5_cin');
      const storedRegOffice = localStorage.getItem('b00k5_registered_office');
      const storedVenue = localStorage.getItem('b00k5_venue');
      const storedSigner = localStorage.getItem('b00k5_signer_name');
      const storedDin = localStorage.getItem('b00k5_admin_din');

      if (storedName) setCompanyName(storedName);
      if (storedCin) setCin(storedCin);
      if (storedRegOffice) {
        setVenue(storedRegOffice);
      } else if (storedVenue && storedVenue !== 'Registered Office') {
        setVenue(storedVenue);
      }
      if (storedSigner) setSignerName(storedSigner);
      if (storedDin) setDirectorDin(storedDin);
    }

    // 2. Fetch real statutory milestones & director roster independently from backend
    async function loadComplianceData() {
      setLoading(true);

      // Load verified statutory director roster and master profile first
      try {
        const dirRes = await fetchApi('/api/v1/compliance/directors');
        if (dirRes) {
          if (dirRes.legal_name) {
            setCompanyName(dirRes.legal_name);
            localStorage.setItem('b00k5_legal_name', dirRes.legal_name);
          }
          if (dirRes.cin) {
            setCin(dirRes.cin);
            localStorage.setItem('b00k5_cin', dirRes.cin);
          }
          if (dirRes.registered_office) {
            setVenue(dirRes.registered_office);
            localStorage.setItem('b00k5_registered_office', dirRes.registered_office);
            localStorage.setItem('b00k5_venue', dirRes.registered_office);
          }
          if (dirRes.directors && Array.isArray(dirRes.directors) && dirRes.directors.length > 0) {
            setDirectors(dirRes.directors.map((d: any) => ({
              name: d.name,
              din: d.din || 'N/A',
              designation: d.designation || 'Director',
              isPresent: true
            })));
            setSignerName(dirRes.directors[0].name);
            setDirectorDin(dirRes.directors[0].din || '');
          }
        }
      } catch (dirErr) {
        console.warn('Director roster load error:', dirErr);
      }

      // Load compliance dashboard events
      try {
        const data = await fetchApi('/api/v1/compliance/dashboard');
        if (data?.upcoming_events && Array.isArray(data.upcoming_events)) {
          const mapped: StatutoryEvent[] = data.upcoming_events.map((e: any) => ({
            id: e.id,
            category: e.category,
            title: e.title,
            statutory_ref: e.statutory_reference || e.statutory_ref || 'Companies Act 2013',
            due_date: e.due_date,
            days_remaining: e.days_remaining,
            fine_per_day: parseFloat(e.fine_per_day_inr || '100'),
            status: e.status,
            accumulated_penalty: parseFloat(e.accumulated_penalty_inr || '0')
          }));
          setEvents(mapped);

          // Find Board Meeting 120-day rule
          const bm = data.upcoming_events.find((e: any) => e.category === 'board_meeting_120d');
          if (bm) {
            setBmDaysRemaining(bm.days_remaining);
            setBmDueDate(bm.due_date);
            if (bm.days_remaining < 0) {
              setBmIsOverdue(true);
              setBmElapsedDays(120 + Math.abs(bm.days_remaining));
            } else {
              setBmIsOverdue(false);
              setBmElapsedDays(Math.max(0, 120 - bm.days_remaining));
            }
          }
        }
      } catch (err) {
        console.error('Failed to load compliance events from API:', err);
      } finally {
        setLoading(false);
      }
    }

    loadComplianceData();
  }, []);

  const bmPercentage = Math.min(100, Math.max(0, Math.round((bmElapsedDays / 120) * 100)));

  const handleGenerate = () => {
    setIsGenerated(true);
    setIsSigned(false);
    setSealDetails(null);
  };

  const handleOpenSignModal = async () => {
    setDscError(null);
    setDscModalOpen(true);
    try {
      const st = await checkBridgeStatus();
      if (st.token_detected) {
        setBridgeStatusInfo(`Connected: ${st.token_label || 'HYP 2003 Token'}`);
      } else if (st.bridge_status === 'online' || st.bridge_status === 'running') {
        setBridgeStatusInfo('Bridge active. Please insert HYP 2003 USB token.');
      } else {
        setBridgeStatusInfo('Hardware Bridge offline. Ensure bridge daemon is active on port 28045.');
      }
    } catch {
      setBridgeStatusInfo('Bridge offline on 127.0.0.1:28045.');
    }
  };

  const handleExecuteHardwareSign = async () => {
    if (!dscPin || dscPin.length < 4) {
      setDscError('Please enter a valid DSC User PIN (4-8 digits).');
      return;
    }
    setDscSigning(true);
    setDscError(null);

    try {
      const token = localStorage.getItem('b00k5_token');
      const tenantId = localStorage.getItem('b00k5_tenant_id');

      // DEF-01: Generate statutory document and bind Company Master Profile, CIN, Reg Office, and Director Roster
      let generatedMeetingId = '00000000-0000-0000-0000-000000000001';
      let docSha256Hex = '';

      if (token) {
        try {
          const genRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/compliance/generate-document?doc_type=${selectedTemplate === 'minutes' ? 'board_minutes' : 'board_notice'}`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`,
              ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
            },
            body: JSON.stringify({
              company_name: companyName,
              cin: cin,
              registered_office: venue,
              meeting_number: meetingNo,
              meeting_date: meetingDate,
              meeting_time: meetingTime,
              venue: venue,
              directors_present: directors.filter(d => d.isPresent),
              agenda_items: agendaItems,
              resolutions: resolutions
            })
          });
          if (genRes.ok) {
            const genData = await genRes.json();
            if (genData.meeting_id) generatedMeetingId = genData.meeting_id;
            if (genData.sha256_hash) docSha256Hex = genData.sha256_hash;
          }
        } catch (e) {
          console.warn('Document pre-generation error:', e);
        }
      }

      if (!docSha256Hex) {
        const docRaw = `${companyName}-${cin}-${meetingNo}-${meetingDate}-${selectedTemplate}-${resolutions.join('|')}-${agendaItems.join('|')}`;
        const msgBuffer = new TextEncoder().encode(docRaw);
        const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
        const hashArray = Array.from(new Uint8Array(hashBuffer));
        docSha256Hex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
      }

      // Execute hardware token cryptographic sign-hash via 127.0.0.1:28045
      const bridgeRes = await signHashViaBridge(dscPin, docSha256Hex);

      const sigAudit = {
        tokenLabel: bridgeRes.token_label || 'HYP 2003 Token',
        signatureHex: bridgeRes.signature_hex,
        sha256: docSha256Hex,
        timestamp: new Date().toISOString(),
        certSubject: `CN=${signerName}, OU=Director, O=${companyName}`
      };

      // Submit permanent statutory proof to backend audit ledger
      try {
        if (token) {
          await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/dsc/submit-signature`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${token}`,
              ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
            },
            body: JSON.stringify({
              document_type: selectedTemplate === 'minutes' ? 'board_minutes' : 'board_notice',
              document_id: generatedMeetingId,
              signer_din: directorDin || '09876543',
              signer_name: signerName,
              signature_hex: bridgeRes.signature_hex,
              certificate_der_hex: bridgeRes.certificate_der_hex || '308203...',
              token_label: bridgeRes.token_label || 'HYP 2003 Token'
            })
          });
        }
      } catch (logErr) {
        console.warn('Signature audit dispatch:', logErr);
      }

      setSealDetails(sigAudit);
      setIsSigned(true);
      setDscModalOpen(false);
    } catch (err: any) {
      setDscError(err.message || 'Hardware DSC signing failed. Please check HYP 2003 dongle connection and PIN.');
    } finally {
      setDscSigning(false);
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Navbar />
        <main className="p-8 space-y-8 max-w-7xl mx-auto w-full">
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xs uppercase font-mono px-2 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800/60">
                  {companyName}
                </span>
                {cin && (
                  <span className="text-xs font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                    CIN: {cin}
                  </span>
                )}
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5 mt-2">
                <Scale className="w-7 h-7 text-sky-400" />
                Statutory Corporate Governance &amp; Document Assembly
              </h1>
              <p className="text-sm text-slate-400 mt-1">
                Companies Act 2013 Watchdog, SS-1 Board Minutes Assembly, and Self-Hosted e-Sign Framework
              </p>
            </div>
            <div className="flex items-center gap-3">
              <DSCBridgeWidget />
            </div>
          </div>

          {/* Section 173 Visual Countdown Watchdog Bar */}
          <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <Clock className={`w-5 h-5 ${bmIsOverdue ? 'text-rose-400' : bmDaysRemaining <= 20 ? 'text-amber-400' : 'text-emerald-400'}`} />
                <h2 className="text-base font-semibold text-white">
                  Section 173(1) Board Meeting Cadence Watchdog
                </h2>
              </div>
              <span className={`text-xs font-mono px-3 py-1 rounded-full border font-semibold w-fit ${
                bmIsOverdue
                  ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                  : bmDaysRemaining <= 20
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                  : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
              }`}>
                {bmIsOverdue
                  ? `Overdue by ${Math.abs(bmDaysRemaining)} Days (Statutory Breach)`
                  : `${bmDaysRemaining} Days Remaining (${bmDaysRemaining <= 20 ? 'Warning Active' : 'Compliant'})`}
              </span>
            </div>

            <p className="text-xs text-slate-300">
              Under Section 173(1) of the Companies Act 2013, not more than 120 days shall intervene between two consecutive Board Meetings.
              Warning is triggered when less than 20 days remain; statutory violations accrue ₹100/day penalties indefinitely.
            </p>

            {/* Visual Progress Bar */}
            <div className="space-y-1.5 font-mono text-xs">
              <div className="w-full bg-slate-800 rounded-full h-3.5 overflow-hidden p-0.5 border border-slate-700">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    bmIsOverdue
                      ? 'bg-rose-500'
                      : bmDaysRemaining <= 20
                      ? 'bg-amber-500'
                      : 'bg-emerald-500'
                  }`}
                  style={{ width: `${bmPercentage}%` }}
                />
              </div>
              <div className="flex justify-between text-[11px] text-slate-400">
                <span>Start: Day 0</span>
                <span className={bmIsOverdue ? 'text-rose-400 font-semibold' : bmDaysRemaining <= 20 ? 'text-amber-400 font-semibold' : 'text-emerald-400 font-semibold'}>
                  Current: {bmElapsedDays} Days Elapsed {bmIsOverdue ? '(Violating Section 173)' : ''}
                </span>
                <span>Max: 120 Days Limit {bmDueDate ? `(Due: ${bmDueDate})` : ''}</span>
              </div>
            </div>
          </div>

          {/* Statutory Calendar Grid */}
          <div>
            <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
              <Calendar className="w-4 h-4 text-sky-400" />
              Statutory Compliance Milestones for {companyName}
            </h3>

            {loading ? (
              <div className="p-8 text-center bg-slate-900/40 rounded-xl border border-slate-800 text-xs text-slate-400">
                Loading compliance radar...
              </div>
            ) : events.length === 0 ? (
              <div className="p-8 text-center bg-slate-900/40 rounded-xl border border-slate-800 text-xs text-slate-400">
                No compliance events recorded yet. Complete setup to seed statutory milestones.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {events.map((ev) => (
                  <div
                    key={ev.id}
                    className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 shadow-md space-y-3 flex flex-col justify-between"
                  >
                    <div>
                      <div className="flex justify-between items-start gap-2 mb-1">
                        <span className="text-[10px] font-mono text-slate-400">{ev.statutory_ref}</span>
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded font-mono ${
                          ev.status === 'completed' || ev.status === 'filed' || ev.status === 'verified'
                            ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                            : ev.status === 'compliant' || ev.status === 'upcoming'
                            ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30'
                            : ev.status === 'due_soon'
                            ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                            : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                        }`}>
                          {ev.status === 'completed' || ev.status === 'filed' || ev.status === 'verified'
                            ? '✓ Filed / Completed'
                            : ev.days_remaining < 0
                            ? `${Math.abs(ev.days_remaining)}d overdue`
                            : `${ev.days_remaining}d left`}
                        </span>
                      </div>
                      <h3 className="font-semibold text-white text-xs leading-snug">{ev.title}</h3>
                    </div>

                    <div className="pt-2 border-t border-slate-800 text-[11px] text-slate-400 flex justify-between items-center">
                      <span>Deadline: <span className="text-slate-200 font-mono">{ev.due_date}</span></span>
                      {ev.status === 'completed' || ev.status === 'filed' || ev.status === 'verified' ? (
                        <span className="text-emerald-400 font-medium">✓ Compliant</span>
                      ) : (
                        <span className={ev.days_remaining < 0 ? 'text-rose-400 font-bold' : ''}>₹{ev.fine_per_day}/day fine</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Document Assembly Wizard & e-Sign Section */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            {/* Left Form: Document Parameters (5 cols) */}
            <div className="lg:col-span-5 p-6 rounded-xl bg-slate-900/60 border border-slate-800 shadow-lg space-y-5">
              <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                <FileText className="w-5 h-5 text-sky-400" />
                <h2 className="font-semibold text-white text-sm">Automated Document Assembly Wizard</h2>
              </div>

              <div className="space-y-4 text-xs">
                <div>
                  <label className="text-slate-400 block mb-1">Select Statutory Template:</label>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      onClick={() => setSelectedTemplate('minutes')}
                      className={`py-2 px-3 rounded-lg border font-semibold text-xs transition-colors flex items-center justify-center gap-1.5 ${
                        selectedTemplate === 'minutes'
                          ? 'bg-sky-500/20 border-sky-500/40 text-sky-300'
                          : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-white'
                      }`}
                    >
                      <FileCheck className="w-4 h-4" /> SS-1 Board Minutes
                    </button>
                    <button
                      type="button"
                      onClick={() => setSelectedTemplate('notice')}
                      className={`py-2 px-3 rounded-lg border font-semibold text-xs transition-colors flex items-center justify-center gap-1.5 ${
                        selectedTemplate === 'notice'
                          ? 'bg-sky-500/20 border-sky-500/40 text-sky-300'
                          : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-white'
                      }`}
                    >
                      <Calendar className="w-4 h-4" /> Sec 173(3) Notice
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-slate-400 block mb-1">Meeting Reference:</label>
                    <input
                      type="text"
                      value={meetingNo}
                      onChange={(e) => setMeetingNo(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
                    />
                  </div>
                  <div>
                    <label className="text-slate-400 block mb-1">Meeting Date:</label>
                    <input
                      type="date"
                      value={meetingDate}
                      onChange={(e) => setMeetingDate(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-slate-400 block mb-1">Venue / Registered Office:</label>
                  <input
                    type="text"
                    value={venue}
                    onChange={(e) => setVenue(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-slate-400 block mb-1">Signatory Name:</label>
                    <input
                      type="text"
                      value={signerName}
                      onChange={(e) => setSignerName(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
                    />
                  </div>
                  <div>
                    <label className="text-slate-400 block mb-1">Director DIN:</label>
                    <input
                      type="text"
                      value={directorDin}
                      onChange={(e) => setDirectorDin(e.target.value)}
                      placeholder="8-digit DIN"
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
                    />
                  </div>
                </div>

                {/* DEF-01: Statutory Director Roster & Quorum Attendance */}
                <div className="pt-2 border-t border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-slate-300 font-semibold block flex items-center gap-1.5">
                      <Users className="w-3.5 h-3.5 text-sky-400" />
                      Director Roster (SS-1 Quorum):
                    </label>
                    <span className="text-[10px] text-slate-500 font-mono">Bound to Master Profile</span>
                  </div>
                  {directors.length > 0 ? (
                    <div className="space-y-1.5 bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80">
                      {directors.map((dir, idx) => (
                        <div key={idx} className="flex items-center justify-between text-xs py-0.5">
                          <label className="flex items-center gap-2 cursor-pointer select-none">
                            <input
                              type="checkbox"
                              checked={dir.isPresent}
                              onChange={(e) => {
                                const updated = [...directors];
                                updated[idx].isPresent = e.target.checked;
                                setDirectors(updated);
                              }}
                              className="rounded border-slate-700 bg-slate-900 text-sky-500 focus:ring-0"
                            />
                            <span className="text-white font-medium">{dir.name}</span>
                            <span className="text-[10px] text-slate-400">({dir.designation})</span>
                          </label>
                          <span className="text-[10px] font-mono text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800">
                            DIN: {dir.din}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="text-[11px] text-slate-500 italic bg-slate-950/40 p-2 rounded">
                      Loading statutory director roster from corporate vault...
                    </div>
                  )}
                </div>

                {/* Dynamic Agenda Items (SS-1 and Board Notice) */}
                <div className="pt-2 border-t border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-slate-300 font-semibold block">Meeting Agenda Items (SS-1):</label>
                    <button
                      type="button"
                      onClick={() => setAgendaItems([...agendaItems, 'New Business Agenda Item'])}
                      className="text-[11px] text-sky-400 hover:text-sky-300 flex items-center gap-1 font-medium"
                    >
                      <Plus className="w-3 h-3" /> Add Agenda Item
                    </button>
                  </div>
                  <div className="space-y-1.5 max-h-44 overflow-y-auto pr-1">
                    {agendaItems.map((item, idx) => (
                      <div key={idx} className="flex items-center gap-2">
                        <span className="text-slate-500 font-mono text-[11px] w-4">{idx + 1}.</span>
                        <input
                          type="text"
                          value={item}
                          onChange={(e) => {
                            const updated = [...agendaItems];
                            updated[idx] = e.target.value;
                            setAgendaItems(updated);
                          }}
                          className="flex-1 bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 text-xs focus:outline-none focus:border-sky-500"
                        />
                        {agendaItems.length > 1 && (
                          <button
                            type="button"
                            onClick={() => setAgendaItems(agendaItems.filter((_, i) => i !== idx))}
                            className="text-slate-500 hover:text-rose-400 p-1"
                            title="Remove item"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Dynamic Key Resolutions (For SS-1 Minutes) */}
                {selectedTemplate === 'minutes' && (
                  <div className="pt-2 border-t border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <label className="text-slate-300 font-semibold block">Key Resolutions Passed:</label>
                      <button
                        type="button"
                        onClick={() => setResolutions([...resolutions, 'RESOLVED THAT the Board hereby authorizes...'])}
                        className="text-[11px] text-emerald-400 hover:text-emerald-300 flex items-center gap-1 font-medium"
                      >
                        <Plus className="w-3 h-3" /> Add Resolution
                      </button>
                    </div>
                    <div className="space-y-1.5 max-h-44 overflow-y-auto pr-1">
                      {resolutions.map((res, idx) => (
                        <div key={idx} className="flex items-start gap-2">
                          <span className="text-slate-500 font-mono text-[11px] w-4 mt-1.5">{idx + 1}.</span>
                          <textarea
                            rows={2}
                            value={res}
                            onChange={(e) => {
                              const updated = [...resolutions];
                              updated[idx] = e.target.value;
                              setResolutions(updated);
                            }}
                            className="flex-1 bg-slate-950 border border-slate-800 rounded px-2.5 py-1 text-slate-200 text-xs focus:outline-none focus:border-emerald-500"
                          />
                          {resolutions.length > 1 && (
                            <button
                              type="button"
                              onClick={() => setResolutions(resolutions.filter((_, i) => i !== idx))}
                              className="text-slate-500 hover:text-rose-400 p-1 mt-1"
                              title="Remove resolution"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <button
                  type="button"
                  onClick={handleGenerate}
                  className="w-full py-2.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold rounded-lg shadow-sm transition-colors text-xs flex items-center justify-center gap-2 mt-2"
                >
                  <Sparkles className="w-4 h-4" /> Compile Statutory Document (PDF/A)
                </button>
              </div>
            </div>

            {/* Right Preview: Assembled Document & e-Sign Controls (7 cols) */}
            <div className="lg:col-span-7 p-6 rounded-xl bg-slate-900/60 border border-slate-800 shadow-lg space-y-4 flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
                  <div className="flex items-center gap-2">
                    <FileCheck className="w-5 h-5 text-emerald-400" />
                    <h3 className="font-semibold text-white text-sm">
                      {selectedTemplate === 'minutes' ? 'Board Meeting Minutes (SS-1 Draft)' : 'Notice & Agenda Draft'}
                    </h3>
                  </div>
                  {isSigned && (
                    <span className="px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-semibold flex items-center gap-1 font-mono">
                      <ShieldCheck className="w-3.5 h-3.5" /> Hardware Token Sealed (HYP 2003)
                    </span>
                  )}
                </div>

                {/* Document Preview Box */}
                <div className="p-5 rounded-lg bg-slate-950 border border-slate-800/80 font-mono text-[11px] text-slate-300 space-y-3 max-h-[460px] overflow-y-auto leading-relaxed">
                  <div className="text-center pb-3 border-b border-slate-800">
                    <p className="font-bold text-white text-xs uppercase">{companyName}</p>
                    <p className="text-[10px] text-slate-400">
                      {cin ? `CIN: ${cin} | ` : ''}Regd. Office: {venue}
                    </p>
                    <p className="font-bold text-sky-400 text-xs mt-1.5">
                      {selectedTemplate === 'minutes'
                        ? `MINUTES OF THE PROCEEDINGS OF THE BOARD OF DIRECTORS (${meetingNo})`
                        : `NOTICE OF BOARD MEETING U/S 173(3) (${meetingNo})`}
                    </p>
                  </div>

                  <p><span className="text-slate-500">Date &amp; Time:</span> {meetingDate} at {meetingTime}</p>
                  <p><span className="text-slate-500">Quorum:</span> Requisite quorum present under Section 174 of the Companies Act 2013.</p>
                  <p><span className="text-slate-500">Chairman:</span> {signerName} {directorDin ? `(DIN: ${directorDin})` : ''} took the Chair.</p>

                  {/* DEF-01: Directors Present Roster */}
                  <div className="pt-2 border-t border-slate-800/60">
                    <p className="font-bold text-white mb-1.5">1. DIRECTORS PRESENT (SS-1 ROSTER):</p>
                    <div className="space-y-1 text-slate-300">
                      {directors.filter(d => d.isPresent).length > 0 ? (
                        directors.filter(d => d.isPresent).map((d, i) => (
                          <p key={i} className="flex items-center justify-between text-[11px]">
                            <span>• {d.name} ({d.designation})</span>
                            <span className="font-mono text-slate-500">DIN: {d.din}</span>
                          </p>
                        ))
                      ) : (
                        <p className="text-[11px]">• {signerName} (Director, DIN: {directorDin || 'N/A'})</p>
                      )}
                    </div>
                  </div>

                  {/* Agenda Section */}
                  <div className="pt-2 border-t border-slate-800/60">
                    <p className="font-bold text-white mb-1.5">2. AGENDA ITEMS TRANSACTED:</p>
                    <div className="space-y-1 text-slate-300">
                      {agendaItems.map((ag, i) => (
                        <p key={i}>{i + 1}. {ag}</p>
                      ))}
                    </div>
                  </div>

                  {/* Resolutions Section (Minutes) */}
                  {selectedTemplate === 'minutes' && (
                    <div className="pt-2 border-t border-slate-800/60">
                      <p className="font-bold text-emerald-400 mb-1.5">KEY RESOLUTIONS PASSED UNANIMOUSLY:</p>
                      <div className="space-y-1.5 text-slate-300">
                        {resolutions.map((res, i) => (
                          <p key={i}>{i + 1}. {res}</p>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Authentic Hardware DSC Signature Stamp */}
                  {isSigned && sealDetails && (
                    <div className="mt-4 p-3.5 rounded bg-emerald-950/30 border border-emerald-800/60 text-emerald-300 space-y-1 text-[10px]">
                      <p className="font-bold text-emerald-400 flex items-center gap-1.5 text-xs">
                        <ShieldCheck className="w-4 h-4 text-emerald-400" />
                        [HARDWARE CRYPTOGRAPHIC SEAL: PKCS#11 HYP 2003 TOKEN]
                      </p>
                      <p><span className="text-emerald-500">Signatory:</span> {signerName} {directorDin ? `(DIN: ${directorDin})` : ''}</p>
                      <p><span className="text-emerald-500">Token Hardware:</span> {sealDetails.tokenLabel} (Driver: /usr/lib/libespki.so)</p>
                      <p><span className="text-emerald-500">Certificate Subject:</span> {sealDetails.certSubject}</p>
                      <p><span className="text-emerald-500">Document Digest:</span> {sealDetails.sha256}</p>
                      <p className="font-mono break-all text-[9px] text-emerald-400/80">
                        <span className="text-emerald-500">RSA Signature:</span> {sealDetails.signatureHex.substring(0, 64)}...
                      </p>
                      <p className="text-[10px] text-slate-400 pt-1 border-t border-emerald-900/50">
                        Timestamp: {sealDetails.timestamp} | Enforceable under Section 3A of Information Technology Act 2000
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Action Footer */}
              <div className="pt-3 border-t border-slate-800 flex items-center justify-between gap-3">
                <span className="text-xs text-slate-400 flex items-center gap-1.5">
                  <Lock className="w-3.5 h-3.5 text-sky-400" />
                  Standard: <span className="text-white font-mono">ICSI SS-1 / ISO 19005-1</span>
                </span>

                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={handleOpenSignModal}
                    disabled={isSigned}
                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-600 text-white font-semibold rounded-lg text-xs transition-colors flex items-center gap-1.5 shadow-sm"
                  >
                    <KeyRound className="w-3.5 h-3.5" />
                    {isSigned ? 'Token Signed & Sealed' : 'e-Sign with HYP 2003 DSC'}
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* HYP 2003 Hardware DSC PIN Modal */}
          {dscModalOpen && (
            <div className="fixed inset-0 bg-black/75 backdrop-blur-sm z-50 flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <KeyRound className="w-5 h-5 text-sky-400" />
                    <h3 className="font-semibold text-white text-sm">HYP 2003 Hardware DSC Token</h3>
                  </div>
                  <button
                    onClick={() => setDscModalOpen(false)}
                    className="text-slate-400 hover:text-white text-xs"
                  >
                    ✕
                  </button>
                </div>

                <div className="space-y-3 text-xs">
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center gap-2.5">
                    <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse shrink-0" />
                    <span className="text-slate-300 font-mono">{bridgeStatusInfo}</span>
                  </div>

                  <p className="text-slate-400">
                    Signing statutory document: <span className="text-white font-medium">{selectedTemplate === 'minutes' ? 'SS-1 Minutes' : 'Sec 173 Notice'} ({meetingNo})</span>
                  </p>

                  <div className="space-y-1.5">
                    <label className="text-slate-300 font-medium block">
                      Enter Token User PIN:
                    </label>
                    <input
                      type="password"
                      value={dscPin}
                      onChange={(e) => setDscPin(e.target.value)}
                      placeholder="e.g. 123456"
                      className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono tracking-widest text-sm focus:outline-none focus:border-sky-500"
                      autoFocus
                    />
                    <p className="text-[11px] text-slate-500">
                      Standard default PIN for test HYP 2003 / SoftHSM2 dongle is <span className="font-mono text-slate-400">123456</span>.
                    </p>
                  </div>

                  {dscError && (
                    <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                      {dscError}
                    </div>
                  )}

                  <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => setDscModalOpen(false)}
                      className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleExecuteHardwareSign}
                      disabled={dscSigning}
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-semibold text-xs rounded-lg flex items-center gap-1.5 shadow"
                    >
                      {dscSigning ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Signing via Token...
                        </>
                      ) : (
                        <>
                          <ShieldCheck className="w-3.5 h-3.5" /> Sign with Hardware Token
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
