import { useState } from 'react';

import type { Speaker } from '../api/types';
import { GenderBadge, speakerColor } from './ui';

function SpeakerItem({
  speaker,
  index,
  onRename,
}: {
  speaker: Speaker;
  index: number;
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
    <li className="flex items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-1.5">
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
          className="w-40 rounded border border-slate-300 px-1.5 py-0.5 text-sm"
          aria-label="Tên người nói"
        />
      ) : (
        <button
          type="button"
          onClick={() => setEditing(true)}
          className={`text-sm font-semibold hover:underline ${speakerColor(index)}`}
          title={`${speaker.label} · bấm để đổi tên`}
        >
          {speaker.display_name}
        </button>
      )}
      <GenderBadge gender={speaker.gender} confidence={speaker.gender_confidence} />
    </li>
  );
}

export default function SpeakerList({
  speakers,
  onRename,
}: {
  speakers: Speaker[];
  onRename: (speaker: Speaker, name: string) => Promise<void>;
}) {
  return (
    <ul className="flex flex-wrap gap-2">
      {speakers.map((speaker, index) => (
        <SpeakerItem key={speaker.id} speaker={speaker} index={index} onRename={onRename} />
      ))}
    </ul>
  );
}
