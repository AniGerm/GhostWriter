import { useEffect, useState } from "react";
import { api } from "../api";

type Props = {
  projectId: string;
  documentId: string;
  title?: string;
  onClose: () => void;
};

export function DocumentViewer({ projectId, documentId, title, onClose }: Props) {
  const [pageCount, setPageCount] = useState(0);
  const [displayName, setDisplayName] = useState(title || "Dokument");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void api
      .documentPreview(projectId, documentId)
      .then((meta) => {
        if (cancelled) return;
        setPageCount(meta.page_count);
        setDisplayName(meta.display_name || title || "Dokument");
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "Vorschau fehlgeschlagen");
        setPageCount(0);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
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
    <div
      className="doc-viewer-overlay"
      role="presentation"
      onClick={onClose}
    >
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
          {loading && <p className="hint">Seiten werden geladen …</p>}
          {error && <p className="error">{error}</p>}
          {!loading && !error && pageCount === 0 && (
            <p className="hint">Keine Seiten gefunden.</p>
          )}
          {!loading &&
            !error &&
            Array.from({ length: pageCount }, (_, index) => {
              const page = index + 1;
              return (
                <figure key={page} className="doc-viewer-page">
                  <figcaption>
                    Seite {page} / {pageCount}
                  </figcaption>
                  <img
                    src={api.documentPageUrl(projectId, documentId, page)}
                    alt={`Seite ${page}`}
                    loading={page <= 2 ? "eager" : "lazy"}
                  />
                </figure>
              );
            })}
        </div>
      </div>
    </div>
  );
}
