import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { audioUrl, exportUrl, getMeeting, getTranscript, renameSpeaker } from '../api/client';
import type { ExportFormat, MeetingDetail, Speaker, Transcript } from '../api/types';
import { formatClock, stageLabel } from '../lib/format';
import { SKIP_SECONDS, shortcutFor } from '../lib/player';
import { findActiveIndex, flattenUtterances, sentenceStart, talkTime } from '../lib/transcript';
import { usePolling } from '../lib/usePolling';
import AudioPlayer, { useAudioPlayer } from './AudioPlayer';
import SpeakerList from './SpeakerList';
import TranscriptView from './TranscriptView';
import { ArrowLeftIcon, CrosshairIcon, DownloadIcon, SpinnerIcon } from './icons';
import { Card, ErrorNote, StatusBadge } from './ui';

const POLL_MS = 3000;
const EXPORTS: { format: ExportFormat; label: string; title: string }[] = [
  { format: 'txt', label: 'TXT', title: 'Văn bản' },
  { format: 'srt', label: 'SRT', title: 'Phụ đề' },
  { format: 'json', label: 'JSON', title: 'Dữ liệu cho hệ thống khác' },
];
const SHORTCUTS: [string, string][] = [
  ['Space', 'Phát / dừng'],
  ['← →', `Lùi / tới ${SKIP_SECONDS} giây`],
  ['↑ ↓', 'Câu trước / câu sau'],
];

