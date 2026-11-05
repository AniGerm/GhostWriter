import { useEffect, useState } from "react";
import { api } from "../api";

type Props = {
  projectId: string;
  documentId: string;
  title?: string;
  onClose: () => void;
};

export function DocumentViewer({ projectId, documentId, title, onClose }: Props) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [pageCount, setPageCount] = useState(0);
  const [displayName, setDisplayName] = useState(title || "Dokument");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    let objectUrl = "";
    setLoading(true);
    setError(null);
    setPdfUrl(null);
    setPageCount(0);

    const fileUrl = api.documentUrl(projectId, documentId);
    void (async () => {
      try {
        const response = await fetch(fileUrl);
        if (!response.ok) throw new Error("Dokument nicht lesbar");
        const type = (response.headers.get("content-type") || "").toLowerCase();
        const blob = await response.blob();
        const looksPdf =
          type.includes("pdf") || (title || "").toLowerCase().endsWith(".pdf");
        if (cancelled) return;
        if (looksPdf) {
          objectUrl = URL.createObjectURL(new Blob([blob], { type: "application/pdf" }));
          setPdfUrl(objectUrl);
          setDisplayName(title || "Dokument");
          return;
        }
        const meta = await api.documentPreview(projectId, documentId);
        if (cancelled) return;
        setPageCount(meta.page_count);
        setDisplayName(meta.display_name || title || "Dokument");
      } catch (e: unknown) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "Vorschau fehlgeschlagen");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
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
          {loading && <p className="hint">Dokument wird geladen …</p>}
          {error && <p className="error">{error}</p>}
          {pdfUrl && (
            <iframe className="doc-viewer-frame" title={displayName} src={pdfUrl} />
          )}
          {!pdfUrl &&
            !loading &&
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
                  />
                </figure>
              );
            })}
        </div>
      </div>
    </div>
  );
}
