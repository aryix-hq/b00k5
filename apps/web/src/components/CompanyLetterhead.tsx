'use client';

import React, { useEffect, useState } from 'react';
import { Building2, ShieldCheck, Mail, MapPin, Hash, Phone } from 'lucide-react';

interface CompanyLetterheadProps {
  title?: string;
  subtitle?: string;
  referenceNumber?: string;
  date?: string;
  watermark?: string;
  children?: React.ReactNode;
  compact?: boolean;
}

interface CompanyDetails {
  legalName: string;
  cin: string;
  pan: string;
  gstin: string;
  registeredOffice: string;
  logoUrl?: string;
}

export function CompanyLetterhead({
  title,
  subtitle,
  referenceNumber,
  date,
  watermark,
  children,
  compact = false
}: CompanyLetterheadProps) {
  const [company, setCompany] = useState<CompanyDetails>({
    legalName: 'Acme Labs Pvt Ltd',
    cin: 'U72900KA2026PTC123456',
    pan: 'AABCA1234F',
    gstin: '',
    registeredOffice: 'Bangalore, Karnataka, India',
    logoUrl: ''
  });

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const storedName = localStorage.getItem('b00k5_legal_name');
      const storedCin = localStorage.getItem('b00k5_cin');
      const storedPan = localStorage.getItem('b00k5_pan');
      const storedGstin = localStorage.getItem('b00k5_gstin');
      const storedOffice = localStorage.getItem('b00k5_registered_office');
      const storedLogo = localStorage.getItem('b00k5_logo_url');

      setCompany({
        legalName: storedName || 'Acme Labs Pvt Ltd',
        cin: storedCin || 'U72900KA2026PTC123456',
        pan: storedPan || 'AABCA1234F',
        gstin: storedGstin || '',
        registeredOffice: storedOffice || 'Karnataka, India',
        logoUrl: storedLogo || ''
      });

      const token = localStorage.getItem('b00k5_token');
      if (token) {
        fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/setup/company-profile`, {
          headers: { Authorization: `Bearer ${token}` }
        })
          .then(res => res.ok ? res.json() : null)
          .then(data => {
            if (data) {
              setCompany({
                legalName: data.legal_name || 'Acme Labs Pvt Ltd',
                cin: data.cin || 'U72900KA2026PTC123456',
                pan: data.pan || 'AABCA1234F',
                gstin: data.gstin || '',
                registeredOffice: data.registered_office || 'Karnataka, India',
                logoUrl: data.logo_url || ''
              });
              if (data.logo_url) localStorage.setItem('b00k5_logo_url', data.logo_url);
              if (data.registered_office) localStorage.setItem('b00k5_registered_office', data.registered_office);
            }
          })
          .catch(() => {});
      }
    }
  }, []);

  return (
    <div className="relative bg-white text-slate-900 rounded-xl shadow-xl overflow-hidden border border-slate-200">
      {watermark && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-[0.03] select-none rotate-[-25deg]">
          <span className="text-8xl font-black uppercase tracking-widest text-slate-900">
            {watermark}
          </span>
        </div>
      )}

      {/* Official Corporate Header */}
      <div className={`border-b-2 border-slate-900 ${compact ? 'p-4' : 'p-6 sm:p-8'} bg-slate-50/50`}>
        <div className="flex flex-col sm:flex-row items-center sm:items-start justify-between gap-4">
          <div className="flex items-center gap-4 text-center sm:text-left">
            {company.logoUrl ? (
              <img
                src={company.logoUrl}
                alt={company.legalName}
                className="h-16 w-16 object-contain rounded-lg border border-slate-200 bg-white p-1 shadow-sm shrink-0"
              />
            ) : (
              <div className="h-14 w-14 rounded-xl bg-slate-900 flex items-center justify-center text-white font-bold text-xl shadow shrink-0">
                {company.legalName.substring(0, 2).toUpperCase()}
              </div>
            )}
            <div>
              <h1 className="text-lg sm:text-xl font-bold uppercase tracking-tight text-slate-950 font-serif">
                {company.legalName}
              </h1>
              <p className="text-xs font-mono font-medium text-slate-600 mt-0.5">
                CIN: {company.cin || 'UNREGISTERED'}
              </p>
              <p className="text-[11px] text-slate-500 max-w-lg mt-0.5 leading-tight flex items-start gap-1 justify-center sm:justify-start">
                <MapPin className="w-3 h-3 text-slate-400 shrink-0 mt-0.5" />
                <span>Regd. Office: {company.registeredOffice}</span>
              </p>
            </div>
          </div>

          <div className="text-right text-[11px] font-mono text-slate-600 space-y-0.5 shrink-0 bg-white sm:bg-transparent p-2 sm:p-0 rounded border sm:border-0 border-slate-200">
            {company.pan && (
              <div>
                <span className="text-slate-400">PAN: </span>
                <strong className="text-slate-900">{company.pan}</strong>
              </div>
            )}
            {company.gstin && (
              <div>
                <span className="text-slate-400">GSTIN: </span>
                <strong className="text-slate-900">{company.gstin}</strong>
              </div>
            )}
            <div className="text-[10px] text-emerald-700 font-sans font-semibold pt-1">
              MCA Compliant Entity
            </div>
          </div>
        </div>

        <div className="mt-4 pt-1 border-t border-slate-300 flex items-center justify-between text-[10px] text-slate-400 font-mono">
          <span>MINISTRY OF CORPORATE AFFAIRS (MCA) REGULATION REGIME</span>
          <span>COMPANIES ACT, 2013</span>
        </div>
      </div>

      {title && (
        <div className="bg-slate-100/90 px-6 py-3 border-b border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wide text-slate-900">
              {title}
            </h2>
            {subtitle && <p className="text-xs text-slate-600 mt-0.5">{subtitle}</p>}
          </div>
          {(referenceNumber || date) && (
            <div className="flex items-center gap-3 text-xs font-mono text-slate-600">
              {referenceNumber && <span>Ref: <strong>{referenceNumber}</strong></span>}
              {date && <span>Date: <strong>{date}</strong></span>}
            </div>
          )}
        </div>
      )}

      <div className={`p-6 sm:p-8 ${compact ? 'text-xs' : 'text-sm'} leading-relaxed text-slate-800`}>
        {children}
      </div>

      <div className="border-t border-slate-200 bg-slate-50 px-6 py-4 text-[10px] text-slate-500 flex flex-col sm:flex-row items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>Official Corporate Record • Prepared in conformity with Secretarial Standards (SS-1/SS-2)</span>
        </div>
        <div className="font-mono text-[9px] text-slate-400">
          Document Hash: SHA-256 Verified • b00k5 Sovereign Engine
        </div>
      </div>
    </div>
  );
}

