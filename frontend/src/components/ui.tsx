import type { ReactNode } from 'react';

import type { MeetingStatus } from '../api/types';
import { STATUS_LABELS, genderLabel } from '../lib/format';

const STATUS_STYLES: Record<MeetingStatus, string> = {
  queued: 'bg-slate-100 text-slate-700',
  processing: 'bg-amber-100 text-amber-800',
  done: 'bg-brand-100 text-brand-700',
  failed: 'bg-red-100 text-red-700',
};

export function StatusBadge({ status }: { status: MeetingStatus }) {
  return (
    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}

const GENDER_STYLES: Record<string, string> = {
  male: 'bg-sky-100 text-sky-800',
  female: 'bg-pink-100 text-pink-800',
};

export function GenderBadge({ gender, confidence }: { gender: string; confidence?: number }) {
  const known = gender in GENDER_STYLES;
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${GENDER_STYLES[gender] ?? 'bg-slate-100 text-slate-600'}`}
      title={confidence !== undefined ? `Độ tin cậy ${Math.round(confidence * 100)}%` : undefined}
    >
      {genderLabel(gender)}
      {known && confidence !== undefined ? ` · ${Math.round(confidence * 100)}%` : ''}
    </span>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  variant = 'secondary',
  title,
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: 'primary' | 'secondary' | 'danger';
  title?: string;
}) {
  const styles = {
    primary: 'bg-brand-600 text-white hover:bg-brand-700',
    secondary: 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50',
    danger: 'border border-red-200 bg-white text-red-700 hover:bg-red-50',
  }[variant];
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`rounded-md px-3 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50 ${styles}`}
    >
      {children}
    </button>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{message}</p>;
}

// Distinct colours per speaker, in order of appearance.
const SPEAKER_COLORS = ['text-brand-700', 'text-violet-700', 'text-orange-700', 'text-sky-700', 'text-rose-700'];

export function speakerColor(index: number): string {
  return SPEAKER_COLORS[index % SPEAKER_COLORS.length]!;
}
