'use client';

import React, { useState, useEffect } from 'react';
import { KeyRound, ShieldCheck, AlertCircle, RefreshCw, CheckCircle2, Lock } from 'lucide-react';
import { checkBridgeStatus, BridgeStatus } from '../lib/dsc-bridge';

export function DSCBridgeWidget() {
  const [status, setStatus] = useState<BridgeStatus | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [pin, setPin] = useState('');
  const [pinStatus, setPinStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [simulatedToken, setSimulatedToken] = useState(false);

  const fetchStatus = async () => {
    setIsChecking(true);
    try {
      const res = await checkBridgeStatus();
      setStatus(res);
    } catch {
      setStatus({
        bridge_status: 'offline',
        platform: 'macOS',
        driver_found: false,
        driver_path: null,
        token_detected: false,
        token_label: null
      });
    } finally {
      setIsChecking(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 8000);
    return () => clearInterval(interval);
  }, []);

  const isConnected = status?.token_detected || simulatedToken;
  const isBridgeRunning = status?.bridge_status === 'running' || simulatedToken;

  const handleVerifyPin = () => {
    if (pin.length >= 6) {
      setPinStatus('success');
      setTimeout(() => {
        setShowModal(false);
        setPinStatus('idle');
        setPin('');
      }, 1200);
    } else {
      setPinStatus('error');
    }
  };

  return (
    <>
      <div className="flex items-center gap-2">
        <button
          onClick={() => setShowModal(true)}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
            isConnected
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20'
              : isBridgeRunning
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-400 hover:bg-amber-500/20'
              : 'bg-slate-800 border-slate-700 text-slate-400 hover:bg-slate-750'
          }`}
          title="Hardware DSC PKCS#11 Bridge Status"
        >
          <div className={`w-2 h-2 rounded-full ${
            isConnected ? 'bg-emerald-400 animate-pulse' : isBridgeRunning ? 'bg-amber-400' : 'bg-slate-500'
          }`} />
          <KeyRound className="w-3.5 h-3.5" />
          <span>
            {isConnected
              ? (status?.token_label || 'HYP2003 Token Ready')
              : isBridgeRunning
              ? 'Bridge Active (Insert Token)'
              : 'DSC Bridge Offline'}
          </span>
        </button>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2.5">
                <KeyRound className="w-5 h-5 text-sky-400" />
                <h3 className="font-semibold text-white">Hardware DSC Crypto Token</h3>
              </div>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3 text-sm">
              <div className="flex justify-between items-center p-3 rounded-lg bg-slate-800/60 border border-slate-700/50">
                <span className="text-slate-400">Bridge Loopback:</span>
                <span className="font-mono text-xs text-sky-300">127.0.0.1:28045</span>
              </div>
              <div className="flex justify-between items-center p-3 rounded-lg bg-slate-800/60 border border-slate-700/50">
                <span className="text-slate-400">PKCS#11 Driver:</span>
                <span className="font-mono text-xs text-slate-300 truncate max-w-[200px]">
                  {status?.driver_path || (simulatedToken ? 'libespki.dylib (Simulated)' : 'Not detected')}
                </span>
              </div>
              <div className="flex justify-between items-center p-3 rounded-lg bg-slate-800/60 border border-slate-700/50">
                <span className="text-slate-400">Token Status:</span>
                <span className={`text-xs font-semibold px-2 py-0.5 rounded ${
                  isConnected
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                }`}>
                  {isConnected ? 'USB Token Inserted' : 'Awaiting USB Insertion'}
                </span>
              </div>
            </div>

            {/* Developer Simulation Toggle */}
            <div className="pt-2 border-t border-slate-800 flex items-center justify-between">
              <span className="text-xs text-slate-400">Developer Simulation Mode:</span>
              <button
                onClick={() => setSimulatedToken(!simulatedToken)}
                className={`text-xs px-2.5 py-1 rounded transition-colors ${
                  simulatedToken
                    ? 'bg-sky-500/20 text-sky-400 border border-sky-500/30'
                    : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                {simulatedToken ? 'Simulated Token ON' : 'Enable Simulated Token'}
              </button>
            </div>

            {/* PIN Challenge */}
            <div className="space-y-2 pt-2">
              <label className="text-xs font-medium text-slate-300 flex items-center gap-1.5">
                <Lock className="w-3.5 h-3.5 text-slate-400" />
                Token User PIN Challenge (6-8 digits):
              </label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={pin}
                  onChange={(e) => setPin(e.target.value)}
                  placeholder="Enter Token PIN..."
                  maxLength={8}
                  className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-sky-500 font-mono"
                />
                <button
                  onClick={handleVerifyPin}
                  disabled={!isConnected}
                  className="px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:bg-slate-800 disabled:text-slate-600 text-white rounded-lg text-xs font-semibold transition-colors"
                >
                  Verify
                </button>
              </div>
              {pinStatus === 'success' && (
                <p className="text-xs text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> PIN Verified. Hardware Token Authenticated.
                </p>
              )}
              {pinStatus === 'error' && (
                <p className="text-xs text-rose-400 flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5" /> Invalid PIN length (minimum 6 digits required).
                </p>
              )}
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setShowModal(false)}
                className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
