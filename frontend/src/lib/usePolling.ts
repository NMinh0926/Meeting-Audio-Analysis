import { useEffect, useRef } from 'react';

/** Call `callback` every `intervalMs` while `active` (e.g. while a job is still running). */
export function usePolling(callback: () => void, intervalMs: number, active: boolean): void {
  const latest = useRef(callback);
  useEffect(() => {
    latest.current = callback;
  });
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => latest.current(), intervalMs);
    return () => window.clearInterval(timer);
  }, [active, intervalMs]);
}
