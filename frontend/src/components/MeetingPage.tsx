import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { audioUrl, exportUrl, getMeeting, getTranscript, renameSpeaker } from '../api/client';
import type { ExportFormat, MeetingDetail, Speaker, Transcript } from '../api/types';
import { formatClock, stageLabel } from '../lib/format';
import { findActiveIndex, flattenUtterances } from '../lib/transcript';
import { usePolling } from '../lib/usePolling';
import SpeakerList from './SpeakerList';
import TranscriptView from './TranscriptView';
import { ErrorNote, StatusBadge } from './ui';

const POLL_MS = 3000;
const EXPORTS: { format: ExportFormat; label: string }[] = [
  { format: 'txt', label: 'TXT' },
  { format: 'srt', label: 'SRT (phụ đề)' },
  { format: 'json', label: 'JSON (dữ liệu)' },
];

export default function MeetingPage({ id }: { id: string }) {
  const [meeting, setMeeting] = useState<MeetingDetail | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [time, setTime] = useState(0);
  const [started, setStarted] = useState(false);
  const [follow, setFollow] = useState(true);
  const audio = useRef<HTMLAudioElement>(null);

  const load = useCallback(async () => {
    try {
      const detail = await getMeeting(id);
      setMeeting(detail);
      if (detail.status === 'done') setTranscript(await getTranscript(id));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);
  const running = meeting?.status === 'queued' || meeting?.status === 'processing';
  usePolling(() => void load(), POLL_MS, running);

  const refs = useMemo(() => flattenUtterances(transcript?.turns ?? []), [transcript]);
  const activeIndex = started ? findActiveIndex(refs, time) : -1;
  const active = activeIndex >= 0 ? refs[activeIndex]! : null;

  const seek = useCallback((seconds: number) => {
    const player = audio.current;
    if (!player) return;
    player.currentTime = seconds;
    setTime(seconds);
    setStarted(true);
    void player.play();
  }, []);

  async function rename(speaker: Speaker, name: string) {
    try {
      const updated = await renameSpeaker(id, speaker.id, name);
      const replace = (list: Speaker[]) => list.map((s) => (s.id === updated.id ? updated : s));
      setTranscript((t) => t && { ...t, speakers: replace(t.speakers) });
      setMeeting((m) => m && { ...m, speakers: replace(m.speakers) });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-6">
      <a href="#/" className="text-sm text-brand-700 hover:underline">
        ← Danh sách cuộc họp
      </a>

      <header className="mt-2 mb-4 flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold break-all">{meeting?.filename ?? '…'}</h1>
        {meeting && <StatusBadge status={meeting.status} />}
        {meeting?.duration_seconds != null && (
          <span className="text-sm text-slate-500">{formatClock(meeting.duration_seconds)}</span>
        )}
      </header>

      <ErrorNote message={error} />

      {/* Sticky so the player stays reachable while reading a long transcript. */}
      <div className="sticky top-0 z-10 -mx-4 space-y-3 border-b border-slate-200 bg-slate-50/95 px-4 py-3 backdrop-blur">
        <audio
          ref={audio}
          controls
          preload="metadata"
          src={audioUrl(id)}
          className="w-full"
          onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
          onPlay={() => setStarted(true)}
          onSeeked={(e) => setTime(e.currentTarget.currentTime)}
        />
        {transcript && (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <SpeakerList speakers={transcript.speakers} onRename={rename} />
            <div className="flex items-center gap-3 text-sm">
              <label className="flex items-center gap-1.5 text-slate-600">
                <input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} />
                Tự cuộn theo audio
              </label>
              {EXPORTS.map(({ format, label }) => (
                <a
                  key={format}
                  href={exportUrl(id, format)}
                  className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-slate-700 hover:bg-slate-50"
                >
                  {label}
                </a>
              ))}
            </div>
          </div>
        )}
      </div>

      {meeting && meeting.status !== 'done' && (
        <section className="mt-6 rounded-lg border border-slate-200 bg-white p-4 text-sm">
          {running && (
            <p>
              Đang xử lý{meeting.current_stage ? `: ${stageLabel(meeting.current_stage)}` : '…'} — bản ghi sẽ hiện
              khi xong. Trong lúc chờ vẫn nghe được audio.
            </p>
          )}
          {meeting.status === 'failed' && (
            <p className="text-red-700">
              Xử lý lỗi ({meeting.error_code}): {meeting.error_message}
            </p>
          )}
        </section>
      )}

      {transcript && (
        <section className="mt-2">
          <p className="py-2 text-xs text-slate-500">Bấm vào một câu để nghe từ chỗ đó.</p>
          <TranscriptView
            turns={transcript.turns}
            speakers={transcript.speakers}
            active={active}
            follow={follow}
            onSeek={seek}
          />
        </section>
      )}
    </main>
  );
}
