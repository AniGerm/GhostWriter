import { useMemo, useState } from "react";
import type { AppSettings, ProjectSummary } from "../api";
import { filterProjects } from "../fuzzy";
import { AppSettingsMenu } from "./AppSettingsMenu";
import { ConfirmDialog } from "./ConfirmDialog";

type Props = {
  version: string;
  steps: readonly string[];
  step: string;
  stepIndex: number;
  onSelectStep: (name: string) => void;
  projects: ProjectSummary[];
  activeProjectId: string | null;
  onOpenProject: (id: string) => void;
  onDeleteProject: (id: string) => Promise<void>;
  settings: AppSettings | null;
  onSettingsSaved: (settings: AppSettings) => void;
};

export function AppSidebar({
  version,
  steps,
  step,
  stepIndex,
  onSelectStep,
  projects,
  activeProjectId,
  onOpenProject,
  onDeleteProject,
  settings,
  onSettingsSaved,
}: Props) {
  const [query, setQuery] = useState("");
  const [pendingDelete, setPendingDelete] = useState<ProjectSummary | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const filtered = useMemo(
    () => filterProjects(projects, query),
    [projects, query],
  );

  return (
    <aside className="app-sidebar" aria-label="Navigation">
      <div className="sidebar-brand">
        <img className="brand-mark" src="/favicon.svg" alt="" width={32} height={32} />
        <div>
          <strong>GhostWriter</strong>
          <span>{version ? `v${version}` : "lokal"}</span>
        </div>
      </div>

      <nav className="sidebar-steps" aria-label="Ablauf">
        {steps.map((name, index) => {
          const reachable = index <= stepIndex;
          const active = step === name;
          const done = index < stepIndex;
          return (
            <button
              key={name}
              type="button"
              className={`sidebar-step${active ? " active" : ""}${done ? " done" : ""}`}
              disabled={!reachable}
              onClick={() => reachable && onSelectStep(name)}
            >
              <span className="sidebar-step-num">{index + 1}</span>
              <span>{name}</span>
            </button>
          );
        })}
      </nav>

      <div className="sidebar-projects">
        <label className="sidebar-section-label" htmlFor="project-search">
          Projekte
        </label>
        <input
          id="project-search"
          className="sidebar-search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Suchen …"
          autoComplete="off"
        />
        <ul className="sidebar-project-list">
          {filtered.length === 0 ? (
            <li className="sidebar-empty">
              {projects.length === 0 ? "Noch keine Projekte" : "Keine Treffer"}
            </li>
          ) : (
            filtered.map((p) => (
              <li key={p.id} className={p.id === activeProjectId ? "is-active" : ""}>
                <button
                  type="button"
                  className="sidebar-project-open"
                  onClick={() => onOpenProject(p.id)}
                >
                  <strong>{p.patient_label}</strong>
                  <span>{p.reference || "ohne Aktenzeichen"}</span>
                </button>
                <button
                  type="button"
                  className="sidebar-project-delete"
                  title="Projekt löschen"
                  aria-label={`Projekt ${p.patient_label} löschen`}
                  onClick={() => setPendingDelete(p)}
                >
                  ×
                </button>
              </li>
            ))
          )}
        </ul>
      </div>

      <div className="sidebar-footer">
        <AppSettingsMenu settings={settings} onSaved={onSettingsSaved} />
      </div>

      {pendingDelete && (
        <ConfirmDialog
          title="Projekt löschen?"
          message={`„${pendingDelete.patient_label}“ wird entfernt. Sie können das kurz danach rückgängig machen.`}
          busy={deleteBusy}
          onCancel={() => setPendingDelete(null)}
          onConfirm={() => {
            void (async () => {
              setDeleteBusy(true);
              try {
                await onDeleteProject(pendingDelete.id);
                setPendingDelete(null);
              } finally {
                setDeleteBusy(false);
              }
            })();
          }}
        />
      )}
    </aside>
  );
}
