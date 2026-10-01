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

/**
 * Up to two letters for a speaker's avatar: the first and last words of a given name ("Nguyễn Văn An" → "NA"),
 * or the speaker's number while it still has the automatic label ("SPEAKER_00").
 */
export function speakerInitials(name: string, index: number): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0 || /^SPEAKER_\d+$/.test(name.trim())) return String(index + 1);
  const first = words[0]!;
  const last = words[words.length - 1]!;
  const letters = words.length > 1 ? [...first][0]! + [...last][0]! : [...first].slice(0, 2).join('');
  return letters.toLocaleUpperCase('vi');
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

/** "2 nam · 1 nữ" style summary of who speaks; speakers of unknown gender are counted separately. */
export function genderSummary(genders: string[]): string {
  const male = genders.filter((g) => g === 'male').length;
  const female = genders.filter((g) => g === 'female').length;
  const unknown = genders.length - male - female;
  return [
    male > 0 && `${male} nam`,
    female > 0 && `${female} nữ`,
    unknown > 0 && `${unknown} không rõ`,
  ]
    .filter(Boolean)
    .join(' · ');
}
