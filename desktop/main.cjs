/**
 * Minimale Electron-Shell um die lokale GhostWriter-UI.
 * Dev: VITE + API. Prod: http://127.0.0.1:8787 (FastAPI liefert dist).
 */
const { app, BrowserWindow, shell } = require("electron");
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
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  win.removeMenu();
  win.loadURL(START_URL);
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
