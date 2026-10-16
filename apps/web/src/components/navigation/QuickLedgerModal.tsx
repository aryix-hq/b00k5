'use client';

import React, { useState } from 'react';
import { BookOpen, Plus, CheckCircle2, AlertCircle } from 'lucide-react';
import { fetchApi } from '@/lib/api';

interface QuickLedgerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAccountCreated?: (account: any) => void;
}

export function QuickLedgerModal({ isOpen, onClose, onAccountCreated }: QuickLedgerModalProps) {
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [type, setType] = useState('Expense');
  const [subType, setSubType] = useState('Operating');
  const [normalBal, setNormalBal] = useState<'debit' | 'credit'>('debit');
  const [description, setDescription] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code || !name) {
      setErrorMsg('Account code and name are required.');
      return;
    }

    setSubmitting(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const res = await fetchApi('/api/v1/ledger/accounts', {
        method: 'POST',
        body: JSON.stringify({
          code: code.trim(),
          name: name.trim(),
          type: type,
          sub_type: subType,
          normal_balance: normalBal,
          description: description.trim() || undefined
        })
      });

      setSuccessMsg(`Account [${res.code}] ${res.name} created!`);
      if (onAccountCreated) onAccountCreated(res);

      setTimeout(() => {
        onClose();
        setCode('');
        setName('');
        setDescription('');
        setSuccessMsg(null);
      }, 1000);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to create account.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-fadeIn"
      onClick={onClose}
    >
      <div
        className="bg-slate-900 border border-slate-700 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-sky-400" />
            <h3 className="text-base font-bold text-white">
              Quick Ledger Account (Alt+C)
            </h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-sm">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 text-xs font-sans">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-300 font-semibold mb-1">
                Account Code*
              </label>
              <input
                type="text"
                value={code}
                onChange={e => setCode(e.target.value)}
                placeholder="e.g. 4170"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-sky-500"
                required
                autoFocus
              />
            </div>

            <div>
              <label className="block text-slate-300 font-semibold mb-1">
                Account Type*
              </label>
              <select
                value={type}
                onChange={e => {
                  const val = e.target.value;
                  setType(val);
                  if (val === 'Asset' || val === 'Expense') {
                    setNormalBal('debit');
                  } else {
                    setNormalBal('credit');
                  }
                }}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-medium focus:outline-none focus:border-sky-500"
              >
                <option value="Expense">Expense</option>
                <option value="Asset">Asset</option>
                <option value="Liability">Liability</option>
                <option value="Equity">Equity</option>
                <option value="Revenue">Revenue</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-slate-300 font-semibold mb-1">
              Account Name*
            </label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Consulting & Advisory Retainers"
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-medium focus:outline-none focus:border-sky-500"
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-slate-300 font-semibold mb-1">
                Sub-Type
              </label>
              <input
                type="text"
                value={subType}
                onChange={e => setSubType(e.target.value)}
                placeholder="Operating / Current"
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-medium focus:outline-none focus:border-sky-500"
              />
            </div>

            <div>
              <label className="block text-slate-300 font-semibold mb-1">
                Normal Balance
              </label>
              <select
                value={normalBal}
                onChange={e => setNormalBal(e.target.value as 'debit' | 'credit')}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-mono focus:outline-none focus:border-sky-500"
              >
                <option value="debit">Debit (Dr)</option>
                <option value="credit">Credit (Cr)</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-slate-300 font-semibold mb-1">
              Description (Optional)
            </label>
            <input
              type="text"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Schedule III classification notes..."
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-white font-medium focus:outline-none focus:border-sky-500"
            />
          </div>

          {errorMsg && (
            <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-400 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {successMsg && (
            <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-slate-800 text-slate-300 hover:bg-slate-700"
            >
              Cancel (Esc)
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 disabled:bg-sky-800 text-white font-semibold flex items-center gap-1.5"
            >
              <Plus className="w-4 h-4" />
              {submitting ? 'Creating...' : 'Create Ledger (Ctrl+Enter)'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

