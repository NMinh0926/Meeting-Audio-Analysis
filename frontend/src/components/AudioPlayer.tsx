import { type SyntheticEvent, useCallback, useEffect, useRef, useState } from 'react';

import { formatClock } from '../lib/format';
import { SKIP_SECONDS, clampTime, nextRate } from '../lib/player';
import { PauseIcon, PlayIcon, SkipIcon } from './icons';

/** State of the meeting's audio element and the actions on it, shared by the player bar and the page. */
export function useAudioPlayer(fallbackDuration: number | null) {
  const audio = useRef<HTMLAudioElement>(null);
  const [time, setTime] = useState(0);
  const [loadedDuration, setLoadedDuration] = useState(Number.NaN);
  const [paused, setPaused] = useState(true);
  const [rate, setRate] = useState(1);
  // Nothing is highlighted in the transcript until the user plays or seeks.
  const [started, setStarted] = useState(false);
  const duration = Number.isFinite(loadedDuration) ? loadedDuration : (fallbackDuration ?? Number.NaN);
  const durationRef = useRef(duration);
  useEffect(() => {
    durationRef.current = duration;
  });

  const seek = useCallback((seconds: number, play = false) => {
    const player = audio.current;
    if (!player) return;
    const target = clampTime(seconds, durationRef.current);
    player.currentTime = target;
    setTime(target);
    setStarted(true);
    if (play) void player.play();
  }, []);

  const skip = useCallback((delta: number) => {
    const player = audio.current;
    if (player) seek(player.currentTime + delta);
  }, [seek]);

  const toggle = useCallback(() => {
    const player = audio.current;
    if (!player) return;
    if (player.paused) void player.play();
    else player.pause();
  }, []);

  const changeRate = useCallback(() => {
    const player = audio.current;
    if (player) player.playbackRate = nextRate(player.playbackRate);
  }, []);

  const bind = {
    ref: audio,
    onTimeUpdate: (e: SyntheticEvent<HTMLAudioElement>) => setTime(e.currentTarget.currentTime),
    onSeeked: (e: SyntheticEvent<HTMLAudioElement>) => setTime(e.currentTarget.currentTime),
    onDurationChange: (e: SyntheticEvent<HTMLAudioElement>) => setLoadedDuration(e.currentTarget.duration),
    onPlay: () => {
      setPaused(false);
      setStarted(true);
    },
    onPause: () => setPaused(true),
    onRateChange: (e: SyntheticEvent<HTMLAudioElement>) => setRate(e.currentTarget.playbackRate),
  };

  return { bind, time, duration, paused, rate, started, seek, skip, toggle, changeRate };
}

export type AudioPlayerState = ReturnType<typeof useAudioPlayer>;

const roundButton =
  'inline-flex items-center justify-center rounded-full text-slate-600 transition hover:bg-slate-100 hover:text-slate-900';

export default function AudioPlayer({ src, player }: { src: string; player: AudioPlayerState }) {
  const { bind, time, duration, paused, rate, seek, skip, toggle, changeRate } = player;
  const known = Number.isFinite(duration) && duration > 0;
  return (
    <div className="flex items-center gap-2 sm:gap-3">
      <audio {...bind} preload="metadata" src={src} className="hidden" />
      <button
        type="button"
        onClick={() => skip(-SKIP_SECONDS)}
        className={`${roundButton} h-9 w-9`}
        title={`Lùi ${SKIP_SECONDS} giây (←)`}
        aria-label={`Lùi ${SKIP_SECONDS} giây`}
      >
        <SkipIcon seconds={SKIP_SECONDS} className="h-6 w-6" />
      </button>
      <button
        type="button"
        onClick={toggle}
        className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-600 text-white shadow-sm transition hover:bg-brand-700"
        title={paused ? 'Phát (Space)' : 'Dừng (Space)'}
        aria-label={paused ? 'Phát' : 'Dừng'}
      >
        {paused ? <PlayIcon className="ml-0.5 h-5 w-5" /> : <PauseIcon className="h-5 w-5" />}
      </button>
      <button
        type="button"
        onClick={() => skip(SKIP_SECONDS)}
        className={`${roundButton} h-9 w-9`}
        title={`Tới ${SKIP_SECONDS} giây (→)`}
        aria-label={`Tới ${SKIP_SECONDS} giây`}
      >
        <SkipIcon seconds={SKIP_SECONDS} forward className="h-6 w-6" />
      </button>

      <span className="w-14 text-right text-sm text-slate-600 tabular-nums">{formatClock(time)}</span>
      <input
        type="range"
        min={0}
        max={known ? duration : 0}
        step={0.1}
        value={Math.min(time, known ? duration : 0)}
        disabled={!known}
        onChange={(e) => seek(Number(e.target.value))}
        className="h-1.5 min-w-0 flex-1 cursor-pointer accent-brand-600"
        aria-label="Vị trí phát"
      />
      <span className="w-14 text-sm text-slate-400 tabular-nums">{known ? formatClock(duration) : '–:––'}</span>

      <button
        type="button"
        onClick={changeRate}
        className="w-14 rounded-full border border-slate-200 py-1 text-sm font-medium text-slate-700 tabular-nums hover:bg-slate-50"
        title="Tốc độ phát"
      >
        {rate}×
      </button>
    </div>
  );
}
