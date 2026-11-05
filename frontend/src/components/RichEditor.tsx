import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import TextAlign from "@tiptap/extension-text-align";
import { FontSize, TextStyle } from "@tiptap/extension-text-style";
import Underline from "@tiptap/extension-underline";
import Placeholder from "@tiptap/extension-placeholder";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { BlockClass } from "../blockClass";
import { PageGaps } from "../pageGaps";
import { normalizeReportHtml } from "../stripHeadingBrackets";
import {
  IconAlignCenter,
  IconAlignJustify,
  IconAlignLeft,
  IconBold,
  IconHeading,
  IconItalic,
  IconList,
  IconRedo,
  IconUnderline,
  IconUndo,
} from "./editorIcons";

type Props = {
  html: string;
  onChange: (html: string) => void;
  /** Aktionen rechts in der Toolbar (Speichern, Vorschau, …) */
  trailing?: ReactNode;
  bodyPt?: number;
  headingPt?: number;
  onBodyPt?: (pt: number) => void;
  onHeadingPt?: (pt: number) => void;
};

function normalizeHtml(value: string): string {
  const trimmed = normalizeReportHtml(value.trim());
  return trimmed.length > 0 ? trimmed : "<p></p>";
}

export function RichEditor({
  html,
  onChange,
  trailing,
  bodyPt = 12,
  headingPt = 14,
  onBodyPt,
  onHeadingPt,
}: Props) {
  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Underline,
      TextStyle,
      FontSize,
      BlockClass,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Placeholder.configure({
        placeholder: "Ihr Antwortschreiben erscheint hier …",
      }),
      PageGaps,
    ],
    content: normalizeHtml(html),
    editorProps: {
      attributes: {
        class: "gw-editor-surface",
        "aria-label": "Antwortschreiben",
      },
    },
    onUpdate: ({ editor: ed }) => onChange(normalizeReportHtml(ed.getHTML())),
  });

  useEffect(() => {
    if (!editor || editor.isDestroyed) return;
    const incoming = normalizeHtml(html);
    if (incoming === normalizeReportHtml(editor.getHTML())) return;
    editor.commands.setContent(incoming, { emitUpdate: false });
  }, [html, editor]);

  const [markPt, setMarkPt] = useState(bodyPt);
  const selectionRef = useRef<{ from: number; to: number } | null>(null);

  useEffect(() => {
    if (!editor) return;
    const sync = () => {
      const raw = editor.getAttributes("textStyle").fontSize;
      const parsed = typeof raw === "string" ? Number.parseInt(raw, 10) : Number.NaN;
      setMarkPt(Number.isFinite(parsed) && parsed > 0 ? parsed : bodyPt);
    };
    editor.on("selectionUpdate", sync);
    editor.on("transaction", sync);
    return () => {
      editor.off("selectionUpdate", sync);
      editor.off("transaction", sync);
    };
  }, [editor, bodyPt]);

  if (!editor) return null;

  function rememberSelection() {
    const { from, to } = editor!.state.selection;
    selectionRef.current = { from, to };
  }

  function focusSelection() {
    const saved = selectionRef.current;
    const max = editor!.state.doc.content.size;
    if (saved && saved.from !== saved.to && saved.from >= 0 && saved.to <= max) {
      editor!.commands.setTextSelection(saved);
    }
    return editor!.chain().focus();
  }

  function applyMarkSize(pt: number) {
    focusSelection().setFontSize(`${pt}pt`).run();
    const { from, to } = editor!.state.selection;
    selectionRef.current = { from, to };
  }

  function applyBlockStyle(style: "paragraph" | "heading" | "bullet") {
    focusSelection();
    const inList = editor!.isActive("bulletList");
    const chain = editor!.chain().focus();
    if (style === "heading") {
      if (inList) chain.toggleBulletList();
      chain.setHeading({ level: 2 }).run();
    } else if (style === "bullet") {
      if (!inList) chain.toggleBulletList().run();
    } else {
      if (inList) chain.toggleBulletList();
      chain.setParagraph().run();
    }
    const { from, to } = editor!.state.selection;
    selectionRef.current = { from, to };
  }

  const blockValue = editor.isActive("bulletList")
    ? "bullet"
    : editor.isActive("heading")
      ? "heading"
      : "paragraph";

  return (
    <div className="editor-shell">
      <div className="editor-toolbar" role="toolbar" aria-label="Textformatierung">
        <div
          className="editor-toolbar-format"
          onPointerDown={rememberSelection}
          onMouseDown={(event) => {
            const target = event.target as HTMLElement;
            if (target.closest("input, select, textarea")) return;
            event.preventDefault();
          }}
        >
          <button
            type="button"
            title="Rückgängig"
            aria-label="Rückgängig"
            onClick={() => editor.chain().focus().undo().run()}
          >
            <IconUndo />
          </button>
          <button
            type="button"
            title="Wiederholen"
            aria-label="Wiederholen"
            onClick={() => editor.chain().focus().redo().run()}
          >
            <IconRedo />
          </button>
          <span className="toolbar-sep" />
          <label className="toolbar-size">
            Absatz
            <select
              aria-label="Absatzformat der Markierung"
              title="Absatz der Markierung"
              value={blockValue}
              onChange={(event) =>
                applyBlockStyle(event.target.value as "paragraph" | "heading" | "bullet")
              }
            >
              <option value="paragraph">Fließtext</option>
              <option value="heading">Überschrift</option>
              <option value="bullet">Aufzählung</option>
            </select>
          </label>
          <span className="toolbar-sep" />
          <button
            type="button"
            title="Markierung fett"
            aria-label="Fett"
            className={editor.isActive("bold") ? "is-active" : ""}
            onClick={() => focusSelection().toggleBold().run()}
          >
            <IconBold />
          </button>
          <button
            type="button"
            title="Markierung kursiv"
            aria-label="Kursiv"
            className={editor.isActive("italic") ? "is-active" : ""}
            onClick={() => focusSelection().toggleItalic().run()}
          >
            <IconItalic />
          </button>
          <button
            type="button"
            title="Markierung unterstrichen"
            aria-label="Unterstrichen"
            className={editor.isActive("underline") ? "is-active" : ""}
            onClick={() => focusSelection().toggleUnderline().run()}
          >
            <IconUnderline />
          </button>
          <span className="toolbar-sep" />
          <button
            type="button"
            title="Absatz als Überschrift"
            aria-label="Überschrift"
            className={editor.isActive("heading", { level: 2 }) ? "is-active" : ""}
            onClick={() => applyBlockStyle(editor.isActive("heading") ? "paragraph" : "heading")}
          >
            <IconHeading />
          </button>
          <button
            type="button"
            title="Absatz als Aufzählung"
            aria-label="Aufzählung"
            className={editor.isActive("bulletList") ? "is-active" : ""}
            onClick={() => applyBlockStyle(editor.isActive("bulletList") ? "paragraph" : "bullet")}
          >
            <IconList />
          </button>
          <span className="toolbar-sep" />
          <button
            type="button"
            title="Linksbündig"
            aria-label="Linksbündig"
            className={editor.isActive({ textAlign: "left" }) ? "is-active" : ""}
            onClick={() => focusSelection().setTextAlign("left").run()}
          >
            <IconAlignLeft />
          </button>
          <button
            type="button"
            title="Zentriert"
            aria-label="Zentriert"
            className={editor.isActive({ textAlign: "center" }) ? "is-active" : ""}
            onClick={() => focusSelection().setTextAlign("center").run()}
          >
            <IconAlignCenter />
          </button>
          <button
            type="button"
            title="Blocksatz"
            aria-label="Blocksatz"
            className={editor.isActive({ textAlign: "justify" }) ? "is-active" : ""}
            onClick={() => focusSelection().setTextAlign("justify").run()}
          >
            <IconAlignJustify />
          </button>
          <span className="toolbar-sep" />
          <label className="toolbar-size">
            Markierung
            <input
              type="number"
              min={8}
              max={28}
              aria-label="Schriftgröße der Markierung"
              title="Größe des markierten Textes"
              value={markPt}
              onPointerDown={() => {
                const { from, to } = editor.state.selection;
                selectionRef.current = { from, to };
              }}
              onFocus={() => {
                const { from, to } = editor.state.selection;
                if (from !== to) selectionRef.current = { from, to };
              }}
              onChange={(event) => {
                const pt = Number(event.target.value);
                if (!Number.isFinite(pt)) return;
                setMarkPt(pt);
                applyMarkSize(pt);
              }}
            />
          </label>
          <label className="toolbar-size">
            Text
            <input
              type="number"
              min={8}
              max={28}
              aria-label="Schriftgröße Text"
              value={bodyPt}
              onChange={(event) => onBodyPt?.(Number(event.target.value))}
            />
          </label>
          <label className="toolbar-size">
            Überschrift
            <input
              type="number"
              min={8}
              max={28}
              aria-label="Schriftgröße Überschrift"
              value={headingPt}
              onChange={(event) => onHeadingPt?.(Number(event.target.value))}
            />
          </label>
        </div>
        {trailing ? (
          <>
            <span className="toolbar-sep toolbar-sep-tall" aria-hidden />
            <div className="editor-toolbar-actions">{trailing}</div>
          </>
        ) : null}
      </div>
      <div className="editor-desk" aria-label="A4-Briefblatt">
        <div
          className="editor-canvas"
          style={{ ["--gw-body" as string]: `${bodyPt}pt`, ["--gw-heading" as string]: `${headingPt}pt` }}
        >
          <EditorContent editor={editor} />
        </div>
      </div>
    </div>
  );
}