export default function MeetingPage({ id }: { id: string }) {
  const [meeting, setMeeting] = useState<MeetingDetail | null>(null);
  const [transcript, setTranscript] = useState<Transcript | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [follow, setFollow] = useState(true);
  const player = useAudioPlayer(meeting?.duration_seconds ?? null);

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
  const speaking = useMemo(() => talkTime(transcript?.turns ?? []), [transcript]);
  const activeIndex = player.started ? findActiveIndex(refs, player.time) : -1;
  const active = activeIndex >= 0 ? refs[activeIndex]! : null;

  // Keyboard shortcuts; the handler reads the latest state through a ref so it is bound once.
  const shortcut = useRef<(e: KeyboardEvent) => void>(() => undefined);
  useEffect(() => {
    shortcut.current = (e) => {
      const action = shortcutFor(e);
      if (!action) return;
      e.preventDefault();
      if (action === 'toggle') player.toggle();
      else if (action === 'back') player.skip(-SKIP_SECONDS);
      else if (action === 'forward') player.skip(SKIP_SECONDS);
      else {
        const target = sentenceStart(refs, player.started ? player.time : -1, action);
        if (target !== null) player.seek(target);
      }
    };
  });
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => shortcut.current(e);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  async function rename(speaker: Speaker, name: string) {
    try {
      const updated = await renameSpeaker(id, speaker.id, name);
      // Merge: the rename response has no emotion fields, which only the transcript carries.
      const replace = <T extends Speaker>(list: T[]) => list.map((s) => (s.id === updated.id ? { ...s, ...updated } : s));
      setTranscript((t) => t && { ...t, speakers: replace(t.speakers) });
      setMeeting((m) => m && { ...m, speakers: replace(m.speakers) });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      throw e;
    }
  }

  return (
    <div className="min-h-full">
      {/* Sticky so the way back and the player stay in reach anywhere in a long transcript. */}
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/90 shadow-sm backdrop-blur">
        <div className="mx-auto max-w-6xl space-y-2 px-4 py-2.5">
          <div className="flex items-center gap-3">
            <a
              href="#/"
              className="inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              title="Về danh sách cuộc họp"
            >
              <ArrowLeftIcon className="h-4 w-4" />
              <span className="hidden sm:inline">Danh sách</span>
            </a>
            <span className="h-5 w-px bg-slate-200" />
            <h1 className="min-w-0 truncate font-semibold" title={meeting?.filename}>
              {meeting?.filename ?? '…'}
            </h1>
            {meeting && <StatusBadge status={meeting.status} />}
          </div>
          <AudioPlayer src={audioUrl(id)} player={player} />
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        <ErrorNote message={error} />

        {meeting && meeting.status !== 'done' && (
          <Card className="p-5 text-sm">
            {running && (
              <p className="flex items-center gap-3 text-slate-700">
                <SpinnerIcon className="h-5 w-5 text-brand-600" />
                <span>
                  Đang xử lý{meeting.current_stage ? `: ${stageLabel(meeting.current_stage)}` : '…'} — bản ghi sẽ
                  hiện khi xong. Trong lúc chờ vẫn nghe được audio.
                </span>
              </p>
            )}
            {meeting.status === 'failed' && (
              <p className="text-red-700">
                Xử lý lỗi ({meeting.error_code}): {meeting.error_message}
              </p>
            )}
          </Card>
        )}

        {transcript && (
          <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
            <aside className="space-y-4 lg:sticky lg:top-32 lg:order-2">
              <Card className="px-4 pt-3 pb-1">
                <h2 className="text-xs font-semibold tracking-wide text-slate-500 uppercase">
                  {transcript.speakers.length} người nói
                </h2>
                <SpeakerList speakers={transcript.speakers} talkTime={speaking} onRename={rename} />
              </Card>

              <Card className="space-y-3 p-4 text-sm">
                <h2 className="text-xs font-semibold tracking-wide text-slate-500 uppercase">Tải bản ghi</h2>
                <div className="grid grid-cols-3 gap-2">
                  {EXPORTS.map(({ format, label, title }) => (
                    <a
                      key={format}
                      href={exportUrl(id, format)}
                      title={title}
                      className="inline-flex items-center justify-center gap-1 rounded-lg border border-slate-200 py-1.5 font-medium text-slate-700 hover:border-brand-500 hover:text-brand-700"
                    >
                      <DownloadIcon className="h-3.5 w-3.5" />
                      {label}
                    </a>
                  ))}
                </div>
              </Card>

              <Card className="space-y-2 p-4 text-sm">
                <label className="flex items-center gap-2 text-slate-700">
                  <input
                    type="checkbox"
                    checked={follow}
                    onChange={(e) => setFollow(e.target.checked)}
                    className="accent-brand-600"
                  />
                  Tự cuộn theo câu đang phát
                </label>
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 pt-1 text-xs text-slate-500">
                  {SHORTCUTS.map(([keys, action]) => (
                    <div key={keys} className="contents">
                      <dt>
                        <kbd className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-sans text-slate-700">
                          {keys}
                        </kbd>
                      </dt>
                      <dd className="self-center">{action}</dd>
                    </div>
                  ))}
                </dl>
              </Card>
            </aside>

            <Card className="overflow-hidden">
              <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2.5 text-xs text-slate-500 sm:px-5">
                <span>Bấm vào một câu để nghe từ chỗ đó.</span>
                {meeting?.duration_seconds != null && (
                  <span className="tabular-nums">Thời lượng {formatClock(meeting.duration_seconds)}</span>
                )}
              </div>
              <TranscriptView
                turns={transcript.turns}
                speakers={transcript.speakers}
                active={active}
                follow={follow}
                onSeek={player.seek}
              />
            </Card>
          </div>
        )}
      </main>

      {transcript && !follow && active && (
        <button
          type="button"
          onClick={() =>
            document.querySelector('[data-active]')?.scrollIntoView({ block: 'center', behavior: 'smooth' })
          }
          className="fixed right-6 bottom-6 z-20 inline-flex items-center gap-2 rounded-full bg-brand-600 px-4 py-2.5 text-sm font-medium text-white shadow-lg hover:bg-brand-700"
        >
          <CrosshairIcon className="h-4 w-4" />
          Về câu đang phát
        </button>
      )}
    </div>
  );
}
