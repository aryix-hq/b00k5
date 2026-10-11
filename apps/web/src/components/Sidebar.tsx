'use client';

import React from 'react';
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
  Wallet
} from 'lucide-react';

interface NavItem {
  name: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

const navSections: NavSection[] = [
  {
    title: 'Operations',
    items: [
      { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
      { name: 'Expenses & Founder Claims', href: '/expenses', icon: Wallet },
      { name: 'Record Vendor Bill / Expense', href: '/expenses/new', icon: Receipt },
      { name: 'Invoices & AR', href: '/invoices', icon: Receipt },
      { name: 'Bank Reconciliation', href: '/reconciliation', icon: FileSpreadsheet },
      { name: 'Year Book', href: '/yearbook', icon: BookOpen },
    ],
  },
  {
    title: 'Statutory & Governance',
    items: [
      { name: 'Company Profile & Filings', href: '/settings/company-profile', icon: Settings },
      { name: 'Statutory Governance', href: '/governance', icon: Scale },
      { name: 'Team & Access (IAM)', href: '/iam', icon: Users },
      { name: 'Document Vault', href: '/vault', icon: FolderLock },
      { name: 'DSC & eSign', href: '/dsc', icon: KeyRound },
    ],
  },
  {
    title: 'Financial Tools',
    items: [
      { name: 'Margin & GST Calculator', href: '/calculator', icon: Calculator },
      { name: 'General Ledger', href: '/reports/general-ledger', icon: FileSpreadsheet },
    ],
  },
  {
    title: 'Settings & Cloud',
    items: [
      { name: 'Google Drive Sync', href: '/gdrive', icon: Cloud },
      { name: 'Database Backup', href: '/settings/integrations', icon: Database },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r border-slate-800 bg-slate-900/50 flex flex-col justify-between p-4 shrink-0 overflow-y-auto">
      <div>
        <div className="flex items-center gap-3 px-3 py-4 mb-4 border-b border-slate-800">
          <div className="w-9 h-9 rounded-lg bg-sky-500/20 border border-sky-500/30 flex items-center justify-center text-sky-400 font-mono font-bold text-lg">
            b5
          </div>
          <div>
            <h1 className="font-bold tracking-tight text-white flex items-center gap-1.5">
              b00k5
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                v1.0
              </span>
            </h1>
            <p className="text-xs text-slate-400">Financial Operating System</p>
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
                      className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                        isActive
                          ? 'bg-sky-500/10 text-sky-400 border border-sky-500/20 shadow-sm font-semibold'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                      }`}
                    >
                      <Icon className={`w-3.5 h-3.5 shrink-0 ${isActive ? 'text-sky-400' : 'text-slate-400'}`} />
                      <span className="truncate">{item.name}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>
      </div>

      <div className="border-t border-slate-800 pt-3 mt-4 px-2">
        <div className="flex items-center gap-2 text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-2 rounded-lg">
          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>Statutory &amp; Tax Compliant</span>
        </div>
      </div>
    </aside>
  );
}
