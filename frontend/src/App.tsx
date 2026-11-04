import { useEffect, useMemo, useState } from "react";
import { api, type Job, type Project, type ProjectSummary } from "./api";
import { DropZone } from "./components/DropZone";
import { RichEditor } from "./components/RichEditor";

const STEPS = [
  "Start",
  "Anfrage",
  "Befunde",
  "Analyse",
  "Schreiben",
  "Kosten",
] as const;

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
  const [postage, setPostage] = useState<string>("standard");
  const [cost, setCost] = useState<Project["cost"]>(null);
  const [version, setVersion] = useState("");

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
  }, []);

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
    try {
      const result = await api.costs(project.id, pages, postage);
      setCost(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Kostenfehler");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <strong>GhostWriter</strong>
          <span>Lokale GdB-Berichte{version ? ` · v${version}` : ""}</span>
        </div>
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
            <h1 className="hero-title">Antwortschreiben</h1>
            <p className="hero-copy">
              Entwurf prüfen und feinschleifen. Typografie wie auf Briefpapier –
              Blocksatz, klare Hierarchie.
            </p>
            {!draft.trim() && (
              <p className="error">Noch kein Entwurf geladen. Analyse erneut starten oder Projekt neu öffnen.</p>
            )}
            <RichEditor
              key={`${project.id}-${draftEpoch}`}
              html={draft}
              onChange={setDraft}
            />
            {project.questions.length > 0 && (
              <ul className="file-list" style={{ marginTop: 18 }}>
                {project.questions.map((q) => (
                  <li key={q.number}>
                    <span>
                      {q.number}. {q.text}
                    </span>
                    <span>{q.keyword}</span>
                  </li>
                ))}
              </ul>
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
                onClick={() => {
                  void saveDraft();
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
            <h1 className="hero-title">Druck & Kosten</h1>
            <p className="hero-copy">
              Die Anfrage des Landratsamts wird nicht mitgezählt. Seiten manuell
              korrigierbar.
            </p>
            <div className="grid-2">
              <div className="field">
                <label htmlFor="pages">Seiten (manuell)</label>
                <input
                  id="pages"
                  type="number"
                  min={0}
                  value={pages}
                  onChange={(e) => setPages(Number(e.target.value))}
                />
              </div>
              <div className="field">
                <label htmlFor="postage">Versand</label>
                <input
                  id="postage"
                  value={postage}
                  onChange={(e) => setPostage(e.target.value)}
                  placeholder="standard | kompakt | gross | maxi"
                />
              </div>
            </div>
            <div className="actions">
              <button className="btn btn-ghost" onClick={() => setStep("Schreiben")}>
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
          </>
        )}

        {error && <p className="error">{error}</p>}
      </main>
    </div>
  );
}
