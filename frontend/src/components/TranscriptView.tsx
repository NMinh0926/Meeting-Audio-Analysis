import { memo, useEffect, useRef } from 'react';

import type { Speaker, Turn } from '../api/types';
import { formatClock } from '../lib/format';
import { GenderBadge, SpeakerAvatar, speakerColor } from './ui';

interface TurnProps {
  turn: Turn;
  speaker: Speaker | undefined;
  speakerIndex: number;
  /** Index of the playing utterance in this turn, -1 when the playing one is elsewhere. */
  activeUtterance: number;
  follow: boolean;
  onSeek: (seconds: number, play?: boolean) => void;
}

// Memoised: while audio plays only the turns whose active utterance changes re-render.
const TurnView = memo(function TurnView({ turn, speaker, speakerIndex, activeUtterance, follow, onSeek }: TurnProps) {
  const active = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (follow && activeUtterance >= 0) active.current?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, [activeUtterance, follow]);

  const name = speaker?.display_name ?? '?';
  return (
    <article className={`flex gap-3 px-4 py-4 sm:px-5 ${activeUtterance >= 0 ? 'bg-amber-50/60' : ''}`}>
      <SpeakerAvatar name={name} index={speakerIndex} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className={`text-sm font-semibold ${speakerColor(speakerIndex)}`}>{name}</span>
          {speaker && <GenderBadge gender={speaker.gender} />}
          <button
            type="button"
            onClick={() => onSeek(turn.start, true)}
            className="rounded px-1 text-xs text-slate-400 tabular-nums hover:bg-slate-100 hover:text-brand-700"
            title="Phát từ đầu lượt nói này"
          >
            {formatClock(turn.start)}
          </button>
        </div>
        <p className="mt-1 leading-7 text-slate-800">
          {turn.utterances.map((u, i) => (
            <span
              key={i}
              ref={i === activeUtterance ? active : undefined}
              data-active={i === activeUtterance || undefined}
              role="button"
              tabIndex={0}
              onClick={() => onSeek(u.start, true)}
              onKeyDown={(e) => e.key === 'Enter' && onSeek(u.start, true)}
              title={`${formatClock(u.start)} – ${formatClock(u.end)}`}
              className={`cursor-pointer rounded px-0.5 transition-colors ${
                i === activeUtterance ? 'bg-amber-200 text-slate-900' : 'hover:bg-slate-100'
              }`}
            >
              {u.text.trim()}{' '}
            </span>
          ))}
        </p>
      </div>
    </article>
  );
});

export default function TranscriptView({
  turns,
  speakers,
  active,
  follow,
  onSeek,
}: {
  turns: Turn[];
  speakers: Speaker[];
  active: { turn: number; utterance: number } | null;
  follow: boolean;
  onSeek: (seconds: number, play?: boolean) => void;
}) {
  const byId = new Map(speakers.map((s, index) => [s.id, { speaker: s, index }]));
  return (
    <div className="divide-y divide-slate-100">
      {turns.map((turn, t) => {
        const entry = byId.get(turn.speaker_id);
        return (
          <TurnView
            key={turn.id}
            turn={turn}
            speaker={entry?.speaker}
            speakerIndex={entry?.index ?? 0}
            activeUtterance={active?.turn === t ? active.utterance : -1}
            follow={follow}
            onSeek={onSeek}
          />
        );
      })}
    </div>
  );
}
