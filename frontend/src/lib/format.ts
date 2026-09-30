import type { MeetingStatus } from '../api/types';

/** H:MM:SS for an hour or more, otherwise M:SS. */
export function formatClock(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = String(total % 60).padStart(2, '0');
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${s}` : `${m}:${s}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const GENDER_LABELS: Record<string, string> = { male: 'Nam', female: 'Nữ' };

export function genderLabel(gender: string): string {
  return GENDER_LABELS[gender] ?? 'Không rõ';
}

export const STATUS_LABELS: Record<MeetingStatus, string> = {
  queued: 'Đang chờ',
  processing: 'Đang xử lý',
  done: 'Xong',
  failed: 'Lỗi',
};

// Names of the stages reported by the worker (app/services/pipeline.py, app/services/jobs.py).
const STAGE_LABELS: Record<string, string> = {
  downloading: 'Tải file',
  preprocessing: 'Chuẩn hoá audio',
  transcription: 'Chuyển giọng nói thành chữ',
  diarization: 'Tách người nói',
  alignment: 'Ghép thời gian',
  merging: 'Gộp lượt nói',
  gender: 'Nhận diện giới tính',
  sentiment: 'Phân tích cảm xúc',
};

export function stageLabel(stage: string | null): string {
  return stage ? (STAGE_LABELS[stage] ?? stage) : '';
}
