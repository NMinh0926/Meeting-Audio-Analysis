export const SKIP_SECONDS = 5;
export const PLAYBACK_RATES = [0.75, 1, 1.25, 1.5, 2] as const;

/** Keep a seek target inside the recording; an unknown duration only bounds it below. */
export function clampTime(seconds: number, duration: number): number {
  const upper = Number.isFinite(duration) && duration > 0 ? duration : Number.POSITIVE_INFINITY;
  return Math.min(Math.max(0, seconds), upper);
}

/** The next playback rate in the list, wrapping round; an unlisted rate goes back to normal speed. */
export function nextRate(current: number): number {
  const index = PLAYBACK_RATES.indexOf(current as (typeof PLAYBACK_RATES)[number]);
  return index < 0 ? 1 : PLAYBACK_RATES[(index + 1) % PLAYBACK_RATES.length]!;
}

export type Shortcut = 'back' | 'forward' | 'previous' | 'next' | 'toggle';

const SHORTCUTS: Record<string, Shortcut> = {
  ArrowLeft: 'back',
  ArrowRight: 'forward',
  ArrowUp: 'previous',
  ArrowDown: 'next',
  ' ': 'toggle',
};

// Inputs whose arrow keys and space belong to the player rather than to typing.
const NON_TEXT_INPUTS = new Set(['range', 'checkbox', 'radio', 'button']);

/** The parts of an element that tell whether it takes typed text. */
interface TargetLike {
  tagName?: string;
  type?: string;
  isContentEditable?: boolean;
}

export interface KeyLike {
  key: string;
  ctrlKey: boolean;
  altKey: boolean;
  metaKey: boolean;
  target: EventTarget | TargetLike | null;
}

function isTextEntry(target: KeyLike['target']): boolean {
  const element = target as TargetLike | null;
  if (!element?.tagName) return false;
  if (element.isContentEditable || element.tagName === 'TEXTAREA' || element.tagName === 'SELECT') return true;
  return element.tagName === 'INPUT' && !NON_TEXT_INPUTS.has(element.type ?? 'text');
}

/** The player action for a key press, or null when the key is not a shortcut or the user is typing. */
export function shortcutFor(event: KeyLike): Shortcut | null {
  if (event.ctrlKey || event.altKey || event.metaKey || isTextEntry(event.target)) return null;
  return SHORTCUTS[event.key] ?? null;
}
