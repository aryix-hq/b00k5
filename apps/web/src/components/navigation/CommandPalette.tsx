'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import {
  Search,
  BookOpen,
  FileText,
  Receipt,
  Scale,
  Building2,
  FolderArchive,
  Calendar,
  Settings,
  ShieldCheck,
  Plus,
  Coins,
  ArrowRight,
  TrendingDown,
  Clock
} from 'lucide-react';

interface CommandItem {
  id: string;
  title: string;
  subtitle: string;
  category: 'Navigation' | 'Actions' | 'Compliance';
  icon: React.ReactNode;
  url?: string;
  action?: () => void;
  shortcut?: string;
}

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenQuickLedger?: () => void;
}

export function CommandPalette({ isOpen, onClose, onOpenQuickLedger }: CommandPaletteProps) {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const commands: CommandItem[] = [
    {
      id: 'gl',
      title: 'General Ledger & Trial Balance',
      subtitle: 'View double-entry journals, sub-ledgers, and account balances',
      category: 'Navigation',
      icon: <BookOpen className="w-4 h-4 text-sky-400" />,
      url: '/reports/general-ledger',
      shortcut: 'Alt+G'
    },
    {
      id: 'invoices',
      title: 'Invoices & E-Invoicing Hub',
      subtitle: 'Create GST B2B tax invoices, compute IRN hash, and print QR codes',
      category: 'Navigation',
      icon: <FileText className="w-4 h-4 text-emerald-400" />,
      url: '/invoices'
    },
    {
      id: 'expenses',
      title: 'Expenses & OCR Bill Ingestion',
      subtitle: 'Scan supplier receipts, claim ITC, and book founder expenses',
      category: 'Navigation',
      icon: <Receipt className="w-4 h-4 text-amber-400" />,
      url: '/expenses',
      shortcut: 'Alt+N'
    },
    {
      id: 'banking',
      title: 'Bank Feeds & 3-Tier Reconciliation',
      subtitle: 'Upload bank statements and match UTR transactions with zero drift',
      category: 'Navigation',
      icon: <Building2 className="w-4 h-4 text-blue-400" />,
      url: '/banking/reconciliation'
    },
    {
      id: 'governance',
      title: 'Statutory Governance & Board Minutes',
      subtitle: 'Companies Act 2013 SS-1 minutes, 120-day cadence, and DSC signing',
      category: 'Compliance',
      icon: <Scale className="w-4 h-4 text-purple-400" />,
      url: '/governance'
    },
    {
      id: 'tds',
      title: 'TDS & TCS Withholding (Challan 281 & 26Q)',
      subtitle: 'Sections 194C, 194J, 194I, 194Q sub-ledgers and Protean Form 26Q export',
      category: 'Compliance',
      icon: <Clock className="w-4 h-4 text-amber-400" />,
      url: '/governance'
    },
    {
      id: 'assets',
      title: 'Schedule II Fixed Assets & Depreciation',
      subtitle: 'Statutory asset registry, 5% salvage floor, and period-end depreciation JV',
      category: 'Compliance',
      icon: <TrendingDown className="w-4 h-4 text-rose-400" />,
      url: '/governance'
    },
    {
      id: 'vault',
      title: 'Sovereign S3 Document Vault',
      subtitle: 'Content-addressed MinIO vault for authentic MCA returns and invoices',
      category: 'Navigation',
      icon: <FolderArchive className="w-4 h-4 text-indigo-400" />,
      url: '/vault'
    },
    {
      id: 'yearbook',
      title: 'Year Book & 5-Year Historical Radar',
      subtitle: 'Inspect prior year filed returns and statutory baseline calibrations',
      category: 'Navigation',
      icon: <Calendar className="w-4 h-4 text-teal-400" />,
      url: '/yearbook'
    },
    {
      id: 'create_ledger',
      title: 'In-Place Create Chart of Accounts Ledger',
      subtitle: 'Instant statutory account creation without losing form context',
      category: 'Actions',
      icon: <Plus className="w-4 h-4 text-emerald-400" />,
      action: () => {
        onClose();
        if (onOpenQuickLedger) onOpenQuickLedger();
      },
      shortcut: 'Alt+C'
    },
    {
      id: 'settings',
      title: 'Company Statutory Profile & Settings',
      subtitle: 'Configure CIN, GSTIN, registered office, and authorized signatories',
      category: 'Navigation',
      icon: <Settings className="w-4 h-4 text-slate-400" />,
      url: '/settings/company-profile'
    }
  ];

  const filteredCommands = commands.filter(cmd =>
    cmd.title.toLowerCase().includes(query.toLowerCase()) ||
    cmd.subtitle.toLowerCase().includes(query.toLowerCase()) ||
    cmd.category.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    if (isOpen) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      onClose();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => (prev < filteredCommands.length - 1 ? prev + 1 : 0));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => (prev > 0 ? prev - 1 : filteredCommands.length - 1));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const selected = filteredCommands[selectedIndex];
      if (selected) {
        executeCommand(selected);
      }
    }
  };

  const executeCommand = (cmd: CommandItem) => {
    onClose();
    if (cmd.action) {
      cmd.action();
    } else if (cmd.url) {
      router.push(cmd.url);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-24 bg-black/70 backdrop-blur-sm p-4 animate-fadeIn"
      onClick={onClose}
    >
      <div
        className="bg-slate-900 border border-slate-700 rounded-2xl max-w-2xl w-full shadow-2xl overflow-hidden"
        onClick={e => e.stopPropagation()}
        onKeyDown={handleKeyDown}
      >
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-slate-800 bg-slate-950/80">
          <Search className="w-5 h-5 text-sky-400 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={e => {
              setQuery(e.target.value);
              setSelectedIndex(0);
            }}
            placeholder="Type a command, page, or statutory action (e.g. Ledger, E-Invoice, TDS, Alt+N)..."
            className="w-full bg-transparent text-white text-sm font-medium focus:outline-none placeholder-slate-500"
          />
          <kbd className="px-2 py-0.5 rounded text-[10px] font-mono text-slate-400 bg-slate-800 border border-slate-700">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div className="max-h-96 overflow-y-auto p-2 divide-y divide-slate-800/40">
          {filteredCommands.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-500 font-mono">
              No matching commands or pages found.
            </div>
          ) : (
            filteredCommands.map((cmd, idx) => (
              <div
                key={cmd.id}
                onClick={() => executeCommand(cmd)}
                className={`p-3 rounded-xl flex items-center justify-between cursor-pointer transition-all ${
                  idx === selectedIndex
                    ? 'bg-sky-500/15 border border-sky-500/30 text-white'
                    : 'hover:bg-slate-800/50 text-slate-300'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-slate-800 border border-slate-700/60 shrink-0">
                    {cmd.icon}
                  </div>
                  <div>
                    <div className="text-xs font-semibold flex items-center gap-2">
                      {cmd.title}
                      <span className="text-[10px] font-normal text-slate-500 uppercase font-mono">
                        {cmd.category}
                      </span>
                    </div>
                    <div className="text-[11px] text-slate-400">{cmd.subtitle}</div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {cmd.shortcut && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-mono text-sky-300 bg-slate-950 border border-slate-800">
                      {cmd.shortcut}
                    </span>
                  )}
                  <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer Hotkey Legend */}
        <div className="px-4 py-2 bg-slate-950 border-t border-slate-800 text-[11px] text-slate-500 flex items-center justify-between font-mono">
          <div className="flex items-center gap-3">
            <span>↑↓ Navigate</span>
            <span>↵ Select</span>
            <span>ESC Close</span>
          </div>
          <div>
            <span className="text-sky-400 font-semibold">Tally-Speed Hotkeys Active</span>
          </div>
        </div>
      </div>
    </div>
  );
}

