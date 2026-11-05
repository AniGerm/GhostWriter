type Props = {
  name: string;
  meta: string;
  included: boolean;
  busy?: boolean;
  onOpen: () => void;
  onToggleIncluded: (included: boolean) => void;
  onRemove: () => void;
};

export function DocumentListItem({
  name,
  meta,
  included,
  busy = false,
  onOpen,
  onToggleIncluded,
  onRemove,
}: Props) {
  return (
    <li className={`file-list-item${included ? "" : " is-excluded"}`}>
      <label className="file-list-include">
        <input
          type="checkbox"
          checked={included}
          disabled={busy}
          onChange={(e) => onToggleIncluded(e.target.checked)}
        />
        <span>Verwenden</span>
      </label>
      <div className="file-list-main">
        <button type="button" className="file-list-open" onClick={onOpen} disabled={busy}>
          {name}
        </button>
        <span className="file-list-meta">{meta}</span>
      </div>
      <button
        type="button"
        className="btn btn-ghost file-list-remove"
        disabled={busy}
        onClick={onRemove}
      >
        Entfernen
      </button>
    </li>
  );
}
