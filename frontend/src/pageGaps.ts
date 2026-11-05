/**
 * TipTap-Extension: Seitenumbruch wie im Textprogramm.
 * Vor der Zeile, die in die Fuß-Sperrzone laufen würde, steht eine Lücke
 * (Fuß + Kopf). Die Lücke ist nur eine Decoration, nicht Teil des HTML.
 */
import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import type { EditorView } from "@tiptap/pm/view";
import { pageBreakLineIndices } from "./letterPagination";

const pageGapsKey = new PluginKey<DecorationSet>("pageGaps");

type LineBox = { pos: number; top: number; bottom: number };

function pageHeightPx(): number {
  const probe = document.createElement("div");
  probe.style.cssText = "position:absolute;visibility:hidden;height:297mm;width:0;";
  document.body.appendChild(probe);
  const height = probe.getBoundingClientRect().height;
  probe.remove();
  return height > 0 ? height : (297 * 96) / 25.4;
}

function pageMetrics(view: EditorView): { content: number; gap: number } {
  const page = pageHeightPx();
  const canvas = view.dom.closest(".editor-canvas");
  if (!(canvas instanceof HTMLElement)) {
    const margin = (25 * 96) / 25.4;
    return { content: page - margin * 2, gap: margin * 2 };
  }
  const style = window.getComputedStyle(canvas);
  const top = Number.parseFloat(style.paddingTop) || 0;
  const bottom = Number.parseFloat(style.paddingBottom) || 0;
  return {
    content: Math.max(1, page - top - bottom),
    gap: top + bottom,
  };
}

function gapShiftBefore(top: number, gaps: { top: number; height: number }[]): number {
  let shift = 0;
  for (const gap of gaps) {
    if (gap.top < top - 0.5) shift += gap.height;
  }
  return shift;
}

function collectLines(view: EditorView): LineBox[] {
  const root = view.dom;
  const rootTop = root.getBoundingClientRect().top;
  const gaps = Array.from(root.querySelectorAll<HTMLElement>(".editor-page-gap")).map(
    (el) => {
      const rect = el.getBoundingClientRect();
      return { top: rect.top - rootTop, height: rect.height };
    },
  );
  const lines: LineBox[] = [];

  const push = (pos: number, top: number, bottom: number) => {
    const shift = gapShiftBefore(top, gaps);
    const adjustedTop = top - shift;
    const adjustedBottom = bottom - shift;
    const prev = lines[lines.length - 1];
    if (prev && Math.abs(prev.top - adjustedTop) < 1.5) {
      prev.bottom = Math.max(prev.bottom, adjustedBottom);
      return;
    }
    lines.push({ pos, top: adjustedTop, bottom: adjustedBottom });
  };

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let node = walker.nextNode();
  while (node) {
    const textNode = node;
    const text = textNode.textContent ?? "";
    const parent = textNode.parentElement;
    if (parent?.closest(".editor-page-gap") || text.length === 0) {
      node = walker.nextNode();
      continue;
    }
    let lastTop = Number.NaN;
    const step = text.length > 4000 ? 8 : 1;
    for (let i = 0; i < text.length; i += step) {
      const range = document.createRange();
      range.setStart(textNode, i);
      range.setEnd(textNode, Math.min(text.length, i + 1));
      const rect = range.getBoundingClientRect();
      if (rect.height < 1 && rect.width < 1) continue;
      const top = rect.top - rootTop;
      if (!Number.isNaN(lastTop) && Math.abs(top - lastTop) < 1.5) continue;
      let pos = -1;
      try {
        pos = view.posAtDOM(textNode, i);
      } catch {
        pos = -1;
      }
      if (pos >= 0) push(pos, top, rect.bottom - rootTop);
      lastTop = top;
    }
    node = walker.nextNode();
  }

  root.querySelectorAll<HTMLElement>("p, h1, h2, h3, li").forEach((el) => {
    if (el.closest(".editor-page-gap")) return;
    if ((el.textContent ?? "").trim().length > 0) return;
    const rect = el.getBoundingClientRect();
    if (rect.height < 1) return;
    let pos = -1;
    try {
      pos = view.posAtDOM(el, 0);
    } catch {
      pos = -1;
    }
    if (pos >= 0) push(pos, rect.top - rootTop, rect.bottom - rootTop);
  });

  lines.sort((a, b) => a.top - b.top || a.pos - b.pos);
  return lines;
}

function lineHeights(lines: LineBox[]): number[] {
  return lines.map((line, index) => {
    const next = lines[index + 1];
    if (next) return Math.max(1, next.top - line.top);
    return Math.max(1, line.bottom - line.top);
  });
}

function makeGap(): HTMLElement {
  const el = document.createElement("div");
  el.className = "editor-page-gap";
  el.setAttribute("contenteditable", "false");
  el.setAttribute("aria-hidden", "true");
  const footer = document.createElement("div");
  footer.className = "editor-page-gap-footer";
  const header = document.createElement("div");
  header.className = "editor-page-gap-header";
  el.append(footer, header);
  return el;
}

function computeGapDecorations(view: EditorView): DecorationSet {
  const { content, gap } = pageMetrics(view);
  if (content <= 0 || gap <= 0) return DecorationSet.empty;
  const lines = collectLines(view);
  if (lines.length === 0) return DecorationSet.empty;
  const breaks = pageBreakLineIndices(lineHeights(lines), content);
  const widgets: Decoration[] = [];
  const seen = new Set<number>();
  for (const index of breaks) {
    const pos = lines[index]?.pos;
    if (pos == null || pos <= 0 || seen.has(pos)) continue;
    seen.add(pos);
    widgets.push(
      Decoration.widget(pos, () => makeGap(), {
        side: -1,
        key: `page-gap-${pos}`,
      }),
    );
  }
  return DecorationSet.create(view.state.doc, widgets);
}

function sameGapPositions(a: DecorationSet, b: DecorationSet): boolean {
  const aa = a.find().map((d) => d.from);
  const bb = b.find().map((d) => d.from);
  if (aa.length !== bb.length) return false;
  return aa.every((pos, i) => pos === bb[i]);
}

export const PageGaps = Extension.create({
  name: "pageGaps",

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: pageGapsKey,
        state: {
          init: () => DecorationSet.empty,
          apply(tr, old) {
            const next = tr.getMeta(pageGapsKey) as DecorationSet | undefined;
            if (next) return next;
            if (tr.docChanged) return old.map(tr.mapping, tr.doc);
            return old;
          },
        },
        props: {
          decorations(state) {
            return pageGapsKey.getState(state) ?? DecorationSet.empty;
          },
        },
        view(editorView) {
          let frame = 0;
          let passes = 0;
          let lastDoc = editorView.state.doc;
          const refresh = () => {
            if (editorView.isDestroyed) return;
            if (passes > 6) return;
            const next = computeGapDecorations(editorView);
            const prev = pageGapsKey.getState(editorView.state) ?? DecorationSet.empty;
            if (sameGapPositions(prev, next)) return;
            passes += 1;
            const tr = editorView.state.tr.setMeta(pageGapsKey, next);
            editorView.dispatch(tr);
          };
          const schedule = () => {
            if (editorView.state.doc !== lastDoc) {
              lastDoc = editorView.state.doc;
              passes = 0;
            }
            cancelAnimationFrame(frame);
            frame = requestAnimationFrame(() => {
              frame = requestAnimationFrame(refresh);
            });
          };
          schedule();
          return {
            update() {
              schedule();
            },
            destroy() {
              cancelAnimationFrame(frame);
            },
          };
        },
      }),
    ];
  },
});
