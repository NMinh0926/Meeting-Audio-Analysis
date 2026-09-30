import { useCallback, useEffect, useState } from 'react';

import { deleteMeeting, listMeetings, retryMeeting } from '../api/client';
import type { Meeting } from '../api/types';
import { formatBytes, formatClock, stageLabel } from '../lib/format';
import { meetingHref } from '../lib/route';
import { usePolling } from '../lib/usePolling';
import UploadDropzone from './UploadDropzone';
import { Button, ErrorNote, StatusBadge } from './ui';

const POLL_MS = 3000;

const isRunning = (m: Meeting): boolean => m.status === 'queued' || m.status === 'processing';

export default function MeetingListPage() {
  const [meetings, setMeetings] = useState<Meeting[] | null>(null);
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
    <main className="mx-auto max-w-5xl space-y-6 px-4 py-8">
      <header>
        <h1 className="text-2xl font-semibold">Ghi âm cuộc họp</h1>
        <p className="text-sm text-slate-500">
          Chuyển giọng nói thành chữ, tách người nói và nhận diện giới tính.
        </p>
      </header>

      <UploadDropzone onUploaded={() => void refresh()} />
      <ErrorNote message={error} />

      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">File</th>
              <th className="px-4 py-2 font-medium">Trạng thái</th>
              <th className="px-4 py-2 font-medium">Thời lượng</th>
              <th className="px-4 py-2 font-medium">Người nói</th>
              <th className="px-4 py-2 font-medium">Tải lên</th>
              <th className="px-4 py-2" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {meetings?.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  Chưa có cuộc họp nào.
                </td>
              </tr>
            )}
            {meetings?.map((m) => (
              <tr key={m.id} className="hover:bg-slate-50">
                <td className="px-4 py-2">
                  <a href={meetingHref(m.id)} className="font-medium text-brand-700 hover:underline">
                    {m.filename}
                  </a>
                  <div className="text-xs text-slate-400">{formatBytes(m.size_bytes)}</div>
                </td>
                <td className="px-4 py-2">
                  <StatusBadge status={m.status} />
                  {m.status === 'processing' && (
                    <div className="mt-1 text-xs text-slate-500">{stageLabel(m.current_stage)}</div>
                  )}
                  {m.status === 'failed' && (
                    <div className="mt-1 max-w-xs truncate text-xs text-red-600" title={m.error_message ?? ''}>
                      {m.error_code}
                    </div>
                  )}
                </td>
                <td className="px-4 py-2 tabular-nums">
                  {m.duration_seconds !== null ? formatClock(m.duration_seconds) : '–'}
                </td>
                <td className="px-4 py-2">{m.speaker_count ?? '–'}</td>
                <td className="px-4 py-2 text-slate-500">{new Date(m.created_at).toLocaleString('vi-VN')}</td>
                <td className="space-x-2 px-4 py-2 text-right whitespace-nowrap">
                  {m.status === 'failed' && <Button onClick={() => void act(() => retryMeeting(m.id))}>Chạy lại</Button>}
                  <Button
                    variant="danger"
                    disabled={m.status === 'processing'}
                    title={m.status === 'processing' ? 'Đang xử lý, chưa xoá được' : undefined}
                    onClick={() => {
                      if (window.confirm(`Xoá "${m.filename}" và toàn bộ kết quả?`)) void act(() => deleteMeeting(m.id));
                    }}
                  >
                    Xoá
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
