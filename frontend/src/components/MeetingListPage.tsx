import { useCallback, useEffect, useState } from 'react';

import { deleteMeeting, listMeetings, retryMeeting } from '../api/client';
import type { Meeting, MeetingDetail } from '../api/types';
import { formatBytes, formatClock, genderSummary, stageLabel } from '../lib/format';
import { meetingHref } from '../lib/route';
import { usePolling } from '../lib/usePolling';
import UploadDropzone from './UploadDropzone';
import { MicIcon, RetryIcon, SpinnerIcon, TrashIcon } from './icons';
import { Card, ErrorNote, StatusBadge } from './ui';

const POLL_MS = 3000;

const isRunning = (m: Meeting): boolean => m.status === 'queued' || m.status === 'processing';

const iconButton =
  'relative z-10 inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition disabled:cursor-not-allowed disabled:opacity-40';

function MeetingRow({ meeting: m, onAction }: { meeting: MeetingDetail; onAction: (action: () => Promise<unknown>) => void }) {
  const genders = genderSummary(m.speakers.map((s) => s.gender));
  return (
    // The file name link covers the whole row; the action buttons sit above it.
    <li className="relative flex items-center gap-4 px-4 py-3.5 transition hover:bg-slate-50 sm:px-5">
      <span className="hidden h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600 sm:inline-flex">
        <MicIcon className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1">
        <a href={meetingHref(m.id)} className="block truncate font-medium text-slate-900 after:absolute after:inset-0">
          {m.filename}
        </a>
        <p className="mt-0.5 text-xs text-slate-500 tabular-nums">
          {m.duration_seconds !== null && <>{formatClock(m.duration_seconds)} · </>}
          {formatBytes(m.size_bytes)} · {new Date(m.created_at).toLocaleString('vi-VN')}
        </p>
      </div>

      <div className="hidden w-44 text-sm md:block">
        {m.speaker_count !== null ? (
          <>
            <div className="font-medium text-slate-700">{m.speaker_count} người nói</div>
            {genders && <div className="text-xs text-slate-500">{genders}</div>}
          </>
        ) : (
          <span className="text-slate-400">–</span>
        )}
      </div>

      <div className="w-36 text-right sm:text-left">
        <StatusBadge status={m.status} />
        {m.status === 'processing' && (
          <div className="mt-1 flex items-center justify-end gap-1.5 text-xs text-slate-500 sm:justify-start">
            <SpinnerIcon className="h-3 w-3 text-brand-600" />
            {stageLabel(m.current_stage)}
          </div>
        )}
        {m.status === 'failed' && (
          <div className="mt-1 truncate text-xs text-red-600" title={m.error_message ?? ''}>
            {m.error_code}
          </div>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-1">
        {m.status === 'failed' && (
          <button
            type="button"
            className={`${iconButton} hover:bg-brand-50 hover:text-brand-700`}
            title="Chạy lại"
            aria-label="Chạy lại"
            onClick={() => onAction(() => retryMeeting(m.id))}
          >
            <RetryIcon className="h-4 w-4" />
          </button>
        )}
        <button
          type="button"
          className={`${iconButton} hover:bg-red-50 hover:text-red-600`}
          disabled={m.status === 'processing'}
          title={m.status === 'processing' ? 'Đang xử lý, chưa xoá được' : 'Xoá'}
          aria-label="Xoá"
          onClick={() => {
            if (window.confirm(`Xoá "${m.filename}" và toàn bộ kết quả?`)) onAction(() => deleteMeeting(m.id));
          }}
        >
          <TrashIcon className="h-4 w-4" />
        </button>
      </div>
    </li>
  );
}

export default function MeetingListPage() {
  const [meetings, setMeetings] = useState<MeetingDetail[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setMeetings((await listMeetings()).items);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);
  usePolling(() => void refresh(), POLL_MS, meetings?.some(isRunning) ?? false);

  async function act(action: () => Promise<unknown>) {
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
    await refresh();
  }

  return (
    <div className="min-h-full">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-4">
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-white shadow-sm">
            <MicIcon className="h-5 w-5" />
          </span>
          <div>
            <h1 className="text-lg leading-tight font-semibold">Ghi âm cuộc họp</h1>
            <p className="text-sm text-slate-500">Chuyển giọng nói thành chữ, tách người nói, nhận diện nam/nữ</p>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-6 px-4 py-6">
        <UploadDropzone onUploaded={() => void refresh()} />
        <ErrorNote message={error} />

        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-700">
            Cuộc họp{meetings ? ` (${meetings.length})` : ''}
          </h2>
          <Card className="overflow-hidden">
            {meetings?.length === 0 && (
              <p className="px-5 py-10 text-center text-sm text-slate-500">
                Chưa có cuộc họp nào. Tải file ghi âm lên để bắt đầu.
              </p>
            )}
            <ul className="divide-y divide-slate-100">
              {meetings?.map((m) => <MeetingRow key={m.id} meeting={m} onAction={(a) => void act(a)} />)}
            </ul>
          </Card>
        </section>
      </main>
    </div>
  );
}
