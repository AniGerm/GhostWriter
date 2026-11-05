/**
 * TipTap-Extension: sichtbare Lücken für Kopf-/Fuß-Sperrzonen zwischen A4-Seiten.
 * Widgets ändern das gespeicherte HTML nicht.
 */
import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import type { EditorView } from "@tiptap/pm/view";
import {
  A4_MARGIN_BOTTOM_MM,
  A4_MARGIN_TOP_MM,
  a4ContentHeightPx,
} from "./letterPagination";

const pageGapsKey = new PluginKey<DecorationSet>("pageGaps");

function gapHeightPx(): number {
  return Math.round(((A4_MARGIN_TOP_MM + A4_MARGIN_BOTTOM_MM) * 96) / 25.4);
}

function blockHeight(el: HTMLElement): number {
  const style = window.getComputedStyle(el);
  return (
    el.offsetHeight +
    Number.parseFloat(style.marginTop || "0") +
    Number.parseFloat(style.marginBottom || "0")
  );
}

function computeGapDecorations(view: EditorView): DecorationSet {
  const contentH = a4ContentHeightPx();
  const gapH = gapHeightPx();
  if (contentH <= 0 || gapH <= 0) return DecorationSet.empty;

  const widgets: Decoration[] = [];
  let used = 0;
  const doc = view.state.doc;

  doc.forEach((child, offset) => {
    const dom = view.nodeDOM(offset);
    if (!(dom instanceof HTMLElement)) return;

    const height = blockHeight(dom);
    // Lücke VOR dem Block, der die Inhaltsfläche sprengen würde
    if (used > 0 && used + height > contentH) {
      widgets.push(
        Decoration.widget(
          offset,
          () => {
            const el = document.createElement("div");
            el.className = "editor-page-gap";
            el.setAttribute("contenteditable", "false");
            el.setAttribute("aria-hidden", "true");
            el.style.height = `${gapH}px`;
            return el;
          },
          { side: -1, key: `page-gap-before-${offset}` },
        ),
      );
      used = 0;
    }

    used += height;

    // Nach einem Block, der die Seite füllt/überläuft: Lücke DANACH,
    // damit folgender Text nicht in der Fuß-Sperrzone startet.
    if (used >= contentH) {
      const after = offset + child.nodeSize;
      widgets.push(
        Decoration.widget(
          after,
          () => {
            const el = document.createElement("div");
            el.className = "editor-page-gap";
            el.setAttribute("contenteditable", "false");
            el.setAttribute("aria-hidden", "true");
            el.style.height = `${gapH}px`;
            return el;
          },
          { side: 1, key: `page-gap-after-${after}` },
        ),
      );
      used = Math.max(0, used - contentH);
      if (used === 0 || height >= contentH) {
        used = 0;
      }
    }
  });

  return DecorationSet.create(doc, widgets);
}

function sameGapPositions(a: DecorationSet, b: DecorationSet): boolean {
  const aa = a.find().map((d) => `${d.from}:${d.spec?.side ?? 0}`);
  const bb = b.find().map((d) => `${d.from}:${d.spec?.side ?? 0}`);
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
          const refresh = () => {
            const next = computeGapDecorations(editorView);
            const prev = pageGapsKey.getState(editorView.state) ?? DecorationSet.empty;
            if (sameGapPositions(prev, next)) return;
            const tr = editorView.state.tr.setMeta(pageGapsKey, next);
            editorView.dispatch(tr);
          };
          const schedule = () => {
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
