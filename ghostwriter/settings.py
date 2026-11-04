"""Anwendungseinstellungen (JSON, ohne Qt)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from ghostwriter.costs import CopyTier, CostSettings, PostageOption
from ghostwriter.updates import DEFAULT_GITHUB_REPO


@dataclass
class AppSettings:
    """Persistente Einstellungen."""

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:14b-q8_0"
    ollama_num_ctx: int = 16384
    letterhead_html: str = ""
    signature_html: str = "<p>Mit freundlichen Grüßen</p>"
    flat_fee: float = 25.0
    copy_tier_up_to: int = 100
    copy_tier_price: float = 0.50
    after_last_tier_price: float = 0.15
    postage: dict[str, float] = field(
        default_factory=lambda: {
            "standard": 0.95,
            "kompakt": 1.10,
            "gross": 1.80,
            "maxi": 3.40,
        }
    )
    default_postage_key: str = "gross"
    spool_dir: str = ""
    default_font: str = "Liberation Serif"
    default_font_size: int = 12
    github_repo: str = DEFAULT_GITHUB_REPO
    check_updates_on_startup: bool = True

    def to_cost_settings(self) -> CostSettings:
        labels = {
            "standard": "Standardbrief bis 20 g",
            "kompakt": "Kompaktbrief bis 50 g",
            "gross": "Großbrief bis 500 g",
            "maxi": "Maxibrief bis 1000 g",
        }
        options = tuple(
            PostageOption(key=k, label=labels.get(k, k), price=v) for k, v in self.postage.items()
        )
        return CostSettings(
            flat_fee=self.flat_fee,
            copy_tiers=(
                CopyTier(up_to_page=self.copy_tier_up_to, price_per_page=self.copy_tier_price),
            ),
            after_last_tier_price=self.after_last_tier_price,
            postage_options=options,
        )


def load_settings(path: Path) -> AppSettings:
    if not path.is_file():
        return AppSettings()
    data = json.loads(path.read_text(encoding="utf-8"))
    known = {f.name for f in fields(AppSettings)}
    filtered = {k: v for k, v in data.items() if k in known}
    return AppSettings(**filtered)


def save_settings(path: Path, settings: AppSettings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(settings), indent=2, ensure_ascii=False), encoding="utf-8")
