import type { ExportFormat, Meeting, MeetingDetail, MeetingList, Speaker, Transcript } from './types';

const BASE = '/api/v1/meetings';

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

/** The API's `detail` message, or a generic one when the body is not the usual JSON error. */
export function errorMessage(status: number, body: string): string {
  try {
    const detail: unknown = JSON.parse(body).detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.length > 0) return String(detail[0]?.msg ?? `Lỗi ${status}`);
  } catch {
    // Not JSON (e.g. a proxy error page).
  }
  return `Lỗi ${status}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) throw new ApiError(response.status, errorMessage(response.status, await response.text()));
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export const audioUrl = (id: string): string => `${BASE}/${id}/audio`;
export const exportUrl = (id: string, format: ExportFormat): string => `${BASE}/${id}/export?format=${format}`;

export const listMeetings = (limit = 100): Promise<MeetingList> => request(`${BASE}?limit=${limit}`);
export const getMeeting = (id: string): Promise<MeetingDetail> => request(`${BASE}/${id}`);
export const getTranscript = (id: string): Promise<Transcript> => request(`${BASE}/${id}/transcript`);
export const retryMeeting = (id: string): Promise<Meeting> => request(`${BASE}/${id}/retry`, { method: 'POST' });
export const deleteMeeting = (id: string): Promise<void> => request(`${BASE}/${id}`, { method: 'DELETE' });

export const renameSpeaker = (meetingId: string, speakerId: number, displayName: string): Promise<Speaker> =>
  request(`${BASE}/${meetingId}/speakers/${speakerId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ display_name: displayName }),
  });

/** Upload recordings with progress (fetch cannot report upload progress). */
export function uploadMeetings(files: File[], onProgress: (fraction: number) => void): Promise<Meeting[]> {
  const form = new FormData();
  for (const file of files) form.append('files', file);
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', BASE);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    };
    xhr.onload = () => {
      if (xhr.status === 202) resolve(JSON.parse(xhr.responseText) as Meeting[]);
      else reject(new ApiError(xhr.status, errorMessage(xhr.status, xhr.responseText)));
    };
    xhr.onerror = () => reject(new ApiError(0, 'Không kết nối được máy chủ'));
    xhr.send(form);
  });
}
