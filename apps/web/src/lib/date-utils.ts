/**
 * b00k5 - Indian Date & Time Formatter Utilities
 * Formats dates into DD/MM/YYYY and Indian Standard Time (IST) 12-hour AM/PM format.
 */

export function formatIndianDate(isoOrDateString?: string | Date | null): string {
  if (!isoOrDateString) return 'N/A';
  try {
    const d = typeof isoOrDateString === 'string' ? new Date(isoOrDateString) : isoOrDateString;
    if (isNaN(d.getTime())) return String(isoOrDateString);
    return d.toLocaleDateString('en-IN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      timeZone: 'Asia/Kolkata',
    });
  } catch {
    return String(isoOrDateString);
  }
}

export function formatIndianDateTime(isoOrDateString?: string | Date | null, includeSeconds = false): string {
  if (!isoOrDateString) return 'N/A';
  try {
    const d = typeof isoOrDateString === 'string' ? new Date(isoOrDateString) : isoOrDateString;
    if (isNaN(d.getTime())) return String(isoOrDateString);
    const dateStr = d.toLocaleDateString('en-IN', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      timeZone: 'Asia/Kolkata',
    });
    const timeOptions: Intl.DateTimeFormatOptions = {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
      timeZone: 'Asia/Kolkata',
    };
    if (includeSeconds) {
      timeOptions.second = '2-digit';
    }
    const timeStr = d.toLocaleTimeString('en-IN', timeOptions);
    return `${dateStr} ${timeStr} IST`;
  } catch {
    return String(isoOrDateString);
  }
}
