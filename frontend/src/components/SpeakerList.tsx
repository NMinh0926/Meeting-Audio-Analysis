import { useState } from 'react';

import type { Speaker, TranscriptSpeaker } from '../api/types';
import { formatClock } from '../lib/format';
import { PencilIcon } from './icons';
import { EmotionBadge, EmotionBar, GenderBadge, SpeakerAvatar, speakerColor } from './ui';

function SpeakerItem({
  speaker,
  index,
  seconds,
  share,
  onRename,
}: {
  speaker: TranscriptSpeaker;
  index: number;
  seconds: number;
  share: number;
  onRename: (speaker: Speaker, name: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(speaker.display_name);
  const [saving, setSaving] = useState(false);

  async function save() {
    const trimmed = name.trim();
    if (!trimmed || trimmed === speaker.display_name) {
      setEditing(false);
      setName(speaker.display_name);
      return;
    }
    setSaving(true);
    try {
      await onRename(speaker, trimmed);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <li className="flex gap-3 py-3">
      <SpeakerAvatar name={speaker.display_name} index={index} />
      <div className="min-w-0 flex-1">
        {editing ? (
          <input
            autoFocus
            value={name}
            maxLength={100}
            disabled={saving}
            onChange={(e) => setName(e.target.value)}
            onBlur={() => void save()}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void save();
              if (e.key === 'Escape') {
                setName(speaker.display_name);
                setEditing(false);
              }
            }}
            className="w-full rounded-md border border-slate-300 px-2 py-0.5 text-sm"
            aria-label="Tên người nói"
          />
        ) : (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className={`group flex max-w-full items-center gap-1 text-left text-sm font-semibold ${speakerColor(index)}`}
            title={`${speaker.label} · bấm để đổi tên`}
          >
            <span className="truncate">{speaker.display_name}</span>
            <PencilIcon className="h-3.5 w-3.5 shrink-0 opacity-0 transition group-hover:opacity-60" />
          </button>
        )}
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          <GenderBadge gender={speaker.gender} confidence={speaker.gender_confidence} />
          <EmotionBadge emotion={speaker.emotion} title="Cảm xúc chiếm nhiều thời gian nói nhất" />
        </div>
        <div className="mt-1.5 text-xs text-slate-500 tabular-nums" title="Tổng thời gian nói">
          {formatClock(seconds)} · {Math.round(share * 100)}% thời gian nói
        </div>
        <div className="mt-1">
          <EmotionBar shares={speaker.emotion_shares} widthPercent={share * 100} />
        </div>
      </div>
    </li>
  );
}

export default function SpeakerList({
  speakers,
  talkTime,
  onRename,
}: {
  speakers: TranscriptSpeaker[];
  /** Seconds spoken per speaker id. */
  talkTime: Map<number, number>;
  onRename: (speaker: Speaker, name: string) => Promise<void>;
}) {
  const total = [...talkTime.values()].reduce((sum, s) => sum + s, 0);
  return (
    <ul className="divide-y divide-slate-100">
      {speakers.map((speaker, index) => {
        const seconds = talkTime.get(speaker.id) ?? 0;
        return (
          <SpeakerItem
            key={speaker.id}
            speaker={speaker}
            index={index}
            seconds={seconds}
            share={total > 0 ? seconds / total : 0}
            onRename={onRename}
          />
        );
      })}
    </ul>
  );
}
