import { useEffect, useRef, useState } from "react";
import { api, type AppSettings } from "../api";
import { IconGear } from "./editorIcons";

type PrinterOption = { name: string; is_default?: boolean };

type Props = {
  settings: AppSettings | null;
  onSaved: (settings: AppSettings) => void;
};

export function AppSettingsMenu({ settings, onSaved }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [ollamaUrl, setOllamaUrl] = useState("http://127.0.0.1:11434");
  const [ollamaModel, setOllamaModel] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [printer, setPrinter] = useState("");
  const [printers, setPrinters] = useState<PrinterOption[]>([]);
  const [updateInfo, setUpdateInfo] = useState<{
    phase: string;
    current_version?: string | null;
    latest_version?: string | null;
    available?: boolean;
    download_percent?: number;
    error?: string | null;
  } | null>(null);
  const [updateBusy, setUpdateBusy] = useState(false);

  useEffect(() => {
    if (!settings) return;
    setOllamaUrl(settings.ollama_base_url || "http://127.0.0.1:11434");
    setOllamaModel(settings.ollama_model || "");
    setPrinter(settings.default_printer || "");
  }, [settings]);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: MouseEvent | PointerEvent) => {
      const target = event.target as Node | null;
      if (wrapRef.current && target && !wrapRef.current.contains(target)) {
        setOpen(false);
        setSaved(false);
        setError(null);
      }
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        setSaved(false);
        setError(null);
      }
    };
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    void (async () => {
      const options: PrinterOption[] = [];
      let preferred = "";
      try {
        const cups = await api.listPrinters();
        for (const p of cups.printers) {
          options.push({ name: p.name, is_default: p.is_default });
        }
        preferred = cups.default_printer || cups.system_default || "";
      } catch {
        /* CUPS optional */
      }
      if (window.ghostwriterDesktop?.listPrinters) {
        try {
          const desktop = await window.ghostwriterDesktop.listPrinters();
          for (const p of desktop) {
            if (!options.some((o) => o.name === p.name)) {
              options.push({ name: p.name, is_default: Boolean(p.isDefault) });
            }
          }
        } catch {
          /* Electron optional */
        }
      }
      try {
        const status = await api.updateStatus();
        if (!cancelled) setUpdateInfo(status);
      } catch {
        /* updates optional */
      }
      if (cancelled) return;
      setPrinters(options);
      setPrinter((current) => current || preferred);
    })();
    return () => {
      cancelled = true;
    };
  }, [open]);

  async function checkForUpdates() {
    setUpdateBusy(true);
    setError(null);
    try {
      const status = await api.checkUpdate();
      setUpdateInfo(status);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update-Prüfung fehlgeschlagen");
    } finally {
      setUpdateBusy(false);
    }
  }

  async function downloadAndInstallUpdate() {
    setUpdateBusy(true);
    setError(null);
    try {
      let status = await api.downloadUpdate();
      setUpdateInfo(status);
      status = await api.installUpdate();
      setUpdateInfo(status);
      if (status.error) {
        setError(String(status.error));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update fehlgeschlagen");
    } finally {
      setUpdateBusy(false);
      try {
        setUpdateInfo(await api.updateStatus());
      } catch {
        /* ignore */
      }
    }
  }

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      void (async () => {
        setModelsError(null);
        try {
          const result = await api.listOllamaModels(ollamaUrl.trim());
          if (cancelled) return;
          const names = result.models ?? [];
          setModels(names);
          setOllamaModel((current) => {
            if (current && names.includes(current)) return current;
            if (current) return current;
            return names[0] || "";
          });
        } catch (e) {
          if (cancelled) return;
          setModels([]);
          setModelsError(
            e instanceof Error ? e.message : "Modelle konnten nicht geladen werden",
          );
        }
      })();
    }, 250);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [open, ollamaUrl]);

  async function save() {
    setBusy(true);
    setError(null);
    setSaved(false);
    try {
      const next = await api.putSettings({
        ollama_base_url: ollamaUrl.trim(),
        ollama_model: ollamaModel.trim(),
        default_printer: printer,
      });
      onSaved(next);
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Speichern fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  const modelOptions = models.slice();
  if (ollamaModel && !modelOptions.includes(ollamaModel)) {
    modelOptions.unshift(ollamaModel);
  }

  return (
    <div className="app-settings-wrap" ref={wrapRef}>
      <button
        type="button"
        className="icon-btn"
        title="Einstellungen"
        aria-label="Einstellungen"
        aria-expanded={open}
        onClick={() => {
          setOpen((v) => !v);
          setSaved(false);
          setError(null);
        }}
      >
        <IconGear />
      </button>
      {open && (
        <div className="app-settings-popover" role="dialog" aria-label="App-Einstellungen">
          <h2>Einstellungen</h2>
          <p className="hint">
            Ollama darf lokal oder im Praxis-LAN liegen (z. B. Server-IP). Öffentliche
            Cloud-URLs sind gesperrt.
          </p>
          <div className="field">
            <label htmlFor="ollama-url">Ollama-URL</label>
            <input
              id="ollama-url"
              value={ollamaUrl}
              onChange={(e) => setOllamaUrl(e.target.value)}
              placeholder="http://127.0.0.1:11434"
            />
          </div>
          <div className="field">
            <label htmlFor="ollama-model">Ollama-Modell</label>
            <select
              id="ollama-model"
              value={ollamaModel}
              onChange={(e) => setOllamaModel(e.target.value)}
              disabled={modelOptions.length === 0}
            >
              {modelOptions.length === 0 ? (
                <option value="">Keine Modelle gefunden</option>
              ) : (
                modelOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))
              )}
            </select>
            {modelsError && <p className="hint">{modelsError}</p>}
          </div>
          <div className="field">
            <label htmlFor="default-printer">Standarddrucker</label>
            <select
              id="default-printer"
              value={printer}
              onChange={(e) => setPrinter(e.target.value)}
            >
              <option value="">Systemstandard</option>
              {printers.map((p) => (
                <option key={p.name} value={p.name}>
                  {p.name}
                  {p.is_default ? " (System)" : ""}
                </option>
              ))}
            </select>
          </div>
          <div className="actions" style={{ marginTop: 12 }}>
            <button className="btn btn-primary" disabled={busy} onClick={() => void save()}>
              Speichern
            </button>
          </div>
          {saved && <p className="hint">Gespeichert.</p>}

          <div className="settings-divider" />
          <h2>App-Updates</h2>
          <p className="hint">
            Aktuell: {updateInfo?.current_version || "–"}
            {updateInfo?.latest_version
              ? ` · Neueste: ${updateInfo.latest_version}`
              : ""}
          </p>
          {updateInfo?.available && (
            <p className="hint">Update verfügbar – Download & Installation benötigt Bestätigung.</p>
          )}
          {typeof updateInfo?.download_percent === "number" &&
            updateInfo.phase === "downloading" && (
              <p className="hint">Download: {updateInfo.download_percent} %</p>
            )}
          <div className="actions" style={{ marginTop: 10 }}>
            <button
              className="btn btn-ghost"
              disabled={updateBusy}
              onClick={() => void checkForUpdates()}
            >
              Auf Updates prüfen
            </button>
            <button
              className="btn btn-primary"
              disabled={updateBusy || !updateInfo?.available}
              onClick={() => void downloadAndInstallUpdate()}
            >
              Download & installieren
            </button>
          </div>
          {updateInfo?.error && <p className="error">{updateInfo.error}</p>}
          {error && <p className="error">{error}</p>}
        </div>
      )}
    </div>
  );
}
