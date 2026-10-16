'use client';

import React, { useState } from 'react';
import {
  X,
  ExternalLink,
  ShieldCheck,
  Building2,
  Code2,
  Server,
  Database,
  ArrowRight,
  BookOpen,
  Sparkles,
  CheckCircle2,
  Lock,
  Layers
} from 'lucide-react';

interface AboutModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AboutModal({ isOpen, onClose }: AboutModalProps) {
  const [activeTab, setActiveTab] = useState<'manifesto' | 'offering' | 'specs'>('manifesto');

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-2xl w-full p-6 space-y-6 shadow-2xl relative my-8">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-sky-500/20 border border-sky-500/30 flex items-center justify-center text-sky-400 font-mono font-bold text-lg">
              b5
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white tracking-tight">b00k5</h2>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20 font-semibold">
                  v1.0.4-ga
                </span>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">
                  Apache 2.0
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                The Sovereign Financial Operating System &amp; MCA Compliance Engine
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition"
            title="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 border-b border-slate-800 pb-2 text-xs font-semibold">
          <button
            id="tab-about-manifesto"
            onClick={() => setActiveTab('manifesto')}
            className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition ${
              activeTab === 'manifesto'
                ? 'bg-sky-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            <span>The Sovereign Manifesto</span>
          </button>
          <button
            id="tab-about-offering"
            onClick={() => setActiveTab('offering')}
            className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition ${
              activeTab === 'offering'
                ? 'bg-sky-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Community vs. Enterprise</span>
          </button>
          <button
            id="tab-about-specs"
            onClick={() => setActiveTab('specs')}
            className={`px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition ${
              activeTab === 'specs'
                ? 'bg-sky-600 text-white shadow-sm'
                : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
            }`}
          >
            <Server className="w-3.5 h-3.5" />
            <span>Engine Specs &amp; Telemetry</span>
          </button>
        </div>

        {/* Tab 1: Manifesto */}
        {activeTab === 'manifesto' && (
          <div className="space-y-4 text-xs leading-relaxed text-slate-300">
            <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl space-y-3">
              <h3 className="text-sm font-bold text-white flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                Why We Built b00k5
              </h3>
              <p>
                In April 2023, Intuit abruptly pulled QuickBooks out of India, stranding tens of thousands of growing businesses and proving that closed cloud ERPs pose an existential threat to company continuity.
              </p>
              <p>
                Meanwhile, desktop alternatives like Tally Prime remain anchored in the 1990s—prone to corrupted proprietary <code className="text-sky-300 bg-slate-900 px-1 py-0.5 rounded">.tsf</code> binary files and isolated from modern web APIs. Modern cloud accounting platforms charge steep per-user monthly subscription taxes while locking your most sensitive commercial ledger on foreign servers.
              </p>
              <p>
                We engineered <strong>b00k5</strong> at <strong>ARYIX</strong> on a singular principle: <strong>your corporate financial ledger and statutory compliance must remain sovereign, local-first, and mathematically verifiable.</strong>
              </p>
              <p>
                b00k5 combines PostgreSQL 16 ACID transactions, authentic MinIO document preservation, and automated Companies Act secretarial governance (SS-1/SS-2) into a 100% free, open-source platform that no cloud vendor can ever turn off or hold hostage.
              </p>
            </div>

            <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-[11px] text-slate-400">
              <div>
                <span className="font-semibold text-white">Adithya Khamithkar</span>
                <span className="text-slate-500"> • Founder, ARYIX</span>
              </div>
              <a
                href="https://www.aryix.co.in/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sky-400 hover:text-sky-300 font-semibold flex items-center gap-1 transition"
              >
                <span>Visit ARYIX</span>
                <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        )}

        {/* Tab 2: Community vs. Enterprise Offering */}
        {activeTab === 'offering' && (
          <div className="space-y-4">
            <p className="text-xs text-slate-400 leading-relaxed">
              b00k5 follows a transparent Commercial Open-Source (COSS) model. The core software is 100% free and open-source forever. For organizations seeking turnkey deployment, dedicated SLAs, and custom ledger engineering, ARYIX provides enterprise support:
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
              {/* Community Card */}
              <div className="p-4 bg-slate-950/80 border border-slate-800 rounded-xl space-y-3 flex flex-col justify-between">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-white text-sm">Community Edition</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">
                      100% Free
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400">
                    Self-hosted, autonomous, and free under the Apache 2.0 license.
                  </p>
                  <ul className="space-y-1.5 text-slate-300 text-[11px] pt-2">
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                      <span>Deploy on Docker / Local Bare Metal</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                      <span>Self-managed backups &amp; recovery</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                      <span>Community GitHub issue reporting</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0 mt-0.5" />
                      <span>Zero licensing fees forever</span>
                    </li>
                  </ul>
                </div>
                <div className="pt-3 border-t border-slate-800/80 text-[11px] text-slate-500">
                  Ideal for solo technical founders, independent CAs, and open-source developers.
                </div>
              </div>

              {/* Enterprise Card */}
              <div className="p-4 bg-sky-950/30 border border-sky-500/30 rounded-xl space-y-3 flex flex-col justify-between">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-white text-sm">Enterprise Support</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/20 font-semibold">
                      By ARYIX
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-300">
                    White-glove implementation, bespoke integrations, and statutory compliance SLA.
                  </p>
                  <ul className="space-y-1.5 text-slate-200 text-[11px] pt-2">
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-sky-400 shrink-0 mt-0.5" />
                      <span>Turnkey private cloud / server deployment</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-sky-400 shrink-0 mt-0.5" />
                      <span>Custom Tally, QuickBooks &amp; ERP migrations</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-sky-400 shrink-0 mt-0.5" />
                      <span>Statutory SLA for urgent MCA / GST changes</span>
                    </li>
                    <li className="flex items-start gap-1.5">
                      <CheckCircle2 className="w-3.5 h-3.5 text-sky-400 shrink-0 mt-0.5" />
                      <span>Bespoke custom ERP and bank API engineering</span>
                    </li>
                  </ul>
                </div>

                <div className="pt-3 border-t border-sky-500/20">
                  <a
                    id="about-contact-enterprise-btn"
                    href="https://www.aryix.co.in/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="w-full py-2 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg flex items-center justify-center gap-1.5 shadow-md shadow-sky-600/20 transition"
                  >
                    <span>Contact ARYIX Enterprise</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Specs & Telemetry */}
        {activeTab === 'specs' && (
          <div className="space-y-4 text-xs">
            <div className="grid grid-cols-2 gap-3 font-mono">
              <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                <span className="text-[10px] text-slate-500 uppercase flex items-center gap-1">
                  <Code2 className="w-3.5 h-3.5 text-sky-400" /> Platform Version
                </span>
                <p className="text-white font-bold">b00k5 v1.0.4-ga</p>
                <p className="text-[10px] text-slate-500">Kernel Release: 2026.10</p>
              </div>

              <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                <span className="text-[10px] text-slate-500 uppercase flex items-center gap-1">
                  <Database className="w-3.5 h-3.5 text-emerald-400" /> Relational Engine
                </span>
                <p className="text-white font-bold">PostgreSQL 16.8 (ACID)</p>
                <p className="text-[10px] text-emerald-400">Row-Level Security Active</p>
              </div>

              <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                <span className="text-[10px] text-slate-500 uppercase flex items-center gap-1">
                  <Server className="w-3.5 h-3.5 text-amber-400" /> Object Storage
                </span>
                <p className="text-white font-bold">MinIO S3 Sovereign Vault</p>
                <p className="text-[10px] text-amber-400">WORM Object Locking Enabled</p>
              </div>

              <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-1">
                <span className="text-[10px] text-slate-500 uppercase flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-purple-400" /> Ledger Invariant
                </span>
                <p className="text-emerald-400 font-bold">|∑ Dr - ∑ Cr| ≡ 0.00</p>
                <p className="text-[10px] text-slate-500">Zero Drift Kernel Trigger</p>
              </div>
            </div>

            <div className="p-3 bg-slate-950/60 border border-slate-800 rounded-xl text-slate-400 text-[11px] leading-relaxed">
              <strong>Statutory Compliance Engine:</strong> Built in accordance with Companies Act, 2013 (Section 128, 173, 174, Schedule III), Income Tax Act, 1961 (Section 44AA, 40A(3), 69C, 115BBE), and Central Goods and Services Tax (CGST) Act, 2017 (Section 16, 22, 36).
            </div>
          </div>
        )}

        {/* Modal Footer */}
        <div className="flex items-center justify-between pt-3 border-t border-slate-800 text-xs">
          <div className="text-[11px] text-slate-500 flex items-center gap-1">
            <span>Engineered with pride by</span>
            <a
              href="https://www.aryix.co.in/"
              target="_blank"
              rel="noopener noreferrer"
              className="text-white font-bold hover:text-sky-400 transition"
            >
              ARYIX
            </a>
          </div>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs rounded-lg transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

