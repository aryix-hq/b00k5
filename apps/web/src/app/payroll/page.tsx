'use client';

import React, { useEffect, useState } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import {
  Users,
  Plus,
  Calendar,
  Lock,
  Send,
  FileText,
  DollarSign,
  Shield,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Search,
  Filter,
  Check,
  Download,
  CreditCard,
  Building,
  ArrowRight,
  TrendingUp,
  FileSpreadsheet,
  Briefcase,
  X
} from 'lucide-react';
import { fetchApi } from '@/lib/api';

interface Employee {
  id: string;
  employee_code: string;
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
  date_of_joining: string;
  designation?: string;
  department?: string;
  pan_number: string;
  bank_account_number?: string;
  bank_ifsc_code?: string;
  bank_name?: string;
  tax_regime: string;
  pt_state: string;
  is_pf_capped: boolean;
  is_esi_eligible: boolean;
  status: string;
  salary_structures?: SalaryStructure[];
}

interface SalaryStructure {
  id: string;
  employee_id: string;
  effective_from: string;
  annual_ctc: number;
  monthly_basic: number;
  monthly_hra: number;
  monthly_da: number;
  monthly_conveyance: number;
  monthly_special_allowance: number;
  monthly_gross: number;
  employer_pf_monthly: number;
  employer_esi_monthly: number;
  is_active: boolean;
}

interface PayrollRun {
  id: string;
  run_number: string;
  month: number;
  year: number;
  fiscal_year: string;
  status: 'draft' | 'calculated' | 'locked' | 'disbursed';
  total_employees: number;
  total_gross_pay: number;
  total_deductions: number;
  total_net_pay: number;
  total_employer_pf: number;
  total_employer_esi: number;
  total_tds_192: number;
  total_pt: number;
  accrual_journal_id?: string;
  disbursement_journal_id?: string;
  sha256_audit_hash?: string;
  created_at: string;
}

interface Payslip {
  id: string;
  payroll_run_id: string;
  employee_id: string;
  payslip_number: string;
  total_days: number;
  paid_days: number;
  loss_of_pay_days: number;
  basic_earned: number;
  hra_earned: number;
  conveyance_earned: number;
  special_allowance_earned: number;
  gross_earnings: number;
  employee_pf: number;
  employee_esi: number;
  professional_tax: number;
  tds_deducted: number;
  total_deductions: number;
  net_salary: number;
  employer_pf: number;
  employer_eps: number;
  employer_esi: number;
  employer_edli: number;
  payout_status: 'unpaid' | 'paid';
  payout_utr?: string;
}

interface Contractor {
  id: string;
  contractor_code: string;
  name: string;
  contractor_type: 'individual_huf' | 'company_firm';
  pan_number: string;
  gstin?: string;
  tds_section: string;
  tds_rate: number;
  email: string;
  phone?: string;
  address?: string;
  bank_name: string;
  bank_account_number: string;
  bank_ifsc_code: string;
  status: string;
  created_at: string;
}

interface ContractorPayment {
  id: string;
  contractor_id: string;
  payment_number: string;
  invoice_number: string;
  invoice_date: string;
  payment_date: string;
  description: string;
  gross_amount: number;
  gst_rate: number;
  gst_amount: number;
  tds_section: string;
  tds_rate: number;
  tds_amount: number;
  net_payable: number;
  status: 'pending' | 'approved' | 'disbursed';
  accrual_journal_id?: string;
  disbursement_journal_id?: string;
  payout_utr?: string;
  payout_date?: string;
  contractor_name?: string;
  contractor_pan?: string;
  contractor_code?: string;
  created_at: string;
}

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

