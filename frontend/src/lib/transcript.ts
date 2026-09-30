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
