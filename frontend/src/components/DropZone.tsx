import { useCallback, useState, type DragEvent } from "react";

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
