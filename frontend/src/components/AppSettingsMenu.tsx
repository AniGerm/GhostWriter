import { useEffect, useRef, useState } from "react";
import { api, type AppSettings } from "../api";
import { composeSignatureHtml, parseSignatureHtml } from "../signature";
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
  const [greeting, setGreeting] = useState("Mit freundlichen Grüßen");
  const [doctor, setDoctor] = useState("");
  const [updateInfo, setUpdateInfo] = useState<{
    phase: string;
    current_version?: string | null;
    latest_version?: string | null;
    available?: boolean;
    download_percent?: number;
    error?: string | null;
    message?: string | null;
  } | null>(null);
  const [updateBusy, setUpdateBusy] = useState(false);
  const [updateOverlay, setUpdateOverlay] = useState<string | null>(null);

  useEffect(() => {
    if (!settings) return;
    setOllamaUrl(settings.ollama_base_url || "http://127.0.0.1:11434");
    setOllamaModel(settings.ollama_model || "");
    setPrinter(settings.default_printer || "");
    const parsed = parseSignatureHtml(settings.signature_html || "");
    setGreeting(parsed.greeting || "Mit freundlichen Grüßen");
    setDoctor(parsed.doctor);
  }, [settings]);

  useEffect(() => {
    if (!open || updateOverlay) return;
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
  }, [open, updateOverlay]);

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

  async function closeAppAfterUpdate() {
    await new Promise((r) => window.setTimeout(r, 1800));
    if (window.ghostwriterDesktop?.quitApp) {
      try {
        await window.ghostwriterDesktop.quitApp();
        return;
      } catch {
        /* fall through */
      }
    }
    window.close();
  }

  async function downloadAndInstallUpdate() {
    setUpdateBusy(true);
    setError(null);
    setUpdateOverlay(
      "Update wird vorbereitet …\nDie App schließt sich gleich, installiert das Paket und startet danach neu.",
    );
    try {
      setUpdateOverlay("Update wird heruntergeladen …");
      let status = await api.downloadUpdate();
      setUpdateInfo(status);
      if (status.error) {
        setError(String(status.error));
        setUpdateOverlay(null);
        return;
      }
      setUpdateOverlay(
        "Installation startet.\n\nDie App wird jetzt geschlossen.\nDanach: Paket installieren → GhostWriter startet automatisch neu.\n\nBitte Bestätigung im Systemdialog abwarten.",
      );
      status = await api.installUpdate();
      setUpdateInfo(status);
      if (status.error) {
        setError(String(status.error));
        setUpdateOverlay(null);
        return;
      }
      setUpdateOverlay(
        status.message ||
          "Die App wird jetzt geschlossen.\nInstallation läuft – GhostWriter startet anschließend neu.",
      );
      void closeAppAfterUpdate();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update fehlgeschlagen");
      setUpdateOverlay(null);
    } finally {
      setUpdateBusy(false);
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
        signature_html: composeSignatureHtml(greeting, doctor),
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
          <div className="app-settings-grid">
            <section>
              <h2>Verbindung</h2>
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
            </section>

            <section>
              <h2>Briefabschluss</h2>
              <div className="field">
                <label htmlFor="signature-greeting">Grußformel</label>
                <input
                  id="signature-greeting"
                  value={greeting}
                  onChange={(e) => setGreeting(e.target.value)}
                  placeholder="Mit freundlichen Grüßen"
                />
              </div>
              <div className="field">
                <label htmlFor="signature-doctor">Arzt / Absender</label>
                <textarea
                  id="signature-doctor"
                  rows={3}
                  value={doctor}
                  onChange={(e) => setDoctor(e.target.value)}
                  placeholder={"Dr. med. …\nFacharzt für …"}
                />
              </div>
              <div className="actions" style={{ marginTop: 8 }}>
                <button className="btn btn-primary" disabled={busy} onClick={() => void save()}>
                  Speichern
                </button>
                {saved && <span className="hint">Gespeichert.</span>}
              </div>
            </section>

            <section className="app-settings-updates">
              <h2>App-Updates</h2>
              <p className="hint">
                Aktuell: {updateInfo?.current_version || "–"}
                {updateInfo?.latest_version
                  ? ` · Neueste: ${updateInfo.latest_version}`
                  : ""}
              </p>
              {updateInfo?.available && (
                <p className="hint">Update verfügbar.</p>
              )}
              {typeof updateInfo?.download_percent === "number" &&
                updateInfo.phase === "downloading" && (
                  <p className="hint">Download: {updateInfo.download_percent} %</p>
                )}
              <div className="actions" style={{ marginTop: 8 }}>
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
            </section>
          </div>
        </div>
      )}
      {updateOverlay && (
        <div className="update-overlay" role="alertdialog" aria-live="assertive">
          <div className="update-overlay-card">
            <h2>Update</h2>
            <p style={{ whiteSpace: "pre-line" }}>{updateOverlay}</p>
          </div>
        </div>
      )}
    </div>
  );
}
