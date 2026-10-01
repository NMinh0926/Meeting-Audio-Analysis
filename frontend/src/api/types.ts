// Mirrors the response models in app/models/schemas.py.

export type MeetingStatus = 'queued' | 'processing' | 'done' | 'failed';
export type Gender = 'male' | 'female' | 'unknown';
export type Emotion = 'neutral' | 'happy' | 'sad' | 'angry' | 'surprised' | 'fearful';
export type ExportFormat = 'txt' | 'srt' | 'json';

export interface Meeting {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  status: MeetingStatus;
  current_stage: string | null;
  error_code: string | null;
  error_message: string | null;
  attempts: number;
  duration_seconds: number | null;
  speaker_count: number | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface MeetingList {
  items: MeetingDetail[];
  total: number;
  limit: number;
  offset: number;
}

export interface Speaker {
  id: number;
  label: string;
  display_name: string;
  gender: Gender | string;
  gender_confidence: number;
}

export interface MeetingDetail extends Meeting {
  speakers: Speaker[];
}

export interface Utterance {
  start: number;
  end: number;
  text: string;
}

export interface Turn {
  id: number;
  speaker_id: number;
  start: number;
  end: number;
  text: string;
  /** Emotion of the turn (field name kept from the first API version). */
  sentiment: Emotion | string;
  sentiment_confidence: number;
  utterances: Utterance[];
}

export interface TranscriptSpeaker extends Speaker {
  /** Emotion filling most of the speaker's talk time, and each emotion's share of it (largest first). */
  emotion: Emotion | string;
  emotion_shares: Record<string, number>;
}

export interface Transcript {
  meeting_id: string;
  filename: string;
  duration_seconds: number | null;
  speakers: TranscriptSpeaker[];
  turns: Turn[];
}
