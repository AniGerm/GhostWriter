import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import TextAlign from "@tiptap/extension-text-align";
import Underline from "@tiptap/extension-underline";
import Placeholder from "@tiptap/extension-placeholder";
import { useEffect } from "react";
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
};

function normalizeHtml(value: string): string {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : "<p></p>";
}

export function RichEditor({ html, onChange }: Props) {
  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
      }),
      Underline,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Placeholder.configure({
        placeholder: "Ihr Antwortschreiben erscheint hier …",
      }),
    ],
    content: normalizeHtml(html),
    editorProps: {
      attributes: {
        class: "gw-editor-surface",
        "aria-label": "Antwortschreiben",
      },
    },
    onUpdate: ({ editor: ed }) => onChange(ed.getHTML()),
  });

  useEffect(() => {
    if (!editor || editor.isDestroyed) return;
    const incoming = normalizeHtml(html);
    if (incoming === editor.getHTML()) return;
    editor.commands.setContent(incoming, { emitUpdate: false });
  }, [html, editor]);

  if (!editor) return null;

  return (
    <div className="editor-shell">
      <div className="editor-toolbar" role="toolbar" aria-label="Textformatierung">
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
        <button
          type="button"
          title="Fett"
          aria-label="Fett"
          className={editor.isActive("bold") ? "is-active" : ""}
          onClick={() => editor.chain().focus().toggleBold().run()}
        >
          <IconBold />
        </button>
        <button
          type="button"
          title="Kursiv"
          aria-label="Kursiv"
          className={editor.isActive("italic") ? "is-active" : ""}
          onClick={() => editor.chain().focus().toggleItalic().run()}
        >
          <IconItalic />
        </button>
        <button
          type="button"
          title="Unterstrichen"
          aria-label="Unterstrichen"
          className={editor.isActive("underline") ? "is-active" : ""}
          onClick={() => editor.chain().focus().toggleUnderline().run()}
        >
          <IconUnderline />
        </button>
        <span className="toolbar-sep" />
        <button
          type="button"
          title="Überschrift"
          aria-label="Überschrift"
          className={editor.isActive("heading", { level: 2 }) ? "is-active" : ""}
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
        >
          <IconHeading />
        </button>
        <button
          type="button"
          title="Aufzählung"
          aria-label="Aufzählung"
          className={editor.isActive("bulletList") ? "is-active" : ""}
          onClick={() => editor.chain().focus().toggleBulletList().run()}
        >
          <IconList />
        </button>
        <span className="toolbar-sep" />
        <button
          type="button"
          title="Linksbündig"
          aria-label="Linksbündig"
          className={editor.isActive({ textAlign: "left" }) ? "is-active" : ""}
          onClick={() => editor.chain().focus().setTextAlign("left").run()}
        >
          <IconAlignLeft />
        </button>
        <button
          type="button"
          title="Zentriert"
          aria-label="Zentriert"
          className={editor.isActive({ textAlign: "center" }) ? "is-active" : ""}
          onClick={() => editor.chain().focus().setTextAlign("center").run()}
        >
          <IconAlignCenter />
        </button>
        <button
          type="button"
          title="Blocksatz"
          aria-label="Blocksatz"
          className={editor.isActive({ textAlign: "justify" }) ? "is-active" : ""}
          onClick={() => editor.chain().focus().setTextAlign("justify").run()}
        >
          <IconAlignJustify />
        </button>
      </div>
      <div className="editor-canvas">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}
