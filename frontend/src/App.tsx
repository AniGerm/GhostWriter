import { useEffect, useMemo, useState } from "react";
import { api, type AppSettings, type Job, type Project, type ProjectSummary } from "./api";
import { AppSidebar } from "./components/AppSidebar";
import { DocumentListItem } from "./components/DocumentListItem";
import { DocumentViewer } from "./components/DocumentViewer";
import { DropZone } from "./components/DropZone";
import { IconGear } from "./components/editorIcons";
import {
  PrintPreview,
  buildPreviewPages,
  countSelectedPages,
  letterIncluded,
  selectedBefundDocumentIds,
} from "./components/PrintPreview";
import { RichEditor } from "./components/RichEditor";

const STEPS = [
  "Start",
  "Anfrage",
  "Befunde",
  "Analyse",
  "Schreiben",
  "Vorschau",
  "Kosten",
] as const;

const POSTAGE_LABELS: Record<string, string> = {
  standard: "Standardbrief bis 20 g",
  kompakt: "Kompaktbrief bis 50 g",
  gross: "Großbrief bis 500 g",
  maxi: "Maxibrief bis 1000 g",
};

type Step = (typeof STEPS)[number];

export default function App() {
  const [step, setStep] = useState<Step>("Start");
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [patient, setPatient] = useState("");
  const [reference, setReference] = useState("");
  const [notes, setNotes] = useState("");
  const [draft, setDraft] = useState("");
  const [draftEpoch, setDraftEpoch] = useState(0);
  const [job, setJob] = useState<Job | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pages, setPages] = useState(1);
  const [postage, setPostage] = useState<string>("gross");
  const [customPostage, setCustomPostage] = useState<string>("");
  const [cost, setCost] = useState<Project["cost"]>(null);
  const [version, setVersion] = useState("");
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [postageDraft, setPostageDraft] = useState<Record<string, number>>({});
  const [flatFeeDraft, setFlatFeeDraft] = useState(25);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsSaved, setSettingsSaved] = useState(false);
  const [pageSelection, setPageSelection] = useState<Record<string, boolean>>({});
  const [regenOpen, setRegenOpen] = useState(false);
  const [revisionNotes, setRevisionNotes] = useState("");
  const [undoToast, setUndoToast] = useState<{
    projectId: string;
    label: string;
  } | null>(null);
  const [inboxToast, setInboxToast] = useState<string | null>(null);
  const [inboxBanner, setInboxBanner] = useState<{
    kind: "warn" | "ok";
    text: string;
  } | null>(null);
  const [viewerDoc, setViewerDoc] = useState<{
    id: string;
    name: string;
  } | null>(null);

  const stepIndex = STEPS.indexOf(step);

  useEffect(() => {
    if (!undoToast) return;
    const timer = window.setTimeout(() => setUndoToast(null), 8000);
    return () => window.clearTimeout(timer);
  }, [undoToast]);

  useEffect(() => {
    if (!inboxToast) return;
    const timer = window.setTimeout(() => setInboxToast(null), 8000);
    return () => window.clearTimeout(timer);
  }, [inboxToast]);

  // Inbox: Spool-PDFs vom virtuellen Drucker ins aktuelle Projekt holen
  useEffect(() => {
    if ((step !== "Befunde" && step !== "Anfrage") || !project) return;
    let cancelled = false;
    let importing = false;
    const role = step === "Anfrage" ? "anfrage" : "befund";
    const probe = () => {
      void api
        .inboxStatus()
        .then(async (status) => {
          if (cancelled) return;
          if (!status.cups_running) {
            setInboxBanner({
              kind: "warn",
              text: "CUPS-Druckdienst läuft nicht. Bitte starten: sudo systemctl start cups",
            });
          } else if (!status.readable) {
            setInboxBanner({
              kind: "warn",
              text:
                "Drucker-Spool nicht lesbar (Rechte). Nach dem Update: sudo /usr/lib/ghostwriter/install-printer.sh",
            });
          } else if (status.new_pdf_count > 0) {
            setInboxBanner({
              kind: "ok",
              text: `${status.new_pdf_count} gedruckte Datei(en) – werden übernommen …`,
            });
            if (!importing) {
              importing = true;
              try {
                const result = await api.importInbox(project.id, role);
                if (cancelled) return;
                setProject(result.project);
                if (result.imported.length > 0) {
                  const names = result.imported.map((d) => d.display_name).join(", ");
                  setInboxToast(
                    result.imported.length === 1
                      ? `Gedrucktes Dokument übernommen: ${names}`
                      : `${result.imported.length} gedruckte Dokumente übernommen`,
                  );
                }
                setInboxBanner(null);
              } catch (e) {
                if (!cancelled) {
                  setInboxBanner({
                    kind: "warn",
                    text: e instanceof Error ? e.message : "Inbox-Import fehlgeschlagen",
                  });
                }
              } finally {
                importing = false;
              }
            }
          } else {
            setInboxBanner(null);
          }
        })
        .catch(() => undefined);
    };
    probe();
    const timer = window.setInterval(probe, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [step, project?.id]);

  useEffect(() => {
    api
      .health()
      .then((h) => {
        setVersion(h.version);
        const ollama = (h as { ollama?: { model_available?: boolean; model?: string; error?: string } })
          .ollama;
        if (ollama && ollama.model_available === false) {
          setError(
            ollama.error ||
              `Ollama-Modell „${ollama.model ?? "?"}“ fehlt. Bitte Modell installieren oder in den Einstellungen wechseln.`,
          );
        }
      })
      .catch(() => undefined);
    api.listProjects().then(setProjects).catch(() => undefined);
    api
      .getSettings()
      .then((s) => {
        setSettings(s);
        setPostageDraft({ ...s.postage });
        setFlatFeeDraft(s.flat_fee);
        const preferred = s.default_postage_key || "gross";
        setPostage(preferred in s.postage ? preferred : "gross");
      })
      .catch(() => undefined);
  }, []);

  function initPreviewSelection(proj: Project, html: string) {
    const list = buildPreviewPages(proj, html);
    const next: Record<string, boolean> = {};
    for (const page of list) next[page.id] = true;
    setPageSelection(next);
    setPages(countSelectedPages(next));
  }

  function applyServerDraft(html: string) {
    setDraft(html || "");
    setDraftEpoch((n) => n + 1);
  }

  async function loadProjectDraft(projectId: string) {
    const fresh = await api.getProject(projectId);
    setProject(fresh);
    applyServerDraft(fresh.draft_html);
    setNotes(fresh.notes);
    return fresh;
  }

  useEffect(() => {
    if (!job || job.phase === "done" || job.phase === "error") return;
    const projectId = project?.id;
    if (!projectId) return;
    const timer = window.setInterval(() => {
      api
        .getJob(job.id)
        .then(async (next) => {
          setJob(next);
          if (next.phase === "done") {
            await loadProjectDraft(projectId);
            setStep("Schreiben");
          }
        })
        .catch(() => undefined);
    }, 800);
    return () => window.clearInterval(timer);
  }, [job, project?.id]);

  const anfrage = useMemo(
    () => project?.documents.find((d) => d.role === "anfrage"),
    [project],
  );
  const befund = useMemo(
    () => project?.documents.filter((d) => d.role === "befund") ?? [],
    [project],
  );

  async function startProject() {
    setBusy(true);
    setError(null);
    try {
      const created = await api.createProject(patient.trim() || "Neuer Fall", reference.trim());
      setProject(created);
      setNotes(created.notes);
      setDraft(created.draft_html);
      setStep("Anfrage");
      setProjects(await api.listProjects());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Fehler");
    } finally {
      setBusy(false);
    }
  }

  async function openProject(id: string) {
    setBusy(true);
    setError(null);
    try {
      const loaded = await loadProjectDraft(id);
      setPatient(loaded.patient_label);
      setReference(loaded.reference);
      setCost(loaded.cost);
      const hasAnfrage = loaded.documents.some((d) => d.role === "anfrage");
      const hasBefund = loaded.documents.some((d) => d.role === "befund");
      if (loaded.draft_html.trim()) setStep("Schreiben");
      else if (hasBefund) setStep("Analyse");
      else if (hasAnfrage) setStep("Befunde");
      else setStep("Anfrage");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Fehler");
    } finally {
      setBusy(false);
    }
  }

  async function upload(role: "anfrage" | "befund", files: File[]) {
    if (!project) return;
    setBusy(true);
    setError(null);
    try {
      let current = project;
      for (const file of files) {
        current = await api.uploadDocument(current.id, role, file);
      }
      setProject(current);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function toggleDocumentIncluded(documentId: string, included: boolean) {
    if (!project) return;
    setBusy(true);
    setError(null);
    try {
      setProject(await api.setDocumentIncluded(project.id, documentId, included));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Auswahl fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function removeDocument(documentId: string) {
    if (!project) return;
    setBusy(true);
    setError(null);
    try {
      setProject(await api.deleteDocument(project.id, documentId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Löschen fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  function openDocument(documentId: string) {
    if (!project) return;
    const doc = project.documents.find((d) => d.id === documentId);
    setViewerDoc({ id: documentId, name: doc?.display_name || "Dokument" });
  }

  async function runAnalyze() {
    if (!project) return;
    setBusy(true);
    setError(null);
    try {
      await api.setNotes(project.id, notes);
      const { job_id } = await api.analyze(project.id);
      setJob({ id: job_id, phase: "extracting", percent: 1, message: "Start …" });
      setStep("Analyse");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analyse fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function saveDraft() {
    if (!project) return;
    setBusy(true);
    try {
      const saved = await api.setDraft(project.id, draft);
      setProject(saved);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Speichern fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function regenerateDraft() {
    if (!project) return;
    setBusy(true);
    setError(null);
    try {
      await api.setDraft(project.id, draft);
      const { job_id } = await api.regenerate(project.id, revisionNotes.trim());
      setJob({ id: job_id, phase: "composing", percent: 5, message: "Schreiben neu erzeugen …" });
      setRegenOpen(false);
      setStep("Analyse");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Neu erzeugen fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function calcCost() {
    if (!project) return;
    setBusy(true);
    setError(null);
    try {
      const custom = customPostage.trim() === "" ? null : Number(customPostage);
      if (custom !== null && (Number.isNaN(custom) || custom < 0)) {
        throw new Error("Manueller Versandpreis muss eine Zahl ≥ 0 sein");
      }
      const result = await api.costs(project.id, pages, postage || null, custom);
      setCost(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Kostenfehler");
    } finally {
      setBusy(false);
    }
  }

  async function saveCostDefaults() {
    setBusy(true);
    setError(null);
    setSettingsSaved(false);
    try {
      const saved = await api.putSettings({
        postage: postageDraft,
        flat_fee: flatFeeDraft,
        default_postage_key: postage || "gross",
      });
      setSettings(saved);
      setPostageDraft({ ...saved.postage });
      setFlatFeeDraft(saved.flat_fee);
      setSettingsSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Einstellungen speichern fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  function finishToStart() {
    setProject(null);
    setDraft("");
    setDraftEpoch(0);
    setJob(null);
    setCost(null);
    setPageSelection({});
    setNotes("");
    setRegenOpen(false);
    setStep("Start");
    void api.listProjects().then(setProjects).catch(() => undefined);
  }

  async function handleDeleteProject(id: string) {
    const summary = projects.find((p) => p.id === id);
    await api.deleteProject(id);
    setProjects(await api.listProjects());
    setUndoToast({
      projectId: id,
      label: summary?.patient_label || "Projekt",
    });
    if (project?.id === id) {
      finishToStart();
    }
  }

  async function handleUndoDelete() {
    if (!undoToast) return;
    const id = undoToast.projectId;
    setUndoToast(null);
    await api.restoreProject(id);
    setProjects(await api.listProjects());
  }

  async function printPacket() {
    if (!project) return;
    if (letterIncluded(pageSelection) && draft.trim()) {
      const html = `<!doctype html><html lang="de"><head><meta charset="utf-8" />
<title>Anschreiben</title>
<style>
  body { font-family: "Times New Roman", serif; font-size: 12pt; line-height: 1.5; margin: 25mm 23mm; color: #111; }
  h1,h2,h3 { font-family: system-ui, sans-serif; }
  @media print { body { margin: 25mm 23mm; } }
</style></head><body>${draft}</body></html>`;
      const device = settings?.default_printer || "";
      if (window.ghostwriterDesktop?.printHtml) {
        try {
          await window.ghostwriterDesktop.printHtml(html, device);
        } catch {
          const popup = window.open("", "_blank", "noopener,noreferrer,width=900,height=1100");
          if (popup) {
            popup.document.write(html);
            popup.document.close();
            popup.focus();
            popup.print();
          }
        }
      } else {
        const popup = window.open("", "_blank", "noopener,noreferrer,width=900,height=1100");
        if (popup) {
          popup.document.write(html);
          popup.document.close();
          popup.focus();
          popup.print();
        }
      }
    }
    const pagesList = buildPreviewPages(project, draft);
    for (const docId of selectedBefundDocumentIds(pagesList, pageSelection)) {
      window.open(api.documentUrl(project.id, docId), "_blank", "noopener,noreferrer");
    }
  }

  function printAndFinish() {
    void printPacket().finally(() => finishToStart());
  }

  async function goToPreview() {
    if (!project) return;
    setBusy(true);
    setError(null);
    try {
      await api.setDraft(project.id, draft);
      initPreviewSelection(project, draft);
      setStep("Vorschau");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Vorschau fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  const postageOptions = useMemo(() => {
    const source = Object.keys(postageDraft).length
      ? postageDraft
      : settings?.postage ?? { standard: 0.95, kompakt: 1.25, gross: 2.1, maxi: 3.4 };
    return Object.entries(source);
  }, [postageDraft, settings]);

  return (
    <div className="app-shell">
      <AppSidebar
        version={version}
        steps={STEPS}
        step={step}
        stepIndex={stepIndex}
        onSelectStep={(name) => setStep(name as Step)}
        projects={projects}
        activeProjectId={project?.id ?? null}
        onOpenProject={(id) => void openProject(id)}
        onDeleteProject={handleDeleteProject}
        settings={settings}
        onSettingsSaved={(s) => {
          setSettings(s);
          setPostageDraft({ ...s.postage });
          setFlatFeeDraft(s.flat_fee);
        }}
      />

      <main className="panel">
        {step === "Start" && (
          <>
            <h1 className="hero-title">Neues Projekt</h1>
            <div className="grid-2">
              <div className="field">
                <label htmlFor="patient">Patient / Kennung</label>
                <input
                  id="patient"
                  value={patient}
                  onChange={(e) => setPatient(e.target.value)}
                  placeholder="z. B. Fall 2026-041"
                />
              </div>
              <div className="field">
                <label htmlFor="reference">Aktenzeichen</label>
                <input
                  id="reference"
                  value={reference}
                  onChange={(e) => setReference(e.target.value)}
                  placeholder="optional"
                />
              </div>
            </div>
            <div className="actions">
              <button className="btn btn-primary" disabled={busy} onClick={() => void startProject()}>
                Neues Projekt starten
              </button>
            </div>
          </>
        )}

        {step === "Anfrage" && project && (
          <>
            <h1 className="hero-title">Schreiben des Landratsamts</h1>
            <p className="hero-copy">
              Laden Sie die Anfrage mit den konkreten Fragen hoch. Text-PDFs werden
              direkt gelesen, Scans per OCR.
            </p>
            {inboxBanner && (
              <p className={`inbox-banner is-${inboxBanner.kind}`}>{inboxBanner.text}</p>
            )}
            <DropZone
              title="Anfrage hierher ziehen"
              hint="PDF oder Scan · eine Datei"
              onFiles={(files) => void upload("anfrage", files)}
            />
            {anfrage && (
              <ul className="file-list">
                <DocumentListItem
                  name={anfrage.display_name}
                  meta={anfrage.has_text ? "Text vorhanden" : "bereit zur OCR"}
                  included={anfrage.included}
                  busy={busy}
                  onOpen={() => openDocument(anfrage.id)}
                  onToggleIncluded={(value) => void toggleDocumentIncluded(anfrage.id, value)}
                  onRemove={() => void removeDocument(anfrage.id)}
                />
              </ul>
            )}
            <div className="actions">
              <button className="btn btn-ghost" onClick={() => setStep("Start")}>
                Zurück
              </button>
              <button
                className="btn btn-primary"
                disabled={!anfrage || !anfrage.included || busy}
                onClick={() => setStep("Befunde")}
              >
                Weiter zu Befunden
              </button>
            </div>
          </>
        )}

        {step === "Befunde" && project && (
          <>
            <h1 className="hero-title">Fachärztliche Befunde</h1>
            <p className="hero-copy">
              Aus der Patientenakte drucken Sie auf den GhostWriter-Drucker – oder
              laden Dateien hier manuell nach.
            </p>
            {inboxBanner && (
              <p className={`inbox-banner is-${inboxBanner.kind}`}>{inboxBanner.text}</p>
            )}
            <DropZone
              title="Befunde hinzufügen"
              hint="Mehrere PDFs oder Bilder möglich"
              multiple
              onFiles={(files) => void upload("befund", files)}
            />
            <ul className="file-list">
              {befund.map((d) => (
                <DocumentListItem
                  key={d.id}
                  name={d.display_name}
                  meta={d.page_count ? `${d.page_count} S.` : "neu"}
                  included={d.included}
                  busy={busy}
                  onOpen={() => openDocument(d.id)}
                  onToggleIncluded={(value) => void toggleDocumentIncluded(d.id, value)}
                  onRemove={() => void removeDocument(d.id)}
                />
              ))}
            </ul>
            <div className="field" style={{ marginTop: 20 }}>
              <label htmlFor="notes">Hinweise zum Patienten</label>
              <textarea
                id="notes"
                rows={4}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Begleitumstände, Besonderheiten …"
              />
            </div>
            <div className="actions">
              <button className="btn btn-ghost" onClick={() => setStep("Anfrage")}>
                Zurück
              </button>
              <button
                className="btn btn-primary"
                disabled={busy || !anfrage || !anfrage.included}
                onClick={() => void runAnalyze()}
              >
                Analyse starten
              </button>
            </div>
          </>
        )}

        {step === "Analyse" && (
          <>
            <h1 className="hero-title">Lokale Analyse</h1>
            <p className="hero-copy">
              OCR und Ollama arbeiten nacheinander auf diesem Rechner. Nichts verlässt
              den Praxisrechner.
            </p>
            <div className="progress-wrap">
              <div className="progress-label">
                <span>{job?.message || "Vorbereitung …"}</span>
                <span>{job?.percent ?? 0} %</span>
              </div>
              <div className="progress-track">
                <div
                  className="progress-bar"
                  style={{ width: `${Math.max(job?.percent ?? 0, 4)}%` }}
                />
              </div>
            </div>
            {job?.phase === "error" && (
              <p className="error">Analyse fehlgeschlagen: {job.error}</p>
            )}
            <div className="actions">
              <button className="btn btn-ghost" onClick={() => setStep("Befunde")}>
                Zurück
              </button>
              {job?.phase === "done" && (
                <button
                  className="btn btn-primary"
                  disabled={busy || !project}
                  onClick={() => {
                    if (!project) return;
                    void (async () => {
                      setBusy(true);
                      try {
                        await loadProjectDraft(project.id);
                        setStep("Schreiben");
                      } catch (e) {
                        setError(e instanceof Error ? e.message : "Entwurf laden fehlgeschlagen");
                      } finally {
                        setBusy(false);
                      }
                    })();
                  }}
                >
                  Zum Schreiben
                </button>
              )}
            </div>
          </>
        )}

        {step === "Schreiben" && project && (
          <>
            {!draft.trim() && (
              <p className="error">Noch kein Entwurf geladen. Analyse erneut starten oder Projekt neu öffnen.</p>
            )}
            <RichEditor
              key={`${project.id}-${draftEpoch}`}
              html={draft}
              onChange={setDraft}
              trailing={
                <>
                  {project.questions.length > 0 && (
                    <details className="toolbar-questions">
                      <summary>
                        Fragen
                        <span className="questions-fold-count">{project.questions.length}</span>
                      </summary>
                      <div className="toolbar-questions-panel">
                        <p className="hint">Erkannte Fragen aus der Landratsamts-Anfrage</p>
                        <ul className="file-list">
                          {project.questions.map((q) => (
                            <li key={q.number}>
                              <span>
                                {q.number}. {q.text}
                              </span>
                              {q.keyword ? <span>{q.keyword}</span> : null}
                            </li>
                          ))}
                        </ul>
                      </div>
                    </details>
                  )}
                  <button
                    type="button"
                    className="toolbar-action"
                    onClick={() => setStep("Analyse")}
                  >
                    Zurück
                  </button>
                  <button
                    type="button"
                    className="toolbar-action"
                    disabled={busy}
                    onClick={() => void saveDraft()}
                  >
                    Speichern
                  </button>
                  <button
                    type="button"
                    className={`toolbar-action${regenOpen ? " is-active" : ""}`}
                    disabled={busy}
                    onClick={() => setRegenOpen((open) => !open)}
                  >
                    Neu erzeugen
                  </button>
                  <button
                    type="button"
                    className="toolbar-action toolbar-action-primary"
                    disabled={busy}
                    onClick={() => void goToPreview()}
                  >
                    Vorschau
                  </button>
                </>
              }
            />
            {regenOpen && (
              <div
                className="regen-overlay"
                role="presentation"
                onClick={() => setRegenOpen(false)}
              >
                <div
                  className="regen-dialog"
                  role="dialog"
                  aria-modal="true"
                  aria-labelledby="regen-title"
                  onClick={(e) => e.stopPropagation()}
                >
                  <h2 id="regen-title">Schreiben neu erzeugen</h2>
                  <p className="hint">
                    Optional Anmerkungen für die KI – z.&nbsp;B. fehlende Punkte,
                    kürzerer Stil oder die Grußformel aus den Einstellungen.
                  </p>
                  <label className="sr-only" htmlFor="revision-notes">
                    Anmerkungen für die KI
                  </label>
                  <textarea
                    id="revision-notes"
                    autoFocus
                    value={revisionNotes}
                    onChange={(e) => setRevisionNotes(e.target.value)}
                    placeholder="Anmerkungen (optional) …"
                    onKeyDown={(e) => {
                      if (e.key === "Escape") {
                        e.stopPropagation();
                        setRegenOpen(false);
                      }
                    }}
                  />
                  <div className="actions" style={{ marginTop: 0 }}>
                    <button
                      type="button"
                      className="btn btn-ghost"
                      disabled={busy}
                      onClick={() => setRegenOpen(false)}
                    >
                      Abbrechen
                    </button>
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={busy}
                      onClick={() => void regenerateDraft()}
                    >
                      Neu erzeugen
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {step === "Vorschau" && project && (
          <>
            <h1 className="hero-title">Druckvorschau</h1>
            <p className="hero-copy">
              Übersicht aller Seiten: Anschreiben und Facharztanhänge. Seiten an- oder
              abwählen, dann drucken oder zu den Kosten weitergehen.
            </p>
            <PrintPreview
              project={project}
              draftHtml={draft}
              selected={pageSelection}
              onChangeSelected={(next) => {
                setPageSelection(next);
                setPages(countSelectedPages(next));
              }}
            />
            <div className="actions">
              <button className="btn btn-ghost" onClick={() => setStep("Schreiben")}>
                Zurück
              </button>
              <button className="btn btn-ghost" onClick={() => printAndFinish()}>
                Drucken & beenden
              </button>
              <button
                className="btn btn-primary"
                onClick={() => {
                  setPages(countSelectedPages(pageSelection));
                  setCost(null);
                  setStep("Kosten");
                }}
              >
                Weiter zu Kosten
              </button>
            </div>
          </>
        )}

        {step === "Kosten" && project && (
          <>
            <h1 className="hero-title">Kosten</h1>
            <p className="hero-copy">
              Berechnet aus den in der Vorschau gewählten Seiten (ohne Landratsamts-Anfrage).
              Versand: Deutsche Post – Standard 0,95 € · Kompakt 1,10 € · Großbrief 1,80 €.
            </p>
            <div className="grid-2">
              <div className="field">
                <label htmlFor="pages">Seiten (aus Vorschau, korrigierbar)</label>
                <input
                  id="pages"
                  type="number"
                  min={0}
                  value={pages}
                  onChange={(e) => setPages(Number(e.target.value))}
                />
              </div>
              <div className="field">
                <label htmlFor="postage">Versandart</label>
                <div className="postage-select-row">
                  <select
                    id="postage"
                    value={postage}
                    onChange={(e) => setPostage(e.target.value)}
                  >
                    {postageOptions.map(([key, price]) => (
                      <option key={key} value={key}>
                        {POSTAGE_LABELS[key] ?? key} ({price.toFixed(2)} €)
                      </option>
                    ))}
                  </select>
                  <div className="postage-gear-wrap">
                    <button
                      type="button"
                      className="icon-btn"
                      title="Versandpreise / Voreinstellungen"
                      aria-label="Versandpreise bearbeiten"
                      aria-expanded={settingsOpen}
                      onClick={() => {
                        setSettingsOpen((v) => !v);
                        setSettingsSaved(false);
                      }}
                    >
                      <IconGear />
                    </button>
                    {settingsOpen && (
                      <div className="postage-popover" role="dialog" aria-label="Kosteneinstellungen">
                        <div className="field">
                          <label htmlFor="flat-fee">Pauschale (€)</label>
                          <input
                            id="flat-fee"
                            type="number"
                            min={0}
                            step={0.01}
                            value={flatFeeDraft}
                            onChange={(e) => setFlatFeeDraft(Number(e.target.value))}
                          />
                        </div>
                        <div className="postage-grid">
                          {postageOptions.map(([key]) => (
                            <div className="field" key={key}>
                              <label htmlFor={`postage-${key}`}>{POSTAGE_LABELS[key] ?? key}</label>
                              <input
                                id={`postage-${key}`}
                                type="number"
                                min={0}
                                step={0.01}
                                value={postageDraft[key] ?? 0}
                                onChange={(e) =>
                                  setPostageDraft((prev) => ({
                                    ...prev,
                                    [key]: Number(e.target.value),
                                  }))
                                }
                              />
                            </div>
                          ))}
                        </div>
                        <div className="field" style={{ marginTop: 10 }}>
                          <label htmlFor="custom-postage">Versand manuell (€, optional)</label>
                          <input
                            id="custom-postage"
                            type="number"
                            min={0}
                            step={0.01}
                            value={customPostage}
                            onChange={(e) => setCustomPostage(e.target.value)}
                            placeholder="leer = Preis der Versandart"
                          />
                        </div>
                        <div className="actions" style={{ marginTop: 12 }}>
                          <button
                            className="btn btn-primary"
                            disabled={busy}
                            onClick={() => void saveCostDefaults()}
                          >
                            Als Voreinstellung speichern
                          </button>
                        </div>
                        {settingsSaved && (
                          <p className="hint">Gespeichert – gilt für künftige Berechnungen.</p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="actions">
              <button className="btn btn-ghost" onClick={() => setStep("Vorschau")}>
                Zurück
              </button>
              <button className="btn btn-primary" disabled={busy} onClick={() => void calcCost()}>
                Kosten berechnen
              </button>
            </div>
            {cost && (
              <div className="cost-card" style={{ marginTop: 20 }}>
                <div className="cost-row">
                  <span>Pauschale</span>
                  <span>{cost.flat_fee.toFixed(2)} €</span>
                </div>
                <div className="cost-row">
                  <span>Kopien</span>
                  <span>{cost.copy_cost.toFixed(2)} €</span>
                </div>
                <div className="cost-row">
                  <span>Versand</span>
                  <span>{cost.postage.toFixed(2)} €</span>
                </div>
                <div className="cost-row total">
                  <span>Summe</span>
                  <span>{cost.total.toFixed(2)} €</span>
                </div>
              </div>
            )}
            <div className="actions">
              <button className="btn btn-primary" onClick={() => printAndFinish()}>
                Drucken & beenden
              </button>
            </div>
          </>
        )}

        {error && <p className="error">{error}</p>}
      </main>

      {undoToast && (
        <div className="undo-toast" role="status">
          <span>„{undoToast.label}“ entfernt.</span>
          <button type="button" className="btn btn-ghost" onClick={() => void handleUndoDelete()}>
            Rückgängig
          </button>
        </div>
      )}
      {inboxToast && (
        <div className="undo-toast" role="status">
          <span>{inboxToast}</span>
        </div>
      )}
      {viewerDoc && project && (
        <DocumentViewer
          projectId={project.id}
          documentId={viewerDoc.id}
          title={viewerDoc.name}
          onClose={() => setViewerDoc(null)}
        />
      )}
    </div>
  );
}
