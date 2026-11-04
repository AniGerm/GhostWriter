import { useMemo } from "react";
import type { Project } from "../api";

export type PreviewPage = {
  id: string;
  group: "anschreiben" | "befund";
  label: string;
  documentId?: string;
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

export function PrintPreview({ project, draftHtml, selected, onChangeSelected }: Props) {
  const pages = useMemo(
    () => buildPreviewPages(project, draftHtml),
    [project, draftHtml],
  );
  const letterPages = pages.filter((p) => p.group === "anschreiben");
  const befundPages = pages.filter((p) => p.group === "befund");

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
            {letterPages.map((page) => (
              <li key={page.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={Boolean(selected[page.id])}
                    onChange={() => toggle(page.id)}
                  />
                  {page.label}
                </label>
              </li>
            ))}
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
              {befundPages.map((page) => (
                <li key={page.id}>
                  <label>
                    <input
                      type="checkbox"
                      checked={Boolean(selected[page.id])}
                      onChange={() => toggle(page.id)}
                    />
                    {page.label}
                  </label>
                </li>
              ))}
            </ul>
          )}
        </div>
        <p className="hint">
          Gewählte Seiten: {countSelectedPages(selected)} (für Kostenberechnung)
        </p>
      </aside>
      <section className="preview-canvas" aria-label="Druckvorschau">
        <div className="preview-sheet">
          <div
            className="preview-letter"
            dangerouslySetInnerHTML={{
              __html: draftHtml.trim() || "<p><em>Kein Anschreiben vorhanden.</em></p>",
            }}
          />
        </div>
        {project.documents
          .filter((d) => d.role === "befund")
          .map((doc) => {
            const anySelected = pages.some(
              (p) => p.documentId === doc.id && selected[p.id],
            );
            if (!anySelected) return null;
            return (
              <div className="preview-sheet preview-attachment" key={doc.id}>
                <h3>{doc.display_name}</h3>
                <p>
                  Anhang ({Math.max(1, doc.page_count || 1)} Seite
                  {doc.page_count === 1 ? "" : "n"}) – wird beim Drucken als Datei geöffnet.
                </p>
              </div>
            );
          })}
      </section>
    </div>
  );
}
