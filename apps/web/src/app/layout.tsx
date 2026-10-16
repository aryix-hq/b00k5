import type { Metadata } from 'next';
import './globals.css';
import { GlobalTallyHotkeys } from '@/components/navigation/GlobalTallyHotkeys';

export const metadata: Metadata = {
  title: 'b00k5 - Financial OS & Statutory Compliance for Indian Startups',
  description: 'Auditor-ready bookkeeping, statutory document vault, GST & MCA compliance platform',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="antialiased bg-slate-950 text-slate-100 min-h-screen">
        {children}
        <GlobalTallyHotkeys />
      </body>
    </html>
  );
}
