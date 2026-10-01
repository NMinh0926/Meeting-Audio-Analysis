import type { Turn } from '../api/types';

/** Position of one utterance in the transcript: turn index and utterance index within the turn. */
export interface UtteranceRef {
  turn: number;
  utterance: number;
  start: number;
  end: number;
}

/** All utterances in time order, keeping a reference back to their turn. */
export function flattenUtterances(turns: Turn[]): UtteranceRef[] {
  const refs: UtteranceRef[] = [];
  turns.forEach((turn, t) =>
    turn.utterances.forEach((u, i) => refs.push({ turn: t, utterance: i, start: u.start, end: u.end })),
  );
  return refs.sort((a, b) => a.start - b.start);
}

/**
 * Index of the utterance playing at `time`: the last one that has started. Stays on it through the
 * pause before the next one, so the highlight does not flicker between sentences. -1 before the first.
 */
export function findActiveIndex(refs: UtteranceRef[], time: number): number {
  let low = 0;
  let high = refs.length - 1;
  let found = -1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    if (refs[mid]!.start <= time) {
      found = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  return found;
}

/** Past this far into a sentence, "previous" goes back to its start first, like a music player. */
export const RESTART_SECONDS = 1.5;

/** Start of the sentence before or after the one playing at `time`; null when there is none. */
export function sentenceStart(refs: UtteranceRef[], time: number, direction: 'previous' | 'next'): number | null {
  const active = findActiveIndex(refs, time);
  if (direction === 'next') return refs[active + 1]?.start ?? null;
  if (active < 0) return null;
  if (time - refs[active]!.start > RESTART_SECONDS || active === 0) return refs[active]!.start;
  return refs[active - 1]!.start;
}

/** Seconds spoken by each speaker id, summed over their turns. */
export function talkTime(turns: Turn[]): Map<number, number> {
  const seconds = new Map<number, number>();
  for (const turn of turns) {
    seconds.set(turn.speaker_id, (seconds.get(turn.speaker_id) ?? 0) + Math.max(0, turn.end - turn.start));
  }
  return seconds;
}
