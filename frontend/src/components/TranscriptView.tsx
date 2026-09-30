import { memo, useEffect, useRef } from 'react';

import type { Speaker, Turn } from '../api/types';
import { formatClock } from '../lib/format';
import { GenderBadge, speakerColor } from './ui';

interface TurnProps {
  turn: Turn;
  speaker: Speaker | undefined;
  speakerIndex: number;
  /** Index of the playing utterance in this turn, -1 when the playing one is elsewhere. */
  activeUtterance: number;
  follow: boolean;
  onSeek: (seconds: number) => void;
}

// Memoised: while audio plays only the turns whose active utterance changes re-render.
const TurnView = memo(function TurnView({ turn, speaker, speakerIndex, activeUtterance, follow, onSeek }: TurnProps) {
  const active = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (follow && activeUtterance >= 0) active.current?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, [activeUtterance, follow]);

  return (
    <article className="grid grid-cols-[5rem_1fr] gap-3 py-3">
      <button
        type="button"
        onClick={() => onSeek(turn.start)}
        className="self-start pt-0.5 text-left text-xs text-slate-400 tabular-nums hover:text-brand-700"
        title="Phát từ đầu lượt nói này"
      >
        {formatClock(turn.start)}
      </button>
      <div>
        <div className="mb-1 flex items-center gap-2">
          <span className={`text-sm font-semibold ${speakerColor(speakerIndex)}`}>
            {speaker?.display_name ?? '?'}
          </span>
          {speaker && <GenderBadge gender={speaker.gender} />}
        </div>
        <p className="leading-relaxed">
          {turn.utterances.map((u, i) => (
            <span
              key={i}
              ref={i === activeUtterance ? active : undefined}
              role="button"
              tabIndex={0}
              onClick={() => onSeek(u.start)}
              onKeyDown={(e) => e.key === 'Enter' && onSeek(u.start)}
              title={`${formatClock(u.start)} – ${formatClock(u.end)}`}
              className={`cursor-pointer rounded px-0.5 transition-colors ${
                i === activeUtterance ? 'bg-amber-200' : 'hover:bg-slate-100'
              }`}
            >
              {u.text}{' '}
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
  onSeek: (seconds: number) => void;
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
