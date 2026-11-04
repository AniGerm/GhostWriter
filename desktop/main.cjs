/**
 * Minimale Electron-Shell um die lokale GhostWriter-UI.
 * Dev: VITE + API. Prod: http://127.0.0.1:8787 (FastAPI liefert dist).
 */
const { app, BrowserWindow, ipcMain, shell } = require("electron");
const path = require("path");

const DEV = !!process.env.GHOSTWRITER_DEV;
const START_URL = DEV ? "http://127.0.0.1:5174" : "http://127.0.0.1:8787";

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 680,
    backgroundColor: "#eceae4",
    title: "GhostWriter",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  win.removeMenu();
  win.loadURL(START_URL);
  win.webContents.setWindowOpenHandler(({ url }) => {
    // Lokale API-Dokumente (PDF) in Electron-Fenster erlauben
    if (url.startsWith("http://127.0.0.1:") || url.startsWith("http://localhost:")) {
      return { action: "allow" };
    }
    shell.openExternal(url);
    return { action: "deny" };
  });
}

ipcMain.handle("printers:list", async (event) => {
  const win = BrowserWindow.fromWebContents(event.sender);
  if (!win) return [];
  try {
    return await win.webContents.getPrintersAsync();
  } catch {
    return [];
  }
});

ipcMain.handle("print:html", async (event, payload) => {
  const html = String((payload && payload.html) || "");
  const deviceName = String((payload && payload.deviceName) || "");
  const printWin = new BrowserWindow({
    show: false,
    webPreferences: { contextIsolation: true, sandbox: true },
  });
  try {
    await printWin.loadURL(
      `data:text/html;charset=utf-8,${encodeURIComponent(html)}`,
    );
    await new Promise((resolve, reject) => {
      printWin.webContents.print(
        {
          silent: Boolean(deviceName),
          printBackground: true,
          deviceName: deviceName || undefined,
        },
        (success, failureReason) => {
          if (success) resolve(undefined);
          else reject(new Error(failureReason || "print failed"));
        },
      );
    });
    return { ok: true };
  } finally {
    printWin.destroy();
  }
});

app.whenReady().then(createWindow);
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