export default function PayrollPage() {
  const [activeTab, setActiveTab] = useState<'runs' | 'employees' | 'payslips' | 'contractors' | 'statutory'>('runs');
  const [contractors, setContractors] = useState<Contractor[]>([]);
  const [contractorPayments, setContractorPayments] = useState<ContractorPayment[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [runs, setRuns] = useState<PayrollRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<PayrollRun | null>(null);
  const [payslips, setPayslips] = useState<Payslip[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Modals
  const [showOnboardModal, setShowOnboardModal] = useState<boolean>(false);
  const [showNewRunModal, setShowNewRunModal] = useState<boolean>(false);
  const [showDisburseModal, setShowDisburseModal] = useState<boolean>(false);
  const [showPayslipModal, setShowPayslipModal] = useState<boolean>(false);
  const [selectedPayslip, setSelectedPayslip] = useState<Payslip | null>(null);
  const [downloadingFile, setDownloadingFile] = useState<string | null>(null);

  // New Employee Form State
  const [empCode, setEmpCode] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [panNumber, setPanNumber] = useState('');
  const [designation, setDesignation] = useState('');
  const [department, setDepartment] = useState('Engineering');
  const [doj, setDoj] = useState(new Date().toISOString().split('T')[0]);
  const [dob, setDob] = useState('1995-01-01');
  const [taxRegime, setTaxRegime] = useState('new_115bac');
  const [ptState, setPtState] = useState('Karnataka');
  const [isPfCapped, setIsPfCapped] = useState(true);
  const [isEsiEligible, setIsEsiEligible] = useState(false);
  const [bankAccount, setBankAccount] = useState('');
  const [bankIfsc, setBankIfsc] = useState('');
  const [bankName, setBankName] = useState('');

  // Initial Salary Structure
  const [monthlyBasic, setMonthlyBasic] = useState('50000');
  const [monthlyHra, setMonthlyHra] = useState('25000');
  const [monthlyConveyance, setMonthlyConveyance] = useState('5000');
  const [monthlySpecial, setMonthlySpecial] = useState('20000');

  // New Run Form State
  const currentDate = new Date();
  const [newRunMonth, setNewRunMonth] = useState<number>(currentDate.getMonth() + 1);
  const [newRunYear, setNewRunYear] = useState<number>(currentDate.getFullYear());

  // Disbursement Modal State
  const [payoutUtr, setPayoutUtr] = useState('');
  const [bankAccountCode, setBankAccountCode] = useState('1010');

  // Contractor Modals & State
  const [showOnboardContractorModal, setShowOnboardContractorModal] = useState<boolean>(false);
  const [showContractorPaymentModal, setShowContractorPaymentModal] = useState<boolean>(false);

  // New Contractor Form State
  const [contractorCode, setContractorCode] = useState('');
  const [contractorName, setContractorName] = useState('');
  const [contractorType, setContractorType] = useState<'individual_huf' | 'company_firm'>('individual_huf');
  const [contractorPan, setContractorPan] = useState('');
  const [contractorGstin, setContractorGstin] = useState('');
  const [contractorTdsSection, setContractorTdsSection] = useState('194J_TECH');
  const [contractorTdsRate, setContractorTdsRate] = useState('2.00');
  const [contractorEmail, setContractorEmail] = useState('');
  const [contractorPhone, setContractorPhone] = useState('');
  const [contractorAddress, setContractorAddress] = useState('');
  const [contractorBankName, setContractorBankName] = useState('');
  const [contractorBankAccount, setContractorBankAccount] = useState('');
  const [contractorBankIfsc, setContractorBankIfsc] = useState('');

  // Contractor Payment Form State
  const [cpayContractorId, setCpayContractorId] = useState('');
  const [cpayInvoiceNumber, setCpayInvoiceNumber] = useState('');
  const [cpayInvoiceDate, setCpayInvoiceDate] = useState(new Date().toISOString().split('T')[0]);
  const [cpayPaymentDate, setCpayPaymentDate] = useState(new Date().toISOString().split('T')[0]);
  const [cpayDescription, setCpayDescription] = useState('');
  const [cpayGrossAmount, setCpayGrossAmount] = useState('50000');
  const [cpayGstRate, setCpayGstRate] = useState('18');
  const [cpayTdsSection, setCpayTdsSection] = useState('194J_TECH');
  const [cpayTdsRate, setCpayTdsRate] = useState('2');

  // Search filter
  const [employeeSearch, setEmployeeSearch] = useState('');
  const [contractorSearch, setContractorSearch] = useState('');

  useEffect(() => {
    loadPayrollData();
  }, []);

  const loadPayrollData = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [empData, runsData, contractorsData, paymentsData] = await Promise.all([
        fetchApi('/api/v1/payroll/employees').catch(() => []),
        fetchApi('/api/v1/payroll/runs').catch(() => []),
        fetchApi('/api/v1/payroll/contractors').catch(() => []),
        fetchApi('/api/v1/payroll/contractor-payments').catch(() => [])
      ]);
      setEmployees(empData || []);
      setRuns(runsData || []);
      setContractors(contractorsData || []);
      setContractorPayments(paymentsData || []);

      if (runsData && runsData.length > 0) {
        setSelectedRun(runsData[0]);
        loadPayslipsForRun(runsData[0].id);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load payroll data.');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateContractor = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const payload = {
        contractor_code: contractorCode.trim(),
        name: contractorName.trim(),
        contractor_type: contractorType,
        pan_number: contractorPan.trim().toUpperCase(),
        gstin: contractorGstin.trim().toUpperCase() || undefined,
        tds_section: contractorTdsSection,
        tds_rate: parseFloat(contractorTdsRate) || 2.0,
        email: contractorEmail.trim(),
        phone: contractorPhone.trim() || undefined,
        address: contractorAddress.trim() || undefined,
        bank_name: contractorBankName.trim(),
        bank_account_number: contractorBankAccount.trim(),
        bank_ifsc_code: contractorBankIfsc.trim().toUpperCase()
      };
      await fetchApi('/api/v1/payroll/contractors', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      setSuccessMsg('Contractor onboarded successfully!');
      setShowOnboardContractorModal(false);
      setContractorCode('');
      setContractorName('');
      setContractorPan('');
      setContractorGstin('');
      setContractorEmail('');
      setContractorPhone('');
      setContractorAddress('');
      setContractorBankName('');
      setContractorBankAccount('');
      setContractorBankIfsc('');
      loadPayrollData();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to onboard contractor.');
    }
  };

  const handleCreateContractorPayment = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const gross = parseFloat(cpayGrossAmount) || 0;
      const gstRate = parseFloat(cpayGstRate) || 0;
      const gstAmount = gross * (gstRate / 100);
      const payload = {
        contractor_id: cpayContractorId,
        invoice_number: cpayInvoiceNumber.trim(),
        invoice_date: cpayInvoiceDate,
        payment_date: cpayPaymentDate,
        description: cpayDescription.trim(),
        gross_amount: gross,
        gst_rate: gstRate,
        gst_amount: gstAmount,
        tds_section: cpayTdsSection,
        tds_rate: parseFloat(cpayTdsRate) || 2.0
      };
      await fetchApi('/api/v1/payroll/contractor-payments', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      setSuccessMsg('Contractor payment claim created!');
      setShowContractorPaymentModal(false);
      setCpayInvoiceNumber('');
      setCpayDescription('');
      loadPayrollData();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to create payment claim.');
    }
  };

  const handleAccrueContractorPayment = async (paymentId: string) => {
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await fetchApi(`/api/v1/payroll/contractor-payments/${paymentId}/accrue`, { method: 'POST' });
      setSuccessMsg('Bill accrued and Leg 1 journal voucher posted to General Ledger!');
      loadPayrollData();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to accrue contractor payment.');
    }
  };

  const handleDisburseContractorPayment = async (paymentId: string) => {
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await fetchApi(`/api/v1/payroll/contractor-payments/${paymentId}/disburse`, { method: 'POST' });
      setSuccessMsg('Payout disbursed and Leg 2 journal voucher posted to General Ledger!');
      loadPayrollData();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to disburse contractor payment.');
    }
  };

  const loadPayslipsForRun = async (runId: string) => {
    try {
      const slips = await fetchApi(`/api/v1/payroll/runs/${runId}/payslips`);
      setPayslips(slips || []);
    } catch (e) {
      setPayslips([]);
    }
  };

  const handleCreateEmployee = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);

    const basic = parseFloat(monthlyBasic) || 0;
    const hra = parseFloat(monthlyHra) || 0;
    const conveyance = parseFloat(monthlyConveyance) || 0;
    const special = parseFloat(monthlySpecial) || 0;
    const grossMonthly = basic + hra + conveyance + special;
    const annualCtc = grossMonthly * 12;

    const payload = {
      employee_code: empCode.trim(),
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      email: email.trim() || undefined,
      phone: phone.trim() || undefined,
      date_of_birth: dob,
      gender: 'other',
      date_of_joining: doj,
      designation: designation.trim() || undefined,
      department: department.trim() || undefined,
      pan_number: panNumber.trim().toUpperCase(),
      bank_account_number: bankAccount.trim() || undefined,
      bank_ifsc_code: bankIfsc.trim().toUpperCase() || undefined,
      bank_name: bankName.trim() || undefined,
      tax_regime: taxRegime,
      pt_state: ptState,
      is_pf_capped: isPfCapped,
      is_esi_eligible: isEsiEligible,
      initial_salary_structure: {
        effective_from: doj,
        annual_ctc: annualCtc,
        monthly_basic: basic,
        monthly_hra: hra,
        monthly_da: 0,
        monthly_conveyance: conveyance,
        monthly_medical_allowance: 0,
        monthly_special_allowance: special,
        employer_pf_monthly: isPfCapped ? 1800 : Math.round(basic * 0.12),
        employer_esi_monthly: isEsiEligible ? Math.round(grossMonthly * 0.0325) : 0
      }
    };

    try {
      await fetchApi('/api/v1/payroll/employees', {
        method: 'POST',
        body: JSON.stringify(payload)
      });
      setSuccessMsg(`Employee ${empCode} onboarded successfully with CTC structure!`);
      setShowOnboardModal(false);
      resetEmployeeForm();
      loadPayrollData();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to onboard employee.');
    }
  };

  const resetEmployeeForm = () => {
    setEmpCode('');
    setFirstName('');
    setLastName('');
    setEmail('');
    setPhone('');
    setPanNumber('');
    setDesignation('');
    setBankAccount('');
    setBankIfsc('');
    setBankName('');
  };

  const handleInitializeRun = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const created = await fetchApi('/api/v1/payroll/runs', {
        method: 'POST',
        body: JSON.stringify({
          month: Number(newRunMonth),
          year: Number(newRunYear)
        })
      });
      setSuccessMsg(`Payroll run ${created.run_number} initialized and calculated!`);
      setShowNewRunModal(false);
      loadPayrollData();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to initialize payroll run.');
    }
  };

  const handleCalculateRun = async (runId: string) => {
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const updated = await fetchApi(`/api/v1/payroll/runs/${runId}/calculate`, {
        method: 'POST'
      });
      setSuccessMsg(`Calculated payroll for ${updated.total_employees} employees. Gross: ₹${Number(updated.total_gross_pay).toLocaleString('en-IN')}`);
      loadPayrollData();
      if (selectedRun?.id === runId) {
        loadPayslipsForRun(runId);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to calculate run.');
    }
  };

  const handleLockAndAccrue = async (runId: string) => {
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const res = await fetchApi(`/api/v1/payroll/runs/${runId}/lock-and-post-accrual`, {
        method: 'POST'
      });
      setSuccessMsg(`Leg 1 Accrual Journal Voucher #${res.entry_number} posted to General Ledger! Run locked with SHA-256 seal.`);
      loadPayrollData();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to lock and post accrual.');
    }
  };

  const handleDisbursement = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedRun) return;
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const res = await fetchApi(`/api/v1/payroll/runs/${selectedRun.id}/post-disbursement?bank_account_code=${bankAccountCode}&payout_utr=${encodeURIComponent(payoutUtr.trim())}`, {
        method: 'POST'
      });
      setSuccessMsg(`Leg 2 Salary Disbursement Voucher #${res.entry_number} posted! Net payout cleared via Bank ${bankAccountCode}.`);
      setShowDisburseModal(false);
      setPayoutUtr('');
      loadPayrollData();
      loadPayslipsForRun(selectedRun.id);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to post salary disbursement.');
    }
  };

  const handleDownloadFile = async (endpoint: string, defaultFilename: string) => {
    try {
      setDownloadingFile(defaultFilename);
      const token = typeof window !== 'undefined' ? (localStorage.getItem('token') || sessionStorage.getItem('token') || '') : '';
      const tenantId = typeof window !== 'undefined' ? (localStorage.getItem('active_tenant_id') || '') : '';
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}${endpoint}`, {
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
          'X-Tenant-ID': tenantId
        }
      });
      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || 'Failed to download statutory export');
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = defaultFilename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      alert(err.message || 'Error downloading file');
    } finally {
      setDownloadingFile(null);
    }
  };

  const filteredEmployees = employees.filter(emp =>
    `${emp.first_name} ${emp.last_name} ${emp.employee_code} ${emp.designation || ''}`
      .toLowerCase()
      .includes(employeeSearch.toLowerCase())
  );

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'draft':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20">Draft</span>;
      case 'calculated':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-sky-500/10 text-sky-400 border border-sky-500/20">Calculated</span>;
      case 'locked':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 flex items-center gap-1"><Lock className="w-3 h-3" /> Accrued & Locked</span>;
      case 'disbursed':
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Disbursed</span>;
      default:
        return <span className="px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-700 text-slate-300">{status}</span>;
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <Navbar />

        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-5">
            <div>
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                  <Users className="w-6 h-6" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                    Payroll &amp; Statutory Roster
                    <span className="text-xs font-normal px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      Ind AS 19 / Schedule III
                    </span>
                  </h1>
                  <p className="text-sm text-slate-400">
                    Dual-regime Section 192 TDS, EPF, ESIC, Professional Tax, and atomic 3-leg General Ledger vouchers.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowNewRunModal(true)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 rounded-lg text-sm font-medium transition flex items-center gap-2"
              >
                <Calendar className="w-4 h-4 text-sky-400" />
                New Payroll Run
              </button>
              <button
                onClick={() => setShowOnboardModal(true)}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition shadow-lg shadow-emerald-950/40 flex items-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Onboard Employee
              </button>
            </div>
          </div>

          {/* Alert Banners */}
          {errorMsg && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-sm flex items-center gap-3">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}
          {successMsg && (
            <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-sm flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80">
              <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
                <span>Active Roster</span>
                <Users className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-2xl font-bold text-white">{employees.length}</div>
              <div className="text-xs text-slate-500 mt-1">Active salaried employees</div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80">
              <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
                <span>Latest Run Gross Pay</span>
                <TrendingUp className="w-4 h-4 text-sky-400" />
              </div>
              <div className="text-2xl font-bold text-white">
                ₹{runs[0] ? Number(runs[0].total_gross_pay).toLocaleString('en-IN') : '0.00'}
              </div>
              <div className="text-xs text-slate-500 mt-1">{runs[0] ? runs[0].run_number : 'No runs executed'}</div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80">
              <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
                <span>Net Salary Payable</span>
                <DollarSign className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="text-2xl font-bold text-emerald-400">
                ₹{runs[0] ? Number(runs[0].total_net_pay).toLocaleString('en-IN') : '0.00'}
              </div>
              <div className="text-xs text-slate-500 mt-1">GL Account 2070 balance</div>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800/80">
              <div className="flex items-center justify-between text-slate-400 text-xs mb-1">
                <span>Statutory Dues Withheld</span>
                <ShieldCheck className="w-4 h-4 text-indigo-400" />
              </div>
              <div className="text-2xl font-bold text-indigo-300">
                ₹{runs[0] ? Number(runs[0].total_deductions).toLocaleString('en-IN') : '0.00'}
              </div>
              <div className="text-xs text-slate-500 mt-1">EPF + ESI + PT + TDS 192</div>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="flex border-b border-slate-800 gap-6">
            <button
              onClick={() => setActiveTab('runs')}
              className={`pb-3 text-sm font-medium transition relative ${
                activeTab === 'runs' ? 'text-emerald-400' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Payroll Runs & General Ledger
              {activeTab === 'runs' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-500" />}
            </button>
            <button
              onClick={() => setActiveTab('employees')}
              className={`pb-3 text-sm font-medium transition relative ${
                activeTab === 'employees' ? 'text-emerald-400' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Employee Roster & CTC ({employees.length})
              {activeTab === 'employees' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-500" />}
            </button>
            <button
              onClick={() => setActiveTab('payslips')}
              className={`pb-3 text-sm font-medium transition relative ${
                activeTab === 'payslips' ? 'text-emerald-400' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Itemized Payslips ({payslips.length})
              {activeTab === 'payslips' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-500" />}
            </button>
            <button
              onClick={() => setActiveTab('contractors')}
              className={`pb-3 text-sm font-medium transition relative ${
                activeTab === 'contractors' ? 'text-emerald-400' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Contractors &amp; Freelancers ({contractors.length})
              {activeTab === 'contractors' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-500" />}
            </button>
            <button
              onClick={() => setActiveTab('statutory')}
              className={`pb-3 text-sm font-medium transition relative ${
                activeTab === 'statutory' ? 'text-emerald-400' : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Statutory Breakdown &amp; Schedule III
              {activeTab === 'statutory' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-emerald-500" />}
            </button>
          </div>

          {/* TAB 1: PAYROLL RUNS */}
          {activeTab === 'runs' && (
            <div className="space-y-4">
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 font-medium">
                    <tr>
                      <th className="py-3 px-4">Period</th>
                      <th className="py-3 px-4">Run Number</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4 text-right">Headcount</th>
                      <th className="py-3 px-4 text-right">Gross Earnings</th>
                      <th className="py-3 px-4 text-right">Deductions</th>
                      <th className="py-3 px-4 text-right">Net Payable</th>
                      <th className="py-3 px-4 text-center">SHA-256 Seal</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {runs.length === 0 ? (
                      <tr>
                        <td colSpan={9} className="py-12 text-center text-slate-500">
                          No payroll runs generated yet. Click &quot;New Payroll Run&quot; to initialize monthly processing.
                        </td>
                      </tr>
                    ) : (
                      runs.map(run => (
                        <tr
                          key={run.id}
                          className={`hover:bg-slate-800/40 transition cursor-pointer ${
                            selectedRun?.id === run.id ? 'bg-slate-800/25' : ''
                          }`}
                          onClick={() => {
                            setSelectedRun(run);
                            loadPayslipsForRun(run.id);
                          }}
                        >
                          <td className="py-3 px-4 font-medium text-white">
                            {MONTH_NAMES[run.month - 1]} {run.year}
                          </td>
                          <td className="py-3 px-4 font-mono text-xs text-slate-300">{run.run_number}</td>
                          <td className="py-3 px-4">{getStatusBadge(run.status)}</td>
                          <td className="py-3 px-4 text-right text-slate-300">{run.total_employees}</td>
                          <td className="py-3 px-4 text-right font-mono text-slate-200">
                            ₹{Number(run.total_gross_pay).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="py-3 px-4 text-right font-mono text-rose-400">
                            ₹{Number(run.total_deductions).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="py-3 px-4 text-right font-mono font-bold text-emerald-400">
                            ₹{Number(run.total_net_pay).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                          </td>
                          <td className="py-3 px-4 text-center">
                            {run.sha256_audit_hash ? (
                              <span
                                title={run.sha256_audit_hash}
                                className="inline-flex items-center gap-1 font-mono text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                              >
                                <ShieldCheck className="w-3.5 h-3.5" />
                                {run.sha256_audit_hash.slice(0, 8)}...
                              </span>
                            ) : (
                              <span className="text-xs text-slate-600">Unsealed</span>
                            )}
                          </td>
                          <td className="py-3 px-4 text-right space-x-2">
                            {run.status === 'draft' && (
                              <button
                                onClick={e => {
                                  e.stopPropagation();
                                  handleCalculateRun(run.id);
                                }}
                                className="px-2.5 py-1 text-xs rounded bg-sky-600 hover:bg-sky-500 text-white font-medium"
                              >
                                Calculate
                              </button>
                            )}
                            {run.status === 'calculated' && (
                              <button
                                onClick={e => {
                                  e.stopPropagation();
                                  handleLockAndAccrue(run.id);
                                }}
                                className="px-2.5 py-1 text-xs rounded bg-indigo-600 hover:bg-indigo-500 text-white font-medium flex-inline items-center gap-1"
                              >
                                <Lock className="w-3 h-3 inline mr-1" />
                                Post Accrual
                              </button>
                            )}
                            {run.status === 'locked' && (
                              <button
                                onClick={e => {
                                  e.stopPropagation();
                                  setSelectedRun(run);
                                  setShowDisburseModal(true);
                                }}
                                className="px-2.5 py-1 text-xs rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium"
                              >
                                Disburse
                              </button>
                            )}
                            <button
                              onClick={e => {
                                e.stopPropagation();
                                setSelectedRun(run);
                                loadPayslipsForRun(run.id);
                                setActiveTab('payslips');
                              }}
                              className="px-2 py-1 text-xs text-slate-400 hover:text-slate-200"
                            >
                              Slips →
                            </button>

                            {run.status !== 'draft' && (
                              <span className="inline-flex items-center gap-1 ml-1 border-l border-slate-800 pl-2">
                                <button
                                  onClick={e => {
                                    e.stopPropagation();
                                    handleDownloadFile(`/api/v1/payroll/runs/${run.id}/export/epfo-ecr`, `ECR_${run.run_number}_${run.month}_${run.year}.txt`);
                                  }}
                                  className="px-2 py-0.5 text-[10px] font-mono rounded bg-slate-800 hover:bg-slate-700 text-sky-400 border border-slate-700"
                                  title="Download EPFO ECR 2.0 Text Return"
                                >
                                  ECR
                                </button>
                                <button
                                  onClick={e => {
                                    e.stopPropagation();
                                    handleDownloadFile(`/api/v1/payroll/runs/${run.id}/export/esic`, `ESIC_${run.run_number}_${run.month}_${run.year}.csv`);
                                  }}
                                  className="px-2 py-0.5 text-[10px] font-mono rounded bg-slate-800 hover:bg-slate-700 text-amber-400 border border-slate-700"
                                  title="Download ESIC Monthly Return CSV"
                                >
                                  ESI
                                </button>
                                <button
                                  onClick={e => {
                                    e.stopPropagation();
                                    handleDownloadFile(`/api/v1/payroll/runs/${run.id}/export/pt`, `PT_${run.run_number}_${run.month}_${run.year}.csv`);
                                  }}
                                  className="px-2 py-0.5 text-[10px] font-mono rounded bg-slate-800 hover:bg-slate-700 text-indigo-400 border border-slate-700"
                                  title="Download Professional Tax Return CSV"
                                >
                                  PT
                                </button>
                              </span>
                            )}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* 3-Leg Accounting Explainer Card */}
              <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 text-xs text-slate-400 flex flex-col md:flex-row gap-4 justify-between items-center">
                <div>
                  <div className="font-semibold text-slate-200 mb-1 flex items-center gap-1.5">
                    <Shield className="w-4 h-4 text-emerald-400" />
                    Double-Entry Statutory Accounting Invariants
                  </div>
                  <div>
                    Leg 1: Dr. Salaries (4020) &amp; Employer PF/ESI (4021/4022) ↔ Cr. Net Salaries Payable (2070) &amp; Statutory Duties (2071-2076).
                  </div>
                  <div>
                    Leg 2: Dr. Net Salaries Payable (2070) ↔ Cr. Bank (1010). Unpaid salaries automatically map to Schedule III Note 7.
                  </div>
                </div>
                <div className="shrink-0 font-mono text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20">
                  |Debits - Credits| ≡ 0.00
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: EMPLOYEE ROSTER */}
          {activeTab === 'employees' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-4">
                <div className="relative flex-1 max-w-sm">
                  <Search className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                  <input
                    type="text"
                    value={employeeSearch}
                    onChange={e => setEmployeeSearch(e.target.value)}
                    placeholder="Search by code, name, designation..."
                    className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <button
                  onClick={() => setShowOnboardModal(true)}
                  className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition flex items-center gap-1.5"
                >
                  <Plus className="w-4 h-4" />
                  Add Employee
                </button>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 font-medium">
                    <tr>
                      <th className="py-3 px-4">Code</th>
                      <th className="py-3 px-4">Employee Name</th>
                      <th className="py-3 px-4">Designation &amp; Dept</th>
                      <th className="py-3 px-4">PAN</th>
                      <th className="py-3 px-4">Regime</th>
                      <th className="py-3 px-4">PT State</th>
                      <th className="py-3 px-4 text-right">Monthly Gross</th>
                      <th className="py-3 px-4 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {filteredEmployees.length === 0 ? (
                      <tr>
                        <td colSpan={8} className="py-12 text-center text-slate-500">
                          No employees onboarded yet. Click &quot;Add Employee&quot; to get started.
                        </td>
                      </tr>
                    ) : (
                      filteredEmployees.map(emp => {
                        const activeStruct = emp.salary_structures?.find(s => s.is_active);
                        return (
                          <tr key={emp.id} className="hover:bg-slate-800/30 transition">
                            <td className="py-3 px-4 font-mono font-medium text-white">{emp.employee_code}</td>
                            <td className="py-3 px-4">
                              <div className="font-medium text-slate-200">{emp.first_name} {emp.last_name}</div>
                              <div className="text-xs text-slate-500">{emp.email || 'No email registered'}</div>
                            </td>
                            <td className="py-3 px-4">
                              <div className="text-slate-300">{emp.designation || 'Staff'}</div>
                              <div className="text-xs text-slate-500">{emp.department || 'Operations'}</div>
                            </td>
                            <td className="py-3 px-4 font-mono text-xs text-slate-300">{emp.pan_number}</td>
                            <td className="py-3 px-4">
                              <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                                {emp.tax_regime === 'new_115bac' ? '115BAC (New)' : 'Old Regime'}
                              </span>
                            </td>
                            <td className="py-3 px-4 text-slate-300 text-xs">{emp.pt_state}</td>
                            <td className="py-3 px-4 text-right font-mono font-semibold text-slate-100">
                              {activeStruct ? `₹${Number(activeStruct.monthly_gross).toLocaleString('en-IN')}` : 'Not set'}
                            </td>
                            <td className="py-3 px-4 text-center">
                              <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                {emp.status}
                              </span>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 3: ITEMIZED PAYSLIPS */}
          {activeTab === 'payslips' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <span className="text-sm text-slate-400">Viewing Run:</span>
                  <select
                    value={selectedRun?.id || ''}
                    onChange={e => {
                      const run = runs.find(r => r.id === e.target.value);
                      if (run) {
                        setSelectedRun(run);
                        loadPayslipsForRun(run.id);
                      }
                    }}
                    className="bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-200 px-3 py-1.5 focus:outline-none focus:border-emerald-500"
                  >
                    {runs.map(r => (
                      <option key={r.id} value={r.id}>
                        {r.run_number} ({MONTH_NAMES[r.month - 1]} {r.year}) - {r.status.toUpperCase()}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="text-xs text-slate-400">
                  Total Slips: <span className="font-bold text-white">{payslips.length}</span>
                </div>
              </div>

              <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 font-medium text-xs">
                    <tr>
                      <th className="py-3 px-3">Slip #</th>
                      <th className="py-3 px-3">Employee</th>
                      <th className="py-3 px-3 text-right">Paid Days</th>
                      <th className="py-3 px-3 text-right">Gross Earnings</th>
                      <th className="py-3 px-3 text-right">PF</th>
                      <th className="py-3 px-3 text-right">ESI</th>
                      <th className="py-3 px-3 text-right">PT</th>
                      <th className="py-3 px-3 text-right">TDS 192</th>
                      <th className="py-3 px-3 text-right font-bold text-emerald-400">Net Take-Home</th>
                      <th className="py-3 px-3 text-center">Payout</th>
                      <th className="py-3 px-3 text-center">Receipt</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 text-xs">
                    {payslips.length === 0 ? (
                      <tr>
                        <td colSpan={11} className="py-12 text-center text-slate-500">
                          No payslips calculated for this run yet. Run &quot;Calculate&quot; in Payroll Runs tab.
                        </td>
                      </tr>
                    ) : (
                      payslips.map(ps => {
                        const emp = employees.find(e => e.id === ps.employee_id);
                        return (
                          <tr key={ps.id} className="hover:bg-slate-800/30 transition">
                            <td className="py-3 px-3 font-mono text-slate-400">{ps.payslip_number}</td>
                            <td className="py-3 px-3">
                              <div className="font-medium text-white">{emp ? `${emp.first_name} ${emp.last_name}` : 'Employee'}</div>
                              <div className="text-slate-500 font-mono">{emp?.employee_code}</div>
                            </td>
                            <td className="py-3 px-3 text-right text-slate-300">{ps.paid_days}</td>
                            <td className="py-3 px-3 text-right font-mono text-slate-200">
                              ₹{Number(ps.gross_earnings).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                            </td>
                            <td className="py-3 px-3 text-right font-mono text-slate-300">₹{Number(ps.employee_pf).toFixed(2)}</td>
                            <td className="py-3 px-3 text-right font-mono text-slate-300">₹{Number(ps.employee_esi).toFixed(2)}</td>
                            <td className="py-3 px-3 text-right font-mono text-slate-300">₹{Number(ps.professional_tax).toFixed(2)}</td>
                            <td className="py-3 px-3 text-right font-mono text-slate-300">₹{Number(ps.tds_deducted).toFixed(2)}</td>
                            <td className="py-3 px-3 text-right font-mono font-bold text-emerald-400">
                              ₹{Number(ps.net_salary).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                            </td>
                            <td className="py-3 px-3 text-center">
                              {ps.payout_status === 'paid' ? (
                                <span className="px-2 py-0.5 rounded-full text-2xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" title={`UTR: ${ps.payout_utr}`}>
                                  Paid
                                </span>
                              ) : (
                                <span className="px-2 py-0.5 rounded-full text-2xs bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                  Unpaid
                                </span>
                              )}
                            </td>
                            <td className="py-3 px-3 text-center whitespace-nowrap">
                              <button
                                onClick={() => {
                                  setSelectedPayslip(ps);
                                  setShowPayslipModal(true);
                                }}
                                className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-2xs font-medium"
                              >
                                View
                              </button>
                              <button
                                onClick={() => {
                                  handleDownloadFile(
                                    `/api/v1/payroll/employees/${ps.employee_id}/form-16/pdf?financial_year=${selectedRun?.fiscal_year || '2026-27'}`,
                                    `Form16_${emp?.employee_code || ps.employee_id}_${(selectedRun?.fiscal_year || '2026-27').replace('/', '-')}.pdf`
                                  );
                                }}
                                className="ml-1 px-2 py-1 rounded bg-indigo-950/60 hover:bg-indigo-900 border border-indigo-700/50 text-indigo-300 text-2xs font-medium"
                                title="Download Section 192 Form 16 PDF"
                              >
                                Form 16
                              </button>
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 4: STATUTORY BREAKDOWN & SCHEDULE III */}
          {activeTab === 'statutory' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Employee Benefits (P&L Note 17) */}
                <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <h3 className="font-semibold text-white flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-sky-400" />
                      P&amp;L Statement — Note 17: Employee Benefits Expense
                    </h3>
                    <span className="text-xs font-mono text-slate-400">Debit Accounts (4020-4023)</span>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between py-1.5 border-b border-slate-800/40">
                      <span className="text-slate-400">4020 Salaries &amp; Wages</span>
                      <span className="font-mono text-white">
                        ₹{selectedRun ? Number(selectedRun.total_gross_pay).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
                      </span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800/40">
                      <span className="text-slate-400">4021 Contribution to Provident Fund</span>
                      <span className="font-mono text-white">
                        ₹{selectedRun ? Number(selectedRun.total_employer_pf).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
                      </span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800/40">
                      <span className="text-slate-400">4022 Contribution to ESI</span>
                      <span className="font-mono text-white">
                        ₹{selectedRun ? Number(selectedRun.total_employer_esi).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
                      </span>
                    </div>
                    <div className="flex justify-between pt-2 font-bold">
                      <span className="text-slate-200">Total Employee Benefits Cost (CTC Burden)</span>
                      <span className="font-mono text-emerald-400">
                        ₹{selectedRun
                          ? (Number(selectedRun.total_gross_pay) + Number(selectedRun.total_employer_pf) + Number(selectedRun.total_employer_esi)).toLocaleString('en-IN', { minimumFractionDigits: 2 })
                          : '0.00'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Current Liabilities (Balance Sheet Note 7) */}
                <div className="p-5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <h3 className="font-semibold text-white flex items-center gap-2">
                      <Building className="w-4 h-4 text-emerald-400" />
                      Balance Sheet — Note 7: Other Current Liabilities
                    </h3>
                    <span className="text-xs font-mono text-slate-400">Credit Accounts (2070-2076)</span>
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between py-1.5 border-b border-slate-800/40">
                      <span className="text-slate-400">2070 Salaries &amp; Wages Payable (Net Pay)</span>
                      <span className="font-mono text-white">
                        ₹{selectedRun ? Number(selectedRun.total_net_pay).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
                      </span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800/40">
                      <span className="text-slate-400">2071 &amp; 2072 PF Dues (Employee + Employer)</span>
                      <span className="font-mono text-white">
                        ₹{selectedRun ? (Number(selectedRun.total_employer_pf) * 2).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
                      </span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800/40">
                      <span className="text-slate-400">2073 &amp; 2074 ESI Dues (Employee + Employer)</span>
                      <span className="font-mono text-white">
                        ₹{selectedRun ? (Number(selectedRun.total_employer_esi) * 1.23).toFixed(2) : '0.00'}
                      </span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800/40">
                      <span className="text-slate-400">2075 Professional Tax (PT) Payable</span>
                      <span className="font-mono text-white">
                        ₹{selectedRun ? Number(selectedRun.total_pt).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
                      </span>
                    </div>
                    <div className="flex justify-between py-1.5 border-b border-slate-800/40">
                      <span className="text-slate-400">2076 TDS on Salaries (Sec 192) Payable</span>
                      <span className="font-mono text-white">
                        ₹{selectedRun ? Number(selectedRun.total_tds_192).toLocaleString('en-IN', { minimumFractionDigits: 2 }) : '0.00'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Statutory Due Dates & Exporters Banner */}
              <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800 grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
                <div className="space-y-2 p-3 rounded-lg bg-slate-800/40 border border-slate-800/80 flex flex-col justify-between">
                  <div>
                    <div className="font-semibold text-slate-200 flex items-center justify-between">
                      <span>EPFO ECR 2.0 Return</span>
                      <span className="text-[10px] text-sky-400">Due 15th</span>
                    </div>
                    <div className="text-slate-400 text-[11px] mt-1">EPF Scheme Paragraph 38 official text return file.</div>
                  </div>
                  <button
                    disabled={!selectedRun || selectedRun.status === 'draft'}
                    onClick={() => {
                      if (!selectedRun) return;
                      handleDownloadFile(`/api/v1/payroll/runs/${selectedRun.id}/export/epfo-ecr`, `ECR_${selectedRun.run_number}_${selectedRun.month}_${selectedRun.year}.txt`);
                    }}
                    className="w-full mt-2 px-2.5 py-1.5 rounded bg-sky-950/60 hover:bg-sky-900 border border-sky-800/50 text-sky-300 text-xs font-medium flex items-center justify-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed transition"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download EPFO ECR (.txt)
                  </button>
                </div>

                <div className="space-y-2 p-3 rounded-lg bg-slate-800/40 border border-slate-800/80 flex flex-col justify-between">
                  <div>
                    <div className="font-semibold text-slate-200 flex items-center justify-between">
                      <span>ESIC Monthly Return</span>
                      <span className="text-[10px] text-amber-400">Due 15th</span>
                    </div>
                    <div className="text-slate-400 text-[11px] mt-1">Monthly wage contribution sheet for ESIC IP portal.</div>
                  </div>
                  <button
                    disabled={!selectedRun || selectedRun.status === 'draft'}
                    onClick={() => {
                      if (!selectedRun) return;
                      handleDownloadFile(`/api/v1/payroll/runs/${selectedRun.id}/export/esic`, `ESIC_${selectedRun.run_number}_${selectedRun.month}_${selectedRun.year}.csv`);
                    }}
                    className="w-full mt-2 px-2.5 py-1.5 rounded bg-amber-950/60 hover:bg-amber-900 border border-amber-800/50 text-amber-300 text-xs font-medium flex items-center justify-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed transition"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download ESIC Return (.csv)
                  </button>
                </div>

                <div className="space-y-2 p-3 rounded-lg bg-slate-800/40 border border-slate-800/80 flex flex-col justify-between">
                  <div>
                    <div className="font-semibold text-slate-200 flex items-center justify-between">
                      <span>Professional Tax (PT) Form 5</span>
                      <span className="text-[10px] text-indigo-400">Due 20th</span>
                    </div>
                    <div className="text-slate-400 text-[11px] mt-1">State-wise slab distribution and liability schedule.</div>
                  </div>
                  <button
                    disabled={!selectedRun || selectedRun.status === 'draft'}
                    onClick={() => {
                      if (!selectedRun) return;
                      handleDownloadFile(`/api/v1/payroll/runs/${selectedRun.id}/export/pt`, `PT_Return_${selectedRun.run_number}_${selectedRun.month}_${selectedRun.year}.csv`);
                    }}
                    className="w-full mt-2 px-2.5 py-1.5 rounded bg-indigo-950/60 hover:bg-indigo-900 border border-indigo-800/50 text-indigo-300 text-xs font-medium flex items-center justify-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed transition"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download PT Form 5 (.csv)
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: CONTRACTORS & FREELANCERS */}
          {activeTab === 'contractors' && (
            <div className="space-y-6">
              {/* Header Action Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-slate-900/60 border border-slate-800">
                <div>
                  <h2 className="text-base font-semibold text-white flex items-center gap-2">
                    <Briefcase className="w-5 h-5 text-emerald-400" />
                    Contractors, Retainers &amp; Freelancers Roster
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Process contractor payouts with automated Section 194C (1%/2%) &amp; 194J (2%/10%) TDS withholding, Ledger posting, and Form 16A certificates.
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => {
                      if (contractors.length > 0 && !cpayContractorId) {
                        setCpayContractorId(contractors[0].id);
                        setCpayTdsSection(contractors[0].tds_section);
                        setCpayTdsRate(String(contractors[0].tds_rate));
                      }
                      setShowContractorPaymentModal(true);
                    }}
                    className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition flex items-center gap-1.5 shadow-lg shadow-indigo-950/40"
                  >
                    <Plus className="w-4 h-4" />
                    Record Payout Claim
                  </button>
                  <button
                    onClick={() => {
                      setContractorCode(`CON-${String(contractors.length + 1).padStart(3, '0')}`);
                      setShowOnboardContractorModal(true);
                    }}
                    className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium transition flex items-center gap-1.5 shadow-lg shadow-emerald-950/40"
                  >
                    <Plus className="w-4 h-4" />
                    Onboard Contractor
                  </button>
                </div>
              </div>

              {/* Contractor Directory Table */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
                <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-white">Active Contractor Directory</span>
                    <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
                      {contractors.length}
                    </span>
                  </div>
                  <div className="relative w-64">
                    <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
                    <input
                      type="text"
                      placeholder="Search name, code, PAN..."
                      value={contractorSearch}
                      onChange={(e) => setContractorSearch(e.target.value)}
                      className="w-full bg-slate-800/60 border border-slate-700/80 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 font-medium text-xs">
                      <tr>
                        <th className="py-3 px-4">Code &amp; Name</th>
                        <th className="py-3 px-4">Entity Type</th>
                        <th className="py-3 px-4">PAN / GSTIN</th>
                        <th className="py-3 px-4">Statutory Scheme</th>
                        <th className="py-3 px-4">Bank Details</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4 text-right">Form 16A</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 text-xs">
                      {contractors.length === 0 ? (
                        <tr>
                          <td colSpan={7} className="py-8 text-center text-slate-500">
                            No contractors onboarded yet. Click &quot;Onboard Contractor&quot; to add your first vendor or freelancer.
                          </td>
                        </tr>
                      ) : (
                        contractors
                          .filter(c =>
                            !contractorSearch ||
                            c.name.toLowerCase().includes(contractorSearch.toLowerCase()) ||
                            c.contractor_code.toLowerCase().includes(contractorSearch.toLowerCase()) ||
                            c.pan_number.toLowerCase().includes(contractorSearch.toLowerCase())
                          )
                          .map(c => (
                            <tr key={c.id} className="hover:bg-slate-800/30 transition">
                              <td className="py-3 px-4">
                                <div className="font-semibold text-white">{c.name}</div>
                                <div className="text-[11px] font-mono text-slate-400">{c.contractor_code} • {c.email}</div>
                              </td>
                              <td className="py-3 px-4">
                                <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                                  c.contractor_type === 'individual_huf' ? 'bg-sky-500/10 text-sky-400 border border-sky-500/20' : 'bg-purple-500/10 text-purple-400 border border-purple-500/20'
                                }`}>
                                  {c.contractor_type === 'individual_huf' ? 'Individual / HUF' : 'Company / Firm'}
                                </span>
                              </td>
                              <td className="py-3 px-4 font-mono">
                                <div className="text-slate-200">{c.pan_number}</div>
                                {c.gstin && <div className="text-[10px] text-slate-400">{c.gstin}</div>}
                              </td>
                              <td className="py-3 px-4">
                                <span className="font-medium text-emerald-400">
                                  {c.tds_section === '194C' ? 'Sec 194C (Contractor)' : c.tds_section === '194J_PROF' ? 'Sec 194J (Professional)' : 'Sec 194J (Technical)'}
                                </span>
                                <div className="text-[11px] text-slate-400 font-mono">TDS Rate: {Number(c.tds_rate).toFixed(1)}%</div>
                              </td>
                              <td className="py-3 px-4">
                                <div className="text-slate-300">{c.bank_name}</div>
                                <div className="font-mono text-[11px] text-slate-500">A/C: ••••{c.bank_account_number.slice(-4)} • {c.bank_ifsc_code}</div>
                              </td>
                              <td className="py-3 px-4">
                                <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/20 text-emerald-300">
                                  {c.status.toUpperCase()}
                                </span>
                              </td>
                              <td className="py-3 px-4 text-right">
                                <button
                                  onClick={() => handleDownloadFile(`/api/v1/payroll/contractors/${c.id}/form-16a/pdf`, `Form16A_${c.contractor_code}_2026-27.pdf`)}
                                  className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-white transition inline-flex items-center gap-1.5 text-xs"
                                >
                                  <Download className="w-3.5 h-3.5 text-sky-400" />
                                  Certificate
                                </button>
                              </td>
                            </tr>
                          ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Payment Claims & Ledger Vouchers Table */}
              <div className="bg-slate-900/60 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
                <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                  <div>
                    <h3 className="text-sm font-semibold text-white">Contractor Invoices &amp; Payout Claims</h3>
                    <p className="text-xs text-slate-400 mt-0.5">Two-leg accounting lifecycle: Leg 1 Accrual (Expense/TDS) and Leg 2 Disbursement (Bank Payout).</p>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-900 border-b border-slate-800 text-slate-400 font-medium text-xs">
                      <tr>
                        <th className="py-3 px-4">Payment Ref</th>
                        <th className="py-3 px-4">Contractor</th>
                        <th className="py-3 px-4">Invoice Details</th>
                        <th className="py-3 px-4">Description</th>
                        <th className="py-3 px-4 text-right">Gross (₹)</th>
                        <th className="py-3 px-4 text-right">TDS (₹)</th>
                        <th className="py-3 px-4 text-right">Net Payable (₹)</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 text-xs">
                      {contractorPayments.length === 0 ? (
                        <tr>
                          <td colSpan={9} className="py-8 text-center text-slate-500">
                            No contractor invoices submitted yet. Click &quot;Record Payout Claim&quot; to initiate a retainer or bill payout.
                          </td>
                        </tr>
                      ) : (
                        contractorPayments.map(p => (
                          <tr key={p.id} className="hover:bg-slate-800/30 transition">
                            <td className="py-3 px-4 font-mono font-medium text-sky-400">
                              {p.payment_number}
                            </td>
                            <td className="py-3 px-4">
                              <div className="font-semibold text-white">{p.contractor_name || 'Contractor'}</div>
                              <div className="text-[11px] font-mono text-slate-500">{p.contractor_code}</div>
                            </td>
                            <td className="py-3 px-4">
                              <div className="font-mono text-slate-200">#{p.invoice_number}</div>
                              <div className="text-[11px] text-slate-500">{p.invoice_date}</div>
                            </td>
                            <td className="py-3 px-4 text-slate-300 max-w-xs truncate">
                              {p.description}
                            </td>
                            <td className="py-3 px-4 text-right font-mono text-slate-200">
                              ₹{Number(p.gross_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                            </td>
                            <td className="py-3 px-4 text-right font-mono text-rose-400">
                              -₹{Number(p.tds_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                              <div className="text-[10px] text-slate-500">{p.tds_section} @ {Number(p.tds_rate).toFixed(1)}%</div>
                            </td>
                            <td className="py-3 px-4 text-right font-mono font-semibold text-emerald-400">
                              ₹{Number(p.net_payable).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                            </td>
                            <td className="py-3 px-4">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                                p.status === 'disbursed' ? 'bg-emerald-500/20 text-emerald-300' :
                                p.status === 'approved' ? 'bg-blue-500/20 text-blue-300' :
                                'bg-amber-500/20 text-amber-300'
                              }`}>
                                {p.status.toUpperCase()}
                              </span>
                              {p.payout_utr && (
                                <div className="text-[10px] font-mono text-slate-400 mt-0.5">{p.payout_utr}</div>
                              )}
                            </td>
                            <td className="py-3 px-4 text-right">
                              {p.status === 'pending' && (
                                <button
                                  onClick={() => handleAccrueContractorPayment(p.id)}
                                  className="px-2.5 py-1 rounded bg-blue-600 hover:bg-blue-500 text-white font-medium text-xs transition"
                                >
                                  Accrue (Leg 1)
                                </button>
                              )}
                              {p.status === 'approved' && (
                                <button
                                  onClick={() => handleDisburseContractorPayment(p.id)}
                                  className="px-2.5 py-1 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-medium text-xs transition flex items-center gap-1 ml-auto"
                                >
                                  <Send className="w-3 h-3" />
                                  Disburse (Leg 2)
                                </button>
                              )}
                              {p.status === 'disbursed' && (
                                <button
                                  onClick={() => handleDownloadFile(`/api/v1/payroll/contractors/${p.contractor_id}/form-16a/pdf`, `Form16A_${p.contractor_code || 'CON'}_2026-27.pdf`)}
                                  className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition inline-flex items-center gap-1"
                                >
                                  <Download className="w-3 h-3 text-sky-400" />
                                  Form 16A
                                </button>
                              )}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* MODAL: ONBOARD EMPLOYEE */}
          {showOnboardModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl my-8">
                <div className="flex items-center justify-between p-5 border-b border-slate-800">
                  <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <Users className="w-5 h-5 text-emerald-400" />
                    Onboard Employee
                  </h2>
                  <button onClick={() => setShowOnboardModal(false)} className="text-slate-400 hover:text-white">
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <form onSubmit={handleCreateEmployee} className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
                  {/* Basic Information */}
                  <div>
                    <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                      1. Demographic &amp; Employment Details
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Employee Code *</label>
                        <input
                          type="text"
                          required
                          value={empCode}
                          onChange={e => setEmpCode(e.target.value)}
                          placeholder="e.g. EMP-101"
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500 font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">First Name *</label>
                        <input
                          type="text"
                          required
                          value={firstName}
                          onChange={e => setFirstName(e.target.value)}
                          placeholder="First Name"
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Last Name *</label>
                        <input
                          type="text"
                          required
                          value={lastName}
                          onChange={e => setLastName(e.target.value)}
                          placeholder="Last Name"
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Work Email</label>
                        <input
                          type="email"
                          value={email}
                          onChange={e => setEmail(e.target.value)}
                          placeholder="name@company.com"
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Designation</label>
                        <input
                          type="text"
                          value={designation}
                          onChange={e => setDesignation(e.target.value)}
                          placeholder="e.g. Senior Software Engineer"
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Department</label>
                        <input
                          type="text"
                          value={department}
                          onChange={e => setDepartment(e.target.value)}
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Date of Joining</label>
                        <input
                          type="date"
                          value={doj}
                          onChange={e => setDoj(e.target.value)}
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Date of Birth</label>
                        <input
                          type="date"
                          value={dob}
                          onChange={e => setDob(e.target.value)}
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Statutory & Tax Settings */}
                  <div>
                    <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                      2. Statutory &amp; Withholding Profile
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Permanent Account Number (PAN) *</label>
                        <input
                          type="text"
                          required
                          maxLength={10}
                          value={panNumber}
                          onChange={e => setPanNumber(e.target.value.toUpperCase())}
                          placeholder="ABCDE1234F"
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500 font-mono uppercase"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Income Tax Regime</label>
                        <select
                          value={taxRegime}
                          onChange={e => setTaxRegime(e.target.value)}
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500"
                        >
                          <option value="new_115bac">New Regime (115BAC - Default)</option>
                          <option value="old_regime">Old Regime (with 80C/80D/24b)</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Professional Tax State</label>
                        <select
                          value={ptState}
                          onChange={e => setPtState(e.target.value)}
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500"
                        >
                          <option value="Karnataka">Karnataka (₹200 on &ge;₹25k)</option>
                          <option value="Maharashtra">Maharashtra (₹200 / ₹300 Feb)</option>
                          <option value="Delhi">Delhi (Exempt)</option>
                        </select>
                      </div>
                    </div>

                    <div className="flex gap-6 mt-3">
                      <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={isPfCapped}
                          onChange={e => setIsPfCapped(e.target.checked)}
                          className="rounded bg-slate-800 border-slate-700 text-emerald-500 focus:ring-0"
                        />
                        Cap PF calculation wage at ₹15,000 statutory ceiling
                      </label>
                      <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={isEsiEligible}
                          onChange={e => setIsEsiEligible(e.target.checked)}
                          className="rounded bg-slate-800 border-slate-700 text-emerald-500 focus:ring-0"
                        />
                        Enable ESI (Wage &le; ₹21,000)
                      </label>
                    </div>
                  </div>

                  {/* Banking Details */}
                  <div>
                    <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                      3. Direct Deposit Bank Coordinates
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Bank Account Number</label>
                        <input
                          type="text"
                          value={bankAccount}
                          onChange={e => setBankAccount(e.target.value)}
                          placeholder="e.g. 5010012345678"
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500 font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Bank IFSC Code</label>
                        <input
                          type="text"
                          maxLength={11}
                          value={bankIfsc}
                          onChange={e => setBankIfsc(e.target.value.toUpperCase())}
                          placeholder="HDFC0000050"
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500 font-mono uppercase"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Bank Name</label>
                        <input
                          type="text"
                          value={bankName}
                          onChange={e => setBankName(e.target.value)}
                          placeholder="e.g. HDFC Bank"
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-emerald-500"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Monthly CTC Structure Breakdown */}
                  <div>
                    <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
                      4. Monthly CTC Structure Breakdown (₹)
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Basic Salary *</label>
                        <input
                          type="number"
                          required
                          value={monthlyBasic}
                          onChange={e => setMonthlyBasic(e.target.value)}
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">House Rent Allowance (HRA)</label>
                        <input
                          type="number"
                          value={monthlyHra}
                          onChange={e => setMonthlyHra(e.target.value)}
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Conveyance Allowance</label>
                        <input
                          type="number"
                          value={monthlyConveyance}
                          onChange={e => setMonthlyConveyance(e.target.value)}
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white font-mono"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Special Allowance</label>
                        <input
                          type="number"
                          value={monthlySpecial}
                          onChange={e => setMonthlySpecial(e.target.value)}
                          className="w-full px-3 py-1.5 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white font-mono"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => setShowOnboardModal(false)}
                      className="px-4 py-2 rounded-lg text-sm text-slate-400 hover:text-white"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition shadow-lg shadow-emerald-950/40"
                    >
                      Onboard &amp; Activate
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* MODAL: NEW PAYROLL RUN */}
          {showNewRunModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl">
                <div className="flex items-center justify-between p-5 border-b border-slate-800">
                  <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <Calendar className="w-5 h-5 text-sky-400" />
                    Initialize Monthly Payroll Run
                  </h2>
                  <button onClick={() => setShowNewRunModal(false)} className="text-slate-400 hover:text-white">
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <form onSubmit={handleInitializeRun} className="p-6 space-y-4">
                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Payroll Month</label>
                    <select
                      value={newRunMonth}
                      onChange={e => setNewRunMonth(Number(e.target.value))}
                      className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-sky-500"
                    >
                      {MONTH_NAMES.map((name, idx) => (
                        <option key={idx + 1} value={idx + 1}>
                          {name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Year</label>
                    <input
                      type="number"
                      value={newRunYear}
                      onChange={e => setNewRunYear(Number(e.target.value))}
                      className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:border-sky-500 font-mono"
                    />
                  </div>

                  <div className="p-3 rounded-lg bg-sky-500/10 border border-sky-500/20 text-xs text-sky-300">
                    This will automatically snapshot current active employee salary structures and compute itemized payslips.
                  </div>

                  <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => setShowNewRunModal(false)}
                      className="px-4 py-2 rounded-lg text-sm text-slate-400 hover:text-white"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-5 py-2 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-sm font-medium transition"
                    >
                      Create &amp; Compute
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* MODAL: POST SALARY DISBURSEMENT (LEG 2) */}
          {showDisburseModal && selectedRun && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl">
                <div className="flex items-center justify-between p-5 border-b border-slate-800">
                  <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <Send className="w-5 h-5 text-emerald-400" />
                    Post Salary Disbursement (Leg 2)
                  </h2>
                  <button onClick={() => setShowDisburseModal(false)} className="text-slate-400 hover:text-white">
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <form onSubmit={handleDisbursement} className="p-6 space-y-4">
                  <div className="p-3.5 rounded-xl bg-slate-800/80 border border-slate-700 space-y-1">
                    <div className="text-xs text-slate-400">Total Net Salaries to Disburse:</div>
                    <div className="text-2xl font-bold font-mono text-emerald-400">
                      ₹{Number(selectedRun.total_net_pay).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </div>
                    <div className="text-xs text-slate-400">Across {selectedRun.total_employees} employee bank accounts.</div>
                  </div>

                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Operating Bank Account Code</label>
                    <input
                      type="text"
                      value={bankAccountCode}
                      onChange={e => setBankAccountCode(e.target.value)}
                      placeholder="1010"
                      className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white font-mono focus:outline-none focus:border-emerald-500"
                    />
                    <span className="text-2xs text-slate-500">Credited in Leg 2 General Ledger journal voucher.</span>
                  </div>

                  <div>
                    <label className="block text-xs text-slate-400 mb-1">Bank Payment Reference / UTR Number</label>
                    <input
                      type="text"
                      required
                      value={payoutUtr}
                      onChange={e => setPayoutUtr(e.target.value)}
                      placeholder="e.g. CMS98234823901"
                      className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white font-mono focus:outline-none focus:border-emerald-500"
                    />
                    <span className="text-2xs text-slate-500">Stamped on employee payslips for proof of settlement.</span>
                  </div>

                  <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => setShowDisburseModal(false)}
                      className="px-4 py-2 rounded-lg text-sm text-slate-400 hover:text-white"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-sm font-medium transition shadow-lg shadow-emerald-950/40"
                    >
                      Confirm Payout
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* MODAL: VIEW PAYSLIP */}
          {showPayslipModal && selectedPayslip && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl overflow-hidden shadow-2xl p-6 space-y-6">
                <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                  <div>
                    <h2 className="text-lg font-bold text-white">Salary Payslip</h2>
                    <p className="text-xs text-slate-400">Slip #{selectedPayslip.payslip_number}</p>
                  </div>
                  <button onClick={() => setShowPayslipModal(false)} className="text-slate-400 hover:text-white">
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-4 text-xs">
                  <div className="p-3 bg-slate-800/50 rounded-lg space-y-1">
                    <span className="text-slate-500 font-semibold uppercase">Earnings</span>
                    <div className="flex justify-between"><span>Basic:</span> <span className="font-mono text-white">₹{Number(selectedPayslip.basic_earned).toFixed(2)}</span></div>
                    <div className="flex justify-between"><span>HRA:</span> <span className="font-mono text-white">₹{Number(selectedPayslip.hra_earned).toFixed(2)}</span></div>
                    <div className="flex justify-between"><span>Conveyance:</span> <span className="font-mono text-white">₹{Number(selectedPayslip.conveyance_earned).toFixed(2)}</span></div>
                    <div className="flex justify-between"><span>Special:</span> <span className="font-mono text-white">₹{Number(selectedPayslip.special_allowance_earned).toFixed(2)}</span></div>
                    <div className="flex justify-between font-bold border-t border-slate-700 pt-1 text-slate-200">
                      <span>Gross:</span>
                      <span className="font-mono">₹{Number(selectedPayslip.gross_earnings).toFixed(2)}</span>
                    </div>
                  </div>

                  <div className="p-3 bg-slate-800/50 rounded-lg space-y-1">
                    <span className="text-slate-500 font-semibold uppercase">Deductions</span>
                    <div className="flex justify-between"><span>EPF (12%):</span> <span className="font-mono text-rose-300">₹{Number(selectedPayslip.employee_pf).toFixed(2)}</span></div>
                    <div className="flex justify-between"><span>ESIC:</span> <span className="font-mono text-rose-300">₹{Number(selectedPayslip.employee_esi).toFixed(2)}</span></div>
                    <div className="flex justify-between"><span>Prof. Tax:</span> <span className="font-mono text-rose-300">₹{Number(selectedPayslip.professional_tax).toFixed(2)}</span></div>
                    <div className="flex justify-between"><span>TDS (Sec 192):</span> <span className="font-mono text-rose-300">₹{Number(selectedPayslip.tds_deducted).toFixed(2)}</span></div>
                    <div className="flex justify-between font-bold border-t border-slate-700 pt-1 text-slate-200">
                      <span>Total:</span>
                      <span className="font-mono text-rose-400">₹{Number(selectedPayslip.total_deductions).toFixed(2)}</span>
                    </div>
                  </div>
                </div>

                <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex items-center justify-between">
                  <div>
                    <span className="text-xs text-emerald-400 font-medium">Net Take-Home Salary</span>
                    <div className="text-2xl font-bold font-mono text-emerald-300">
                      ₹{Number(selectedPayslip.net_salary).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </div>
                  </div>
                  <div className="text-right">
                    <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                      selectedPayslip.payout_status === 'paid' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'
                    }`}>
                      {selectedPayslip.payout_status.toUpperCase()}
                    </span>
                    {selectedPayslip.payout_utr && (
                      <div className="text-2xs font-mono text-slate-400 mt-1">UTR: {selectedPayslip.payout_utr}</div>
                    )}
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <button
                    onClick={() => setShowPayslipModal(false)}
                    className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-lg text-sm font-medium"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* MODAL: ONBOARD CONTRACTOR */}
          {showOnboardContractorModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl my-8">
                <div className="flex items-center justify-between p-5 border-b border-slate-800">
                  <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <Briefcase className="w-5 h-5 text-emerald-400" />
                    Onboard Contractor or Professional Freelancer
                  </h2>
                  <button
                    onClick={() => setShowOnboardContractorModal(false)}
                    className="text-slate-400 hover:text-slate-200 transition"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <form onSubmit={handleCreateContractor} className="p-6 space-y-4 max-h-[80vh] overflow-y-auto text-xs">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Contractor Code</label>
                      <input
                        type="text"
                        required
                        value={contractorCode}
                        onChange={(e) => setContractorCode(e.target.value)}
                        placeholder="e.g. CON-001"
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Entity Type</label>
                      <select
                        value={contractorType}
                        onChange={(e: any) => {
                          setContractorType(e.target.value);
                          if (contractorTdsSection === '194C') {
                            setContractorTdsRate(e.target.value === 'individual_huf' ? '1.00' : '2.00');
                          }
                        }}
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white"
                      >
                        <option value="individual_huf">Individual / Proprietorship / HUF (194C 1%)</option>
                        <option value="company_firm">Company / LLP / Partnership Firm (194C 2%)</option>
                      </select>
                    </div>
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1 font-medium">Full Name / Legal Entity Name</label>
                    <input
                      type="text"
                      required
                      value={contractorName}
                      onChange={(e) => setContractorName(e.target.value)}
                      placeholder="e.g. Arya DevOps Consulting LLP"
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">PAN Number (10 characters)</label>
                      <input
                        type="text"
                        required
                        maxLength={10}
                        value={contractorPan}
                        onChange={(e) => setContractorPan(e.target.value.toUpperCase())}
                        placeholder="e.g. AABCA1234F"
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono uppercase"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">GSTIN (Optional, 15 chars)</label>
                      <input
                        type="text"
                        maxLength={15}
                        value={contractorGstin}
                        onChange={(e) => setContractorGstin(e.target.value.toUpperCase())}
                        placeholder="e.g. 29AABCA1234F1Z5"
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono uppercase"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4 p-3 bg-slate-800/40 border border-slate-700/60 rounded-xl">
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Statutory TDS Scheme</label>
                      <select
                        value={contractorTdsSection}
                        onChange={(e) => {
                          const sec = e.target.value;
                          setContractorTdsSection(sec);
                          if (sec === '194C') {
                            setContractorTdsRate(contractorType === 'individual_huf' ? '1.00' : '2.00');
                          } else if (sec === '194J_PROF') {
                            setContractorTdsRate('10.00');
                          } else {
                            setContractorTdsRate('2.00');
                          }
                        }}
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white"
                      >
                        <option value="194J_TECH">Section 194J(a) — Technical Services / Royalty (2%)</option>
                        <option value="194J_PROF">Section 194J(b) — Professional Services (10%)</option>
                        <option value="194C">Section 194C — Payments to Contractors (1% / 2%)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Default TDS Rate (%)</label>
                      <input
                        type="number"
                        step="0.01"
                        required
                        value={contractorTdsRate}
                        onChange={(e) => setContractorTdsRate(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Email Address</label>
                      <input
                        type="email"
                        required
                        value={contractorEmail}
                        onChange={(e) => setContractorEmail(e.target.value)}
                        placeholder="vendor@company.com"
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Phone Number</label>
                      <input
                        type="text"
                        value={contractorPhone}
                        onChange={(e) => setContractorPhone(e.target.value)}
                        placeholder="9876543210"
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1 font-medium">Registered / Billing Address</label>
                    <textarea
                      rows={2}
                      value={contractorAddress}
                      onChange={(e) => setContractorAddress(e.target.value)}
                      placeholder="Street, City, State, PIN"
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white"
                    />
                  </div>

                  <div className="grid grid-cols-3 gap-3 p-3 bg-slate-800/40 border border-slate-700/60 rounded-xl">
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Bank Name</label>
                      <input
                        type="text"
                        required
                        value={contractorBankName}
                        onChange={(e) => setContractorBankName(e.target.value)}
                        placeholder="e.g. HDFC Bank"
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Account Number</label>
                      <input
                        type="text"
                        required
                        value={contractorBankAccount}
                        onChange={(e) => setContractorBankAccount(e.target.value)}
                        placeholder="Account Number"
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">IFSC Code</label>
                      <input
                        type="text"
                        required
                        value={contractorBankIfsc}
                        onChange={(e) => setContractorBankIfsc(e.target.value.toUpperCase())}
                        placeholder="HDFC0001234"
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono uppercase"
                      />
                    </div>
                  </div>

                  <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => setShowOnboardContractorModal(false)}
                      className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-medium shadow-lg shadow-emerald-950/40"
                    >
                      Onboard Contractor
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* MODAL: CONTRACTOR PAYOUT CLAIM */}
          {showContractorPaymentModal && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
              <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-xl overflow-hidden shadow-2xl my-8">
                <div className="flex items-center justify-between p-5 border-b border-slate-800">
                  <h2 className="text-lg font-bold text-white flex items-center gap-2">
                    <CreditCard className="w-5 h-5 text-indigo-400" />
                    Record Contractor Invoice / Payout Claim
                  </h2>
                  <button
                    onClick={() => setShowContractorPaymentModal(false)}
                    className="text-slate-400 hover:text-slate-200 transition"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <form onSubmit={handleCreateContractorPayment} className="p-6 space-y-4 text-xs">
                  <div>
                    <label className="block text-slate-400 mb-1 font-medium">Select Contractor</label>
                    <select
                      required
                      value={cpayContractorId}
                      onChange={(e) => {
                        const cid = e.target.value;
                        setCpayContractorId(cid);
                        const match = contractors.find(c => c.id === cid);
                        if (match) {
                          setCpayTdsSection(match.tds_section);
                          setCpayTdsRate(String(match.tds_rate));
                        }
                      }}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white text-xs"
                    >
                      <option value="">-- Choose Contractor --</option>
                      {contractors.map(c => (
                        <option key={c.id} value={c.id}>
                          {c.name} ({c.contractor_code} • PAN: {c.pan_number})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Invoice Number</label>
                      <input
                        type="text"
                        required
                        value={cpayInvoiceNumber}
                        onChange={(e) => setCpayInvoiceNumber(e.target.value)}
                        placeholder="e.g. INV-2026-042"
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Invoice Date</label>
                      <input
                        type="date"
                        required
                        value={cpayInvoiceDate}
                        onChange={(e) => setCpayInvoiceDate(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-slate-400 mb-1 font-medium">Nature / Description of Services</label>
                    <input
                      type="text"
                      required
                      value={cpayDescription}
                      onChange={(e) => setCpayDescription(e.target.value)}
                      placeholder="e.g. Frontend Architecture Consulting & Code Review"
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">Gross Base Amount (₹)</label>
                      <input
                        type="number"
                        step="0.01"
                        required
                        value={cpayGrossAmount}
                        onChange={(e) => setCpayGrossAmount(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
                      />
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">GST Rate (%)</label>
                      <select
                        value={cpayGstRate}
                        onChange={(e) => setCpayGstRate(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white"
                      >
                        <option value="0">0% (Nil / Unregistered)</option>
                        <option value="5">5%</option>
                        <option value="12">12%</option>
                        <option value="18">18% (Standard Services)</option>
                        <option value="28">28%</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">TDS Section</label>
                      <select
                        value={cpayTdsSection}
                        onChange={(e) => setCpayTdsSection(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white"
                      >
                        <option value="194J_TECH">Section 194J(a) Technical (2%)</option>
                        <option value="194J_PROF">Section 194J(b) Professional (10%)</option>
                        <option value="194C">Section 194C Contractor (1% / 2%)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-slate-400 mb-1 font-medium">TDS Rate (%)</label>
                      <input
                        type="number"
                        step="0.01"
                        required
                        value={cpayTdsRate}
                        onChange={(e) => setCpayTdsRate(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono"
                      />
                    </div>
                  </div>

                  {/* Live Calculation Card */}
                  {(() => {
                    const gross = parseFloat(cpayGrossAmount) || 0;
                    const gst = gross * ((parseFloat(cpayGstRate) || 0) / 100);
                    const tds = gross * ((parseFloat(cpayTdsRate) || 0) / 100);
                    const net = gross + gst - tds;
                    return (
                      <div className="p-3 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-1.5 text-xs">
                        <div className="flex justify-between text-slate-400">
                          <span>Base Invoice Value:</span>
                          <span className="font-mono text-white">₹{gross.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between text-slate-400">
                          <span>GST Added:</span>
                          <span className="font-mono text-white">₹{gst.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between text-rose-400">
                          <span>TDS Withheld u/s {cpayTdsSection}:</span>
                          <span className="font-mono">-₹{tds.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between pt-1 border-t border-slate-700 font-bold text-emerald-400 text-sm">
                          <span>Net Payable to Contractor:</span>
                          <span className="font-mono">₹{net.toFixed(2)}</span>
                        </div>
                      </div>
                    );
                  })()}

                  <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => setShowContractorPaymentModal(false)}
                      className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={!cpayContractorId}
                      className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg font-medium shadow-lg shadow-indigo-950/40 disabled:opacity-40"
                    >
                      Create Payout Claim
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

