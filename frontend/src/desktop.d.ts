export type DesktopPrinter = {
  name: string;
  displayName?: string;
  description?: string;
  isDefault?: boolean;
};

export type GhostwriterDesktop = {
  listPrinters: () => Promise<DesktopPrinter[]>;
  printHtml: (html: string, deviceName?: string) => Promise<{ ok: boolean }>;
};

declare global {
  interface Window {
    ghostwriterDesktop?: GhostwriterDesktop;
  }
}

export {};
