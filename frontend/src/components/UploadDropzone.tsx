import { useRef, useState } from 'react';

import { uploadMeetings } from '../api/client';
import { UploadIcon } from './icons';
import { ErrorNote } from './ui';

const ACCEPTED = ['.wav', '.mp3', '.m4a'];

const isAccepted = (file: File): boolean => ACCEPTED.some((ext) => file.name.toLowerCase().endsWith(ext));

export default function UploadDropzone({ onUploaded }: { onUploaded: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function upload(fileList: FileList | null) {
    const files = Array.from(fileList ?? []);
    if (files.length === 0 || progress !== null) return;
    const rejected = files.filter((file) => !isAccepted(file));
    if (rejected.length > 0) {
      setError(`Chỉ nhận ${ACCEPTED.join(', ')}: ${rejected.map((f) => f.name).join(', ')}`);
      return;
    }
    setError(null);
    setProgress(0);
    try {
      await uploadMeetings(files, setProgress);
      onUploaded();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setProgress(null);
      if (input.current) input.current.value = '';
    }
  }

  return (
    <div className="space-y-2">
      <div
        role="button"
        tabIndex={0}
        onClick={() => input.current?.click()}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          void upload(e.dataTransfer.files);
        }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition ${
          dragging ? 'border-brand-500 bg-brand-50' : 'border-slate-300 bg-white hover:border-brand-500 hover:bg-brand-50/40'
        }`}
      >
        {progress === null ? (
          <>
            <span className="mb-3 inline-flex h-11 w-11 items-center justify-center rounded-full bg-brand-50 text-brand-600">
              <UploadIcon className="h-5 w-5" />
            </span>
            <p className="font-medium">Kéo thả file ghi âm vào đây hoặc bấm để chọn</p>
            <p className="mt-1 text-sm text-slate-500">WAV, MP3, M4A · chọn được nhiều file một lúc</p>
          </>
        ) : (
          <div className="w-full max-w-sm">
            <p className="mb-2 text-sm">Đang tải lên… {Math.round(progress * 100)}%</p>
            <div className="h-2 overflow-hidden rounded bg-slate-200">
              <div className="h-full bg-brand-500 transition-all" style={{ width: `${progress * 100}%` }} />
            </div>
          </div>
        )}
        <input
          ref={input}
          type="file"
          multiple
          accept={ACCEPTED.join(',')}
          className="hidden"
          onChange={(e) => void upload(e.target.files)}
        />
      </div>
      <ErrorNote message={error} />
    </div>
  );
}
