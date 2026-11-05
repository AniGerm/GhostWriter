/** Entfernt eckige Klammern um Stichwörter in h1–h3 (wie Backend report_html). */

const HEADING_RE = /(<(h[1-3])\b[^>]*>)([\s\S]*?)(<\/\2>)/gi;
const BRACKET_WRAP_RE = /\[([^\[\]]+)\]/g;

export function stripHeadingBrackets(html: string): string {
  return html.replace(HEADING_RE, (_full, open, _level, body, close) => {
    const cleaned = String(body)
      .replace(BRACKET_WRAP_RE, "$1")
      .replace(/[ \t]{2,}/g, " ");
    return `${open}${cleaned}${close}`;
  });
}
