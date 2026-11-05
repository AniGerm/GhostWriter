import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";

type Props = {
  title: string;
  hint: string;
  accept?: string;
  multiple?: boolean;
  onFiles: (files: File[]) => void;
};

export function DropZone({
  title,
  hint,
  accept = "application/pdf,image/*",
  multiple = false,
  onFiles,
}: Props) {
  const [drag, setDrag] = useState(false);
  const ref = useRef<HTMLLabelElement>(null);

  // #region agent log
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const parent = el.parentElement;
    const cs = window.getComputedStyle(el);
    const data = {
      dropWidth: Math.round(el.getBoundingClientRect().width),
      parentWidth: parent ? Math.round(parent.getBoundingClientRect().width) : null,
      display: cs.display,
      widthCss: cs.width,
      textAlign: cs.textAlign,
      title,
    };
    void fetch("/api/debug/log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        hypothesisId: "H1",
        location: "DropZone.tsx:mount",
        message: "dropzone_geometry",
        data,
      }),
    }).catch(() => undefined);
    fetch("http://127.0.0.1:7618/ingest/e4f895d3-7933-43f7-9300-cd580c137a2e", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Debug-Session-Id": "3e0627",
      },
      body: JSON.stringify({
        sessionId: "3e0627",
        hypothesisId: "H1",
        location: "DropZone.tsx:mount",
        message: "dropzone_geometry",
        data,
        timestamp: Date.now(),
      }),
    }).catch(() => undefined);
  }, [title]);
  // #endregion

  const take = useCallback(
    (list: FileList | null) => {
      if (!list?.length) return;
      const files = Array.from(list);
      onFiles(multiple ? files : files.slice(0, 1));
    },
    [multiple, onFiles],
  );

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDrag(false);
    take(event.dataTransfer.files);
  };

  return (
    <label
      ref={ref}
      className={`dropzone${drag ? " drag" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
    >
      <strong>{title}</strong>
      <p>{hint}</p>
      <input
        type="file"
        accept={accept}
        multiple={multiple}
        hidden
        onChange={(e) => take(e.target.files)}
      />
    </label>
  );
}
