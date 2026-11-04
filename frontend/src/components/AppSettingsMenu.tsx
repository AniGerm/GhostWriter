import { useEffect, useState } from "react";
import { api, type AppSettings } from "../api";
import { IconGear } from "./editorIcons";

type PrinterOption = { name: string; is_default?: boolean };

type Props = {
  settings: AppSettings | null;
  onSaved: (settings: AppSettings) => void;
};

export function AppSettingsMenu({ settings, onSaved }: Props) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [ollamaUrl, setOllamaUrl] = useState("http://127.0.0.1:11434");
  const [ollamaModel, setOllamaModel] = useState("");
  const [printer, setPrinter] = useState("");
  const [printers, setPrinters] = useState<PrinterOption[]>([]);

  useEffect(() => {
    if (!settings) return;
    setOllamaUrl(settings.ollama_base_url || "http://127.0.0.1:11434");
    setOllamaModel(settings.ollama_model || "");
    setPrinter(settings.default_printer || "");
  }, [settings]);

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
      if (cancelled) return;
      setPrinters(options);
      setPrinter((current) => current || preferred);
    })();
    return () => {
      cancelled = true;
    };
  }, [open]);

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

  return (
    <div className="app-settings-wrap">
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
            <input
              id="ollama-model"
              value={ollamaModel}
              onChange={(e) => setOllamaModel(e.target.value)}
              placeholder="qwen3:14b-q8_0"
            />
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
          {error && <p className="error">{error}</p>}
        </div>
      )}
    </div>
  );
}
