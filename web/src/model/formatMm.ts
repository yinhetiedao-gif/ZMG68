/** Display precision only: never use this value when committing a document. */
export function formatMm(value: number): string {
  return Number.isFinite(value) ? Number(value.toFixed(3)).toString() : '—'
}
