import type { ReactNode } from 'react';

import type { MeetingStatus } from '../api/types';
import { STATUS_LABELS, emotionLabel, genderLabel, speakerInitials } from '../lib/format';

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

const EMOTION_STYLES: Record<string, { badge: string; bar: string }> = {
  neutral: { badge: 'bg-slate-100 text-slate-600', bar: 'bg-slate-300' },
  happy: { badge: 'bg-amber-100 text-amber-800', bar: 'bg-amber-400' },
  sad: { badge: 'bg-blue-100 text-blue-800', bar: 'bg-blue-400' },
  angry: { badge: 'bg-red-100 text-red-700', bar: 'bg-red-400' },
  surprised: { badge: 'bg-violet-100 text-violet-700', bar: 'bg-violet-400' },
  fearful: { badge: 'bg-teal-100 text-teal-800', bar: 'bg-teal-400' },
};

const emotionStyle = (emotion: string) => EMOTION_STYLES[emotion] ?? EMOTION_STYLES.neutral!;

export function EmotionBadge({ emotion, title }: { emotion: string; title?: string }) {
  return (
    <span
      className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${emotionStyle(emotion).badge}`}
      title={title}
    >
      {emotionLabel(emotion)}
    </span>
  );
}

/** One bar split by each emotion's share of the speaker's talk time. */
export function EmotionBar({ shares, widthPercent }: { shares: Record<string, number>; widthPercent: number }) {
  const title = Object.entries(shares)
    .map(([emotion, share]) => `${emotionLabel(emotion)} ${Math.round(share * 100)}%`)
    .join(' · ');
  return (
    <div className="h-1.5 overflow-hidden rounded-full bg-slate-100" title={title}>
      <div className="flex h-full" style={{ width: `${widthPercent}%` }}>
        {Object.entries(shares).map(([emotion, share]) => (
          <div key={emotion} className={`h-full ${emotionStyle(emotion).bar}`} style={{ width: `${share * 100}%` }} />
        ))}
      </div>
    </div>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{message}</p>;
}

// Distinct colours per speaker, in order of appearance.
const SPEAKER_STYLES = [
  { text: 'text-brand-700', avatar: 'bg-brand-100 text-brand-700' },
  { text: 'text-violet-700', avatar: 'bg-violet-100 text-violet-700' },
  { text: 'text-orange-700', avatar: 'bg-orange-100 text-orange-700' },
  { text: 'text-sky-700', avatar: 'bg-sky-100 text-sky-700' },
  { text: 'text-rose-700', avatar: 'bg-rose-100 text-rose-700' },
  { text: 'text-amber-700', avatar: 'bg-amber-100 text-amber-800' },
];

export function speakerColor(index: number): string {
  return SPEAKER_STYLES[index % SPEAKER_STYLES.length]!.text;
}

export function SpeakerAvatar({ name, index }: { name: string; index: number }) {
  const style = SPEAKER_STYLES[index % SPEAKER_STYLES.length]!;
  return (
    <span
      aria-hidden="true"
      className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold ${style.avatar}`}
    >
      {speakerInitials(name, index)}
    </span>
  );
}

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white shadow-sm ${className}`}>{children}</section>
  );
}
