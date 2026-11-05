/** Entfernt eckige Klammern um Stichwörter in h1–h3 und stellt Umlaute wieder her. */

const HEADING_RE = /(<(h[1-3])\b[^>]*>)([\s\S]*?)(<\/\2>)/gi;
const BRACKET_WRAP_RE = /\[([^\[\]]+)\]/g;
const TAG_OR_TEXT_RE = /(<[^>]+>)|([^<]+)/g;
const UMLAUT_DENY = new Set(["Statuen", "statuen", "Individuen", "individuen"]);

export function stripHeadingBrackets(html: string): string {
  return html.replace(HEADING_RE, (_full, open, _level, body, close) => {
    const cleaned = String(body)
      .replace(BRACKET_WRAP_RE, "$1")
      .replace(/[ \t]{2,}/g, " ");
    return `${open}${cleaned}${close}`;
  });
}

function restoreInText(text: string): string {
  return text.replace(/[A-Za-zÄÖÜäöüß]+/g, (word) => {
    if (UMLAUT_DENY.has(word)) return word;
    return word
      .replace(/(?<![aeiouäöüAEIOUÄÖÜ])Ue/g, "Ü")
      .replace(/(?<![aeiouäöüAEIOUÄÖÜ])Oe/g, "Ö")
      .replace(/(?<![aeiouäöüAEIOUÄÖÜ])Ae/g, "Ä")
      .replace(/(?<![aeiouäöüAEIOUÄÖÜ])ue/g, "ü")
      .replace(/(?<![aeiouäöüAEIOUÄÖÜ])oe/g, "ö")
      .replace(/(?<![aeiouäöüAEIOUÄÖÜ])ae/g, "ä");
  });
}

export function restoreAsciiUmlauts(html: string): string {
  return html.replace(TAG_OR_TEXT_RE, (_full, tag: string | undefined, text: string | undefined) => {
    if (tag) return tag;
    return restoreInText(text || "");
  });
}

export function normalizeReportHtml(html: string): string {
  return restoreAsciiUmlauts(stripHeadingBrackets(html));
}
