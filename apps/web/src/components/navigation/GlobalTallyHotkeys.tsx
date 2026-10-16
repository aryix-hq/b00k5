'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { CommandPalette } from './CommandPalette';
import { QuickLedgerModal } from './QuickLedgerModal';
import { Zap, Command, X } from 'lucide-react';

export function GlobalTallyHotkeys() {
  const router = useRouter();
  const [isPaletteOpen, setIsPaletteOpen] = useState(false);
  const [isLedgerModalOpen, setIsLedgerModalOpen] = useState(false);
  const [pillVisible, setPillVisible] = useState(true);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // 1. Ctrl+K or Cmd+K: Open Universal Command Palette
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        setIsPaletteOpen(prev => !prev);
        return;
      }

      // 2. Alt+N or Option+N: Quick New Bill / Expense
      if (e.altKey && (e.key === 'n' || e.key === 'N')) {
        e.preventDefault();
        router.push('/expenses');
        return;
      }

      // 3. Alt+C or Option+C: In-Place Create Chart of Accounts Ledger
      if (e.altKey && (e.key === 'c' || e.key === 'C')) {
        e.preventDefault();
        setIsLedgerModalOpen(true);
        return;
      }

      // 4. Alt+G or Option+G: Jump to General Ledger
      if (e.altKey && (e.key === 'g' || e.key === 'G')) {
        e.preventDefault();
        router.push('/reports/general-ledger');
        return;
      }

      // 5. Alt+I or Option+I: Jump to Invoices
      if (e.altKey && (e.key === 'i' || e.key === 'I')) {
        e.preventDefault();
        router.push('/invoices');
        return;
      }

      // 6. Escape closes open modals
      if (e.key === 'Escape') {
        if (isPaletteOpen) setIsPaletteOpen(false);
        if (isLedgerModalOpen) setIsLedgerModalOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [router, isPaletteOpen, isLedgerModalOpen]);

  return (
    <>
      <CommandPalette
        isOpen={isPaletteOpen}
        onClose={() => setIsPaletteOpen(false)}
        onOpenQuickLedger={() => setIsLedgerModalOpen(true)}
      />

      <QuickLedgerModal
        isOpen={isLedgerModalOpen}
        onClose={() => setIsLedgerModalOpen(false)}
      />

      {/* Discreet bottom-right Tally-Speed status pill */}
      {pillVisible && (
        <div className="fixed bottom-4 right-4 z-40 hidden sm:flex items-center gap-2 bg-slate-900/90 border border-slate-800 text-slate-300 text-[11px] font-mono px-3 py-1.5 rounded-full shadow-lg backdrop-blur-md">
          <Zap className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
          <span className="font-semibold text-white">Tally-Speed:</span>
          <button
            onClick={() => setIsPaletteOpen(true)}
            className="hover:text-sky-400 flex items-center gap-1"
          >
            <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-[10px]">
              Ctrl+K
            </kbd>
            <span>Palette</span>
          </button>
          <span className="text-slate-600">|</span>
          <button
            onClick={() => router.push('/expenses')}
            className="hover:text-amber-400 flex items-center gap-1"
          >
            <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-[10px]">
              Alt+N
            </kbd>
            <span>Bill</span>
          </button>
          <span className="text-slate-600">|</span>
          <button
            onClick={() => setIsLedgerModalOpen(true)}
            className="hover:text-emerald-400 flex items-center gap-1"
          >
            <kbd className="px-1.5 py-0.5 rounded bg-slate-800 border border-slate-700 text-[10px]">
              Alt+C
            </kbd>
            <span>Ledger</span>
          </button>
          <button
            onClick={() => setPillVisible(false)}
            className="ml-1 text-slate-500 hover:text-slate-300"
            title="Dismiss shortcut bar"
          >
            <X className="w-3 h-3" />
          </button>
        </div>
      )}
    </>
  );
}

