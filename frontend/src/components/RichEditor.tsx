import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import TextAlign from "@tiptap/extension-text-align";
import Underline from "@tiptap/extension-underline";
import Placeholder from "@tiptap/extension-placeholder";
import { useEffect } from "react";

type Props = {
  html: string;
  onChange: (html: string) => void;
};

export function RichEditor({ html, onChange }: Props) {
  const editor = useEditor({
    extensions: [
      StarterKit,
      Underline,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Placeholder.configure({
        placeholder: "Ihr Antwortschreiben erscheint hier …",
      }),
    ],
    content: html || "<p></p>",
    onUpdate: ({ editor: ed }) => onChange(ed.getHTML()),
  });

  useEffect(() => {
    if (!editor) return;
    const current = editor.getHTML();
    if (html && html !== current) {
      editor.commands.setContent(html, { emitUpdate: false });
    }
  }, [html, editor]);

  if (!editor) return null;

  return (
    <div className="editor-shell">
      <div className="editor-toolbar">
        <button
          type="button"
          className={editor.isActive("bold") ? "is-active" : ""}
          onClick={() => editor.chain().focus().toggleBold().run()}
        >
          Fett
        </button>
        <button
          type="button"
          className={editor.isActive("italic") ? "is-active" : ""}
          onClick={() => editor.chain().focus().toggleItalic().run()}
        >
          Kursiv
        </button>
        <button
          type="button"
          className={editor.isActive("underline") ? "is-active" : ""}
          onClick={() => editor.chain().focus().toggleUnderline().run()}
        >
          Unterstrichen
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().setTextAlign("left").run()}
        >
          Links
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().setTextAlign("center").run()}
        >
          Mitte
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().setTextAlign("justify").run()}
        >
          Blocksatz
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleBulletList().run()}
        >
          Liste
        </button>
      </div>
      <div className="editor-canvas">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}
