"""Deutsche Rechtschreibprüfung (Hunspell via pyenchant)."""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextDocument

WORD_RE = re.compile(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß\-']*")


class SpellChecker:
    """Enchant-basierte Prüfung mit optionalem Benutzerwörterbuch."""

    def __init__(self, user_dict_path: Path | None = None) -> None:
        self._dict = None
        self._user_words: set[str] = set()
        self._user_dict_path = user_dict_path
        try:
            import enchant

            self._dict = enchant.Dict("de_DE")
        except Exception:
            self._dict = None
        if user_dict_path and user_dict_path.is_file():
            self._user_words = {
                line.strip()
                for line in user_dict_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }

    @property
    def available(self) -> bool:
        return self._dict is not None

    def check(self, word: str) -> bool:
        if len(word) < 2:
            return True
        if word in self._user_words:
            return True
        if self._dict is None:
            return True
        return bool(self._dict.check(word))

    def suggest(self, word: str) -> list[str]:
        if self._dict is None:
            return []
        return list(self._dict.suggest(word))[:8]

    def add(self, word: str) -> None:
        self._user_words.add(word)
        if self._user_dict_path is None:
            return
        self._user_dict_path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._user_words
        self._user_dict_path.write_text("\n".join(sorted(existing)) + "\n", encoding="utf-8")


class SpellHighlighter(QSyntaxHighlighter):
    """Unterstreicht unbekannte Wörter rot."""

    def __init__(self, document: QTextDocument, checker: SpellChecker) -> None:
        super().__init__(document)
        self._checker = checker
        self._fmt = QTextCharFormat()
        self._fmt.setUnderlineColor(QColor("#b00020"))
        self._fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)

    def highlightBlock(self, text: str) -> None:
        for match in WORD_RE.finditer(text):
            word = match.group(0)
            if not self._checker.check(word):
                self.setFormat(match.start(), match.end() - match.start(), self._fmt)
