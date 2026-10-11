'use client';

import React from 'react';
import { ExpenseForm } from '@/components/expenses/ExpenseForm';
import { Receipt, ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';

export default function NewExpensePage() {
  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Navbar />
        <main className="flex-1 overflow-y-auto p-8 max-w-4xl mx-auto w-full space-y-6">
          <div className="flex items-center gap-3 border-b border-slate-800 pb-4">
            <Link href="/expenses" className="p-2 rounded-lg bg-slate-800 text-slate-400 hover:text-white transition">
              <ArrowLeft className="w-5 h-5" />
            </Link>
            <div>
              <h1 className="text-xl font-bold text-white flex items-center gap-2">
                <Receipt className="w-5 h-5 text-emerald-400" />
                Record Corporate Expense
              </h1>
              <p className="text-xs text-slate-400">
                Personal Out-of-Pocket Reimbursements, Statutory Sec 40A(3) Auditing & SmartScan OCR
              </p>
            </div>
          </div>

          <ExpenseForm />
        </main>
      </div>
    </div>
  );
}
