/** Remembers the last hh-store revision; observe() is true only when it changed. */
export function createRevisionGate() {
  let last: number | undefined;
  return (revision: number): boolean => {
    const changed = last !== undefined && last !== revision;
    last = revision;
    return changed;
  };
}
