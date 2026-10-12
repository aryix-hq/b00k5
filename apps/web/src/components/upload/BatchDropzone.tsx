'use client';

import React, { useState, useRef } from 'react';
import { UploadCloud, CheckCircle2, AlertTriangle, FileText, X, Loader2, RefreshCw, Lock, KeyRound } from 'lucide-react';

interface BatchFileItem {
  id: string;
  file: File;
  status: 'pending' | 'uploading' | 'queued' | 'processing' | 'needs_password' | 'skipped_duplicate' | 'complete' | 'error';
  progress: number;
  message?: string;
  assignedFY?: string;
  merchantName?: string;
  totalAmount?: number;
  totalLines?: number;
}

interface BatchDropzoneProps {
  type: 'statements' | 'expenses';
  bankAccountId?: string;
  activeUIFY?: string;
  onUploadComplete?: (manifest: any[]) => void;
  maxFiles?: number;
}

export function BatchDropzone({
  type,
  bankAccountId,
  activeUIFY,
  onUploadComplete,
  maxFiles = 50
}: BatchDropzoneProps) {
  const [items, setItems] = useState<BatchFileItem[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [pdfPassword, setPdfPassword] = useState('');
  const [passwordPromptError, setPasswordPromptError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = (fileList: FileList | null) => {
    if (!fileList) return;
    const newFiles: File[] = Array.from(fileList).slice(0, maxFiles);
    const newItems: BatchFileItem[] = newFiles.map(f => ({
      id: `${f.name}-${Date.now()}-${Math.random()}`,
      file: f,
      status: 'pending',
      progress: 0
    }));

    setItems(prev => [...prev, ...newItems]);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  };

  const removeItem = (id: string) => {
    setItems(prev => prev.filter(item => item.id !== id));
  };

  const clearAll = () => {
    setItems([]);
    setPasswordPromptError(null);
  };

  const startBatchUpload = async () => {
    if (items.length === 0 || isProcessing) return;

    const targetItems = items.filter(it => it.status === 'pending' || it.status === 'needs_password');
    if (targetItems.length === 0) {
      return;
    }

    const hasNeedsPassword = items.some(it => it.status === 'needs_password');
    if (hasNeedsPassword && !pdfPassword.trim()) {
      setPasswordPromptError('Please enter the PDF password (e.g., HDFC Customer ID or PAN) to unlock the encrypted statement(s).');
      return;
    }

    setPasswordPromptError(null);
    setIsProcessing(true);

    // Set uploading state for target items
    setItems(prev => prev.map(it =>
      (it.status === 'pending' || it.status === 'needs_password')
        ? { ...it, status: 'uploading', progress: 30 }
        : it
    ));

    const formData = new FormData();
    targetItems.forEach(it => {
      formData.append('files', it.file);
    });

    if (type === 'statements' && bankAccountId) {
      formData.append('bank_account_id', bankAccountId);
    }
    if (activeUIFY) {
      formData.append('active_ui_fy', activeUIFY);
    }
    if (pdfPassword.trim()) {
      formData.append('password', pdfPassword.trim());
    }

    const endpoint = type === 'statements'
      ? `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/batch/statements`
      : `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/batch/expenses`;

    try {
      const token = typeof window !== 'undefined' ? localStorage.getItem('b00k5_token') : null;
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {})
        },
        body: formData
      });

      if (!res.ok) {
        throw new Error(`Upload failed with HTTP ${res.status}`);
      }

      const data = await res.json();
      const manifest: any[] = data.manifest || [];

      const anyEncrypted = manifest.some(m => m.status === 'needs_password' || m.needs_password);
      if (anyEncrypted) {
        const firstErr = manifest.find(m => m.status === 'needs_password' || m.needs_password)?.message;
        setPasswordPromptError(
          firstErr || 'One or more PDFs are password-protected. Enter the PDF password below and click "Unlock & Ingest".'
        );
      }

      // Update state for each file based on manifest
      setItems(prev => prev.map(item => {
        const found = manifest.find(m => m.filename === item.file.name);
        if (found) {
          let nextStatus: BatchFileItem['status'] = 'queued';
          if (found.status === 'needs_password' || found.needs_password) {
            nextStatus = 'needs_password';
          } else if (found.status === 'skipped_duplicate') {
            nextStatus = 'skipped_duplicate';
          } else if (found.status === 'complete') {
            nextStatus = 'complete';
          } else if (found.status === 'error') {
            nextStatus = 'error';
          }
          return {
            ...item,
            status: nextStatus,
            progress: nextStatus === 'needs_password' ? 0 : 100,
            message: found.message || (
              nextStatus === 'skipped_duplicate'
                ? 'Duplicate file skipped'
                : nextStatus === 'needs_password'
                  ? 'Password required to decrypt PDF'
                  : 'Successfully ingested'
            ),
            assignedFY: found.assigned_fy,
            merchantName: found.merchant_name,
            totalAmount: found.total_amount,
            totalLines: found.total_lines
          };
        }
        return item;
      }));

      // Only trigger onUploadComplete when at least one file actually completed (or none are waiting for password)
      const completedManifest = manifest.filter(m => m.status === 'complete' || m.status === 'skipped_duplicate');
      if (onUploadComplete && completedManifest.length > 0 && !anyEncrypted) {
        onUploadComplete(manifest);
      }
    } catch (err: any) {
      setItems(prev => prev.map(it => it.status === 'uploading' ? { ...it, status: 'error', message: err.message } : it));
    } finally {
      setIsProcessing(false);
    }
  };

  const getStatusBadge = (status: BatchFileItem['status']) => {
    switch (status) {
      case 'uploading':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-sky-500/10 text-sky-400 border border-sky-500/20 animate-pulse">
            <Loader2 className="w-2.5 h-2.5 animate-spin" /> Uploading
          </span>
        );
      case 'queued':
      case 'processing':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <RefreshCw className="w-2.5 h-2.5 animate-spin" /> Processing
          </span>
        );
      case 'needs_password':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-amber-500/15 text-amber-300 border border-amber-500/40">
            <Lock className="w-2.5 h-2.5 text-amber-400" /> Password Required
          </span>
        );
      case 'skipped_duplicate':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-400 border border-slate-700">
            <AlertTriangle className="w-2.5 h-2.5 text-amber-400" /> Skipped (Duplicate)
          </span>
        );
      case 'complete':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-2.5 h-2.5" /> Complete
          </span>
        );
      case 'error':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-rose-500/10 text-rose-400 border border-rose-500/20">
            Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300">
            Pending
          </span>
        );
    }
  };

  const totalFiles = items.length;
  const completedCount = items.filter(it => it.status === 'complete').length;
  const duplicateCount = items.filter(it => it.status === 'skipped_duplicate').length;
  const needsPasswordCount = items.filter(it => it.status === 'needs_password').length;
  const actionableCount = items.filter(it => it.status === 'pending' || it.status === 'needs_password').length;

  return (
    <div className="space-y-4">
      {/* Interactive Drop Area */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all ${
          isDragging
            ? 'border-sky-500 bg-sky-500/5'
            : 'border-slate-800 hover:border-slate-700 bg-slate-900/50 hover:bg-slate-900/80'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept={type === 'statements' ? '.pdf,.csv' : '.pdf,.png,.jpg,.jpeg,.webp'}
          onChange={(e) => handleFiles(e.target.files)}
          className="hidden"
        />
        <div className="flex flex-col items-center justify-center gap-2">
          <div className="w-12 h-12 rounded-full bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
            <UploadCloud className="w-6 h-6" />
          </div>
          <div className="text-sm font-medium text-slate-200">
            Drop up to {maxFiles} {type === 'statements' ? 'bank statements' : 'bills & receipts'} here, or <span className="text-sky-400 underline">browse files</span>
          </div>
          <div className="text-xs text-slate-500 font-mono">
            {type === 'statements' ? 'Accepts PDF, CSV (Max 50MB per file • Supports Encrypted PDFs)' : 'Accepts PDF, PNG, JPG, JPEG (Max 25MB per file)'}
          </div>
        </div>
      </div>

      {/* Manifest Summary & Controls */}
      {items.length > 0 && (
        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
          {/* PDF Password Input Bar (Always visible when PDFs are queued, highlighted when needs_password) */}
          <div className={`p-3 rounded-lg border flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
            needsPasswordCount > 0
              ? 'bg-amber-950/30 border-amber-500/40'
              : 'bg-slate-950/60 border-slate-800'
          }`}>
            <div className="flex items-center gap-2 text-xs">
              <KeyRound className={`w-4 h-4 shrink-0 ${needsPasswordCount > 0 ? 'text-amber-400' : 'text-slate-400'}`} />
              <div>
                <div className={`font-semibold ${needsPasswordCount > 0 ? 'text-amber-200' : 'text-slate-300'}`}>
                  {needsPasswordCount > 0
                    ? `Password Required for ${needsPasswordCount} Encrypted PDF(s)`
                    : 'PDF Password (Optional — if statements/bills are encrypted)'}
                </div>
                <div className="text-[11px] text-slate-400">
                  {passwordPromptError || 'For HDFC / ICICI / SBI statements, enter your Customer ID or PDF unlock password.'}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <input
                type="password"
                value={pdfPassword}
                onChange={(e) => setPdfPassword(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    startBatchUpload();
                  }
                }}
                placeholder="Enter PDF password..."
                className="px-3 py-1.5 bg-slate-950 border border-slate-700 rounded-lg text-xs text-white font-mono focus:outline-none focus:border-sky-500 w-48"
              />
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3 text-xs flex-wrap">
              <span className="font-semibold text-slate-200">Queue: {totalFiles} files</span>
              {completedCount > 0 && (
                <span className="text-emerald-400 font-mono">✓ {completedCount} Processed</span>
              )}
              {needsPasswordCount > 0 && (
                <span className="text-amber-400 font-mono">🔒 {needsPasswordCount} Locked</span>
              )}
              {duplicateCount > 0 && (
                <span className="text-slate-400 font-mono">⚠ {duplicateCount} Duplicates Skipped</span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={clearAll}
                disabled={isProcessing}
                className="px-3 py-1 rounded text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
              >
                Clear
              </button>
              <button
                type="button"
                onClick={startBatchUpload}
                disabled={isProcessing || actionableCount === 0}
                className={`px-4 py-1.5 rounded-lg text-xs font-semibold text-white disabled:opacity-50 disabled:cursor-not-allowed transition flex items-center gap-2 ${
                  needsPasswordCount > 0
                    ? 'bg-amber-600 hover:bg-amber-500'
                    : 'bg-sky-600 hover:bg-sky-500'
                }`}
              >
                {isProcessing && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                {isProcessing
                  ? 'Ingesting...'
                  : needsPasswordCount > 0
                    ? 'Unlock & Ingest Encrypted PDFs'
                    : 'Start Ingestion'}
              </button>
            </div>
          </div>

          {/* Item List */}
          <div className="max-h-60 overflow-y-auto space-y-2 pr-1 divide-y divide-slate-800/60">
            {items.map(item => (
              <div key={item.id} className="pt-2 first:pt-0 flex items-center justify-between text-xs">
                <div className="flex items-center gap-2 min-w-0 pr-4">
                  <FileText className="w-4 h-4 text-slate-400 shrink-0" />
                  <div className="truncate">
                    <span className="font-mono text-slate-200">{item.file.name}</span>
                    <span className="text-[10px] text-slate-500 ml-2">
                      ({(item.file.size / 1024).toFixed(1)} KB)
                    </span>
                    {item.message && (
                      <div className={`text-[10px] font-sans mt-0.5 truncate ${
                        item.status === 'needs_password' ? 'text-amber-400' : 'text-slate-400'
                      }`}>
                        {item.message}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {getStatusBadge(item.status)}
                  {(item.status === 'pending' || item.status === 'needs_password') && (
                    <button
                      type="button"
                      onClick={() => removeItem(item.id)}
                      className="p-1 text-slate-500 hover:text-slate-300"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

