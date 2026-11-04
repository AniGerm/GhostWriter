/** Grußformel und Arztzeilen ↔ signature_html für Einstellungen / Pipeline. */

export function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function parseSignatureHtml(html: string): { greeting: string; doctor: string } {
  const text = html
    .replace(/<\/(p|div|br)\s*>/gi, "\n")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"');
  const lines = text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);
  return {
    greeting: lines[0] || "",
    doctor: lines.slice(1).join("\n"),
  };
}

export function composeSignatureHtml(greeting: string, doctor: string): string {
  const parts: string[] = [];
  const g = greeting.trim();
  if (g) parts.push(`<p>${escapeHtml(g)}</p>`);
  for (const line of doctor.split(/\n+/)) {
    const t = line.trim();
    if (t) parts.push(`<p>${escapeHtml(t)}</p>`);
  }
  return parts.join("\n");
}
