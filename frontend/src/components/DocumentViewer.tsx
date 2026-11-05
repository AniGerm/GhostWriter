import { useEffect, useState } from "react";
import { api } from "../api";

type Props = {
  projectId: string;
  documentId: string;
  title?: string;
  onClose: () => void;
};

export function DocumentViewer({ projectId, documentId, title, onClose }: Props) {
  const [pageCount, setPageCount] = useState(1);
  const [displayName, setDisplayName] = useState(title || "Dokument");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setPageCount(1);
    setDisplayName(title || "Dokument");
    setError(null);
    void api
      .documentPreview(projectId, documentId)
      .then((meta) => {
        if (cancelled) return;
        setPageCount(Math.max(1, meta.page_count));
        setDisplayName(meta.display_name || title || "Dokument");
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "Vorschau fehlgeschlagen");
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, documentId, title]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="doc-viewer-overlay" role="presentation" onClick={onClose}>
      <div
        className="doc-viewer-dialog"
        role="dialog"
        aria-modal="true"
        aria-label={displayName}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="doc-viewer-header">
          <h2>{displayName}</h2>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Schließen
          </button>
        </header>
        <div className="doc-viewer-body">
          {error && <p className="error">{error}</p>}
          {Array.from({ length: pageCount }, (_, index) => {
            const page = index + 1;
            return (
              <figure key={page} className="doc-viewer-page">
                <figcaption>
                  Seite {page}
                  {pageCount > 1 ? ` / ${pageCount}` : ""}
                </figcaption>
                <img
                  src={api.documentPageUrl(projectId, documentId, page)}
                  alt={`Seite ${page}`}
                  loading={page === 1 ? "eager" : "lazy"}
                  decoding="async"
                />
              </figure>
            );
          })}
        </div>
      </div>
    </div>
  );
}
