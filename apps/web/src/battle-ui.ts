export function battlePower(score: number | undefined, revealed: boolean): number {
  if (!revealed || score === undefined) return 100;
  return Math.max(0, Math.min(100, score));
}
