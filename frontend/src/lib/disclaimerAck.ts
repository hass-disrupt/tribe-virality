export const DISCLAIMER_VERSION = 1;
const KEY = "tribe_virality.disclaimer_ack";

export function hasAckedDisclaimer(): boolean {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return false;
    const parsed = JSON.parse(raw);
    return parsed?.version === DISCLAIMER_VERSION;
  } catch {
    return false;
  }
}

export function ackDisclaimer(): void {
  localStorage.setItem(
    KEY,
    JSON.stringify({ version: DISCLAIMER_VERSION, ackedAt: new Date().toISOString() }),
  );
}
