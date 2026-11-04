import { useEffect, useMemo, useState } from "react";
import { api, type AppSettings, type Job, type Project, type ProjectSummary } from "./api";
import { AppSettingsMenu } from "./components/AppSettingsMenu";
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

  const stepIndex = STEPS.indexOf(step);

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
    setStep("Start");
    void api.listProjects().then(setProjects).catch(() => undefined);
  }

  async function printPacket() {
    if (!project) return;
    if (letterIncluded(pageSelection) && draft.trim()) {
      const html = `<!doctype html><html lang="de"><head><meta charset="utf-8" />
<title>Anschreiben</title>
<style>
  body { font-family: "Times New Roman", serif; font-size: 12pt; line-height: 1.5; margin: 18mm; color: #111; }
  h1,h2,h3 { font-family: system-ui, sans-serif; }
  @media print { body { margin: 12mm; } }
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
      <header className="topbar">
        <div className="brand">
          <img className="brand-mark" src="/favicon.svg" alt="" width={36} height={36} />
          <div>
            <strong>GhostWriter</strong>
            <span>Lokale GdB-Berichte{version ? ` · v${version}` : ""}</span>
          </div>
        </div>
        <div className="topbar-right">
          <nav className="steps" aria-label="Ablauf">
            {STEPS.map((name, index) => (
              <div
                key={name}
                className={`step-pill${step === name ? " active" : ""}${
                  index < stepIndex ? " done" : ""
                }`}
              >
                {index + 1}. {name}
              </div>
            ))}
          </nav>
          <AppSettingsMenu
            settings={settings}
            onSaved={(s) => {
              setSettings(s);
              setPostageDraft({ ...s.postage });
              setFlatFeeDraft(s.flat_fee);
            }}
          />
        </div>
      </header>

      <main className="panel">
        {step === "Start" && (
          <>
            <h1 className="hero-title">Bericht in einem klaren Flow.</h1>
            <p className="hero-copy">
              Anfrage des Landratsamts, fachärztliche Befunde, lokale KI-Analyse –
              danach ein Editor, der sich wie ein gutes Schreiben anfühlt.
            </p>
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
            {projects.length > 0 && (
              <div className="project-list">
                {projects.map((p) => (
                  <button key={p.id} type="button" onClick={() => void openProject(p.id)}>
                    <strong>{p.patient_label}</strong>
                    <span>{p.reference || "ohne Aktenzeichen"}</span>
                  </button>
                ))}
              </div>
            )}
          </>
        )}

        {step === "Anfrage" && project && (
          <>
            <h1 className="hero-title">Schreiben des Landratsamts</h1>
            <p className="hero-copy">
              Laden Sie die Anfrage mit den konkreten Fragen hoch. Text-PDFs werden
              direkt gelesen, Scans per OCR.
            </p>
            <DropZone
              title="Anfrage hierher ziehen"
              hint="PDF oder Scan · eine Datei"
              onFiles={(files) => void upload("anfrage", files)}
            />
            {anfrage && (
              <ul className="file-list">
                <li>
                  <span>{anfrage.display_name}</span>
                  <span>{anfrage.has_text ? "Text vorhanden" : "bereit zur OCR"}</span>
                </li>
              </ul>
            )}
            <div className="actions">
              <button className="btn btn-ghost" onClick={() => setStep("Start")}>
                Zurück
              </button>
              <button
                className="btn btn-primary"
                disabled={!anfrage || busy}
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
            <DropZone
              title="Befunde hinzufügen"
              hint="Mehrere PDFs oder Bilder möglich"
              multiple
              onFiles={(files) => void upload("befund", files)}
            />
            <ul className="file-list">
              {befund.map((d) => (
                <li key={d.id}>
                  <span>{d.display_name}</span>
                  <span>{d.page_count ? `${d.page_count} S.` : "neu"}</span>
                </li>
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
                disabled={busy || !anfrage}
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
            />
            {project.questions.length > 0 && (
              <details className="questions-fold">
                <summary>
                  Erkannte Fragen aus der Landratsamts-Anfrage
                  <span className="questions-fold-count">{project.questions.length}</span>
                </summary>
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
              </details>
            )}
            <div className="actions">
              <button className="btn btn-ghost" onClick={() => setStep("Analyse")}>
                Zurück
              </button>
              <button className="btn btn-ghost" disabled={busy} onClick={() => void saveDraft()}>
                Speichern
              </button>
              <button
                className="btn btn-primary"
                disabled={busy}
                onClick={() => void goToPreview()}
              >
                Weiter zur Vorschau
              </button>
            </div>
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
    </div>
  );
}
