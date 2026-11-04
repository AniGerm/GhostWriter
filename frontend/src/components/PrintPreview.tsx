import { useMemo } from "react";
import { api, type Project } from "../api";

export type PreviewPage = {
  id: string;
  group: "anschreiben" | "befund";
  label: string;
  documentId?: string;
  pageNumber: number;
};

type Props = {
  project: Project;
  draftHtml: string;
  selected: Record<string, boolean>;
  onChangeSelected: (next: Record<string, boolean>) => void;
};

export function estimateLetterPages(html: string): number {
  const text = html
    .replace(/<[^>]+>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!text) return 1;
  return Math.max(1, Math.ceil(text.length / 2200));
}

export function buildPreviewPages(project: Project, draftHtml: string): PreviewPage[] {
  const pages: PreviewPage[] = [];
  const letterCount = estimateLetterPages(draftHtml);
  for (let i = 1; i <= letterCount; i += 1) {
    pages.push({
      id: `letter:${i}`,
      group: "anschreiben",
      label: `Anschreiben · Seite ${i}`,
      pageNumber: i,
    });
  }
  for (const doc of project.documents.filter((d) => d.role === "befund")) {
    const count = Math.max(1, doc.page_count || 1);
    for (let i = 1; i <= count; i += 1) {
      pages.push({
        id: `${doc.id}:${i}`,
        group: "befund",
        label: `${doc.display_name} · Seite ${i}`,
        documentId: doc.id,
        pageNumber: i,
      });
    }
  }
  return pages;
}

export function countSelectedPages(selected: Record<string, boolean>): number {
  return Object.values(selected).filter(Boolean).length;
}

export function selectedBefundDocumentIds(
  pages: PreviewPage[],
  selected: Record<string, boolean>,
): string[] {
  const ids = new Set<string>();
  for (const page of pages) {
    if (page.group === "befund" && page.documentId && selected[page.id]) {
      ids.add(page.documentId);
    }
  }
  return [...ids];
}

export function letterIncluded(selected: Record<string, boolean>): boolean {
  return Object.entries(selected).some(([key, on]) => on && key.startsWith("letter:"));
}

function selectionClass(on: boolean): string {
  return on ? "a4-page is-included" : "a4-page is-excluded";
}

export function PrintPreview({ project, draftHtml, selected, onChangeSelected }: Props) {
  const pages = useMemo(
    () => buildPreviewPages(project, draftHtml),
    [project, draftHtml],
  );
  const letterPages = pages.filter((p) => p.group === "anschreiben");
  const befundPages = pages.filter((p) => p.group === "befund");
  const letterCount = letterPages.length;

  function toggle(id: string) {
    onChangeSelected({ ...selected, [id]: !selected[id] });
  }

  function setGroup(group: "anschreiben" | "befund", value: boolean) {
    const next = { ...selected };
    for (const page of pages) {
      if (page.group === group) next[page.id] = value;
    }
    onChangeSelected(next);
  }

  return (
    <div className="preview-layout">
      <aside className="preview-pages">
        <div className="preview-group">
          <div className="preview-group-head">
            <strong>Anschreiben</strong>
            <span>
              <button type="button" className="linkish" onClick={() => setGroup("anschreiben", true)}>
                alle
              </button>
              {" · "}
              <button type="button" className="linkish" onClick={() => setGroup("anschreiben", false)}>
                keine
              </button>
            </span>
          </div>
          <ul>
            {letterPages.map((page) => {
              const on = Boolean(selected[page.id]);
              return (
                <li key={page.id}>
                  <button
                    type="button"
                    className={on ? "preview-pick is-included" : "preview-pick is-excluded"}
                    onClick={() => toggle(page.id)}
                    aria-pressed={on}
                  >
                    <span className="preview-pick-mark" aria-hidden>
                      {on ? "✓" : "×"}
                    </span>
                    <span>{page.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
        <div className="preview-group">
          <div className="preview-group-head">
            <strong>Facharztanhänge</strong>
            <span>
              <button type="button" className="linkish" onClick={() => setGroup("befund", true)}>
                alle
              </button>
              {" · "}
              <button type="button" className="linkish" onClick={() => setGroup("befund", false)}>
                keine
              </button>
            </span>
          </div>
          {befundPages.length === 0 ? (
            <p className="hint">Keine Befunde im Projekt.</p>
          ) : (
            <ul>
              {befundPages.map((page) => {
                const on = Boolean(selected[page.id]);
                return (
                  <li key={page.id}>
                    <button
                      type="button"
                      className={on ? "preview-pick is-included" : "preview-pick is-excluded"}
                      onClick={() => toggle(page.id)}
                      aria-pressed={on}
                    >
                      <span className="preview-pick-mark" aria-hidden>
                        {on ? "✓" : "×"}
                      </span>
                      <span>{page.label}</span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        <p className="hint">
          Gewählte Seiten: {countSelectedPages(selected)} (für Kostenberechnung)
        </p>
      </aside>

      <section className="preview-canvas" aria-label="Druckvorschau">
        {letterPages.map((page) => {
          const on = Boolean(selected[page.id]);
          return (
            <button
              key={page.id}
              type="button"
              className={selectionClass(on)}
              onClick={() => toggle(page.id)}
              aria-pressed={on}
              aria-label={`${page.label}${on ? ", in Druckauswahl" : ", ausgeschlossen"}`}
            >
              <span className="a4-badge" aria-hidden>
                {on ? "✓" : "×"}
              </span>
              <div className="a4-page-label">Anschreiben · Seite {page.pageNumber}/{letterCount}</div>
              <div
                className="a4-page-body preview-letter"
                style={
                  letterCount > 1
                    ? {
                        maxHeight: "257mm",
                        overflow: "hidden",
                      }
                    : undefined
                }
                dangerouslySetInnerHTML={{
                  __html:
                    page.pageNumber === 1
                      ? draftHtml.trim() || "<p><em>Kein Anschreiben vorhanden.</em></p>"
                      : `<p class="hint">Fortsetzung Seite ${page.pageNumber} (geschätzt für Kosten/Druck).</p>`,
                }}
              />
            </button>
          );
        })}

        {befundPages.map((page) => {
          const on = Boolean(selected[page.id]);
          const src =
            page.documentId != null
              ? api.documentPageUrl(project.id, page.documentId, page.pageNumber)
              : "";
          return (
            <button
              key={page.id}
              type="button"
              className={selectionClass(on)}
              onClick={() => toggle(page.id)}
              aria-pressed={on}
              aria-label={`${page.label}${on ? ", in Druckauswahl" : ", ausgeschlossen"}`}
            >
              <span className="a4-badge" aria-hidden>
                {on ? "✓" : "×"}
              </span>
              <div className="a4-page-label">{page.label}</div>
              <div className="a4-page-body a4-page-raster">
                {src ? (
                  <img
                    src={src}
                    alt=""
                    loading="lazy"
                    onError={(event) => {
                      const img = event.currentTarget;
                      img.style.display = "none";
                      const fallback = img.nextElementSibling;
                      if (fallback instanceof HTMLElement) fallback.hidden = false;
                    }}
                  />
                ) : null}
                <p className="hint" hidden>
                  Seitenvorschau nicht verfügbar – Datei wird beim Drucken geöffnet.
                </p>
              </div>
            </button>
          );
        })}
      </section>
    </div>
  );
}
