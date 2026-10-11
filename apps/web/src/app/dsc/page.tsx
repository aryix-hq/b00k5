'use client';

import React, { useEffect, useState } from 'react';
import { Sidebar } from '@/components/Sidebar';
import { Navbar } from '@/components/Navbar';
import {
  KeyRound,
  Usb,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  FileSignature,
  Hash,
  Terminal,
  RefreshCw
} from 'lucide-react';
import { fetchApi } from '@/lib/api';
import { checkBridgeStatus, signHashViaBridge, BridgeStatus } from '@/lib/dsc-bridge';

export default function DSCPage() {
  const [bridgeStatus, setBridgeStatus] = useState<BridgeStatus | null>(null);
  const [pin, setPin] = useState('');
  const [selectedDocType, setSelectedDocType] = useState('board_minutes');
  const [docHash, setDocHash] = useState('a9f4e27c81d34bc58941038204bb842189ad92c89018442841029cba8371903e');
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isSigning, setIsSigning] = useState(false);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);

  async function refreshBridge() {
    const status = await checkBridgeStatus();
    setBridgeStatus(status);
  }

  async function loadAuditLogs() {
    try {
      const logs = await fetchApi('/api/v1/dsc/audit-log');
      setAuditLogs(logs);
    } catch (e) {
      console.error(e);
    }
  }

  useEffect(() => {
    refreshBridge();
    loadAuditLogs();
  }, []);

  const handleExecuteSign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pin) {
      alert('Please enter your USB Token PIN.');
      return;
    }
    setIsSigning(true);
    setStatusMessage('Communicating with local bridge on 127.0.0.1:28045...');

    try {
      // 1. Sign via local bridge
      setStatusMessage('Sending SHA-256 hash to HYP 2003 PKCS#11 chip...');
      const signRes = await signHashViaBridge(pin, docHash);

      setStatusMessage('Hardware signature received. Registering statutory audit seal...');
      // 2. Submit signature to backend
      await fetchApi('/api/v1/dsc/submit-signature', {
        method: 'POST',
        body: JSON.stringify({
          document_type: selectedDocType,
          document_id: '11111111-1111-1111-1111-111111111111',
          sha256_hash: docHash,
          signature_hex: signRes.signature_hex,
          certificate_der_hex: signRes.certificate_der_hex,
          signer_din: '09876543',
          signer_name: 'Director (DSC Authorized Signatory)',
          token_model: signRes.token_label || 'HyperPKI HYP2003',
        }),
      });

      setStatusMessage('Document sealed and cryptographically verified!');
      setPin('');
      await loadAuditLogs();
    } catch (err: any) {
      setStatusMessage(`Signing failed: ${err.message}`);
    } finally {
      setIsSigning(false);
    }
  };

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <Navbar />

        <main className="p-8 space-y-6 max-w-7xl mx-auto w-full">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <KeyRound className="w-6 h-6 text-purple-400" />
              Hardware Token DSC Integration (HYP 2003) & eSign
            </h2>
            <p className="text-xs text-slate-400">
              Sign statutory Board Minutes, Tax Invoices, and MCA filings using an authentic HyperPKI USB Crypto Token
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Signing Pad */}
            <div className="md:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-5">
              <h3 className="font-semibold text-white text-sm flex items-center gap-2">
                <FileSignature className="w-4 h-4 text-purple-400" />
                USB Hardware Signing Pad
              </h3>

              <form onSubmit={handleExecuteSign} className="space-y-4 text-xs">
                <div>
                  <label className="block text-slate-400 mb-1">Target Document Type</label>
                  <select
                    value={selectedDocType}
                    onChange={(e) => setSelectedDocType(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200"
                  >
                    <option value="board_minutes">Board Meeting Minutes (Section 173)</option>
                    <option value="invoice">Statutory GST Tax Invoice</option>
                    <option value="aoc4">Form AOC-4 Financial Statements</option>
                    <option value="mgt7">Form MGT-7 Annual Return</option>
                  </select>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Document SHA-256 Digest</label>
                  <div className="p-2.5 bg-slate-950 rounded-lg border border-slate-800 font-mono text-[11px] text-slate-300 break-all">
                    {docHash}
                  </div>
                </div>

                <div>
                  <label className="block text-slate-400 mb-1">Hardware Token User PIN</label>
                  <input
                    type="password"
                    value={pin}
                    onChange={(e) => setPin(e.target.value)}
                    placeholder="Enter 6-8 digit USB token PIN"
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-slate-200 font-mono"
                  />
                  <p className="text-[11px] text-slate-500 mt-1">
                    PIN unlocks the token&apos;s private key slot locally. It is never transmitted across the network.
                  </p>
                </div>

                {statusMessage && (
                  <div className="p-3 rounded-lg bg-purple-950/20 border border-purple-800/40 text-purple-300 text-xs flex items-center gap-2">
                    <Terminal className="w-4 h-4 shrink-0 text-purple-400" />
                    <span>{statusMessage}</span>
                  </div>
                )}

                <div className="pt-2">
                  <button
                    type="submit"
                    disabled={isSigning}
                    className="px-6 py-2.5 bg-purple-600 hover:bg-purple-500 text-white font-semibold rounded-lg flex items-center gap-2 shadow-lg shadow-purple-950/40"
                  >
                    {isSigning ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" /> Signing on USB Token...
                      </>
                    ) : (
                      <>
                        <Usb className="w-4 h-4" /> Execute Hardware Sign
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>

            {/* Bridge Status Card */}
            <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 className="font-semibold text-white text-sm flex items-center gap-2">
                  <Usb className="w-4 h-4 text-sky-400" />
                  Local Bridge Daemon
                </h3>
                <button onClick={refreshBridge} className="text-slate-400 hover:text-white">
                  <RefreshCw className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Bridge Status:</span>
                  {bridgeStatus?.bridge_status === 'online' ? (
                    <span className="text-emerald-400 font-semibold flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Online (28045)
                    </span>
                  ) : (
                    <span className="text-amber-400 font-semibold flex items-center gap-1">
                      <AlertCircle className="w-3.5 h-3.5" /> Offline / Standby
                    </span>
                  )}
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-slate-400">Operating System:</span>
                  <span className="font-mono text-slate-300">{bridgeStatus?.platform || 'Darwin (macOS)'}</span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-slate-400">PKCS#11 Driver:</span>
                  <span className="font-mono text-slate-300">
                    {bridgeStatus?.driver_found ? 'Loaded' : 'Not Loaded'}
                  </span>
                </div>

                <div className="border-t border-slate-800 pt-3">
                  <span className="text-[11px] text-slate-500 block mb-1">To run bridge locally:</span>
                  <pre className="p-2 bg-slate-950 rounded border border-slate-800 text-[10px] text-sky-400 font-mono overflow-x-auto">
                    cd bridge && bash run_bridge.sh
                  </pre>
                </div>
              </div>
            </div>
          </div>

          {/* Audit Logs Table */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-slate-800 font-semibold text-sm text-white flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              Statutory DSC Signature Audit Trail
            </div>
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950/60 border-b border-slate-800 text-slate-400 font-mono uppercase">
                <tr>
                  <th className="py-3 px-4">Signer Name</th>
                  <th className="py-3 px-4">DIN</th>
                  <th className="py-3 px-4">Document Type</th>
                  <th className="py-3 px-4">Token Model</th>
                  <th className="py-3 px-4">Certificate CA</th>
                  <th className="py-3 px-4">Signed Timestamp (IST)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 text-slate-300">
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-slate-500">
                      No statutory documents signed yet in this session.
                    </td>
                  </tr>
                ) : (
                  auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-800/30">
                      <td className="py-3 px-4 font-medium text-white">{log.signer_name}</td>
                      <td className="py-3 px-4 font-mono">{log.signer_din || 'N/A'}</td>
                      <td className="py-3 px-4 font-mono uppercase">{log.document_type}</td>
                      <td className="py-3 px-4">{log.token_model}</td>
                      <td className="py-3 px-4 text-slate-400">{log.certificate_issuer}</td>
                      <td className="py-3 px-4 font-mono text-slate-400">{log.signed_at.replace('T', ' ').substring(0, 19)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </main>
      </div>
    </div>
  );
}
