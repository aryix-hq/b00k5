'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard,
  Receipt,
  FolderLock,
  Scale,
  KeyRound,
  FileSpreadsheet,
  ShieldCheck,
  BookOpen,
  Settings,
  Cloud,
  Users,
  Calculator,
  Database,
  Wallet,
  Building2,
  FileText,
  Activity,
  Server,
  UserCheck,
  ShieldAlert,
  ArrowDownLeft,
  Info,
  ExternalLink
} from 'lucide-react';
import { AboutModal } from './AboutModal';

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

export function Sidebar() {
  const pathname = usePathname();
  const [role, setRole] = useState<string>('owner');
  const [isSuperAdmin, setIsSuperAdmin] = useState<boolean>(false);
  const [showAboutModal, setShowAboutModal] = useState<boolean>(false);

  useEffect(() => {
    const updateRoles = () => {
      if (typeof window !== 'undefined') {
        const storedRole = (localStorage.getItem('b00k5_role') || 'owner').toLowerCase();
        const storedSuper = localStorage.getItem('b00k5_is_super_admin') === 'true';
        setRole(storedRole);
        setIsSuperAdmin(storedSuper);
      }
    };

    updateRoles();
    window.addEventListener('storage', updateRoles);
    window.addEventListener('b00k5_tenant_changed', updateRoles);
    return () => {
      window.removeEventListener('storage', updateRoles);
      window.removeEventListener('b00k5_tenant_changed', updateRoles);
    };
  }, []);

  const isCA = role.includes('ca') || role.includes('auditor');
  const isEmployee = role === 'employee';
  const isOwner = !isCA && !isEmployee;

  let navSections: NavSection[] = [];
  let roleBadgeLabel = 'Owner Mode';
  let roleBadgeColor = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';

  if (isSuperAdmin) {
    roleBadgeLabel = 'Super Admin';
    roleBadgeColor = 'bg-rose-500/10 text-rose-400 border-rose-500/20';
    navSections = [
      {
        title: 'Platform Administration',
        items: [
          { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
          { name: 'Tenant Directory', href: '/admin/tenants', icon: Building2 },
          { name: 'Global IAM & Access', href: '/iam', icon: Users },
          { name: 'Database Backup & Restore', href: '/settings/integrations', icon: Database },
          { name: 'System Telemetry', href: '/admin/system', icon: Activity },
        ],
      },
      {
        title: 'Operations',
        items: [
          { name: 'Tax Invoices & AR', href: '/invoices', icon: Receipt },
          { name: 'Record Vendor Bill', href: '/expenses/new', icon: Receipt },
          { name: 'Expenses & Reimbursements', href: '/expenses', icon: Wallet },
          { name: 'Bank Feeds & Reconciliation', href: '/reconciliation', icon: FileSpreadsheet },
          { name: 'Year Book & Schedule III', href: '/yearbook', icon: BookOpen },
        ],
      },
      {
        title: 'Statutory & Governance',
        items: [
          { name: 'Statutory Governance (SS-1)', href: '/governance', icon: Scale },
          { name: 'Hardware DSC Signing', href: '/dsc', icon: KeyRound },
          { name: 'Document Vault', href: '/vault', icon: FolderLock },
          { name: 'Company Legal Profile', href: '/settings/company-profile', icon: Settings },
        ],
      },
      {
        title: 'Financial Tools',
        items: [
          { name: 'General Ledger', href: '/reports/general-ledger', icon: FileSpreadsheet },
          { name: 'Margin & GST Calculator', href: '/calculator', icon: Calculator },
        ],
      },
      {
        title: 'Cloud & Database',
        items: [
          { name: 'Google Drive Sync', href: '/gdrive', icon: Cloud },
          { name: 'Database Backups', href: '/settings/integrations', icon: Database },
        ],
      },
    ];
  } else if (isCA) {
    roleBadgeLabel = 'CA / Auditor Mode';
    roleBadgeColor = 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20';
    navSections = [
      {
        title: 'Audit & Financial Statements',
        items: [
          { name: 'Audit Dashboard', href: '/dashboard', icon: LayoutDashboard },
          { name: 'Year Book & Filings', href: '/yearbook', icon: BookOpen },
          { name: 'Schedule III Balance Sheet', href: '/yearbook?tab=schedule_iii', icon: FileText, badge: 'ICAI' },
          { name: 'General Ledger & Journals', href: '/reports/general-ledger', icon: FileSpreadsheet },
        ],
      },
      {
        title: 'Audit Verification Feeds',
        items: [
          { name: 'Bank Reconciliations', href: '/reconciliation', icon: FileSpreadsheet },
          { name: 'Inward Bills & ITC Audit', href: '/expenses', icon: Wallet },
          { name: 'Outward Tax Invoices', href: '/invoices', icon: Receipt },
          { name: 'Statutory Document Vault', href: '/vault', icon: FolderLock },
        ],
      },
      {
        title: 'Compliance & Secretarial',
        items: [
          { name: 'SS-1 Governance Minutes', href: '/governance', icon: Scale },
          { name: 'Statutory Profile', href: '/settings/company-profile', icon: Settings },
        ],
      },
    ];
  } else if (isEmployee) {
    roleBadgeLabel = 'Employee Portal';
    roleBadgeColor = 'bg-amber-500/10 text-amber-400 border-amber-500/20';
    navSections = [
      {
        title: 'My Workspace',
        items: [
          { name: 'Submit Out-of-Pocket Bill', href: '/expenses/new', icon: Receipt },
          { name: 'My Expense Claims', href: '/expenses', icon: Wallet },
        ],
      },
      {
        title: 'Account Settings',
        items: [
          { name: 'My Profile', href: '/settings/company-profile', icon: Settings },
        ],
      },
    ];
  } else {
    // Owner Mode (Full Enterprise ERP)
    roleBadgeLabel = 'Company Owner';
    roleBadgeColor = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
    navSections = [
      {
        title: 'Operations',
        items: [
          { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
          { name: 'Tax Invoices & AR', href: '/invoices', icon: Receipt },
          { name: 'Record Vendor Bill', href: '/expenses/new', icon: Receipt },
          { name: 'Expenses & Reimbursements', href: '/expenses', icon: Wallet },
          { name: 'Bank Feeds & Reconciliation', href: '/reconciliation', icon: FileSpreadsheet },
          { name: 'Year Book & Schedule III', href: '/yearbook', icon: BookOpen },
        ],
      },
      {
        title: 'Statutory & Governance',
        items: [
          { name: 'Statutory Governance (SS-1)', href: '/governance', icon: Scale },
          { name: 'Hardware DSC Signing', href: '/dsc', icon: KeyRound },
          { name: 'Document Vault', href: '/vault', icon: FolderLock },
          { name: 'Team & Access (IAM)', href: '/iam', icon: Users },
          { name: 'Company Legal Profile', href: '/settings/company-profile', icon: Settings },
        ],
      },
      {
        title: 'Financial Tools',
        items: [
          { name: 'General Ledger', href: '/reports/general-ledger', icon: FileSpreadsheet },
          { name: 'Margin & GST Calculator', href: '/calculator', icon: Calculator },
        ],
      },
      {
        title: 'Cloud & Database',
        items: [
          { name: 'Google Drive Sync', href: '/gdrive', icon: Cloud },
          { name: 'Database Backups', href: '/settings/integrations', icon: Database },
        ],
      },
    ];
  }

  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-900/50 flex flex-col justify-between p-4 shrink-0 overflow-y-auto">
      <div>
        <div className="flex items-center gap-3 px-3 py-4 mb-4 border-b border-slate-800">
          <div className="w-9 h-9 rounded-lg bg-sky-500/20 border border-sky-500/30 flex items-center justify-center text-sky-400 font-mono font-bold text-lg">
            b5
          </div>
          <div className="flex-1 min-w-0">
            <h1 className="font-bold tracking-tight text-white flex items-center gap-1.5">
              b00k5
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                v1.0
              </span>
            </h1>
            <div className="mt-1">
              <span className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold border tracking-wide uppercase ${roleBadgeColor}`}>
                {roleBadgeLabel}
              </span>
            </div>
          </div>
        </div>

        <nav className="space-y-4">
          {navSections.map((section) => (
            <div key={section.title} className="space-y-1">
              <div className="px-3 text-[10px] font-mono font-semibold uppercase tracking-wider text-slate-400">
                {section.title}
              </div>
              <div className="space-y-0.5">
                {section.items.map((item) => {
                  const isActive = pathname === item.href;
                  const Icon = item.icon;
                  return (
                    <Link
                      key={item.name}
                      href={item.href}
                      className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                        isActive
                          ? 'bg-sky-500/10 text-sky-400 border border-sky-500/20 shadow-sm font-semibold'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                      }`}
                    >
                      <div className="flex items-center gap-2.5 truncate">
                        <Icon className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-sky-400' : 'text-slate-400'}`} />
                        <span className="truncate">{item.name}</span>
                      </div>
                      {item.badge && (
                        <span className="px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 text-[9px] font-mono">
                          {item.badge}
                        </span>
                      )}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </div>

      <div className="border-t border-slate-800 pt-3 mt-4 px-2 space-y-2.5">
        <div className="flex items-center gap-2 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 rounded-lg">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
          <span className="text-[11px] font-medium">Statutory &amp; Tax Compliant</span>
        </div>

        <div className="px-1 pt-1 space-y-1.5">
          <div className="flex items-center justify-between text-[11px]">
            <button
              id="sidebar-about-btn"
              type="button"
              onClick={() => setShowAboutModal(true)}
              className="text-slate-400 hover:text-white flex items-center gap-1 font-medium transition cursor-pointer"
            >
              <Info className="w-3 h-3 text-sky-400" />
              <span>About b00k5</span>
            </button>
            <span className="text-[10px] font-mono text-slate-500">v1.0.4</span>
          </div>

          <div className="text-[10px] text-slate-500 flex items-center justify-between pt-0.5">
            <span>Crafted by</span>
            <a
              id="sidebar-aryix-link"
              href="https://www.aryix.co.in/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-300 hover:text-sky-400 font-bold tracking-wide flex items-center gap-1 transition"
            >
              <span>ARYIX</span>
              <ExternalLink className="w-2.5 h-2.5" />
            </a>
          </div>
        </div>
      </div>

      <AboutModal isOpen={showAboutModal} onClose={() => setShowAboutModal(false)} />
    </aside>
  );
}
