/** Teilt Brief-HTML in A4-Seiten (DOM-Messung, Blockelemente). */

export function a4ContentHeightPx(): number {
  // 297mm Blatt minus Kopf-/Fußrand (~50mm), bei 96 CSS-dpi
  return Math.round(((297 - 50) * 96) / 25.4);
}

export function a4PageWidthPx(): number {
  return Math.round((210 * 96) / 25.4);
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
    `width:${a4PageWidthPx() - Math.round((36 * 96) / 25.4)}px`,
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
