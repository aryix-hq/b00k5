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
  Users,
  Receipt,
  FileSpreadsheet,
  Building2,
  AlertCircle,
  CheckCircle,
  Search,
  FileDown,
  Coins,
  Upload,
  ShieldAlert,
  TrendingUp,
  ArrowRight,
  Anchor,
  HelpCircle,
  Check,
  Layers,
  LockKeyhole,
  FolderArchive,
  FileCheck2,
  Eye,
  Copy,
  Archive
} from 'lucide-react';
import { DSCBridgeWidget } from '../../components/DSCBridgeWidget';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import { CompanyLetterhead } from '@/components/CompanyLetterhead';
import { fetchApi, fetchRawApi } from '@/lib/api';
import { signHashViaBridge, checkBridgeStatus } from '../../lib/dsc-bridge';
import { TDSComplianceTab } from '@/components/compliance/TDSComplianceTab';
import { FixedAssetsTab } from '@/components/compliance/FixedAssetsTab';
import { MCARegistersTab } from '@/components/compliance/MCARegistersTab';

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
  fiscal_year?: string;
  assessment_year?: string;
}

export default function GovernanceDashboardPage() {
  const [activeTab, setActiveTab] = useState<'board_governance' | 'gstr2b' | 'llp' | 'sec40a3' | 'advance_tax' | 'statutory_baseline' | 'gst_forecast' | 'statutory_dossier' | 'tds_compliance' | 'fixed_assets' | 'mca_registers'>('board_governance');

  const [companyName, setCompanyName] = useState('Sovereign Enterprise');
  const [cin, setCin] = useState('');
  const [entityType, setEntityType] = useState<string>('Private Limited Company');
  const [venue, setVenue] = useState('Registered Office');
  const [signerName, setSignerName] = useState('Authorized Director');
  const [directorDin, setDirectorDin] = useState('');
  const [directors, setDirectors] = useState<Array<{ name: string; din: string; designation: string; isPresent: boolean }>>([]);

  const isLLP =
    entityType.toLowerCase().includes('llp') ||
    companyName.toLowerCase().includes('llp') ||
    cin.toUpperCase().includes('LLP');
  const isOPC =
    entityType.toLowerCase().includes('opc') ||
    entityType.toLowerCase().includes('one person') ||
    companyName.toLowerCase().includes('(opc)') ||
    companyName.toLowerCase().includes('opc ') ||
    cin.toUpperCase().includes('OPC');

  const [events, setEvents] = useState<StatutoryEvent[]>([]);
  const [statutoryEventFyFilter, setStatutoryEventFyFilter] = useState<string>('all');
  const [loading, setLoading] = useState(true);

  // Tab 1: Board Governance & Minutes State
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

  // Tab 2: GSTR-2B Reconciliation State
  const [gstr2bFile, setGstr2bFile] = useState<File | null>(null);
  const [autoUpdateItc, setAutoUpdateItc] = useState(true);
  const [gstr2bLoading, setGstr2bLoading] = useState(false);
  const [gstr2bReport, setGstr2bReport] = useState<any | null>(null);
  const [gstr2bError, setGstr2bError] = useState<string | null>(null);
  const [gstr2bFilter, setGstr2bFilter] = useState<'all' | 'matched' | 'tax_mismatches' | 'missing_in_books' | 'missing_in_2b' | 'blocked_credit'>('all');

  // Tab 3: LLP Secretarial State
  const [llpYear, setLlpYear] = useState('2025-26');
  const [form11Packet, setForm11Packet] = useState<any | null>(null);
  const [form8Packet, setForm8Packet] = useState<any | null>(null);
  const [llpLoading, setLlpLoading] = useState(false);
  const [llpResolutionType, setLlpResolutionType] = useState('approval_of_accounts');
  const [llpResolutionResult, setLlpResolutionResult] = useState<any | null>(null);
  const [llpResolutionLoading, setLlpResolutionLoading] = useState(false);

  // Tab 4: Section 40A(3) Watchdog State
  const [sec40a3Year, setSec40a3Year] = useState('2025-26');
  const [sec40a3Audit, setSec40a3Audit] = useState<any | null>(null);
  const [sec40a3AuditLoading, setSec40a3AuditLoading] = useState(false);
  // Pre-flight test form
  const [testDate, setTestDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [testVendor, setTestVendor] = useState('');
  const [testAmount, setTestAmount] = useState('12000.00');
  const [testGoodsCarriage, setTestGoodsCarriage] = useState(false);
  const [testResult, setTestResult] = useState<any | null>(null);
  const [testLoading, setTestLoading] = useState(false);

  // Tab 5: Advance Tax Forecasting State
  const [advanceTaxFy, setAdvanceTaxFy] = useState('2026-27');
  const [advanceTaxForecast, setAdvanceTaxForecast] = useState<any | null>(null);
  const [advanceTaxLoading, setAdvanceTaxLoading] = useState(false);
  const [customProfitInput, setCustomProfitInput] = useState('');
  const [advanceTaxRegime, setAdvanceTaxRegime] = useState('sec_115baa');
  // Challan recording modal
  const [challanModalOpen, setChallanModalOpen] = useState(false);
  const [challanQuarter, setChallanQuarter] = useState<'Q1' | 'Q2' | 'Q3' | 'Q4'>('Q1');
  const [challanAmount, setChallanAmount] = useState('');
  const [challanDate, setChallanDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [challanBsr, setChallanBsr] = useState('');
  const [challanSerial, setChallanSerial] = useState('');
  const [challanCin, setChallanCin] = useState('');
  const [challanSubmitting, setChallanSubmitting] = useState(false);
  const [challanSuccessMsg, setChallanSuccessMsg] = useState<string | null>(null);
  const [challanErrorMsg, setChallanErrorMsg] = useState<string | null>(null);
  // e-Pay tax packet modal
  const [packetModalOpen, setPacketModalOpen] = useState(false);
  const [packetData, setPacketData] = useState<any | null>(null);
  const [packetLoading, setPacketLoading] = useState(false);

  // Tab 6: Statutory Baseline & Historical Seal State
  const [statutoryFy, setStatutoryFy] = useState('2025-26');
  const [statutoryRadar, setStatutoryRadar] = useState<any | null>(null);
  const [statutoryLoading, setStatutoryLoading] = useState(false);
  const [sealModalOpen, setSealModalOpen] = useState(false);
  const [sealingNotes, setSealingNotes] = useState('');
  const [sealingSubmitting, setSealingSubmitting] = useState(false);
  const [sealResult, setSealResult] = useState<any | null>(null);
  const [sealErrorMsg, setSealErrorMsg] = useState<string | null>(null);
  // Record Anchor modal
  const [anchorModalOpen, setAnchorModalOpen] = useState(false);
  const [anchorFormType, setAnchorFormType] = useState('aoc_4');
  const [anchorSrn, setAnchorSrn] = useState('');
  const [anchorFilingDate, setAnchorFilingDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [anchorDin, setAnchorDin] = useState('');
  const [anchorUdin, setAnchorUdin] = useState('');
  const [anchorPaidUpCapital, setAnchorPaidUpCapital] = useState('100000.00');
  const [anchorRetainedEarnings, setAnchorRetainedEarnings] = useState('0.00');
  const [anchorTradePayables, setAnchorTradePayables] = useState('0.00');
  const [anchorBankBalance, setAnchorBankBalance] = useState('100000.00');
  const [anchorDebtors, setAnchorDebtors] = useState('0.00');
  const [anchorPpe, setAnchorPpe] = useState('0.00');
  const [anchorSubmitting, setAnchorSubmitting] = useState(false);
  const [anchorSuccessMsg, setAnchorSuccessMsg] = useState<string | null>(null);
  const [anchorErrorMsg, setAnchorErrorMsg] = useState<string | null>(null);

  // Milestone 8.1: 3-Stage FY Lifecycle State
  const [lifecycleFy, setLifecycleFy] = useState('2025-26');
  const [fyLifecycle, setFyLifecycle] = useState<any | null>(null);
  const [lifecycleLoading, setLifecycleLoading] = useState(false);
  const [stageModalOpen, setStageModalOpen] = useState(false);
  const [selectedTargetStage, setSelectedTargetStage] = useState<'active' | 'audit_closing_window' | 'statutory_sealed'>('audit_closing_window');
  const [targetDeadline, setTargetDeadline] = useState('2026-10-31');
  const [stageNotes, setStageNotes] = useState('');
  const [stageTransitionSubmitting, setStageTransitionSubmitting] = useState(false);
  const [stageTransitionSuccess, setStageTransitionSuccess] = useState<string | null>(null);
  const [stageTransitionError, setStageTransitionError] = useState<string | null>(null);

  // Milestone 8.2: Multi-Frequency GST Forecasting Engine State
  const [gstFrequency, setGstFrequency] = useState<'monthly' | 'quarterly' | 'composition' | 'annual'>('monthly');
  const [gstFy, setGstFy] = useState('2025-26');
  const [gstQuarter, setGstQuarter] = useState<'Q1' | 'Q2' | 'Q3' | 'Q4'>('Q1');
  const [gstMonth, setGstMonth] = useState<number>(() => new Date().getMonth() + 1);
  const [gstTurnover, setGstTurnover] = useState('0.00');
  const [gstForecast, setGstForecast] = useState<any | null>(null);
  const [gstForecastLoading, setGstForecastLoading] = useState(false);
  const [gstChallansList, setGstChallansList] = useState<any[]>([]);
  // GST Challan Recording Modal
  const [gstChallanModalOpen, setGstChallanModalOpen] = useState(false);
  const [gstChallanRef, setGstChallanRef] = useState('');
  const [gstChallanCpin, setGstChallanCpin] = useState('');
  const [gstChallanCin, setGstChallanCin] = useState('');
  const [gstChallanBank, setGstChallanBank] = useState('HDFC Bank');
  const [gstChallanDate, setGstChallanDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [gstChallanAmount, setGstChallanAmount] = useState('0.00');
  const [gstChallanSubmitting, setGstChallanSubmitting] = useState(false);
  const [gstChallanSuccessMsg, setGstChallanSuccessMsg] = useState<string | null>(null);
  const [gstChallanErrorMsg, setGstChallanErrorMsg] = useState<string | null>(null);
  // PMT-06 Helper Modal
  const [pmt06ModalOpen, setPmt06ModalOpen] = useState(false);
  const [pmt06Data, setPmt06Data] = useState<any | null>(null);
  const [pmt06Loading, setPmt06Loading] = useState(false);

  // Milestone 8.3: Sovereign Statutory Dossier State
  const [dossierFy, setDossierFy] = useState('2025-26');
  const [dossierData, setDossierData] = useState<any | null>(null);
  const [dossierLoading, setDossierLoading] = useState(false);
  const [dossierUploadModalOpen, setDossierUploadModalOpen] = useState(false);
  const [dossierUploadFile, setDossierUploadFile] = useState<File | null>(null);
  const [dossierFormType, setDossierFormType] = useState('aoc_4');
  const [dossierSrn, setDossierSrn] = useState('');
  const [dossierFilingDate, setDossierFilingDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [dossierUploadSubmitting, setDossierUploadSubmitting] = useState(false);
  const [dossierUploadResult, setDossierUploadResult] = useState<any | null>(null);
  const [dossierUploadError, setDossierUploadError] = useState<string | null>(null);
  const [streamingKey, setStreamingKey] = useState<string | null>(null);

  useEffect(() => {
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

      // Global FY synchronization
      const syncFY = (rawVal: string) => {
        const match = (rawVal || '').match(/(\d{4})/);
        if (match) {
          const startY = parseInt(match[1]);
          const clean = `${startY}-${String(startY + 1).slice(-2)}`;
          setLlpYear(clean);
          setSec40a3Year(clean);
          setAdvanceTaxFy(clean);
          setStatutoryFy(clean);
          setLifecycleFy(clean);
          setGstFy(clean);
          setDossierFy(clean);
          setMeetingNo(prev => prev.startsWith('BM/') ? `BM/${clean}/01` : prev);
        }
      };

      const initialFY = localStorage.getItem('b00k5_selected_fy') || localStorage.getItem('b00k5_selected_fy_clean') || '2026-27';
      syncFY(initialFY);

      const onFYChanged = (e: any) => {
        const val = typeof e.detail === 'string' ? e.detail : (e.detail?.full || e.detail?.short || '');
        syncFY(val);
      };

      window.addEventListener('b00k5_fy_changed', onFYChanged);
      window.addEventListener('b00k5_fy_obj_changed', onFYChanged);
    }

    async function loadComplianceData() {
      setLoading(true);
      try {
        const dirRes = await fetchApi('/api/v1/compliance/directors');
        if (dirRes) {
          if (dirRes.legal_name) {
            setCompanyName(dirRes.legal_name);
            localStorage.setItem('b00k5_legal_name', dirRes.legal_name);
          }
          if (dirRes.entity_type) {
            setEntityType(dirRes.entity_type);
            if (dirRes.entity_type.toLowerCase().includes('llp')) {
              setActiveTab('llp');
            }
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
            accumulated_penalty: parseFloat(e.accumulated_penalty_inr || '0'),
            fiscal_year: e.fiscal_year,
            assessment_year: e.assessment_year
          }));
          setEvents(mapped);

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
    loadFyLifecycle('2025-26');
    loadAdvanceTaxForecast('2026-27');
    loadGstForecast('2026-27', 'monthly', 'Q3', new Date().getMonth() + 1, '0.00');
    loadGstChallans('2026-27');
  }, []);

  // Lazy load tab data when switching tabs
  useEffect(() => {
    if (activeTab === 'llp' && !form11Packet) {
      loadLlpData(llpYear);
    }
    if (activeTab === 'sec40a3' && !sec40a3Audit) {
      loadSec40a3Audit(sec40a3Year);
    }
    if (activeTab === 'gst_forecast' && !gstForecast) {
      loadGstForecast(gstFy, gstFrequency, gstQuarter, gstMonth, gstTurnover);
      loadGstChallans(gstFy);
    }
    if (activeTab === 'statutory_dossier' && !dossierData) {
      loadDossierData(dossierFy);
    }
  }, [activeTab]);

  const loadLlpData = async (fy: string) => {
    setLlpLoading(true);
    try {
      const [f11, f8] = await Promise.all([
        fetchApi(`/api/v1/compliance/llp/form11?fy=${fy}`),
        fetchApi(`/api/v1/compliance/llp/form8?fy=${fy}`)
      ]);
      setForm11Packet(f11);
      setForm8Packet(f8);
    } catch (err) {
      console.warn('Error loading LLP packets:', err);
    } finally {
      setLlpLoading(false);
    }
  };

  const handleGenerateLlpResolution = async () => {
    setLlpResolutionLoading(true);
    try {
      const res = await fetchApi('/api/v1/compliance/llp/generate-resolution', {
        method: 'POST',
        body: JSON.stringify({
          resolution_type: llpResolutionType,
          fy: llpYear
        })
      });
      setLlpResolutionResult(res);
    } catch (err) {
      console.error('Error generating LLP resolution:', err);
    } finally {
      setLlpResolutionLoading(false);
    }
  };

  const loadSec40a3Audit = async (fy: string) => {
    setSec40a3AuditLoading(true);
    try {
      const res = await fetchApi(`/api/v1/compliance/sec40a3/audit?fy=${fy}`);
      setSec40a3Audit(res);
    } catch (err) {
      console.warn('Error loading Sec 40A(3) audit:', err);
    } finally {
      setSec40a3AuditLoading(false);
    }
  };

  const handleEvaluateCandidateCash = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!testVendor || !testAmount) return;
    setTestLoading(true);
    try {
      const res = await fetchApi('/api/v1/compliance/sec40a3/evaluate', {
        method: 'POST',
        body: JSON.stringify({
          expense_date: testDate,
          merchant_name: testVendor,
          new_cash_amount: parseFloat(testAmount),
          is_goods_carriage: testGoodsCarriage
        })
      });
      setTestResult(res);
    } catch (err) {
      console.error('Error evaluating candidate cash:', err);
    } finally {
      setTestLoading(false);
    }
  };

  const handleGstr2bUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gstr2bFile) {
      setGstr2bError('Please select an official GSTR-2B JSON file.');
      return;
    }
    setGstr2bLoading(true);
    setGstr2bError(null);
    try {
      const token = localStorage.getItem('b00k5_token');
      const tenantId = localStorage.getItem('b00k5_tenant_id');
      const formData = new FormData();
      formData.append('file', gstr2bFile);
      formData.append('auto_update_eligible_itc', String(autoUpdateItc));

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/compliance/gstr2b/upload`, {
        method: 'POST',
        headers: {
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
          ...(tenantId ? { 'X-Tenant-ID': tenantId } : {})
        },
        body: formData
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to reconcile GSTR-2B statement.');
      }
      const data = await res.json();
      setGstr2bReport(data);
    } catch (err: any) {
      setGstr2bError(err.message || 'Error processing GSTR-2B statement.');
    } finally {
      setGstr2bLoading(false);
    }
  };

  const bmPercentage = Math.min(100, Math.max(0, Math.round((bmElapsedDays / 120) * 100)));

  // Automatic Data Loading on Tab Activation
  useEffect(() => {
    if (activeTab === 'advance_tax') {
      loadAdvanceTaxForecast(advanceTaxFy);
    } else if (activeTab === 'statutory_baseline') {
      loadStatutoryRadar(statutoryFy);
    }
  }, [activeTab, statutoryFy, advanceTaxFy]);

  const loadAdvanceTaxForecast = async (fy?: string, customProfit?: string, regimeOverride?: string) => {
    setAdvanceTaxLoading(true);
    try {
      const targetFy = fy || advanceTaxFy;
      const targetRegime = regimeOverride !== undefined ? regimeOverride : advanceTaxRegime;
      let url = `/api/v1/compliance/advance-tax/forecast?fy=${targetFy}`;
      if (targetRegime) {
        url += `&regime=${encodeURIComponent(targetRegime)}`;
      }
      const profitNum = customProfit !== undefined ? parseFloat(customProfit) : parseFloat(customProfitInput);
      if (!isNaN(profitNum) && profitNum > 0) {
        url += `&custom_projected_profit=${profitNum}`;
      }
      const data = await fetchApi(url);
      setAdvanceTaxForecast(data);
    } catch (err) {
      console.warn('Error loading advance tax forecast:', err);
    } finally {
      setAdvanceTaxLoading(false);
    }
  };

  const handleOpenEpayPacket = async (quarter: string, amount: number) => {
    setPacketLoading(true);
    setPacketModalOpen(true);
    try {
      const data = await fetchApi(`/api/v1/compliance/advance-tax/challan-packet?fy=${advanceTaxFy}&quarter=${quarter}&amount=${amount}`);
      setPacketData(data);
    } catch (err) {
      console.error('Error generating epay tax packet:', err);
    } finally {
      setPacketLoading(false);
    }
  };

  const handleRecordChallan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!challanAmount || !challanBsr || !challanSerial) return;
    setChallanSubmitting(true);
    setChallanErrorMsg(null);
    setChallanSuccessMsg(null);
    try {
      const res = await fetchApi('/api/v1/compliance/advance-tax/challan', {
        method: 'POST',
        body: JSON.stringify({
          fiscal_year: advanceTaxFy,
          quarter: challanQuarter,
          payment_date: challanDate,
          bsr_code: challanBsr,
          challan_serial_no: challanSerial,
          amount_paid: parseFloat(challanAmount),
          cin_number: challanCin || undefined
        })
      });
      setChallanSuccessMsg(`Challan recorded successfully! Serial: ${res.challan_serial_no}`);
      await loadAdvanceTaxForecast(advanceTaxFy);
      setTimeout(() => {
        setChallanModalOpen(false);
        setChallanSuccessMsg(null);
        setChallanAmount('');
        setChallanBsr('');
        setChallanSerial('');
        setChallanCin('');
      }, 1500);
    } catch (err: any) {
      setChallanErrorMsg(err.message || 'Failed to record advance tax challan.');
    } finally {
      setChallanSubmitting(false);
    }
  };

  const loadStatutoryRadar = async (fy?: string) => {
    setStatutoryLoading(true);
    try {
      const targetFy = fy || statutoryFy;
      const data = await fetchApi(`/api/v1/compliance/statutory-anchor/variance-radar?fy=${targetFy}`);
      setStatutoryRadar(data);
    } catch (err) {
      console.warn('Error loading statutory variance radar:', err);
    } finally {
      setStatutoryLoading(false);
    }
  };

  const handleExecuteSeal = async () => {
    setSealingSubmitting(true);
    setSealErrorMsg(null);
    try {
      const res = await fetchApi('/api/v1/compliance/statutory-anchor/calibrate-and-lock', {
        method: 'POST',
        body: JSON.stringify({
          fiscal_year: statutoryFy,
          custom_notes: sealingNotes || `Statutory Calibration aligned with Form AOC-4 for FY ${statutoryFy}`
        })
      });
      setSealResult(res);
      await loadStatutoryRadar(statutoryFy);
    } catch (err: any) {
      setSealErrorMsg(err.message || 'Failed to calibrate and seal fiscal year.');
    } finally {
      setSealingSubmitting(false);
    }
  };

  const handleRecordAnchor = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!anchorSrn) return;
    setAnchorSubmitting(true);
    setAnchorErrorMsg(null);
    setAnchorSuccessMsg(null);
    try {
      const parts = statutoryFy.split('-');
      const startYr = parseInt(parts[0], 10);
      const endYr = parts[1].length === 2 ? startYr + 1 : parseInt(parts[1], 10);
      const ay = `${endYr}-${String(endYr + 1).slice(-2)}`;

      const scheduleIii = {
        '2010': parseFloat(anchorPaidUpCapital) || 0,
        '2020': parseFloat(anchorRetainedEarnings) || 0,
        '2040': parseFloat(anchorTradePayables) || 0,
        '1010': parseFloat(anchorBankBalance) || 0,
        '1020': parseFloat(anchorDebtors) || 0,
        '1050': parseFloat(anchorPpe) || 0
      };

      await fetchApi('/api/v1/compliance/statutory-anchor/record', {
        method: 'POST',
        body: JSON.stringify({
          fiscal_year: statutoryFy,
          assessment_year: ay,
          form_type: anchorFormType,
          srn_or_ack_number: anchorSrn,
          filing_date: anchorFilingDate,
          schedule_iii_payload: scheduleIii,
          signatory_din: anchorDin || undefined,
          auditor_udin: anchorUdin || undefined
        })
      });
      setAnchorSuccessMsg(`Successfully anchored ${anchorFormType.toUpperCase()} for FY ${statutoryFy}!`);
      await loadStatutoryRadar(statutoryFy);
      setTimeout(() => {
        setAnchorModalOpen(false);
        setAnchorSuccessMsg(null);
      }, 1500);
    } catch (err: any) {
      setAnchorErrorMsg(err.message || 'Failed to record statutory anchor.');
    } finally {
      setAnchorSubmitting(false);
    }
  };

  // --- Milestone 8.1 Handlers: 3-Stage FY Lifecycle ---
  const loadFyLifecycle = async (fy?: string) => {
    setLifecycleLoading(true);
    try {
      const targetFy = fy || lifecycleFy;
      const data = await fetchApi(`/api/v1/compliance/fiscal-year/lifecycle?fy=${targetFy}`);
      setFyLifecycle(data);
    } catch (err) {
      console.warn('Error loading FY lifecycle:', err);
    } finally {
      setLifecycleLoading(false);
    }
  };

  const handleTransitionStage = async () => {
    setStageTransitionSubmitting(true);
    setStageTransitionError(null);
    setStageTransitionSuccess(null);
    try {
      const res = await fetchApi('/api/v1/compliance/fiscal-year/transition-stage', {
        method: 'POST',
        body: JSON.stringify({
          fiscal_year: lifecycleFy,
          target_stage: selectedTargetStage,
          audit_closing_deadline: targetDeadline || undefined,
          notes: stageNotes || `Stage transitioned to ${selectedTargetStage}`
        })
      });
      setStageTransitionSuccess(res.message || 'Stage transitioned successfully!');
      await loadFyLifecycle(lifecycleFy);
      setTimeout(() => {
        setStageModalOpen(false);
        setStageTransitionSuccess(null);
        setStageNotes('');
      }, 1500);
    } catch (err: any) {
      setStageTransitionError(err.message || 'Failed to transition fiscal year stage.');
    } finally {
      setStageTransitionSubmitting(false);
    }
  };

  // --- Milestone 8.2 Handlers: Multi-Frequency GST Forecasting ---
  const loadGstForecast = async (
    fy?: string,
    freq?: string,
    q?: string,
    m?: number,
    turnover?: string
  ) => {
    setGstForecastLoading(true);
    try {
      const targetFy = fy || gstFy;
      const targetFreq = freq || gstFrequency;
      const targetQ = q || gstQuarter;
      const targetM = m !== undefined ? m : gstMonth;
      const turnoverNum = parseFloat(turnover || gstTurnover) || 0;

      let url = `/api/v1/compliance/gst/forecast?frequency=${targetFreq}&fy=${targetFy}`;
      if (targetFreq === 'quarterly') url += `&quarter=${targetQ}`;
      if (targetFreq === 'monthly') url += `&month=${targetM}`;
      if (targetFreq === 'composition') url += `&composition_turnover=${turnoverNum}`;

      const data = await fetchApi(url);
      setGstForecast(data);
    } catch (err) {
      console.warn('Error loading GST forecast:', err);
    } finally {
      setGstForecastLoading(false);
    }
  };

  const loadGstChallans = async (fy?: string) => {
    try {
      const targetFy = fy || gstFy;
      const data = await fetchApi(`/api/v1/compliance/gst/challans?fy=${targetFy}`);
      setGstChallansList(data.challans || []);
    } catch (err) {
      console.warn('Error loading GST challans:', err);
    }
  };

  const handleRecordGstChallan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gstChallanRef || !gstChallanCpin) return;
    setGstChallanSubmitting(true);
    setGstChallanErrorMsg(null);
    setGstChallanSuccessMsg(null);
    try {
      const amt = parseFloat(gstChallanAmount) || 0;
      let c_amt = 0;
      let s_amt = 0;
      let i_amt = 0;
      if (gstForecast?.net_cash_payable) {
        const net = gstForecast.net_cash_payable;
        if (net.igst > 0 && net.cgst === 0 && net.sgst === 0) {
          i_amt = amt;
        } else {
          c_amt = Math.round((amt / 2) * 100) / 100;
          s_amt = Math.round((amt - c_amt) * 100) / 100;
        }
      } else {
        c_amt = Math.round((amt / 2) * 100) / 100;
        s_amt = Math.round((amt - c_amt) * 100) / 100;
      }

      await fetchApi('/api/v1/compliance/gst/record-challan', {
        method: 'POST',
        body: JSON.stringify({
          fiscal_year: gstFy,
          return_period: gstFrequency === 'monthly' ? `M${gstMonth}` : gstFrequency === 'quarterly' ? gstQuarter : 'Annual',
          challan_reference: gstChallanRef,
          cpin: gstChallanCpin,
          cin: gstChallanCin || undefined,
          bank_name: gstChallanBank,
          payment_date: gstChallanDate,
          cgst_paid: c_amt,
          sgst_paid: s_amt,
          igst_paid: i_amt,
          cess_paid: 0,
          total_paid: amt
        })
      });
      setGstChallanSuccessMsg(`GST Challan recorded successfully! CPIN: ${gstChallanCpin}`);
      await Promise.all([
        loadGstForecast(gstFy, gstFrequency, gstQuarter, gstMonth, gstTurnover),
        loadGstChallans(gstFy)
      ]);
      setTimeout(() => {
        setGstChallanModalOpen(false);
        setGstChallanSuccessMsg(null);
        setGstChallanRef('');
        setGstChallanCpin('');
        setGstChallanCin('');
      }, 1500);
    } catch (err: any) {
      setGstChallanErrorMsg(err.message || 'Failed to record GST challan.');
    } finally {
      setGstChallanSubmitting(false);
    }
  };

  const handleOpenPmt06Packet = async () => {
    setPmt06Loading(true);
    setPmt06ModalOpen(true);
    try {
      const data = await fetchApi(`/api/v1/compliance/gst/pmt06-packet?fy=${gstFy}&quarter=${gstQuarter}`);
      setPmt06Data(data);
    } catch (err) {
      console.warn('Error loading PMT-06 packet:', err);
    } finally {
      setPmt06Loading(false);
    }
  };

  // --- Milestone 8.3 Handlers: Sovereign Statutory Dossier ---
  const loadDossierData = async (fy?: string) => {
    setDossierLoading(true);
    try {
      const targetFy = fy || dossierFy;
      const data = await fetchApi(`/api/v1/compliance/statutory-dossier/year-dossier?fy=${targetFy}`);
      setDossierData(data);
    } catch (err) {
      console.warn('Error loading statutory dossier:', err);
    } finally {
      setDossierLoading(false);
    }
  };

  const handleUploadDossier = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dossierUploadFile) return;
    setDossierUploadSubmitting(true);
    setDossierUploadError(null);
    setDossierUploadResult(null);

    try {
      const formData = new FormData();
      formData.append('file', dossierUploadFile);
      formData.append('fiscal_year', dossierFy);
      formData.append('form_type', dossierFormType);
      if (dossierSrn) formData.append('srn_or_ack', dossierSrn);
      if (dossierFilingDate) formData.append('filing_date_str', dossierFilingDate);

      const res = await fetchApi('/api/v1/compliance/statutory-dossier/upload', {
        method: 'POST',
        body: formData
      });

      setDossierUploadResult(res);
      await loadDossierData(dossierFy);
      if (!res.is_duplicate) {
        setTimeout(() => {
          setDossierUploadModalOpen(false);
          setDossierUploadFile(null);
          setDossierSrn('');
          setDossierUploadResult(null);
        }, 2000);
      }
    } catch (err: any) {
      setDossierUploadError(err.message || 'Failed to upload statutory filing.');
    } finally {
      setDossierUploadSubmitting(false);
    }
  };

  const handleStreamDocument = async (s3Key: string) => {
    if (!s3Key) return;
    setStreamingKey(s3Key);
    try {
      const res = await fetchRawApi(`/api/v1/compliance/statutory-dossier/stream?s3_key=${encodeURIComponent(s3Key)}`);
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = s3Key.split('/').pop() || 'statutory_return.pdf';
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      alert(`Failed to stream authentic document: ${err.message}`);
    } finally {
      setStreamingKey(null);
    }
  };

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

      const bridgeRes = await signHashViaBridge(dscPin, docSha256Hex);

      const sigAudit = {
        tokenLabel: bridgeRes.token_label || 'HYP 2003 Token',
        signatureHex: bridgeRes.signature_hex,
        sha256: docSha256Hex,
        timestamp: new Date().toISOString(),
        certSubject: `CN=${signerName}, OU=Director, O=${companyName}`
      };

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
                    CIN/LLPIN: {cin}
                  </span>
                )}
              </div>
              <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2.5 mt-2">
                <Scale className="w-7 h-7 text-sky-400" />
                Statutory Governance &amp; Multi-Entity Compliance Hub
              </h1>
              <p className="text-sm text-slate-400 mt-1">
                Companies Act 2013, LLP Act 2008, GSTR-2B Rule 36(4) Matching, and Section 40A(3) Watchdog
              </p>
            </div>
            <div className="flex items-center gap-3">
              <DSCBridgeWidget />
            </div>
          </div>

          {/* 3-STAGE HISTORICAL FY LIFECYCLE BANNER (MILESTONE 8.1) */}
          <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-3">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="p-2 rounded-lg bg-sky-500/10 border border-sky-500/30 text-sky-400">
                  <LockKeyhole className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-sm font-semibold text-white">
                      3-Stage Historical Fiscal Year Lifecycle &amp; Statutory Seal
                    </h2>
                    <select
                      value={lifecycleFy}
                      onChange={(e) => {
                        setLifecycleFy(e.target.value);
                        loadFyLifecycle(e.target.value);
                      }}
                      className="bg-slate-950 border border-slate-700 text-sky-300 text-xs rounded-md px-2 py-0.5 font-mono focus:outline-none"
                    >
                      <option value="2025-26">FY 2025-26 (AY 2026-27)</option>
                      <option value="2026-27">FY 2026-27 (AY 2027-28)</option>
                      <option value="2024-25">FY 2024-25 (AY 2025-26)</option>
                    </select>
                  </div>
                  <p className="text-xs text-slate-400">
                    Governed by Companies Act 2013 Sec 128/130 &amp; AS-5. Transition from Active Operations through Year-End Audit to Cryptographic Statutory Seal.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {fyLifecycle && (
                  <span className={`text-xs font-mono px-3 py-1.5 rounded-lg border font-semibold flex items-center gap-1.5 ${
                    fyLifecycle.closing_stage === 'statutory_sealed'
                      ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/40 shadow-sm'
                      : fyLifecycle.closing_stage === 'audit_closing_window'
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm'
                      : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-sm'
                  }`}>
                    {fyLifecycle.closing_stage === 'statutory_sealed' ? (
                      <>
                        <Lock className="w-3.5 h-3.5 text-indigo-400" /> STAGE 3: STATUTORY SEALED
                      </>
                    ) : fyLifecycle.closing_stage === 'audit_closing_window' ? (
                      <>
                        <Clock className="w-3.5 h-3.5 text-amber-400" /> STAGE 2: AUDIT &amp; FILING WINDOW
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> STAGE 1: ACTIVE FY
                      </>
                    )}
                  </span>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setSelectedTargetStage(
                      fyLifecycle?.closing_stage === 'active'
                        ? 'audit_closing_window'
                        : fyLifecycle?.closing_stage === 'audit_closing_window'
                        ? 'statutory_sealed'
                        : 'audit_closing_window'
                    );
                    setStageModalOpen(true);
                  }}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 flex items-center gap-1.5 transition-colors"
                >
                  <RefreshCw className="w-3.5 h-3.5 text-sky-400" /> Manage FY Stage
                </button>
              </div>
            </div>

            {/* Stepping Indicator */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-2 pt-2 border-t border-slate-800/80 font-mono text-[11px]">
              <div className={`p-2.5 rounded-lg border flex items-center gap-2 ${
                fyLifecycle?.closing_stage === 'active'
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300 font-semibold'
                  : 'bg-slate-950/60 border-slate-800 text-slate-400'
              }`}>
                <div className={`w-2 h-2 rounded-full ${fyLifecycle?.closing_stage === 'active' ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'}`} />
                <span>1. Active Operations (Unrestricted)</span>
              </div>

              <div className={`p-2.5 rounded-lg border flex items-center gap-2 ${
                fyLifecycle?.closing_stage === 'audit_closing_window'
                  ? 'bg-amber-500/10 border-amber-500/30 text-amber-300 font-semibold'
                  : 'bg-slate-950/60 border-slate-800 text-slate-400'
              }`}>
                <div className={`w-2 h-2 rounded-full ${fyLifecycle?.closing_stage === 'audit_closing_window' ? 'bg-amber-400 animate-pulse' : 'bg-slate-600'}`} />
                <span>2. Year-End Audit Window {fyLifecycle?.audit_closing_deadline ? `(Due ${fyLifecycle.audit_closing_deadline})` : '(Till 31/10)'}</span>
              </div>

              <div className={`p-2.5 rounded-lg border flex items-center gap-2 ${
                fyLifecycle?.closing_stage === 'statutory_sealed'
                  ? 'bg-indigo-500/10 border-indigo-500/30 text-indigo-300 font-semibold'
                  : 'bg-slate-950/60 border-slate-800 text-slate-400'
              }`}>
                <div className={`w-2 h-2 rounded-full ${fyLifecycle?.closing_stage === 'statutory_sealed' ? 'bg-indigo-400' : 'bg-slate-600'}`} />
                <span>3. Statutory Seal (Hard-Locked via AOC-4/ITR-6)</span>
              </div>
            </div>
          </div>

          {/* Navigation Tabs - Dynamically Adapted by Entity Type (Pvt Ltd / OPC / LLP) */}
          <div className="flex flex-wrap items-center gap-2 border-b border-slate-800 pb-3">
            {!isLLP && (
              <button
                onClick={() => setActiveTab('board_governance')}
                className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
                  activeTab === 'board_governance'
                    ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-sm'
                    : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white'
                }`}
              >
                <Scale className="w-4 h-4 text-sky-400" />
                {isOPC ? 'Section 122 Resolutions & SS-1 Minutes' : 'Companies Act 2013 & SS-1 Minutes'}
              </button>
            )}
            <button
              onClick={() => setActiveTab('gstr2b')}
              className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
                activeTab === 'gstr2b'
                  ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-sm'
                  : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white'
              }`}
            >
              <Receipt className="w-4 h-4 text-emerald-400" />
              GSTR-2B Monthly ITC Matching (Sec 16(2)(aa))
            </button>
            {isLLP && (
              <button
                onClick={() => setActiveTab('llp')}
                className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
                  activeTab === 'llp'
                    ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-sm'
                    : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white'
                }`}
              >
                <Building2 className="w-4 h-4 text-purple-400" />
                LLP Secretarial Suite (Form 11 &amp; Form 8)
              </button>
            )}
            <button
              onClick={() => setActiveTab('sec40a3')}
              className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
                activeTab === 'sec40a3'
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm'
                  : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white'
              }`}
            >
              <IndianRupee className="w-4 h-4 text-amber-400" />
              Section 40A(3) Cash Payment Watchdog
            </button>
            <button
              onClick={() => setActiveTab('advance_tax')}
              className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
                activeTab === 'advance_tax'
                  ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40 shadow-sm'
                  : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white'
              }`}
            >
              <TrendingUp className="w-4 h-4 text-rose-400" />
              Advance Tax Runway &amp; Cash Watchdog (Sec 208/211)
            </button>
            {!isLLP && (
              <button
                onClick={() => setActiveTab('statutory_baseline')}
                className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
                  activeTab === 'statutory_baseline'
                    ? 'bg-blue-500/20 text-blue-300 border border-blue-500/40 shadow-sm'
                    : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white'
                }`}
              >
                <Anchor className="w-4 h-4 text-blue-400" />
                Statutory Baseline &amp; Historical FY Seal (AOC-4/AS-5)
              </button>
            )}
            <button
              onClick={() => setActiveTab('gst_forecast')}
              className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
                activeTab === 'gst_forecast'
                  ? 'bg-teal-500/20 text-teal-300 border border-teal-500/40 shadow-sm'
                  : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white'
              }`}
            >
              <Coins className="w-4 h-4 text-teal-400" />
              GST Runway &amp; Forecast (Rule 88A)
            </button>
            <button
              onClick={() => setActiveTab('statutory_dossier')}
              className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
                activeTab === 'statutory_dossier'
                  ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 shadow-sm'
                  : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white'
              }`}
            >
              <FolderArchive className="w-4 h-4 text-indigo-400" />
              Sovereign Statutory Dossier (Year-to-Year)
            </button>
            <button
              onClick={() => setActiveTab('tds_compliance')}
              className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
                activeTab === 'tds_compliance'
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm'
                  : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white'
              }`}
            >
              <FileCheck className="w-4 h-4 text-amber-400" />
              TDS &amp; TCS Compliance (Challan 281 &amp; 26Q)
            </button>
            <button
              onClick={() => setActiveTab('fixed_assets')}
              className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
                activeTab === 'fixed_assets'
                  ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-sm'
                  : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white'
              }`}
            >
              <Building2 className="w-4 h-4 text-sky-400" />
              Schedule II Fixed Assets &amp; Depreciation
            </button>
            {!isLLP && (
              <button
                onClick={() => setActiveTab('mca_registers')}
                className={`px-4 py-2 rounded-lg text-xs font-semibold flex items-center gap-2 transition-all ${
                  activeTab === 'mca_registers'
                    ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-sm'
                    : 'bg-slate-900 text-slate-400 border border-slate-800 hover:text-white'
                }`}
              >
                <Users className="w-4 h-4 text-purple-400" />
                MCA Statutory Registers (MGT-1, MBP-1/2/4, SH-1)
              </button>
            )}
          </div>

          {/* TAB 1: BOARD GOVERNANCE & DOCUMENT ASSEMBLY */}
          {activeTab === 'board_governance' && (
            <div className="space-y-8">
              {isOPC && (
                <div className="p-4 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-300 text-xs flex items-start gap-3">
                  <ShieldCheck className="w-5 h-5 shrink-0 text-sky-400 mt-0.5" />
                  <div className="space-y-1">
                    <div className="font-bold flex items-center gap-2 text-white">
                      Companies Act 2013 Section 122 Exemption Active ({companyName})
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-sky-500/20 text-sky-300 border border-sky-500/40 font-mono">
                        OPC Sole Director
                      </span>
                    </div>
                    <p className="text-slate-300 leading-relaxed">
                      Under Section 122(3) &amp; 122(4) of the Companies Act, 2013, an OPC having a single director is legally exempt from the mandatory quarterly Board Meeting and Quorum requirements under Sections 173 and 174. A resolution recorded in the minute book and signed by the sole director serves as deemed valid minutes.
                    </p>
                  </div>
                </div>
              )}
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
                    isOPC
                      ? 'bg-sky-500/20 text-sky-300 border-sky-500/30'
                      : bmIsOverdue
                      ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                      : bmDaysRemaining <= 20
                      ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                      : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                  }`}>
                    {isOPC
                      ? 'Exempt u/s 122 (Sole Director OPC)'
                      : bmIsOverdue
                      ? `Overdue by ${Math.abs(bmDaysRemaining)} Days (Statutory Breach)`
                      : `${bmDaysRemaining} Days Remaining (${bmDaysRemaining <= 20 ? 'Warning Active' : 'Compliant'})`}
                  </span>
                </div>

                <p className="text-xs text-slate-300">
                  {isOPC
                    ? 'Section 122(3) & 122(4) of the Companies Act 2013: An OPC with a single director is exempt from the requirement of holding quarterly Board Meetings under Section 173.'
                    : 'Under Section 173(1) of the Companies Act 2013, not more than 120 days shall intervene between two consecutive Board Meetings. Warning triggers when less than 20 days remain; statutory violations accrue ₹100/day penalties.'}
                </p>

                <div className="space-y-1.5 font-mono text-xs">
                  <div className="w-full bg-slate-800 rounded-full h-3.5 overflow-hidden p-0.5 border border-slate-700">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        isOPC
                          ? 'bg-sky-500'
                          : bmIsOverdue
                          ? 'bg-rose-500'
                          : bmDaysRemaining <= 20
                          ? 'bg-amber-500'
                          : 'bg-emerald-500'
                      }`}
                      style={{ width: `${isOPC ? 100 : bmPercentage}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[11px] text-slate-400">
                    <span>Start: Day 0</span>
                    <span className={isOPC ? 'text-sky-300 font-semibold' : bmIsOverdue ? 'text-rose-400 font-semibold' : bmDaysRemaining <= 20 ? 'text-amber-400 font-semibold' : 'text-emerald-400 font-semibold'}>
                      {isOPC ? 'Section 122 Sole Director Exemption Active' : `Current: ${bmElapsedDays} Days Elapsed ${bmIsOverdue ? '(Violating Section 173)' : ''}`}
                    </span>
                    <span>{isOPC ? 'Deemed Compliant' : `Max: 120 Days Limit ${bmDueDate ? `(Due: ${bmDueDate})` : ''}`}</span>
                  </div>
                </div>
              </div>

              {/* Executive Tax & GST Forecast Command Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Advance Tax Runway Card */}
                <div className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 shadow-lg space-y-4 flex flex-col justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <TrendingUp className="w-4 h-4 text-rose-400" />
                        <h3 className="text-sm font-bold text-white">Advance Tax Runway (Sec 208/211)</h3>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 border border-rose-500/20">
                        {advanceTaxForecast?.financial_year || 'FY 2026-27'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400">
                      Quarterly corporate income tax installments under Section 211 with Section 234C safe harbor monitoring.
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-3 py-2 border-y border-slate-800/80 font-mono text-xs">
                    <div>
                      <span className="text-[10px] text-slate-500 block">Projected Annual PBT</span>
                      <span className="text-sm font-bold text-white">
                        ₹{(advanceTaxForecast?.projected_annual_profit_pbt || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 block">Est. Annual Tax (22%+Cess)</span>
                      <span className="text-sm font-bold text-rose-400">
                        ₹{(advanceTaxForecast?.estimated_annual_tax_liability || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 block">Upcoming Installment</span>
                      <span className="text-xs font-semibold text-amber-300">
                        {advanceTaxForecast?.upcoming_quarter || 'Q3'} (Due {advanceTaxForecast?.upcoming_due_date || '15/12/2026'})
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 block">Amount Payable</span>
                      <span className="text-xs font-bold text-white">
                        ₹{(advanceTaxForecast?.upcoming_installment_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[11px] text-emerald-400 font-medium flex items-center gap-1">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      {advanceTaxForecast?.is_safe_harbor_satisfied ? 'Safe Harbor Active' : 'Installments Scheduled'}
                    </span>
                    <button
                      type="button"
                      onClick={() => setActiveTab('advance_tax')}
                      className="px-3 py-1.5 bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 text-xs font-semibold rounded-lg border border-rose-500/30 flex items-center gap-1.5 transition-colors"
                    >
                      <span>Full Tax Runway</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* GST Runway & Forecast Card */}
                <div className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 shadow-lg space-y-4 flex flex-col justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <Coins className="w-4 h-4 text-teal-400" />
                        <h3 className="text-sm font-bold text-white">GST Runway &amp; Cash Challan (Rule 88A)</h3>
                      </div>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-teal-500/10 text-teal-300 border border-teal-500/20">
                        {gstForecast?.frequency ? `${gstForecast.frequency.toUpperCase()} FILING` : 'MONTHLY FILING'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400">
                      Multi-frequency GST liability forecast, Rule 88A ITC set-off hierarchy, and PMT-06 cash challan estimation.
                    </p>
                  </div>

                  <div className="grid grid-cols-2 gap-3 py-2 border-y border-slate-800/80 font-mono text-xs">
                    <div>
                      <span className="text-[10px] text-slate-500 block">Gross Output GST</span>
                      <span className="text-sm font-bold text-white">
                        ₹{(gstForecast?.output_gst_breakup?.total_output_tax || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 block">Eligible GSTR-2B ITC</span>
                      <span className="text-sm font-bold text-emerald-400">
                        ₹{(gstForecast?.available_itc?.total_itc || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 block">Cash Challan Required</span>
                      <span className="text-xs font-bold text-teal-300">
                        ₹{(gstForecast?.cash_challan_required_pmt06 || gstForecast?.net_gst_liability_payable || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-500 block">Filing Due Date</span>
                      <span className="text-xs font-semibold text-slate-300">
                        20th of Upcoming Month
                      </span>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[11px] text-slate-400">
                      Challans Vaulted: <strong className="text-white font-mono">{gstChallansList.length}</strong>
                    </span>
                    <button
                      type="button"
                      onClick={() => setActiveTab('gst_forecast')}
                      className="px-3 py-1.5 bg-teal-500/15 hover:bg-teal-500/25 text-teal-300 text-xs font-semibold rounded-lg border border-teal-500/30 flex items-center gap-1.5 transition-colors"
                    >
                      <span>Full GST Forecast</span>
                      <ArrowRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>

              {/* Statutory Calendar Grid */}
              <div className="space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <h3 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-sky-400" />
                    Statutory Compliance Radar for {companyName}
                  </h3>
                  <div className="flex items-center gap-1.5 bg-slate-900 p-1 rounded-lg border border-slate-800 text-xs font-mono">
                    <button
                      type="button"
                      onClick={() => setStatutoryEventFyFilter('all')}
                      className={`px-2.5 py-1 rounded text-[11px] transition ${
                        statutoryEventFyFilter === 'all'
                          ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 font-semibold'
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      All Milestones ({events.length})
                    </button>
                    <button
                      type="button"
                      onClick={() => setStatutoryEventFyFilter('2026-27')}
                      className={`px-2.5 py-1 rounded text-[11px] transition ${
                        statutoryEventFyFilter === '2026-27'
                          ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 font-semibold'
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      FY 2026-27 (Current)
                    </button>
                    <button
                      type="button"
                      onClick={() => setStatutoryEventFyFilter('2025-26')}
                      className={`px-2.5 py-1 rounded text-[11px] transition ${
                        statutoryEventFyFilter === '2025-26'
                          ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 font-semibold'
                          : 'text-slate-400 hover:text-white'
                      }`}
                    >
                      FY 2025-26
                    </button>
                  </div>
                </div>

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
                    {events
                      .filter((ev) => statutoryEventFyFilter === 'all' || ev.fiscal_year === statutoryEventFyFilter)
                      .map((ev) => (
                      <div
                        key={ev.id}
                        className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 shadow-md space-y-3 flex flex-col justify-between"
                      >
                        <div>
                          <div className="flex justify-between items-start gap-2 mb-1">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="text-[10px] font-mono text-slate-400">{ev.statutory_ref}</span>
                              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-sky-300 border border-slate-700">
                                FY {ev.fiscal_year || '2026-27'}
                              </span>
                            </div>
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
                        <label className="text-slate-400 block mb-1 flex items-center justify-between">
                          <span>Director DIN:</span>
                          <span className="text-[10px] text-sky-400 font-mono">🔒 Verified DIR-3</span>
                        </label>
                        <input
                          type="text"
                          value={directorDin}
                          readOnly
                          placeholder="Verified 8-digit DIN"
                          className="w-full bg-slate-950/80 border border-slate-800 rounded-lg px-3 py-2 text-white font-mono cursor-not-allowed opacity-90"
                        />
                      </div>
                    </div>

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

                    <div className="p-5 rounded-lg bg-slate-950 border border-slate-800/80 font-mono text-[11px] text-slate-300 space-y-3 max-h-[460px] overflow-y-auto leading-relaxed">
                      <div className="text-center pb-3 border-b border-slate-800">
                        <p className="font-bold text-white text-xs uppercase">{companyName}</p>
                        <p className="text-[10px] text-slate-400">
                          {cin ? `CIN/LLPIN: ${cin} | ` : ''}Regd. Office: {venue}
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

                      <div className="pt-2 border-t border-slate-800/60">
                        <p className="font-bold text-white mb-1.5">2. AGENDA ITEMS TRANSACTED:</p>
                        <div className="space-y-1 text-slate-300">
                          {agendaItems.map((ag, i) => (
                            <p key={i}>{i + 1}. {ag}</p>
                          ))}
                        </div>
                      </div>

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
            </div>
          )}

          {/* TAB 2: GSTR-2B MONTHLY ITC RECONCILIATION */}
          {activeTab === 'gstr2b' && (
            <div className="space-y-6">
              {/* Informational Statutory Header */}
              <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-3">
                <div className="flex items-center gap-2.5">
                  <Receipt className="w-5 h-5 text-emerald-400" />
                  <h2 className="text-base font-semibold text-white">
                    GSTR-2B Automated ITC Reconciliation Engine
                  </h2>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Section 16(2)(aa) of the CGST Act, 2017 prohibits claiming Input Tax Credit (ITC) unless the invoice is furnished by the supplier in GSTR-1/IFF and appears in your GSTR-2B.
                  Upload your monthly GSTR-2B JSON to automatically reconcile against recorded expenses, detect Section 17(5) blocked credits, identify missing supplier filings, and uncover unclaimed ITC.
                </p>
              </div>

              {/* Upload Card */}
              <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800 shadow-md">
                <form onSubmit={handleGstr2bUpload} className="space-y-4">
                  <div className="border-2 border-dashed border-slate-700 hover:border-emerald-500/50 rounded-xl p-6 text-center bg-slate-950/50 transition-colors">
                    <Upload className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                    <p className="text-xs font-medium text-slate-200">
                      Upload GSTR-2B Monthly JSON Statement
                    </p>
                    <p className="text-[11px] text-slate-500 mt-1">
                      Supports official GSTN portal JSON exports containing B2B invoices and CDNR credit notes
                    </p>
                    <input
                      type="file"
                      accept=".json"
                      onChange={(e) => setGstr2bFile(e.target.files?.[0] || null)}
                      className="mt-3 block mx-auto text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-emerald-600 file:text-white hover:file:bg-emerald-500 cursor-pointer"
                    />
                    {gstr2bFile && (
                      <p className="text-xs text-emerald-400 font-mono mt-2">
                        Selected: {gstr2bFile.name} ({(gstr2bFile.size / 1024).toFixed(1)} KB)
                      </p>
                    )}
                  </div>

                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
                    <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-300 select-none">
                      <input
                        type="checkbox"
                        checked={autoUpdateItc}
                        onChange={(e) => setAutoUpdateItc(e.target.checked)}
                        className="rounded border-slate-700 bg-slate-900 text-emerald-500 focus:ring-0"
                      />
                      <span>Auto-mark verified matching book records as eligible ITC under Section 16(2)(aa)</span>
                    </label>

                    <button
                      type="submit"
                      disabled={gstr2bLoading || !gstr2bFile}
                      className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-600 text-white font-semibold rounded-lg text-xs transition-colors flex items-center justify-center gap-2 shadow"
                    >
                      {gstr2bLoading ? (
                        <>
                          <RefreshCw className="w-4 h-4 animate-spin" /> Cross-Reconciling Books vs 2B...
                        </>
                      ) : (
                        <>
                          <CheckCircle className="w-4 h-4" /> Run Statutory Reconciliation
                        </>
                      )}
                    </button>
                  </div>

                  {gstr2bError && (
                    <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
                      <AlertCircle className="w-4 h-4 shrink-0" />
                      <span>{gstr2bError}</span>
                    </div>
                  )}
                </form>
              </div>

              {/* Reconciled Output Report */}
              {gstr2bReport && (
                <div className="space-y-6">
                  {/* KPI Summary Cards */}
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                    <div className="p-4 rounded-xl bg-slate-900/80 border border-emerald-500/30">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] text-slate-400">Matched ITC</span>
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      </div>
                      <p className="text-xl font-bold text-white mt-1">
                        {gstr2bReport.reconciliation_summary?.matched_count || 0}
                      </p>
                      <p className="text-[10px] text-emerald-400 font-mono mt-0.5">
                        ₹{(gstr2bReport.reconciliation_summary?.matched_tax_amount_inr || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-slate-900/80 border border-amber-500/30">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] text-slate-400">Tax Mismatch</span>
                        <AlertTriangle className="w-4 h-4 text-amber-400" />
                      </div>
                      <p className="text-xl font-bold text-white mt-1">
                        {gstr2bReport.reconciliation_summary?.tax_mismatch_count || 0}
                      </p>
                      <p className="text-[10px] text-amber-400 font-mono mt-0.5">
                        Variance &gt; ₹2.00
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-slate-900/80 border border-sky-500/30">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] text-slate-400">Unclaimed ITC</span>
                        <Coins className="w-4 h-4 text-sky-400" />
                      </div>
                      <p className="text-xl font-bold text-white mt-1">
                        {gstr2bReport.reconciliation_summary?.missing_in_books_count || 0}
                      </p>
                      <p className="text-[10px] text-sky-400 font-mono mt-0.5">
                        ₹{(gstr2bReport.reconciliation_summary?.unclaimed_tax_opportunity_inr || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-slate-900/80 border border-rose-500/30">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] text-slate-400">Missing in 2B</span>
                        <ShieldAlert className="w-4 h-4 text-rose-400" />
                      </div>
                      <p className="text-xl font-bold text-white mt-1">
                        {gstr2bReport.reconciliation_summary?.missing_in_2b_count || 0}
                      </p>
                      <p className="text-[10px] text-rose-400 font-mono mt-0.5">
                        Supplier Not Filed
                      </p>
                    </div>

                    <div className="p-4 rounded-xl bg-slate-900/80 border border-purple-500/30">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] text-slate-400">Blocked ITC</span>
                        <Lock className="w-4 h-4 text-purple-400" />
                      </div>
                      <p className="text-xl font-bold text-white mt-1">
                        {gstr2bReport.reconciliation_summary?.blocked_credit_count || 0}
                      </p>
                      <p className="text-[10px] text-purple-400 font-mono mt-0.5">
                        Sec 17(5) Ineligible
                      </p>
                    </div>
                  </div>

                  {/* Filter Tabs & Data Table */}
                  <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800 space-y-4">
                    <div className="flex flex-wrap items-center gap-2 border-b border-slate-800 pb-3">
                      {(['all', 'matched', 'tax_mismatches', 'missing_in_books', 'missing_in_2b', 'blocked_credit'] as const).map((filter) => (
                        <button
                          key={filter}
                          onClick={() => setGstr2bFilter(filter)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-colors ${
                            gstr2bFilter === filter
                              ? 'bg-slate-800 text-white border border-slate-600'
                              : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          {filter.replace(/_/g, ' ')}
                        </button>
                      ))}
                    </div>

                    {/* Table View */}
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs font-mono">
                        <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800">
                          <tr>
                            <th className="p-3">Supplier GSTIN</th>
                            <th className="p-3">Invoice / Doc #</th>
                            <th className="p-3">Category / Details</th>
                            <th className="p-3 text-right">Total (₹)</th>
                            <th className="p-3 text-right">Tax (₹)</th>
                            <th className="p-3">Reconciliation Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-800/60">
                          {/* Matched Rows */}
                          {(gstr2bFilter === 'all' || gstr2bFilter === 'matched') &&
                            gstr2bReport.matched_invoices?.map((row: any, i: number) => (
                              <tr key={`m-${i}`} className="hover:bg-slate-950/40">
                                <td className="p-3 text-slate-300 font-semibold">{row.supplier_gstin}</td>
                                <td className="p-3 text-white">{row.invoice_number}</td>
                                <td className="p-3 text-slate-400">{row.merchant_name || 'Standard Vendor'}</td>
                                <td className="p-3 text-right text-slate-300">₹{parseFloat(row.total_value).toFixed(2)}</td>
                                <td className="p-3 text-right text-emerald-400">₹{parseFloat(row.tax_amount).toFixed(2)}</td>
                                <td className="p-3">
                                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                    MATCHED (SEC 16(2)(aa))
                                  </span>
                                </td>
                              </tr>
                            ))}

                          {/* Tax Mismatch Rows */}
                          {(gstr2bFilter === 'all' || gstr2bFilter === 'tax_mismatches') &&
                            gstr2bReport.tax_mismatches?.map((row: any, i: number) => (
                              <tr key={`tm-${i}`} className="hover:bg-slate-950/40">
                                <td className="p-3 text-slate-300 font-semibold">{row.supplier_gstin}</td>
                                <td className="p-3 text-white">{row.invoice_number}</td>
                                <td className="p-3 text-amber-400 text-[11px]">{row.message}</td>
                                <td className="p-3 text-right text-slate-300">₹{parseFloat(row.gstr2b_total).toFixed(2)}</td>
                                <td className="p-3 text-right text-amber-400">₹{parseFloat(row.gstr2b_tax).toFixed(2)}</td>
                                <td className="p-3">
                                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                                    TAX MISMATCH (₹{parseFloat(row.tax_variance).toFixed(2)})
                                  </span>
                                </td>
                              </tr>
                            ))}

                          {/* Missing in Books (Unclaimed Opportunity) */}
                          {(gstr2bFilter === 'all' || gstr2bFilter === 'missing_in_books') &&
                            gstr2bReport.missing_in_books?.map((row: any, i: number) => (
                              <tr key={`mb-${i}`} className="hover:bg-slate-950/40">
                                <td className="p-3 text-slate-300 font-semibold">{row.supplier_gstin}</td>
                                <td className="p-3 text-white">{row.invoice_number}</td>
                                <td className="p-3 text-sky-400 text-[11px]">{row.opportunity}</td>
                                <td className="p-3 text-right text-slate-300">₹{parseFloat(row.total_value).toFixed(2)}</td>
                                <td className="p-3 text-right text-sky-400">₹{parseFloat(row.tax_amount).toFixed(2)}</td>
                                <td className="p-3">
                                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/30">
                                    UNCLAIMED ITC IN 2B
                                  </span>
                                </td>
                              </tr>
                            ))}

                          {/* Missing in 2B (Ineligible) */}
                          {(gstr2bFilter === 'all' || gstr2bFilter === 'missing_in_2b') &&
                            gstr2bReport.missing_in_2b?.map((row: any, i: number) => (
                              <tr key={`m2-${i}`} className="hover:bg-slate-950/40">
                                <td className="p-3 text-slate-300 font-semibold">{row.supplier_gstin || 'N/A'}</td>
                                <td className="p-3 text-white">{row.invoice_number || 'N/A'}</td>
                                <td className="p-3 text-rose-400 text-[11px]">{row.statutory_warning}</td>
                                <td className="p-3 text-right text-slate-300">₹{parseFloat(row.total_amount_in_books).toFixed(2)}</td>
                                <td className="p-3 text-right text-rose-400">₹{parseFloat(row.tax_amount_in_books).toFixed(2)}</td>
                                <td className="p-3">
                                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                                    SUPPLIER NOT FILED
                                  </span>
                                </td>
                              </tr>
                            ))}

                          {/* Blocked Credit Section 17(5) */}
                          {(gstr2bFilter === 'all' || gstr2bFilter === 'blocked_credit') &&
                            gstr2bReport.blocked_credit?.map((row: any, i: number) => (
                              <tr key={`bc-${i}`} className="hover:bg-slate-950/40">
                                <td className="p-3 text-slate-300 font-semibold">{row.supplier_gstin}</td>
                                <td className="p-3 text-white">{row.invoice_number}</td>
                                <td className="p-3 text-purple-400 text-[11px]">{row.reason}</td>
                                <td className="p-3 text-right text-slate-300">₹{parseFloat(row.total_value).toFixed(2)}</td>
                                <td className="p-3 text-right text-purple-400">₹{parseFloat(row.tax_amount_in_2b).toFixed(2)}</td>
                                <td className="p-3">
                                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-purple-500/20 text-purple-300 border border-purple-500/30">
                                    BLOCKED CREDIT (SEC 17(5))
                                  </span>
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: LLP SECRETARIAL SUITE */}
          {activeTab === 'llp' && (
            <div className="space-y-6">
              {/* Informational Header with Year Picker */}
              <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2.5">
                    <Building2 className="w-5 h-5 text-purple-400" />
                    <h2 className="text-base font-semibold text-white">
                      Limited Liability Partnership (LLP) Statutory Suite
                    </h2>
                  </div>
                  <p className="text-xs text-slate-300">
                    Governed by the LLP Act 2008, LLP Rules 2009, and ICSI Secretarial Standards for Partners Meetings.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <label className="text-xs text-slate-400">Fiscal Year:</label>
                  <select
                    value={llpYear}
                    onChange={(e) => {
                      setLlpYear(e.target.value);
                      loadLlpData(e.target.value);
                    }}
                    className="bg-slate-950 border border-slate-700 text-white rounded-lg px-3 py-1.5 text-xs font-mono"
                  >
                    <option value="2025-26">FY 2025-26</option>
                    <option value="2026-27">FY 2026-27</option>
                    <option value="2024-25">FY 2024-25</option>
                  </select>
                  <button
                    onClick={() => loadLlpData(llpYear)}
                    className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg"
                    title="Refresh"
                  >
                    <RefreshCw className={`w-4 h-4 ${llpLoading ? 'animate-spin' : ''}`} />
                  </button>
                </div>
              </div>

              {/* Form 11 and Form 8 Cards */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Form 11: Annual Return of LLP */}
                <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800 shadow-lg space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div className="flex items-center gap-2">
                      <FileSpreadsheet className="w-5 h-5 text-sky-400" />
                      <div>
                        <h3 className="text-sm font-semibold text-white">Form 11: Annual Return of LLP</h3>
                        <p className="text-[11px] text-slate-400">Rule 25(1) of LLP Rules, 2009 • Due: May 30</p>
                      </div>
                    </div>
                    {form11Packet?.statutory_thresholds?.cs_certification_required ? (
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30 font-mono">
                        CS Certification Mandated (Rule 25(2))
                      </span>
                    ) : (
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono">
                        CS Certification Exempt
                      </span>
                    )}
                  </div>

                  <div className="space-y-3 text-xs">
                    <div className="grid grid-cols-2 gap-3 bg-slate-950 p-3 rounded-lg border border-slate-800 font-mono">
                      <div>
                        <span className="text-slate-500 block text-[10px]">Total Contribution</span>
                        <span className="text-white font-semibold">
                          ₹{parseFloat(form11Packet?.partners_summary?.total_contribution_inr || '0').toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 block text-[10px]">Annual Turnover</span>
                        <span className="text-white font-semibold">
                          ₹{parseFloat(form11Packet?.financial_indicators?.turnover_inr || '0').toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </span>
                      </div>
                    </div>

                    <div>
                      <h4 className="text-slate-300 font-semibold mb-2">Designated Partners &amp; Partners Roster:</h4>
                      <div className="space-y-1.5 max-h-36 overflow-y-auto">
                        {form11Packet?.partners_summary?.partners_roster?.map((p: any, idx: number) => (
                          <div key={idx} className="flex items-center justify-between bg-slate-950/60 p-2 rounded border border-slate-800 text-[11px]">
                            <div>
                              <span className="text-white font-medium">{p.name}</span>
                              <span className="text-slate-500 ml-1.5 font-mono">({p.is_designated ? 'Designated Partner' : 'Partner'})</span>
                            </div>
                            <span className="font-mono text-sky-400">DPIN: {p.dpin}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <button
                      onClick={() => {
                        const blob = new Blob([JSON.stringify(form11Packet, null, 2)], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `LLP_Form11_${companyName.replace(/\s+/g, '_')}_${llpYear}.json`;
                        a.click();
                      }}
                      className="w-full py-2 bg-sky-600 hover:bg-sky-500 text-white font-semibold rounded-lg text-xs transition-colors flex items-center justify-center gap-1.5"
                    >
                      <Download className="w-3.5 h-3.5" /> Download Form 11 JSON Packet
                    </button>
                  </div>
                </div>

                {/* Form 8: Statement of Account & Solvency */}
                <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800 shadow-lg space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div className="flex items-center gap-2">
                      <FileCheck className="w-5 h-5 text-emerald-400" />
                      <div>
                        <h3 className="text-sm font-semibold text-white">Form 8: Statement of Account &amp; Solvency</h3>
                        <p className="text-[11px] text-slate-400">Rule 24 of LLP Rules, 2009 • Due: October 30</p>
                      </div>
                    </div>
                    {form8Packet?.audit_requirement?.statutory_audit_mandated ? (
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30 font-mono">
                        CA Audit Mandated (Rule 24(8))
                      </span>
                    ) : (
                      <span className="px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-mono">
                        Audit Exempt u/r 24(8)
                      </span>
                    )}
                  </div>

                  <div className="space-y-3 text-xs">
                    <div className="p-3 bg-emerald-950/20 border border-emerald-800/40 rounded-lg text-[11px] text-slate-300 leading-relaxed font-mono">
                      <span className="text-emerald-400 font-semibold block mb-1">Part A: Statement of Solvency Declaration</span>
                      {form8Packet?.solvency_declaration?.declaration_text || 'The Designated Partners declare solvency under Rule 24 of LLP Rules, 2009.'}
                    </div>

                    <div className="grid grid-cols-2 gap-3 bg-slate-950 p-3 rounded-lg border border-slate-800 font-mono">
                      <div>
                        <span className="text-slate-500 block text-[10px]">Total Assets (Part B)</span>
                        <span className="text-white font-semibold">
                          ₹{parseFloat(form8Packet?.part_b_statement_of_accounts?.statement_of_assets_and_liabilities?.total_assets_inr || '0').toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-500 block text-[10px]">Net Surplus / (Deficit)</span>
                        <span className="text-emerald-400 font-semibold">
                          ₹{parseFloat(form8Packet?.part_b_statement_of_accounts?.income_and_expenditure_statement?.net_profit_or_loss_inr || '0').toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </span>
                      </div>
                    </div>

                    <button
                      onClick={() => {
                        const blob = new Blob([JSON.stringify(form8Packet, null, 2)], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `LLP_Form8_${companyName.replace(/\s+/g, '_')}_${llpYear}.json`;
                        a.click();
                      }}
                      className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold rounded-lg text-xs transition-colors flex items-center justify-center gap-1.5"
                    >
                      <Download className="w-3.5 h-3.5" /> Download Form 8 JSON Packet
                    </button>
                  </div>
                </div>
              </div>

              {/* Partners Resolution Assembly */}
              <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800 shadow-lg space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-purple-400" />
                    <h3 className="text-sm font-semibold text-white">Designated Partners Meeting Resolution Assembly</h3>
                  </div>
                  <span className="text-[10px] text-slate-500 font-mono">ICSI Secretarial Standards</span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className="text-slate-400 block text-xs mb-1">Select Resolution Type:</label>
                    <select
                      value={llpResolutionType}
                      onChange={(e) => setLlpResolutionType(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-700 text-white rounded-lg px-3 py-2 text-xs"
                    >
                      <option value="approval_of_accounts">Approval of Annual Accounts &amp; Solvency (Form 8)</option>
                      <option value="partner_appointment">Appointment / Admission of Designated Partner</option>
                      <option value="banking_mandate">Authorization of Banking Powers &amp; Mandates</option>
                    </select>
                  </div>

                  <div className="flex items-end">
                    <button
                      onClick={handleGenerateLlpResolution}
                      disabled={llpResolutionLoading}
                      className="w-full py-2 px-4 bg-purple-600 hover:bg-purple-500 text-white font-semibold rounded-lg text-xs transition-colors flex items-center justify-center gap-2"
                    >
                      {llpResolutionLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <PenTool className="w-4 h-4" />}
                      Compile Formal Resolution Draft
                    </button>
                  </div>
                </div>

                {llpResolutionResult && (
                  <div className="p-4 bg-slate-950 rounded-lg border border-slate-800 font-mono text-xs text-slate-300 space-y-2 whitespace-pre-wrap leading-relaxed">
                    <p className="font-bold text-white text-sm pb-1 border-b border-slate-800">
                      {llpResolutionResult.title}
                    </p>
                    <p>{llpResolutionResult.resolution_text}</p>
                    <div className="pt-2 border-t border-slate-800/80 text-[11px] text-slate-400">
                      Signatures mandated: {llpResolutionResult.signers?.map((s: any) => `${s.name} (DPIN: ${s.dpin})`).join(', ')}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 4: SECTION 40A(3) CASH PAYMENT WATCHDOG */}
          {activeTab === 'sec40a3' && (
            <div className="space-y-6">
              {/* Informational Header */}
              <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2.5">
                    <IndianRupee className="w-5 h-5 text-amber-400" />
                    <h2 className="text-base font-semibold text-white">
                      Section 40A(3) Real-Time Cash Payment Watchdog
                    </h2>
                  </div>
                  <p className="text-xs text-slate-300">
                    Income-tax Act, 1961 aggregate daily threshold: ₹10,000 per person per day (₹35,000 for plying, hiring or leasing goods carriages).
                    100% of aggregate expenditures exceeding limits are disallowed from business profits.
                  </p>
                </div>

                <div className="flex items-center gap-2">
                  <label className="text-xs text-slate-400">Fiscal Year:</label>
                  <select
                    value={sec40a3Year}
                    onChange={(e) => {
                      setSec40a3Year(e.target.value);
                      loadSec40a3Audit(e.target.value);
                    }}
                    className="bg-slate-950 border border-slate-700 text-white rounded-lg px-3 py-1.5 text-xs font-mono"
                  >
                    <option value="2025-26">FY 2025-26</option>
                    <option value="2026-27">FY 2026-27</option>
                    <option value="2024-25">FY 2024-25</option>
                  </select>
                  <button
                    onClick={() => loadSec40a3Audit(sec40a3Year)}
                    className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg"
                    title="Refresh"
                  >
                    <RefreshCw className={`w-4 h-4 ${sec40a3AuditLoading ? 'animate-spin' : ''}`} />
                  </button>
                </div>
              </div>

              {/* Two Column Layout: Interactive Evaluator & Form 3CD Clause 21(d) Summary */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Pre-Flight Cash Payment Tester (5 cols) */}
                <div className="lg:col-span-5 p-6 rounded-xl bg-slate-900/60 border border-slate-800 shadow-lg space-y-4">
                  <div className="flex items-center gap-2 border-b border-slate-800 pb-3">
                    <ShieldAlert className="w-5 h-5 text-amber-400" />
                    <h3 className="text-sm font-semibold text-white">Pre-Flight Daily Cash Check</h3>
                  </div>

                  <form onSubmit={handleEvaluateCandidateCash} className="space-y-3 text-xs">
                    <div>
                      <label className="text-slate-400 block mb-1">Payment Date:</label>
                      <input
                        type="date"
                        value={testDate}
                        onChange={(e) => setTestDate(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
                      />
                    </div>

                    <div>
                      <label className="text-slate-400 block mb-1">Payee / Vendor Name:</label>
                      <input
                        type="text"
                        value={testVendor}
                        onChange={(e) => setTestVendor(e.target.value)}
                        placeholder="e.g. Metro Supplies &amp; Hardware"
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white"
                        required
                      />
                    </div>

                    <div>
                      <label className="text-slate-400 block mb-1">Proposed Cash Amount (₹):</label>
                      <input
                        type="number"
                        step="0.01"
                        value={testAmount}
                        onChange={(e) => setTestAmount(e.target.value)}
                        placeholder="e.g. 12000.00"
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
                        required
                      />
                    </div>

                    <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-300 select-none py-1">
                      <input
                        type="checkbox"
                        checked={testGoodsCarriage}
                        onChange={(e) => setTestGoodsCarriage(e.target.checked)}
                        className="rounded border-slate-700 bg-slate-900 text-amber-500 focus:ring-0"
                      />
                      <span>Payment for goods carriage / freight (Threshold elevated to ₹35,000)</span>
                    </label>

                    <button
                      type="submit"
                      disabled={testLoading}
                      className="w-full py-2.5 bg-amber-600 hover:bg-amber-500 text-white font-semibold rounded-lg text-xs transition-colors flex items-center justify-center gap-2"
                    >
                      {testLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                      Check Against Live Expenditures
                    </button>
                  </form>

                  {testResult && (
                    <div className={`p-4 rounded-lg border font-mono text-xs space-y-1.5 ${
                      testResult.is_violation
                        ? 'bg-rose-950/30 border-rose-500/40 text-rose-300'
                        : 'bg-emerald-950/30 border-emerald-500/40 text-emerald-300'
                    }`}>
                      <div className="flex items-center justify-between font-bold">
                        <span>Status: {testResult.status}</span>
                        <span>Limit: ₹{parseFloat(testResult.applicable_limit_inr).toFixed(2)}</span>
                      </div>
                      <p>Prior Cash Spent Today: ₹{parseFloat(testResult.existing_cash_today_inr).toFixed(2)}</p>
                      <p>New Proposed Cash: ₹{parseFloat(testResult.new_payment_inr).toFixed(2)}</p>
                      <p className="font-bold border-t border-slate-800/60 pt-1">
                        Aggregate Daily Total: ₹{parseFloat(testResult.aggregated_daily_cash_inr).toFixed(2)}
                      </p>
                      {testResult.disallowed_amount_inr > 0 && (
                        <p className="text-rose-400 font-bold">
                          Statutory Disallowance: ₹{parseFloat(testResult.disallowed_amount_inr).toFixed(2)}
                        </p>
                      )}
                      <p className="text-[10px] text-slate-400 mt-1">{testResult.message}</p>
                    </div>
                  )}
                </div>

                {/* Form 3CD Clause 21(d) Tax Audit Annexure (7 cols) */}
                <div className="lg:col-span-7 p-6 rounded-xl bg-slate-900/60 border border-slate-800 shadow-lg space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div className="flex items-center gap-2">
                      <FileSpreadsheet className="w-5 h-5 text-amber-400" />
                      <h3 className="text-sm font-semibold text-white">Form 3CD Clause 21(d) Tax Audit Annexure</h3>
                    </div>
                    <span className="text-[10px] text-slate-400 font-mono">
                      FY {sec40a3Audit?.fiscal_year || sec40a3Year}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 font-mono">
                      <span className="text-[10px] text-slate-500 block">Total Violations</span>
                      <span className="text-xl font-bold text-white">
                        {sec40a3Audit?.total_violations || 0}
                      </span>
                    </div>
                    <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 font-mono">
                      <span className="text-[10px] text-slate-500 block">Total Disallowance u/s 40A(3)</span>
                      <span className="text-xl font-bold text-rose-400">
                        ₹{(sec40a3Audit?.total_disallowed_amount_inr || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </span>
                    </div>
                  </div>

                  <div className="overflow-x-auto max-h-72">
                    <table className="w-full text-left text-xs font-mono">
                      <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                        <tr>
                          <th className="p-2">Date</th>
                          <th className="p-2">Payee / Vendor</th>
                          <th className="p-2 text-right">Aggregate (₹)</th>
                          <th className="p-2 text-right">Disallowed (₹)</th>
                          <th className="p-2">Status</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {sec40a3Audit?.tax_audit_annexure_clause_21d?.length > 0 ? (
                          sec40a3Audit.tax_audit_annexure_clause_21d.map((row: any, idx: number) => (
                            <tr key={idx} className="hover:bg-slate-950/40">
                              <td className="p-2 text-slate-300">{row.date}</td>
                              <td className="p-2 text-white font-medium">{row.payee}</td>
                              <td className="p-2 text-right text-slate-300">₹{parseFloat(row.aggregate_daily_cash).toFixed(2)}</td>
                              <td className="p-2 text-right text-rose-400 font-semibold">₹{parseFloat(row.disallowed_amount).toFixed(2)}</td>
                              <td className="p-2">
                                <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30">
                                  {row.status}
                                </span>
                              </td>
                            </tr>
                          ))
                        ) : (
                          <tr>
                            <td colSpan={5} className="p-4 text-center text-slate-500 italic">
                              No Section 40A(3) violations detected for FY {sec40a3Year}. All cash expenditures comply with statutory limits.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: ADVANCE TAX FORECASTING & CASH WATCHDOG */}
          {activeTab === 'advance_tax' && (
            <div className="space-y-8">
              {/* Top Controls & Fiscal Year Selector */}
              <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-rose-400" />
                    <h2 className="text-base font-semibold text-white">Direct Tax Runway &amp; Advance Tax Watchdog</h2>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 font-semibold">
                      Sections 208, 211, 234B &amp; 234C
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    Continuous YTD profit tracking, corporate tax projection, customer TDS credit offsets, and safe harbor cash planning.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">Target FY:</span>
                    <select
                      value={advanceTaxFy}
                      onChange={(e) => {
                        setAdvanceTaxFy(e.target.value);
                        loadAdvanceTaxForecast(e.target.value);
                      }}
                      className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-rose-500"
                    >
                      <option value="2026-27">FY 2026-27 (AY 2027-28)</option>
                      <option value="2025-26">FY 2025-26 (AY 2026-27)</option>
                      <option value="2024-25">FY 2024-25 (AY 2025-26)</option>
                    </select>
                  </div>

                  {!isLLP && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-400">Regime:</span>
                      <select
                        value={advanceTaxRegime}
                        onChange={(e) => {
                          setAdvanceTaxRegime(e.target.value);
                          loadAdvanceTaxForecast(advanceTaxFy, customProfitInput, e.target.value);
                        }}
                        className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-rose-500"
                      >
                        <option value="sec_115baa">Sec 115BAA (22% + 10% Surcharge = 25.17%)</option>
                        <option value="old_regime">Old Regime (25%/30% + Slab Surcharge)</option>
                      </select>
                    </div>
                  )}

                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      placeholder="Custom Profit (₹)..."
                      value={customProfitInput}
                      onChange={(e) => setCustomProfitInput(e.target.value)}
                      className="w-36 bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white font-mono placeholder:text-slate-600 focus:outline-none focus:border-rose-500"
                    />
                    <button
                      type="button"
                      onClick={() => loadAdvanceTaxForecast(advanceTaxFy, customProfitInput)}
                      className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs rounded-lg font-medium transition"
                    >
                      Simulate
                    </button>
                  </div>

                  <button
                    onClick={() => {
                      setCustomProfitInput('');
                      loadAdvanceTaxForecast(advanceTaxFy, '');
                    }}
                    disabled={advanceTaxLoading}
                    className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-50 transition"
                    title="Refresh Live Metrics"
                  >
                    <RefreshCw className={`w-4 h-4 ${advanceTaxLoading ? 'animate-spin text-rose-400' : ''}`} />
                  </button>
                </div>
              </div>

              {advanceTaxLoading && !advanceTaxForecast ? (
                <div className="p-12 text-center text-slate-400 flex items-center justify-center gap-2">
                  <RefreshCw className="w-5 h-5 animate-spin text-rose-400" />
                  <span>Computing direct tax projections and Section 211 thresholds...</span>
                </div>
              ) : advanceTaxForecast ? (
                <>
                  {/* Top 4 Metric KPI Cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span>Projected Taxable Profit</span>
                        <Coins className="w-4 h-4 text-emerald-400" />
                      </div>
                      <div className="text-xl font-bold font-mono text-white">
                        ₹{(advanceTaxForecast.annual_projection?.projected_net_taxable_income || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </div>
                      <p className="text-[11px] text-slate-500 truncate">
                        YTD Rev: ₹{(advanceTaxForecast.ytd_metrics?.operating_revenue || 0).toLocaleString('en-IN')} | Exp: ₹{(advanceTaxForecast.ytd_metrics?.operating_expenses || 0).toLocaleString('en-IN')}
                      </p>
                    </div>

                    <div className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span>Tax Regime &amp; Rate</span>
                        <Scale className="w-4 h-4 text-sky-400" />
                      </div>
                      <div className="text-xl font-bold font-mono text-sky-300">
                        {advanceTaxForecast.effective_tax_rate_percent}%
                      </div>
                      <div className="text-[11px] text-slate-400 truncate">
                        {advanceTaxForecast.tax_breakdown?.regime_name || (advanceTaxForecast.tax_regime === 'sec_115baa_22' ? 'Sec 115BAA Concessional' : 'Corporate / LLP Rate')}
                      </div>
                    </div>

                    <div className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span>Client TDS Offset (26AS)</span>
                        <Receipt className="w-4 h-4 text-amber-400" />
                      </div>
                      <div className="text-xl font-bold font-mono text-amber-300">
                        ₹{(advanceTaxForecast.annual_projection?.tds_credits_claimed || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </div>
                      <p className="text-[11px] text-slate-500 truncate">
                        Gross Tax: ₹{(advanceTaxForecast.annual_projection?.gross_tax_liability || 0).toLocaleString('en-IN')}
                      </p>
                    </div>

                    <div className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 space-y-2">
                      <div className="flex items-center justify-between text-xs text-slate-400">
                        <span>Net Advance Tax Payable</span>
                        <TrendingUp className="w-4 h-4 text-rose-400" />
                      </div>
                      <div className="text-xl font-bold font-mono text-rose-300">
                        ₹{(advanceTaxForecast.annual_projection?.net_advance_tax_payable || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                      </div>
                      <span className={`inline-block text-[10px] font-semibold px-2 py-0.5 rounded border ${
                        advanceTaxForecast.annual_projection?.is_sec208_mandatory
                          ? 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                          : 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                      }`}>
                        {advanceTaxForecast.annual_projection?.is_sec208_mandatory ? 'Section 208 Mandate Active (> ₹10,000)' : 'Exempt (< ₹10,000)'}
                      </span>
                    </div>
                  </div>

                  {/* Dynamic Tax Regime & Surcharge Computation Breakdown Card */}
                  {advanceTaxForecast.tax_breakdown && (
                    <div className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 shadow-md space-y-3">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-2.5">
                        <div className="flex items-center gap-2">
                          <Scale className="w-4 h-4 text-sky-400 shrink-0" />
                          <h4 className="text-xs font-semibold text-white">Dynamic Income-tax Computation &amp; Surcharge Engine</h4>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/20">
                            {advanceTaxForecast.tax_breakdown.statutory_reference}
                          </span>
                        </div>
                        <span className="text-xs font-mono text-slate-300">
                          Effective Tax Rate: <strong className="text-sky-300 font-bold">{advanceTaxForecast.tax_breakdown.effective_rate_pct}%</strong>
                        </span>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                        <div className="p-2.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1">
                          <span className="text-[10px] text-slate-500 block font-sans">Turnover Bracket</span>
                          <span className="text-slate-200 text-xs font-semibold">{advanceTaxForecast.tax_breakdown.turnover_slab}</span>
                        </div>
                        <div className="p-2.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1">
                          <span className="text-[10px] text-slate-500 block font-sans">Base Tax ({advanceTaxForecast.tax_breakdown.base_rate_pct}%)</span>
                          <span className="text-slate-200 text-xs font-semibold">₹{(advanceTaxForecast.tax_breakdown.base_tax_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                        </div>
                        <div className="p-2.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1">
                          <span className="text-[10px] text-slate-500 block font-sans">Surcharge ({advanceTaxForecast.tax_breakdown.surcharge_pct}%)</span>
                          <span className="text-slate-200 text-xs font-semibold">₹{(advanceTaxForecast.tax_breakdown.surcharge_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                        </div>
                        <div className="p-2.5 bg-slate-950/70 border border-slate-800 rounded-lg space-y-1">
                          <span className="text-[10px] text-slate-500 block font-sans">HEC Cess (4%)</span>
                          <span className="text-slate-200 text-xs font-semibold">₹{(advanceTaxForecast.tax_breakdown.cess_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                        </div>
                      </div>

                      <p className="text-[11px] text-slate-400 leading-relaxed pt-1">
                        {advanceTaxForecast.tax_breakdown.notes}
                      </p>
                    </div>
                  )}

                  {/* Immediate Action & Monthly Reserve Runway Watchdog */}
                  <div className="p-6 rounded-xl bg-gradient-to-r from-slate-900 via-rose-950/20 to-slate-900 border border-rose-900/40 shadow-xl space-y-4">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <Clock className="w-5 h-5 text-rose-400" />
                          <h3 className="text-base font-bold text-white">
                            Upcoming Installment Action ({advanceTaxForecast.next_action?.quarter || 'Q1'})
                          </h3>
                        </div>
                        <p className="text-xs text-slate-300">
                          {advanceTaxForecast.next_action?.payable_now > 0 ? (
                            <>
                              Statutory Target: <span className="font-mono font-bold text-rose-300">₹{advanceTaxForecast.next_action.payable_now.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span> payable by <span className="font-semibold text-white">{advanceTaxForecast.next_action.due_date}</span>.
                            </>
                          ) : (
                            <span className="text-emerald-400 font-medium">Safe Harbor requirements fully fulfilled for the current quarter. No immediate payment needed.</span>
                          )}
                        </p>
                      </div>

                      <div className="flex flex-wrap items-center gap-3">
                        <button
                          type="button"
                          onClick={() => handleOpenEpayPacket(advanceTaxForecast.next_action?.quarter || 'Q1', advanceTaxForecast.next_action?.payable_now || 10000)}
                          className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs rounded-lg flex items-center gap-1.5 shadow transition"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                          e-Pay Tax Packet Helper
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setChallanQuarter((advanceTaxForecast.next_action?.quarter as any) || 'Q1');
                            setChallanAmount(String(advanceTaxForecast.next_action?.payable_now || ''));
                            setChallanModalOpen(true);
                          }}
                          className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs rounded-lg flex items-center gap-1.5 border border-slate-700 transition"
                        >
                          <Plus className="w-3.5 h-3.5 text-emerald-400" />
                          Record Paid Challan 280
                        </button>
                      </div>
                    </div>

                    <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
                      <div className="flex items-center gap-2 text-slate-300">
                        <Sparkles className="w-4 h-4 text-amber-400 shrink-0" />
                        <span>
                          <strong>Smooth Cash-Flow Buffer:</strong> Set aside <span className="text-amber-300 font-mono font-semibold">₹{(advanceTaxForecast.next_action?.recommended_monthly_savings_reserve || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })} / month</span> into liquid reserve to eliminate quarterly working capital stress.
                        </span>
                      </div>
                      <div className="text-slate-400 text-[11px] shrink-0 font-mono">
                        Safe Harbor: Q1 &ge; 12% | Q2 &ge; 36% | Q3 &ge; 75% | Q4 = 100%
                      </div>
                    </div>
                  </div>

                  {/* Section 211 Quarterly Installment Matrix */}
                  <div className="space-y-4">
                    <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-sky-400" />
                      Section 211 Statutory Installment Progress &amp; Safe Harbors
                    </h3>

                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                      {advanceTaxForecast.installments?.map((inst: any) => {
                        const targetAmt = inst.target_amount || 0;
                        const paidAmt = inst.cumulative_paid || 0;
                        const pct = targetAmt > 0 ? Math.min(100, Math.round((paidAmt / targetAmt) * 100)) : 100;
                        return (
                          <div key={inst.quarter} className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-3">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-white text-sm">{inst.quarter} Installment</span>
                              <span className="text-xs font-mono text-slate-400 font-semibold">{inst.cumulative_percent}% Due</span>
                            </div>

                            <div className="space-y-1">
                              <div className="text-xs text-slate-400 flex justify-between">
                                <span>Due Date:</span>
                                <span className="text-slate-300 font-medium">{inst.due_date}</span>
                              </div>
                              <div className="text-xs text-slate-400 flex justify-between">
                                <span>Target:</span>
                                <span className="text-white font-mono font-semibold">₹{targetAmt.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                              </div>
                              <div className="text-xs text-slate-400 flex justify-between">
                                <span>Safe Harbor:</span>
                                <span className="text-amber-300 font-mono">₹{(inst.safe_harbor_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                              </div>
                              <div className="text-xs text-slate-400 flex justify-between">
                                <span>Paid:</span>
                                <span className="text-emerald-300 font-mono font-semibold">₹{paidAmt.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                              </div>
                            </div>

                            {/* Progress bar */}
                            <div className="space-y-1">
                              <div className="w-full bg-slate-950 h-2 rounded-full overflow-hidden border border-slate-800">
                                <div
                                  className={`h-full transition-all duration-500 ${
                                    pct >= 100 ? 'bg-emerald-500' : pct >= 80 ? 'bg-amber-500' : 'bg-rose-500'
                                  }`}
                                  style={{ width: `${pct}%` }}
                                />
                              </div>
                              <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                                <span>Progress</span>
                                <span>{pct}%</span>
                              </div>
                            </div>

                            <div className="pt-2 border-t border-slate-800 flex justify-between items-center">
                              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${
                                inst.is_compliant
                                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                                  : 'bg-rose-500/20 text-rose-300 border-rose-500/30'
                              }`}>
                                {inst.is_compliant ? 'Safe Harbor Met' : `Shortfall: ₹${(inst.shortfall || 0).toLocaleString('en-IN')}`}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Penal Interest Simulation & Recorded Challans Table */}
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Section 234C / 234B Interest Risk Radar */}
                    <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-4">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="w-5 h-5 text-amber-400" />
                        <h3 className="text-sm font-semibold text-white">Penal Interest Simulation</h3>
                      </div>
                      <p className="text-xs text-slate-400">
                        Interest calculated at 1% per month simple interest on shortfall under statutory rules.
                      </p>

                      <div className="space-y-2.5 text-xs font-mono">
                        <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex justify-between items-center">
                          <span className="text-slate-300">Sec 234C (Installment Deferral):</span>
                          <span className="text-amber-400 font-bold">
                            ₹{(advanceTaxForecast.penal_interest_simulation?.section_234c_deferral_interest || 0).toFixed(2)}
                          </span>
                        </div>
                        <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex justify-between items-center">
                          <span className="text-slate-300">Sec 234B (Default &lt; 90%):</span>
                          <span className="text-amber-400 font-bold">
                            ₹{(advanceTaxForecast.penal_interest_simulation?.section_234b_default_interest || 0).toFixed(2)}
                          </span>
                        </div>
                        <div className="p-3 rounded-lg bg-slate-950 border border-rose-900/40 flex justify-between items-center text-sm">
                          <span className="text-white font-semibold">Total Penalty Risk:</span>
                          <span className="text-rose-400 font-bold">
                            ₹{(advanceTaxForecast.penal_interest_simulation?.total_statutory_penalty_risk || 0).toFixed(2)}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Paid Challans History Table */}
                    <div className="lg:col-span-2 p-6 rounded-xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-4">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <FileCheck className="w-5 h-5 text-emerald-400" />
                          <h3 className="text-sm font-semibold text-white">Challan 280 / e-Pay Tax Records</h3>
                        </div>
                        <button
                          type="button"
                          onClick={() => setChallanModalOpen(true)}
                          className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg font-medium transition"
                        >
                          + Add Payment
                        </button>
                      </div>

                      <div className="overflow-x-auto max-h-56">
                        <table className="w-full text-left text-xs font-mono">
                          <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                            <tr>
                              <th className="p-2">Quarter</th>
                              <th className="p-2">Payment Date</th>
                              <th className="p-2">BSR Code</th>
                              <th className="p-2">Challan Serial</th>
                              <th className="p-2 text-right">Amount (₹)</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800/60">
                            {advanceTaxForecast.challans_recorded?.length > 0 ? (
                              advanceTaxForecast.challans_recorded.map((c: any, idx: number) => (
                                <tr key={idx} className="hover:bg-slate-950/40">
                                  <td className="p-2 text-white font-bold">{c.quarter}</td>
                                  <td className="p-2 text-slate-300">{c.payment_date}</td>
                                  <td className="p-2 text-slate-300">{c.bsr_code}</td>
                                  <td className="p-2 text-slate-300">{c.challan_serial_no}</td>
                                  <td className="p-2 text-right text-emerald-400 font-semibold">
                                    ₹{parseFloat(c.amount_paid).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                                  </td>
                                </tr>
                              ))
                            ) : (
                              <tr>
                                <td colSpan={5} className="p-4 text-center text-slate-500 italic">
                                  No advance tax payments recorded yet for FY {advanceTaxFy}. Click &ldquo;Record Paid Challan 280&rdquo; to add.
                                </td>
                              </tr>
                            )}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                </>
              ) : null}
            </div>
          )}

          {/* TAB 6: STATUTORY BASELINE & HISTORICAL FY SEAL */}
          {activeTab === 'statutory_baseline' && (
            <div className="space-y-8">
              {/* Header & FY Selector */}
              <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <Anchor className="w-5 h-5 text-blue-400" />
                    <h2 className="text-base font-semibold text-white">Statutory Baseline &amp; Historical FY Seal</h2>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 font-semibold">
                      ICAI AS-5 &amp; Sec 128/130
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    Anchors filed MCA Form AOC-4 as immutable Source of Truth, aligns opening ledger balances via Account 2015, and hard-locks historical books.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">Fiscal Year:</span>
                    <select
                      value={statutoryFy}
                      onChange={(e) => {
                        setStatutoryFy(e.target.value);
                        loadStatutoryRadar(e.target.value);
                      }}
                      className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-blue-500"
                    >
                      <option value="2025-26">FY 2025-26 (AY 2026-27)</option>
                      <option value="2024-25">FY 2024-25 (AY 2025-26)</option>
                    </select>
                  </div>

                  <button
                    onClick={() => setAnchorModalOpen(true)}
                    className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 shadow transition"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Record Filed Return
                  </button>

                  <button
                    onClick={() => loadStatutoryRadar(statutoryFy)}
                    disabled={statutoryLoading}
                    className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-50 transition"
                    title="Refresh Radar"
                  >
                    <RefreshCw className={`w-4 h-4 ${statutoryLoading ? 'animate-spin text-blue-400' : ''}`} />
                  </button>
                </div>
              </div>

              {/* Statutory Seal Status Banner */}
              {statutoryRadar?.is_statutory_sealed ? (
                <div className="p-5 rounded-xl bg-emerald-950/30 border border-emerald-800/60 shadow-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 shrink-0">
                      <Lock className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white flex items-center gap-2">
                        STATUTORY BOOKS SEALED &amp; IMMUTABLE (FY {statutoryFy})
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold">
                          Sec 128 Audit Trail Locked
                        </span>
                      </h3>
                      <p className="text-xs text-slate-300 mt-1">
                        Historical ledger records are cryptographically anchored. Under Companies Act Section 128 &amp; 130, no backdated mutations or insertions are permissible without an NCLT court order.
                      </p>
                      <div className="mt-2 text-[11px] font-mono text-slate-400 flex flex-wrap gap-4">
                        <span>SHA-256 Seal: <strong className="text-emerald-400">{statutoryRadar.statutory_seal_hash?.slice(0, 24)}...</strong></span>
                        {statutoryRadar.sealed_at && <span>Sealed At: {statutoryRadar.sealed_at}</span>}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-5 rounded-xl bg-amber-950/20 border border-amber-800/50 shadow-lg flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                  <div className="flex items-start gap-3">
                    <div className="p-2 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-300 shrink-0">
                      <AlertTriangle className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-white flex items-center gap-2">
                        UNSEALED HISTORICAL PERIOD (FY {statutoryFy})
                        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold">
                          Calibration Recommended
                        </span>
                      </h3>
                      <p className="text-xs text-slate-300 mt-1">
                        Variance detected between internal reconstructed books and filed Form AOC-4. Calibrating will pass an opening entry on April 1 routed to Account 2015 and seal this fiscal period against retrospective alteration.
                      </p>
                    </div>
                  </div>

                  <button
                    onClick={() => setSealModalOpen(true)}
                    className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-slate-950 font-bold text-xs rounded-lg flex items-center gap-2 shadow shrink-0 transition"
                  >
                    <Lock className="w-4 h-4" />
                    Calibrate &amp; Seal FY {statutoryFy}
                  </button>
                </div>
              )}

              {/* Filed Anchor Metadata Card */}
              {statutoryRadar?.filed_anchor ? (
                <div className="p-5 rounded-xl bg-slate-900/90 border border-slate-800 flex flex-wrap items-center justify-between gap-4 text-xs font-mono">
                  <div className="flex items-center gap-2.5">
                    <FileCheck className="w-5 h-5 text-blue-400" />
                    <div>
                      <span className="text-slate-400 text-[11px] block">Verified Statutory Baseline:</span>
                      <span className="text-white font-bold text-sm">
                        {statutoryRadar.filed_anchor.form_type?.toUpperCase()} — SRN: {statutoryRadar.filed_anchor.srn_or_ack_number}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-6 text-slate-300">
                    <div>
                      <span className="text-slate-500 text-[11px] block">Filing Date</span>
                      <span>{statutoryRadar.filed_anchor.filing_date}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 text-[11px] block">Signatory DIN</span>
                      <span>{statutoryRadar.filed_anchor.signatory_din || 'N/A'}</span>
                    </div>
                    <div>
                      <span className="text-slate-500 text-[11px] block">Auditor UDIN</span>
                      <span className="text-sky-400">{statutoryRadar.filed_anchor.auditor_udin || 'N/A'}</span>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800 text-center space-y-2">
                  <FileText className="w-8 h-8 text-slate-600 mx-auto" />
                  <h4 className="text-sm font-semibold text-white">No Filed Return Baseline Recorded</h4>
                  <p className="text-xs text-slate-400 max-w-md mx-auto">
                    Record your filed MCA Form AOC-4 or ITR-6 acknowledgment to establish the legal Source of Truth for opening balances.
                  </p>
                  <button
                    onClick={() => setAnchorModalOpen(true)}
                    className="mt-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs rounded-lg inline-flex items-center gap-1.5 shadow"
                  >
                    <Plus className="w-3.5 h-3.5" /> Record Form AOC-4 Baseline
                  </button>
                </div>
              )}

              {/* Comparative Variance Radar Table */}
              <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 shadow-xl space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <Scale className="w-5 h-5 text-sky-400" />
                    <h3 className="text-sm font-bold text-white">
                      Comparative Schedule III Variance Radar (Books vs. Filed AOC-4)
                    </h3>
                  </div>
                  <div className="text-xs font-mono text-slate-400">
                    Net Absolute Drift: <strong className="text-amber-400">₹{(statutoryRadar?.summary?.total_variance_abs || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                      <tr>
                        <th className="p-2.5">Account Code &amp; Head</th>
                        <th className="p-2.5">Category</th>
                        <th className="p-2.5 text-right">Internal Books (₹)</th>
                        <th className="p-2.5 text-right">Filed AOC-4 Baseline (₹)</th>
                        <th className="p-2.5 text-right">Variance &Delta; (₹)</th>
                        <th className="p-2.5">Adjustment</th>
                        <th className="p-2.5 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {statutoryRadar?.line_items?.map((item: any, idx: number) => {
                        const isMatched = item.status === 'MATCHED';
                        return (
                          <tr key={idx} className="hover:bg-slate-950/40">
                            <td className="p-2.5 text-white font-medium">
                              <span className="text-slate-500 mr-2">{item.account_code}</span>
                              {item.account_name}
                            </td>
                            <td className="p-2.5 text-slate-400 uppercase text-[10px]">{item.category}</td>
                            <td className="p-2.5 text-right text-slate-300">
                              ₹{item.internal_ledger_balance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                            </td>
                            <td className="p-2.5 text-right text-sky-300 font-semibold">
                              ₹{item.filed_statutory_balance.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                            </td>
                            <td className={`p-2.5 text-right font-bold ${
                              isMatched ? 'text-slate-500' : 'text-amber-400'
                            }`}>
                              ₹{Math.abs(item.variance).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                            </td>
                            <td className="p-2.5">
                              {isMatched ? (
                                <span className="text-slate-500 text-[11px]">&mdash;</span>
                              ) : (
                                <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-200 border border-slate-700">
                                  {item.recommended_adjustment}
                                </span>
                              )}
                            </td>
                            <td className="p-2.5 text-center">
                              <span className={`px-2.5 py-0.5 rounded text-[10px] font-semibold border ${
                                isMatched
                                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                                  : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                              }`}>
                                {isMatched ? 'MATCHED' : 'CALIBRATE'}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                <div className="p-3.5 rounded-lg bg-slate-950/80 border border-slate-800 text-xs text-slate-400 space-y-1">
                  <div className="flex items-center gap-2 text-slate-300 font-medium">
                    <Sparkles className="w-4 h-4 text-blue-400" />
                    <span>ICAI AS-5 &amp; Section 128 Calibration Guarantee:</span>
                  </div>
                  <p className="text-[11px] leading-relaxed text-slate-400">
                    Executing calibration passes an Opening Statutory Calibration Journal Entry on <strong>01/04/{statutoryFy ? parseInt(statutoryFy.split('-')[0]) + 1 : '2026'}</strong>.
                    Any net difference between filed assets and liabilities is routed through <strong>Account 2015: Prior Period Statutory Adjustments (Surplus/Deficit)</strong>, ensuring the double-entry invariant &Sigma;Debits &equiv; &Sigma;Credits is maintained with &plusmn;₹0.00 mathematical drift.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* TAB 7: GST RUNWAY & MULTI-FREQUENCY FORECASTING ENGINE */}
          {activeTab === 'gst_forecast' && (
            <div className="space-y-8">
              {/* Header & Controls */}
              <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <Coins className="w-5 h-5 text-teal-400" />
                    <h2 className="text-base font-semibold text-white">Multi-Frequency GST Runway &amp; Cash Watchdog</h2>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-teal-500/20 text-teal-300 border border-teal-500/30 font-semibold">
                      Rule 88A Mathematical Hierarchy
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    Real-time liability calculation for Monthly GSTR-3B, Quarterly QRMP (PMT-06), Composition (CMP-08), and Annual GSTR-9.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">Scheme:</span>
                    <select
                      value={gstFrequency}
                      onChange={(e) => {
                        const newFreq = e.target.value as any;
                        setGstFrequency(newFreq);
                        loadGstForecast(gstFy, newFreq, gstQuarter, gstMonth, gstTurnover);
                      }}
                      className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-teal-500"
                    >
                      <option value="monthly">Monthly (GSTR-3B)</option>
                      <option value="quarterly">Quarterly (QRMP Scheme)</option>
                      <option value="composition">Composition (CMP-08)</option>
                      <option value="annual">Annual True-Up (GSTR-9)</option>
                    </select>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">FY:</span>
                    <select
                      value={gstFy}
                      onChange={(e) => {
                        setGstFy(e.target.value);
                        loadGstForecast(e.target.value, gstFrequency, gstQuarter, gstMonth, gstTurnover);
                        loadGstChallans(e.target.value);
                      }}
                      className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-teal-500"
                    >
                      <option value="2025-26">FY 2025-26</option>
                      <option value="2026-27">FY 2026-27</option>
                      <option value="2024-25">FY 2024-25</option>
                    </select>
                  </div>

                  {gstFrequency === 'quarterly' && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-400">Quarter:</span>
                      <select
                        value={gstQuarter}
                        onChange={(e) => {
                          const q = e.target.value as any;
                          setGstQuarter(q);
                          loadGstForecast(gstFy, gstFrequency, q, gstMonth, gstTurnover);
                        }}
                        className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-teal-500"
                      >
                        <option value="Q1">Q1 (Apr - Jun)</option>
                        <option value="Q2">Q2 (Jul - Sep)</option>
                        <option value="Q3">Q3 (Oct - Dec)</option>
                        <option value="Q4">Q4 (Jan - Mar)</option>
                      </select>
                    </div>
                  )}

                  {gstFrequency === 'composition' && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-400">Quarter Turnover (₹):</span>
                      <input
                        type="number"
                        value={gstTurnover}
                        onChange={(e) => setGstTurnover(e.target.value)}
                        onBlur={() => loadGstForecast(gstFy, gstFrequency, gstQuarter, gstMonth, gstTurnover)}
                        placeholder="Turnover..."
                        className="w-32 bg-slate-950 border border-slate-800 rounded-lg px-2 py-1 text-xs text-white font-mono focus:outline-none focus:border-teal-500"
                      />
                    </div>
                  )}

                  <button
                    onClick={() => {
                      loadGstForecast(gstFy, gstFrequency, gstQuarter, gstMonth, gstTurnover);
                      loadGstChallans(gstFy);
                    }}
                    disabled={gstForecastLoading}
                    className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-50 transition"
                    title="Refresh Forecast"
                  >
                    <RefreshCw className={`w-4 h-4 ${gstForecastLoading ? 'animate-spin text-teal-400' : ''}`} />
                  </button>
                </div>
              </div>

              {/* Status Alert Banner */}
              {gstForecast && (
                <div className={`p-4 rounded-xl border flex flex-col md:flex-row items-start md:items-center justify-between gap-3 ${
                  gstForecast.status_banner?.badge_color === 'danger'
                    ? 'bg-rose-950/20 border-rose-800/60 text-rose-300'
                    : gstForecast.status_banner?.badge_color === 'warning'
                    ? 'bg-amber-950/20 border-amber-800/60 text-amber-300'
                    : 'bg-emerald-950/20 border-emerald-800/60 text-emerald-300'
                }`}>
                  <div className="flex items-center gap-2.5">
                    <AlertCircle className="w-5 h-5 shrink-0" />
                    <div>
                      <div className="font-semibold text-xs text-white">{gstForecast.status_banner?.title}</div>
                      <div className="text-[11px] text-slate-300">{gstForecast.status_banner?.action_required}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold">
                      Net Payable: ₹{(gstForecast.net_cash_payable?.total || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </span>
                    {gstFrequency === 'quarterly' && (
                      <button
                        onClick={handleOpenPmt06Packet}
                        className="px-3 py-1 bg-teal-600 hover:bg-teal-500 text-white font-semibold text-xs rounded-lg shadow flex items-center gap-1.5 transition"
                      >
                        <FileSpreadsheet className="w-3.5 h-3.5" /> PMT-06 Helper
                      </button>
                    )}
                    <button
                      onClick={() => {
                        setGstChallanAmount(String(gstForecast.net_cash_payable?.total || '0.00'));
                        setGstChallanModalOpen(true);
                      }}
                      className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-semibold text-xs rounded-lg shadow flex items-center gap-1.5 transition"
                    >
                      <Plus className="w-3.5 h-3.5 text-teal-400" /> Record GST Challan
                    </button>
                  </div>
                </div>
              )}

              {/* 4 Summary Cards */}
              {gstForecast ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                  {/* Card 1: Gross Output Tax */}
                  <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 shadow space-y-2">
                    <span className="text-xs text-slate-400 flex items-center gap-1.5">
                      <Receipt className="w-4 h-4 text-rose-400" /> Gross Output Tax (Sales)
                    </span>
                    <div className="text-xl font-bold font-mono text-white">
                      ₹{(gstForecast.output_tax?.total || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </div>
                    <div className="text-[11px] font-mono text-slate-400 space-y-0.5 pt-1 border-t border-slate-800">
                      <div className="flex justify-between">
                        <span>IGST:</span>
                        <span className="text-slate-200">₹{(gstForecast.output_tax?.igst || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>CGST + SGST:</span>
                        <span className="text-slate-200">₹{((gstForecast.output_tax?.cgst || 0) + (gstForecast.output_tax?.sgst || 0)).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                      </div>
                    </div>
                  </div>

                  {/* Card 2: Available ITC */}
                  <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 shadow space-y-2">
                    <span className="text-xs text-slate-400 flex items-center gap-1.5">
                      <ShieldCheck className="w-4 h-4 text-emerald-400" /> Available ITC (Purchases)
                    </span>
                    <div className="text-xl font-bold font-mono text-emerald-400">
                      ₹{(gstForecast.input_tax_credit?.total || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </div>
                    <div className="text-[11px] font-mono text-slate-400 space-y-0.5 pt-1 border-t border-slate-800">
                      <div className="flex justify-between">
                        <span>IGST Credit:</span>
                        <span className="text-slate-200">₹{(gstForecast.input_tax_credit?.igst || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>CGST + SGST Credit:</span>
                        <span className="text-slate-200">₹{((gstForecast.input_tax_credit?.cgst || 0) + (gstForecast.input_tax_credit?.sgst || 0)).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                      </div>
                    </div>
                  </div>

                  {/* Card 3: Net Cash Payable */}
                  <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 shadow space-y-2">
                    <span className="text-xs text-slate-400 flex items-center gap-1.5">
                      <IndianRupee className="w-4 h-4 text-teal-400" /> Net Cash Tax Payable
                    </span>
                    <div className="text-xl font-bold font-mono text-teal-300">
                      ₹{(gstForecast.net_cash_payable?.total || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </div>
                    <div className="text-[11px] font-mono text-slate-400 space-y-0.5 pt-1 border-t border-slate-800">
                      <div className="flex justify-between">
                        <span>IGST Cash:</span>
                        <span className="text-slate-200">₹{(gstForecast.net_cash_payable?.igst || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>CGST / SGST Cash:</span>
                        <span className="text-slate-200">₹{(gstForecast.net_cash_payable?.cgst || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })} each</span>
                      </div>
                    </div>
                  </div>

                  {/* Card 4: Recommended Buffer / Safe Harbor */}
                  <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 shadow space-y-2">
                    <span className="text-xs text-slate-400 flex items-center gap-1.5">
                      <TrendingUp className="w-4 h-4 text-sky-400" /> Cash Runway &amp; Buffer
                    </span>
                    <div className="text-xl font-bold font-mono text-white">
                      ₹{(gstForecast.cash_reserve_recommendation?.safe_harbor_buffer_inr || gstForecast.cash_reserve_recommendation?.recommended_weekly_reserve_inr || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </div>
                    <div className="text-[11px] font-mono text-slate-400 space-y-0.5 pt-1 border-t border-slate-800">
                      <div className="flex justify-between">
                        <span>Weekly Buffer:</span>
                        <span className="text-slate-200">₹{(gstForecast.cash_reserve_recommendation?.recommended_weekly_reserve_inr || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                      </div>
                      <div className="flex justify-between">
                        <span>Due Date:</span>
                        <span className="text-amber-400 font-semibold">{gstForecast.due_date || '20th of Month'}</span>
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}

              {/* Rule 88A Mathematical Credit Set-Off Radar */}
              {gstForecast?.rule_88a_breakdown && (
                <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800 shadow space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-5 h-5 text-teal-400" />
                      <h3 className="font-semibold text-white text-sm">Rule 88A Mathematical Set-Off Breakdown</h3>
                    </div>
                    <span className="text-xs font-mono text-slate-400">
                      Statutory Order: IGST &rarr; CGST &rarr; SGST (No Cross-Utilization)
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4 font-mono text-xs">
                    <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
                      <span className="text-slate-400 font-semibold block">1. IGST Credit Allocation:</span>
                      <div className="text-slate-300 space-y-1">
                        <div className="flex justify-between">
                          <span>Against IGST Liability:</span>
                          <span className="text-emerald-400">₹{(gstForecast.rule_88a_breakdown.igst_itc_used_for_igst || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Against CGST Liability:</span>
                          <span className="text-emerald-400">₹{(gstForecast.rule_88a_breakdown.igst_itc_used_for_cgst || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Against SGST Liability:</span>
                          <span className="text-emerald-400">₹{(gstForecast.rule_88a_breakdown.igst_itc_used_for_sgst || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                        </div>
                      </div>
                    </div>

                    <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
                      <span className="text-slate-400 font-semibold block">2. CGST / SGST Credits:</span>
                      <div className="text-slate-300 space-y-1">
                        <div className="flex justify-between">
                          <span>CGST ITC Used:</span>
                          <span className="text-emerald-400">₹{(gstForecast.rule_88a_breakdown.cgst_itc_used_for_cgst || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>SGST ITC Used:</span>
                          <span className="text-emerald-400">₹{(gstForecast.rule_88a_breakdown.sgst_itc_used_for_sgst || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                        </div>
                        <div className="flex justify-between text-slate-500 italic">
                          <span>Cross-Setoff:</span>
                          <span>Prohibited u/s 49(5)</span>
                        </div>
                      </div>
                    </div>

                    <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
                      <span className="text-slate-400 font-semibold block">3. Carry-Forward ITC Balance:</span>
                      <div className="text-slate-300 space-y-1">
                        <div className="flex justify-between">
                          <span>Excess IGST ITC:</span>
                          <span className="text-sky-400">₹{(gstForecast.rule_88a_breakdown.remaining_igst_itc || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Excess CGST ITC:</span>
                          <span className="text-sky-400">₹{(gstForecast.rule_88a_breakdown.remaining_cgst_itc || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Excess SGST ITC:</span>
                          <span className="text-sky-400">₹{(gstForecast.rule_88a_breakdown.remaining_sgst_itc || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Recorded GST Challans Table */}
              <div className="p-6 rounded-xl bg-slate-900/60 border border-slate-800 shadow space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Receipt className="w-5 h-5 text-teal-400" />
                    <h3 className="font-semibold text-white text-sm">Recorded GST Tax Challans for FY {gstFy}</h3>
                  </div>
                  <span className="text-xs text-slate-400 font-mono">
                    {gstChallansList.length} Recorded Payment{gstChallansList.length === 1 ? '' : 's'}
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                      <tr>
                        <th className="p-2.5">Period</th>
                        <th className="p-2.5">CPIN</th>
                        <th className="p-2.5">CIN / Bank</th>
                        <th className="p-2.5">Payment Date</th>
                        <th className="p-2.5 text-right">CGST</th>
                        <th className="p-2.5 text-right">SGST</th>
                        <th className="p-2.5 text-right">IGST</th>
                        <th className="p-2.5 text-right">Total Paid (₹)</th>
                        <th className="p-2.5 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {gstChallansList.length > 0 ? (
                        gstChallansList.map((ch: any, idx: number) => (
                          <tr key={idx} className="hover:bg-slate-950/40">
                            <td className="p-2.5 text-white font-bold">{ch.return_period}</td>
                            <td className="p-2.5 text-slate-200">{ch.cpin}</td>
                            <td className="p-2.5 text-slate-300">{ch.cin || ch.bank_name || 'Online GST Portal'}</td>
                            <td className="p-2.5 text-slate-300">{ch.payment_date}</td>
                            <td className="p-2.5 text-right text-slate-300">₹{parseFloat(ch.cgst_paid || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                            <td className="p-2.5 text-right text-slate-300">₹{parseFloat(ch.sgst_paid || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                            <td className="p-2.5 text-right text-slate-300">₹{parseFloat(ch.igst_paid || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                            <td className="p-2.5 text-right text-emerald-400 font-bold">₹{parseFloat(ch.total_paid || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</td>
                            <td className="p-2.5 text-center">
                              <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                                {ch.status || 'PAID'}
                              </span>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={9} className="p-6 text-center text-slate-500 italic">
                            No GST challans recorded yet for FY {gstFy}. Click &ldquo;Record GST Challan&rdquo; to add e-payments.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 8: YEAR-TO-YEAR SOVEREIGN STATUTORY DOSSIER */}
          {activeTab === 'statutory_dossier' && (
            <div className="space-y-8">
              {/* Header & FY Selector */}
              <div className="p-6 rounded-xl bg-slate-900/80 border border-slate-800 shadow-xl flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <FolderArchive className="w-5 h-5 text-indigo-400" />
                    <h2 className="text-base font-semibold text-white">Sovereign Statutory Dossier (Year-to-Year Archive)</h2>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-semibold">
                      SHA-256 Deduplicated Vault
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1">
                    Authentic filed returns archive organized by financial year. Zero file duplication; instant authentic binary streaming.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400">Fiscal Year:</span>
                    <select
                      value={dossierFy}
                      onChange={(e) => {
                        setDossierFy(e.target.value);
                        loadDossierData(e.target.value);
                      }}
                      className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-indigo-500"
                    >
                      <option value="2025-26">FY 2025-26 (AY 2026-27)</option>
                      <option value="2026-27">FY 2026-27 (AY 2027-28)</option>
                      <option value="2024-25">FY 2024-25 (AY 2025-26)</option>
                    </select>
                  </div>

                  <button
                    onClick={() => setDossierUploadModalOpen(true)}
                    className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 shadow transition"
                  >
                    <Upload className="w-3.5 h-3.5" />
                    Upload Statutory Return
                  </button>

                  <button
                    onClick={() => loadDossierData(dossierFy)}
                    disabled={dossierLoading}
                    className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 disabled:opacity-50 transition"
                    title="Refresh Dossier"
                  >
                    <RefreshCw className={`w-4 h-4 ${dossierLoading ? 'animate-spin text-indigo-400' : ''}`} />
                  </button>
                </div>
              </div>

              {/* Progress Summary Banner */}
              {dossierData && (
                <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 shadow flex flex-col sm:flex-row items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg bg-indigo-500/10 border border-indigo-500/30 text-indigo-300">
                      <Archive className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-xs font-semibold text-white">
                        {dossierData.total_filed} of {dossierData.total_statutory_required} Mandatory Statutory Documents Archived ({dossierData.completion_percentage}%)
                      </div>
                      <div className="text-[11px] text-slate-400">
                        Preserves authentic original files for AOC-4, ITR-6, Auditor&apos;s Report, Board&apos;s Report, and MGT-7A.
                      </div>
                    </div>
                  </div>

                  <div className="w-full sm:w-48 bg-slate-800 rounded-full h-2.5 overflow-hidden">
                    <div
                      className="bg-indigo-500 h-full rounded-full transition-all duration-500"
                      style={{ width: `${dossierData.completion_percentage}%` }}
                    />
                  </div>
                </div>
              )}

              {/* 5 Annual Tiles Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {dossierData?.tiles?.map((tile: any, idx: number) => (
                  <div
                    key={idx}
                    className={`p-5 rounded-xl border flex flex-col justify-between space-y-4 shadow transition-all ${
                      tile.is_uploaded
                        ? 'bg-slate-900/80 border-slate-700/80'
                        : 'bg-slate-900/40 border-slate-800 border-dashed'
                    }`}
                  >
                    <div>
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                          {tile.authority}
                        </span>
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded font-mono border ${
                          tile.is_uploaded
                            ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                            : 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                        }`}>
                          {tile.is_uploaded ? '✓ FILED / ARCHIVED' : 'PENDING FILING'}
                        </span>
                      </div>

                      <h3 className="font-semibold text-white text-sm leading-snug">{tile.title}</h3>
                      <p className="text-[11px] text-slate-400 mt-1">{tile.governing_section}</p>
                    </div>

                    <div className="pt-3 border-t border-slate-800 font-mono text-[11px] space-y-1 text-slate-300">
                      <div className="flex justify-between">
                        <span className="text-slate-400">SRN / Ack No:</span>
                        <span className="text-white font-medium">{tile.srn_or_ack || 'Not Filed'}</span>
                      </div>
                      {tile.filing_date && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">Filing Date:</span>
                          <span className="text-slate-200">{tile.filing_date}</span>
                        </div>
                      )}
                      {tile.signatory && (
                        <div className="flex justify-between">
                          <span className="text-slate-400">Signatory / UDIN:</span>
                          <span className="text-slate-200">{tile.signatory}</span>
                        </div>
                      )}
                      {tile.sha256 && (
                        <div className="flex justify-between text-[10px] text-slate-400 pt-0.5">
                          <span>SHA-256:</span>
                          <span className="text-indigo-300 truncate max-w-[140px]" title={tile.sha256}>
                            {tile.sha256.slice(0, 12)}...
                          </span>
                        </div>
                      )}
                    </div>

                    <div className="pt-2">
                      {tile.has_binary && tile.s3_document_key ? (
                        <button
                          type="button"
                          onClick={() => handleStreamDocument(tile.s3_document_key)}
                          disabled={streamingKey === tile.s3_document_key}
                          className="w-full py-2 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 rounded-lg text-xs font-semibold flex items-center justify-center gap-2 transition"
                        >
                          {streamingKey === tile.s3_document_key ? (
                            <>
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Streaming Binary...
                            </>
                          ) : (
                            <>
                              <Download className="w-3.5 h-3.5" /> Download Authentic Binary
                            </>
                          )}
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => {
                            setDossierFormType(tile.form_type);
                            setDossierUploadModalOpen(true);
                          }}
                          className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition"
                        >
                          <Upload className="w-3.5 h-3.5 text-indigo-400" /> Upload Return
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* RECORD PAID CHALLAN MODAL */}
          {challanModalOpen && (
            <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <Receipt className="w-5 h-5 text-rose-400" />
                    <h3 className="font-semibold text-white text-sm">Record Advance Tax Challan 280</h3>
                  </div>
                  <button
                    onClick={() => { setChallanModalOpen(false); setChallanErrorMsg(null); }}
                    className="text-slate-400 hover:text-white text-xs"
                  >
                    ✕
                  </button>
                </div>

                <form onSubmit={handleRecordChallan} className="space-y-3 text-xs">
                  <div>
                    <label className="text-slate-300 font-medium block mb-1">Quarter:</label>
                    <select
                      value={challanQuarter}
                      onChange={(e) => setChallanQuarter(e.target.value as any)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                    >
                      <option value="Q1">Q1 (Due 15 June - 15%)</option>
                      <option value="Q2">Q2 (Due 15 September - 45%)</option>
                      <option value="Q3">Q3 (Due 15 December - 75%)</option>
                      <option value="Q4">Q4 (Due 15 March - 100%)</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-slate-300 font-medium block mb-1">Amount Paid (₹):</label>
                    <input
                      type="number"
                      step="0.01"
                      required
                      value={challanAmount}
                      onChange={(e) => setChallanAmount(e.target.value)}
                      placeholder="e.g. 50000.00"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">Payment Date:</label>
                      <input
                        type="date"
                        required
                        value={challanDate}
                        onChange={(e) => setChallanDate(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                      />
                    </div>
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">BSR Code (7 Digits):</label>
                      <input
                        type="text"
                        required
                        maxLength={7}
                        value={challanBsr}
                        onChange={(e) => setChallanBsr(e.target.value)}
                        placeholder="e.g. 0290123"
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">Challan Serial No (5 Digits):</label>
                      <input
                        type="text"
                        required
                        maxLength={5}
                        value={challanSerial}
                        onChange={(e) => setChallanSerial(e.target.value)}
                        placeholder="e.g. 00481"
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                      />
                    </div>
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">CIN / Reference (Optional):</label>
                      <input
                        type="text"
                        value={challanCin}
                        onChange={(e) => setChallanCin(e.target.value)}
                        placeholder="CIN number..."
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                      />
                    </div>
                  </div>

                  {challanErrorMsg && (
                    <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                      {challanErrorMsg}
                    </div>
                  )}

                  {challanSuccessMsg && (
                    <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 shrink-0" />
                      {challanSuccessMsg}
                    </div>
                  )}

                  <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => setChallanModalOpen(false)}
                      className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={challanSubmitting}
                      className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs rounded-lg flex items-center gap-1.5 shadow"
                    >
                      {challanSubmitting ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Recording...
                        </>
                      ) : (
                        'Save Challan'
                      )}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* e-PAY TAX PACKET HELPER MODAL */}
          {packetModalOpen && (
            <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-lg w-full shadow-2xl space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <ExternalLink className="w-5 h-5 text-rose-400" />
                    <h3 className="font-semibold text-white text-sm">CBDT e-Pay Tax / Challan 280 Helper</h3>
                  </div>
                  <button
                    onClick={() => setPacketModalOpen(false)}
                    className="text-slate-400 hover:text-white text-xs"
                  >
                    ✕
                  </button>
                </div>

                {packetLoading ? (
                  <div className="p-8 text-center text-slate-400 flex items-center justify-center gap-2">
                    <RefreshCw className="w-5 h-5 animate-spin text-rose-400" />
                    <span>Formatting e-Pay Tax packet...</span>
                  </div>
                ) : packetData ? (
                  <div className="space-y-3 text-xs">
                    <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1 font-mono">
                      <div className="flex justify-between text-slate-400">
                        <span>Entity Name:</span>
                        <strong className="text-white">{packetData.entity_name}</strong>
                      </div>
                      <div className="flex justify-between text-slate-400">
                        <span>PAN:</span>
                        <strong className="text-amber-300">{packetData.pan}</strong>
                      </div>
                      <div className="flex justify-between text-slate-400">
                        <span>Assessment Year (AY):</span>
                        <strong className="text-sky-300">{packetData.assessment_year}</strong>
                      </div>
                      <div className="flex justify-between text-slate-400">
                        <span>Major Head:</span>
                        <strong className="text-white">{packetData.major_head}</strong>
                      </div>
                      <div className="flex justify-between text-slate-400">
                        <span>Minor Head:</span>
                        <strong className="text-white">{packetData.minor_head}</strong>
                      </div>
                      <div className="flex justify-between text-slate-400 border-t border-slate-800 pt-1 text-sm">
                        <span>Recommended Amount:</span>
                        <strong className="text-emerald-400">
                          ₹{(packetData.recommended_amount_inr || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </strong>
                      </div>
                    </div>

                    <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-slate-300 text-[11px] leading-relaxed">
                      {packetData.statutory_instructions}
                    </div>

                    <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                      <button
                        type="button"
                        onClick={() => setPacketModalOpen(false)}
                        className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg"
                      >
                        Close
                      </button>
                      <a
                        href={packetData.payment_portal_url}
                        target="_blank"
                        rel="noreferrer"
                        className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs rounded-lg flex items-center gap-1.5 shadow"
                      >
                        Open CBDT e-Filing Portal <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          )}

          {/* CALIBRATE & SEAL HISTORICAL FY MODAL */}
          {sealModalOpen && (
            <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-lg w-full shadow-2xl space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <Lock className="w-5 h-5 text-amber-400" />
                    <h3 className="font-semibold text-white text-sm">
                      Confirm Statutory Baseline Calibration &amp; FY {statutoryFy} Lock
                    </h3>
                  </div>
                  <button
                    onClick={() => { setSealModalOpen(false); setSealErrorMsg(null); }}
                    className="text-slate-400 hover:text-white text-xs"
                  >
                    ✕
                  </button>
                </div>

                <div className="space-y-3 text-xs text-slate-300">
                  <div className="p-3.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs space-y-2">
                    <div className="font-bold flex items-center gap-1.5">
                      <AlertTriangle className="w-4 h-4 text-amber-400" />
                      Legal Accounting Consequence (Sec 128 &amp; 130 Companies Act 2013)
                    </div>
                    <p className="text-[11px] leading-relaxed">
                      This action will generate an opening compound journal entry on <strong>01/04/{statutoryFy ? parseInt(statutoryFy.split('-')[0]) + 1 : '2026'}</strong> to bring ledger opening balances into strict 1:1 parity with filed MCA Form AOC-4.
                    </p>
                    <p className="text-[11px] leading-relaxed">
                      The net variance will be balanced through <strong>Account 2015: Prior Period Statutory Adjustments</strong>. FY {statutoryFy} will be <strong>permanently locked</strong>, triggering PostgreSQL triggers that reject all future mutations.
                    </p>
                  </div>

                  <div>
                    <label className="text-slate-300 font-medium block mb-1">Auditor / CS Notes (Recorded in Audit Trail):</label>
                    <textarea
                      rows={2}
                      value={sealingNotes}
                      onChange={(e) => setSealingNotes(e.target.value)}
                      placeholder="e.g. Aligned opening books with MCA Form AOC-4 SRN-F98273612 approved by AGM."
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white text-xs focus:outline-none focus:border-amber-500 font-mono"
                    />
                  </div>

                  {sealErrorMsg && (
                    <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                      {sealErrorMsg}
                    </div>
                  )}

                  {sealResult && (
                    <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs space-y-1">
                      <div className="font-bold flex items-center gap-1.5">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        Successfully Sealed &amp; Calibrated!
                      </div>
                      <p className="font-mono text-[11px] text-slate-300">
                        Opening voucher posted on {sealResult.opening_date}. Hash: {sealResult.statutory_seal_hash?.slice(0, 20)}...
                      </p>
                    </div>
                  )}

                  <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => setSealModalOpen(false)}
                      className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg"
                    >
                      Cancel
                    </button>
                    {!sealResult && (
                      <button
                        type="button"
                        onClick={handleExecuteSeal}
                        disabled={sealingSubmitting}
                        className="px-4 py-2 bg-amber-600 hover:bg-amber-500 text-slate-950 font-bold text-xs rounded-lg flex items-center gap-1.5 shadow"
                      >
                        {sealingSubmitting ? (
                          <>
                            <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Sealing FY...
                          </>
                        ) : (
                          'Confirm Seal & Calibrate'
                        )}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* RECORD / UPDATE STATUTORY ANCHOR MODAL */}
          {anchorModalOpen && (
            <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-lg w-full shadow-2xl space-y-4 max-h-[90vh] overflow-y-auto">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <Anchor className="w-5 h-5 text-blue-400" />
                    <h3 className="font-semibold text-white text-sm">
                      Record Filed Statutory Return Anchor (FY {statutoryFy})
                    </h3>
                  </div>
                  <button
                    onClick={() => { setAnchorModalOpen(false); setAnchorErrorMsg(null); }}
                    className="text-slate-400 hover:text-white text-xs"
                  >
                    ✕
                  </button>
                </div>

                <form onSubmit={handleRecordAnchor} className="space-y-3 text-xs">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">Return Form Type:</label>
                      <select
                        value={anchorFormType}
                        onChange={(e) => setAnchorFormType(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                      >
                        <option value="aoc_4">MCA Form AOC-4 (Financials)</option>
                        <option value="itr_6">Income Tax Form ITR-6</option>
                        <option value="mgt_7a">MCA Form MGT-7A (Annual Return)</option>
                        <option value="standalone_audit_report">Independent Auditor's Report</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">SRN / Ack Number:</label>
                      <input
                        type="text"
                        required
                        value={anchorSrn}
                        onChange={(e) => setAnchorSrn(e.target.value)}
                        placeholder="e.g. SRN-F98273612"
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-2">
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">Filing Date:</label>
                      <input
                        type="date"
                        required
                        value={anchorFilingDate}
                        onChange={(e) => setAnchorFilingDate(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                      />
                    </div>
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">Signatory DIN:</label>
                      <input
                        type="text"
                        value={anchorDin}
                        onChange={(e) => setAnchorDin(e.target.value)}
                        placeholder="09876543"
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                      />
                    </div>
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">Auditor UDIN:</label>
                      <input
                        type="text"
                        value={anchorUdin}
                        onChange={(e) => setAnchorUdin(e.target.value)}
                        placeholder="26098765..."
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                      />
                    </div>
                  </div>

                  <div className="border-t border-slate-800 pt-2 space-y-2">
                    <span className="text-slate-400 font-semibold block text-[11px]">
                      Filed Schedule III Balance Sheet Figures (₹):
                    </span>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-slate-400 block mb-0.5 text-[11px]">Paid-up Capital (2010):</label>
                        <input
                          type="number"
                          step="0.01"
                          value={anchorPaidUpCapital}
                          onChange={(e) => setAnchorPaidUpCapital(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-1.5 text-white font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-slate-400 block mb-0.5 text-[11px]">Retained Earnings (2020):</label>
                        <input
                          type="number"
                          step="0.01"
                          value={anchorRetainedEarnings}
                          onChange={(e) => setAnchorRetainedEarnings(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-1.5 text-white font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-slate-400 block mb-0.5 text-[11px]">Trade Payables (2040):</label>
                        <input
                          type="number"
                          step="0.01"
                          value={anchorTradePayables}
                          onChange={(e) => setAnchorTradePayables(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-1.5 text-white font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-slate-400 block mb-0.5 text-[11px]">Cash &amp; Bank Balance (1010):</label>
                        <input
                          type="number"
                          step="0.01"
                          value={anchorBankBalance}
                          onChange={(e) => setAnchorBankBalance(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-1.5 text-white font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-slate-400 block mb-0.5 text-[11px]">Trade Receivables (1020):</label>
                        <input
                          type="number"
                          step="0.01"
                          value={anchorDebtors}
                          onChange={(e) => setAnchorDebtors(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-1.5 text-white font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-slate-400 block mb-0.5 text-[11px]">Fixed Assets / PPE (1050):</label>
                        <input
                          type="number"
                          step="0.01"
                          value={anchorPpe}
                          onChange={(e) => setAnchorPpe(e.target.value)}
                          className="w-full bg-slate-950 border border-slate-800 rounded-lg p-1.5 text-white font-mono"
                        />
                      </div>
                    </div>
                  </div>

                  {anchorErrorMsg && (
                    <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                      {anchorErrorMsg}
                    </div>
                  )}

                  {anchorSuccessMsg && (
                    <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 shrink-0" />
                      {anchorSuccessMsg}
                    </div>
                  )}

                  <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => setAnchorModalOpen(false)}
                      className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={anchorSubmitting}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold text-xs rounded-lg flex items-center gap-1.5 shadow"
                    >
                      {anchorSubmitting ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Recording...
                        </>
                      ) : (
                        'Save Statutory Baseline'
                      )}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

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
          {/* MANAGE FY CLOSING STAGE MODAL (MILESTONE 8.1) */}
          {stageModalOpen && (
            <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-lg w-full shadow-2xl space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <LockKeyhole className="w-5 h-5 text-sky-400" />
                    <h3 className="font-semibold text-white text-sm">
                      Manage Historical FY Closing Stage — FY {lifecycleFy}
                    </h3>
                  </div>
                  <button
                    onClick={() => { setStageModalOpen(false); setStageTransitionError(null); }}
                    className="text-slate-400 hover:text-white text-xs"
                  >
                    ✕
                  </button>
                </div>

                <div className="space-y-4 text-xs">
                  <div>
                    <label className="text-slate-300 font-medium block mb-1.5">Select Target Lifecycle Stage:</label>
                    <div className="space-y-2">
                      <label className={`p-3 rounded-lg border flex items-start gap-2.5 cursor-pointer transition ${
                        selectedTargetStage === 'active'
                          ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-200'
                          : 'bg-slate-950 border-slate-800 text-slate-300 hover:bg-slate-900'
                      }`}>
                        <input
                          type="radio"
                          name="targetStage"
                          checked={selectedTargetStage === 'active'}
                          onChange={() => setSelectedTargetStage('active')}
                          className="mt-0.5"
                        />
                        <div>
                          <div className="font-semibold text-white">Stage 1: Active Operations</div>
                          <div className="text-[11px] text-slate-400 mt-0.5">
                            Unrestricted daily posting of journal entries, vendor bills, and customer invoices.
                          </div>
                        </div>
                      </label>

                      <label className={`p-3 rounded-lg border flex items-start gap-2.5 cursor-pointer transition ${
                        selectedTargetStage === 'audit_closing_window'
                          ? 'bg-amber-500/10 border-amber-500/40 text-amber-200'
                          : 'bg-slate-950 border-slate-800 text-slate-300 hover:bg-slate-900'
                      }`}>
                        <input
                          type="radio"
                          name="targetStage"
                          checked={selectedTargetStage === 'audit_closing_window'}
                          onChange={() => setSelectedTargetStage('audit_closing_window')}
                          className="mt-0.5"
                        />
                        <div>
                          <div className="font-semibold text-white">Stage 2: Year-End Audit &amp; Filing Window</div>
                          <div className="text-[11px] text-slate-400 mt-0.5">
                            Books remain open for pending tasks, depreciation, and CA audit adjustments. Soft confirmation warning on postings.
                          </div>
                        </div>
                      </label>

                      <label className={`p-3 rounded-lg border flex items-start gap-2.5 cursor-pointer transition ${
                        selectedTargetStage === 'statutory_sealed'
                          ? 'bg-indigo-500/10 border-indigo-500/40 text-indigo-200'
                          : 'bg-slate-950 border-slate-800 text-slate-300 hover:bg-slate-900'
                      }`}>
                        <input
                          type="radio"
                          name="targetStage"
                          checked={selectedTargetStage === 'statutory_sealed'}
                          onChange={() => setSelectedTargetStage('statutory_sealed')}
                          className="mt-0.5"
                        />
                        <div>
                          <div className="font-semibold text-white">Stage 3: Cryptographic Statutory Seal</div>
                          <div className="text-[11px] text-slate-400 mt-0.5">
                            Permanently locks books pursuant to Sec 128/130. PostgreSQL trigger hard-blocks all mutations.
                          </div>
                        </div>
                      </label>
                    </div>
                  </div>

                  {selectedTargetStage === 'audit_closing_window' && (
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">Audit Closing Deadline Date:</label>
                      <input
                        type="date"
                        value={targetDeadline}
                        onChange={(e) => setTargetDeadline(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono text-xs"
                      />
                      <p className="text-[11px] text-slate-500 mt-1">
                        Standard deadline for corporate tax audit &amp; ITR filing is 31st October of the assessment year.
                      </p>
                    </div>
                  )}

                  <div>
                    <label className="text-slate-300 font-medium block mb-1">Reason / Statutory Notes:</label>
                    <input
                      type="text"
                      value={stageNotes}
                      onChange={(e) => setStageNotes(e.target.value)}
                      placeholder="e.g. Opened for Year-End CA Audit and Depreciation Run"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white text-xs"
                    />
                  </div>

                  {stageTransitionError && (
                    <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                      {stageTransitionError}
                    </div>
                  )}

                  {stageTransitionSuccess && (
                    <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 shrink-0" />
                      {stageTransitionSuccess}
                    </div>
                  )}

                  <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => setStageModalOpen(false)}
                      className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={handleTransitionStage}
                      disabled={stageTransitionSubmitting}
                      className="px-4 py-2 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg flex items-center gap-1.5 shadow"
                    >
                      {stageTransitionSubmitting ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Updating Stage...
                        </>
                      ) : (
                        'Update Lifecycle Stage'
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* RECORD GST CHALLAN MODAL (MILESTONE 8.2) */}
          {gstChallanModalOpen && (
            <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <Receipt className="w-5 h-5 text-teal-400" />
                    <h3 className="font-semibold text-white text-sm">Record GST Tax Challan Payment</h3>
                  </div>
                  <button
                    onClick={() => { setGstChallanModalOpen(false); setGstChallanErrorMsg(null); }}
                    className="text-slate-400 hover:text-white text-xs"
                  >
                    ✕
                  </button>
                </div>

                <form onSubmit={handleRecordGstChallan} className="space-y-3 text-xs">
                  <div>
                    <label className="text-slate-300 font-medium block mb-1">Challan Reference / Label:</label>
                    <input
                      type="text"
                      required
                      value={gstChallanRef}
                      onChange={(e) => setGstChallanRef(e.target.value)}
                      placeholder="e.g. GST-CHAL-2026-OCT"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">CPIN (14 Digits):</label>
                      <input
                        type="text"
                        required
                        maxLength={14}
                        value={gstChallanCpin}
                        onChange={(e) => setGstChallanCpin(e.target.value)}
                        placeholder="e.g. 26102900123456"
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                      />
                    </div>
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">CIN / Bank Ref:</label>
                      <input
                        type="text"
                        value={gstChallanCin}
                        onChange={(e) => setGstChallanCin(e.target.value)}
                        placeholder="e.g. HDFC26101234"
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">Bank Name:</label>
                      <input
                        type="text"
                        value={gstChallanBank}
                        onChange={(e) => setGstChallanBank(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white"
                      />
                    </div>
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">Payment Date:</label>
                      <input
                        type="date"
                        required
                        value={gstChallanDate}
                        onChange={(e) => setGstChallanDate(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-slate-300 font-medium block mb-1">Total Paid (₹):</label>
                    <input
                      type="number"
                      step="0.01"
                      required
                      value={gstChallanAmount}
                      onChange={(e) => setGstChallanAmount(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                    />
                  </div>

                  {gstChallanErrorMsg && (
                    <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                      {gstChallanErrorMsg}
                    </div>
                  )}

                  {gstChallanSuccessMsg && (
                    <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 shrink-0" />
                      {gstChallanSuccessMsg}
                    </div>
                  )}

                  <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => setGstChallanModalOpen(false)}
                      className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={gstChallanSubmitting}
                      className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white font-semibold text-xs rounded-lg flex items-center gap-1.5 shadow"
                    >
                      {gstChallanSubmitting ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Saving...
                        </>
                      ) : (
                        'Save GST Challan'
                      )}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* PMT-06 HELPER MODAL (MILESTONE 8.2) */}
          {pmt06ModalOpen && (
            <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-lg w-full shadow-2xl space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <FileSpreadsheet className="w-5 h-5 text-teal-400" />
                    <h3 className="font-semibold text-white text-sm">PMT-06 Challan Helper (Quarterly QRMP)</h3>
                  </div>
                  <button
                    onClick={() => setPmt06ModalOpen(false)}
                    className="text-slate-400 hover:text-white text-xs"
                  >
                    ✕
                  </button>
                </div>

                {pmt06Loading ? (
                  <div className="p-8 text-center text-slate-400 flex items-center justify-center gap-2">
                    <RefreshCw className="w-5 h-5 animate-spin text-teal-400" />
                    <span>Preparing PMT-06 packet...</span>
                  </div>
                ) : pmt06Data ? (
                  <div className="space-y-3 text-xs">
                    <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1 font-mono">
                      <div className="flex justify-between text-slate-400">
                        <span>GSTIN:</span>
                        <strong className="text-white">{pmt06Data.gstin}</strong>
                      </div>
                      <div className="flex justify-between text-slate-400">
                        <span>Legal Name:</span>
                        <strong className="text-slate-200">{pmt06Data.legal_name}</strong>
                      </div>
                      <div className="flex justify-between text-slate-400">
                        <span>Quarter / FY:</span>
                        <strong className="text-sky-300">{pmt06Data.quarter} ({pmt06Data.fiscal_year})</strong>
                      </div>
                      <div className="flex justify-between text-slate-400">
                        <span>Major Head:</span>
                        <strong className="text-white">{pmt06Data.challan_details?.major_head}</strong>
                      </div>
                      <div className="flex justify-between text-slate-400">
                        <span>Safe Harbor Buffer (35%):</span>
                        <strong className="text-emerald-400">
                          ₹{(pmt06Data.challan_details?.safe_harbor_buffer_35_pct || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </strong>
                      </div>
                      <div className="flex justify-between text-slate-400 border-t border-slate-800 pt-1 text-sm">
                        <span>Total Recommended Deposit:</span>
                        <strong className="text-teal-300">
                          ₹{(pmt06Data.challan_details?.total_challan_amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </strong>
                      </div>
                    </div>

                    <div className="p-3 rounded-lg bg-teal-500/10 border border-teal-500/20 text-slate-300 text-[11px] leading-relaxed">
                      {pmt06Data.challan_details?.instructions}
                    </div>

                    <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                      <button
                        type="button"
                        onClick={() => setPmt06ModalOpen(false)}
                        className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg"
                      >
                        Close
                      </button>
                      <a
                        href={pmt06Data.challan_details?.gst_portal_url || 'https://services.gst.gov.in'}
                        target="_blank"
                        rel="noreferrer"
                        className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white font-semibold text-xs rounded-lg flex items-center gap-1.5 shadow"
                      >
                        Launch GST Portal <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  </div>
                ) : null}
              </div>
            </div>
          )}

          {/* UPLOAD STATUTORY RETURN MODAL (MILESTONE 8.3) */}
          {dossierUploadModalOpen && (
            <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-lg w-full shadow-2xl space-y-4">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <FolderArchive className="w-5 h-5 text-indigo-400" />
                    <div>
                      <h3 className="font-semibold text-white text-sm">Upload Authentic Statutory Return</h3>
                      <p className="text-[11px] text-slate-400">SHA-256 Deduplicated Sovereign Vault Guard</p>
                    </div>
                  </div>
                  <button
                    onClick={() => { setDossierUploadModalOpen(false); setDossierUploadError(null); setDossierUploadResult(null); }}
                    className="text-slate-400 hover:text-white text-xs"
                  >
                    ✕
                  </button>
                </div>

                <form onSubmit={handleUploadDossier} className="space-y-3 text-xs">
                  <div>
                    <label className="text-slate-300 font-medium block mb-1">Select Return File (PDF):</label>
                    <input
                      type="file"
                      accept=".pdf,application/pdf"
                      required
                      onChange={(e) => setDossierUploadFile(e.target.files?.[0] || null)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono text-xs file:mr-3 file:py-1 file:px-2.5 file:rounded file:border-0 file:text-xs file:bg-indigo-600 file:text-white hover:file:bg-indigo-500"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-slate-300 font-medium block mb-1">Form Category:</label>
                      <select
                        value={dossierFormType}
                        onChange={(e) => setDossierFormType(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                      >
                        <option value="aoc_4">Form AOC-4 (Financials)</option>
                        <option value="itr_6">Form ITR-6 (Income Tax)</option>
                        <option value="auditor_report">Auditor&apos;s Report (UDIN)</option>
                        <option value="boards_report">Board&apos;s Report (Sec 134)</option>
                        <option value="mgt_7a">Form MGT-7 / MGT-7A (Annual Return)</option>
                      </select>
                    </div>

                    <div>
                      <label className="text-slate-300 font-medium block mb-1">Filing Date:</label>
                      <input
                        type="date"
                        value={dossierFilingDate}
                        onChange={(e) => setDossierFilingDate(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="text-slate-300 font-medium block mb-1">SRN / Ack Number (Auto-extracted if blank):</label>
                    <input
                      type="text"
                      value={dossierSrn}
                      onChange={(e) => setDossierSrn(e.target.value)}
                      placeholder="e.g. F98273612 or 998877665544"
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-white font-mono"
                    />
                  </div>

                  {dossierUploadError && (
                    <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs">
                      {dossierUploadError}
                    </div>
                  )}

                  {dossierUploadResult?.is_duplicate && (
                    <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs space-y-1">
                      <div className="font-semibold flex items-center gap-1.5">
                        <AlertTriangle className="w-4 h-4 text-amber-400" />
                        Duplicate Prevented (Zero-Duplication Invariant)
                      </div>
                      <p className="text-[11px] text-slate-300">{dossierUploadResult.message}</p>
                      <p className="font-mono text-[10px] text-slate-400">SHA-256: {dossierUploadResult.sha256}</p>
                    </div>
                  )}

                  {dossierUploadResult && !dossierUploadResult.is_duplicate && (
                    <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 shrink-0" />
                      {dossierUploadResult.message || 'Successfully archived in Sovereign Vault!'}
                    </div>
                  )}

                  <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => setDossierUploadModalOpen(false)}
                      className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-lg"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={dossierUploadSubmitting}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs rounded-lg flex items-center gap-1.5 shadow"
                    >
                      {dossierUploadSubmitting ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" /> Verifying SHA-256 &amp; Saving...
                        </>
                      ) : (
                        'Verify &amp; Archive Return'
                      )}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* TAB 9: TDS & TCS COMPLIANCE (CHALLAN 281 & FORM 26Q) */}
          {activeTab === 'tds_compliance' && <TDSComplianceTab />}

          {/* TAB 10: SCHEDULE II FIXED ASSETS & DEPRECIATION ENGINE */}
          {activeTab === 'fixed_assets' && <FixedAssetsTab />}

          {/* TAB 11: MANDATORY MCA STATUTORY REGISTERS & DISCLOSURES */}
          {activeTab === 'mca_registers' && <MCARegistersTab />}
        </main>
      </div>
    </div>
  );
}
