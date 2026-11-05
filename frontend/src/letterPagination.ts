/** Teilt Brief-HTML in A4-Seiten (DOM-Messung, Blockelemente). */

/** Brief-Ränder in mm – müssen zu styles.css (.editor-canvas / .a4-page-body) passen. */
export const A4_MARGIN_TOP_MM = 25;
export const A4_MARGIN_BOTTOM_MM = 25;
export const A4_MARGIN_X_MM = 23;
export const A4_PAGE_HEIGHT_MM = 297;
export const A4_PAGE_WIDTH_MM = 210;

export function a4ContentHeightPx(): number {
  const usable =
    A4_PAGE_HEIGHT_MM - A4_MARGIN_TOP_MM - A4_MARGIN_BOTTOM_MM;
  // Kleiner Puffer, damit Blöcke nicht in die Fuß-Sperrzone rutschen
  return Math.max(1, Math.round((usable * 96) / 25.4) - 12);
}

export function a4PageWidthPx(): number {
  return Math.round((A4_PAGE_WIDTH_MM * 96) / 25.4);
}

export function a4ContentWidthPx(): number {
  const usable = A4_PAGE_WIDTH_MM - A4_MARGIN_X_MM * 2;
  return Math.round((usable * 96) / 25.4);
}

export function splitElementChildrenIntoPages(
  container: HTMLElement,
  pageHeightPx: number,
): string[] {
  const children = Array.from(container.children) as HTMLElement[];
  if (children.length === 0) {
    const raw = container.innerHTML.trim();
    return [raw || "<p></p>"];
  }

  const pages: string[] = [];
  let bucket: HTMLElement[] = [];
  let used = 0;

  const flush = () => {
    if (bucket.length === 0) return;
    pages.push(bucket.map((node) => node.outerHTML).join(""));
    bucket = [];
    used = 0;
  };

  for (const child of children) {
    const style = window.getComputedStyle(child);
    const margin =
      Number.parseFloat(style.marginTop || "0") +
      Number.parseFloat(style.marginBottom || "0");
    const height = child.offsetHeight + margin;
    if (bucket.length > 0 && used + height > pageHeightPx) {
      flush();
    }
    bucket.push(child);
    used += height;
    if (bucket.length === 1 && height > pageHeightPx) {
      // Überlanger Block: eigene Seite, Inhalt bleibt vollständig (kein Abschneiden)
      flush();
    }
  }
  flush();
  return pages.length > 0 ? pages : ["<p></p>"];
}

export function measureHtmlPages(html: string, pageHeightPx = a4ContentHeightPx()): string[] {
  if (typeof document === "undefined") {
    return [html.trim() || "<p></p>"];
  }
  const host = document.createElement("div");
  host.className = "a4-measure-host preview-letter";
  host.style.cssText = [
    "position:absolute",
    "left:-10000px",
    "top:0",
    `width:${a4ContentWidthPx()}px`,
    "visibility:hidden",
    "pointer-events:none",
  ].join(";");
  host.innerHTML = html.trim() || "<p></p>";
  document.body.appendChild(host);
  try {
    return splitElementChildrenIntoPages(host, pageHeightPx);
  } finally {
    host.remove();
  }
}
