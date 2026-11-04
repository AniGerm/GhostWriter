const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("ghostwriterDesktop", {
  listPrinters: () => ipcRenderer.invoke("printers:list"),
  printHtml: (html, deviceName) =>
    ipcRenderer.invoke("print:html", { html, deviceName: deviceName || "" }),
  quitApp: () => ipcRenderer.invoke("app:quit"),
});
