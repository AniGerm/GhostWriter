/** Leichte Fuzzy-Suche für Projektlisten (kein Extra-Paket). */

export function normalizeSearch(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/ä/g, "a")
    .replace(/ö/g, "o")
    .replace(/ü/g, "u")
    .replace(/ß/g, "ss")
    .trim();
}

/** Höher = besser; 0 = kein Treffer. */
export function fuzzyScore(haystack: string, needle: string): number {
  const h = normalizeSearch(haystack);
  const n = normalizeSearch(needle);
  if (!n) return 1;
  if (!h) return 0;
  if (h.includes(n)) return 100 + Math.max(0, 20 - (h.indexOf(n) || 0));

  let hi = 0;
  let score = 0;
  let streak = 0;
  for (let ni = 0; ni < n.length; ni += 1) {
    const ch = n[ni];
    const found = h.indexOf(ch, hi);
    if (found < 0) return 0;
    streak = found === hi ? streak + 1 : 1;
    score += 1 + streak;
    hi = found + 1;
  }
  return score;
}

export type FuzzyProject = {
  id: string;
  patient_label: string;
  reference: string;
  updated_at: string;
};

export function filterProjects<T extends FuzzyProject>(
  projects: T[],
  query: string,
): T[] {
  const q = query.trim();
  if (!q) {
    return [...projects].sort((a, b) =>
      a.updated_at < b.updated_at ? 1 : a.updated_at > b.updated_at ? -1 : 0,
    );
  }
  const scored = projects
    .map((p) => ({
      project: p,
      score:
        fuzzyScore(`${p.patient_label} ${p.reference}`, q) ||
        Math.max(fuzzyScore(p.patient_label, q), fuzzyScore(p.reference, q)),
    }))
    .filter((row) => row.score > 0);
  scored.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return a.project.updated_at < b.project.updated_at
      ? 1
      : a.project.updated_at > b.project.updated_at
        ? -1
        : 0;
  });
  return scored.map((row) => row.project);
}
