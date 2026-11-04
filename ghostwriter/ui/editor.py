"""Abgespeckter RTF/HTML-Editor mit Formatierung und Rechtschreibprüfung."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont, QPageSize, QTextCharFormat, QTextCursor, QTextListFormat
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QSpinBox,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ghostwriter.ui import strings
from ghostwriter.ui.spellcheck import SpellChecker, SpellHighlighter


class ReportEditor(QWidget):
    """Editor mit Werkzeugleiste und Spellcheck."""

    FONT_CHOICES = (
        "Liberation Serif",
        "Liberation Sans",
        "Carlito",
        "Source Serif 4",
        "DejaVu Serif",
        "Noto Serif",
    )

    def __init__(
        self, *, user_dict_path: Path | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._edit = QTextEdit(self)
        self._edit.setAcceptRichText(True)
        self._checker = SpellChecker(user_dict_path)
        self._highlighter = SpellHighlighter(self._edit.document(), self._checker)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        disclaimer = QLabel(strings.DRAFT_DISCLAIMER)
        disclaimer.setWordWrap(True)
        layout.addWidget(disclaimer)
        layout.addWidget(self._build_toolbar())
        layout.addWidget(self._edit)

        self._edit.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._edit.customContextMenuRequested.connect(self._context_menu)

    def _build_toolbar(self) -> QToolBar:
        bar = QToolBar()
        self._font = QComboBox()
        self._font.addItems(list(self.FONT_CHOICES))
        self._font.currentTextChanged.connect(self._apply_font_family)
        bar.addWidget(self._font)

        self._size = QSpinBox()
        self._size.setRange(8, 36)
        self._size.setValue(12)
        self._size.valueChanged.connect(self._apply_font_size)
        bar.addWidget(self._size)

        for label, slot in (
            ("Fett", self._bold),
            ("Kursiv", self._italic),
            ("Unterstrichen", self._underline),
            ("Links", lambda: self._align(Qt.AlignmentFlag.AlignLeft)),
            ("Zentriert", lambda: self._align(Qt.AlignmentFlag.AlignHCenter)),
            ("Blocksatz", lambda: self._align(Qt.AlignmentFlag.AlignJustify)),
            ("Liste", self._bullet),
        ):
            act = QAction(label, self)
            act.triggered.connect(slot)
            bar.addAction(act)

        self._line_spacing = QSpinBox()
        self._line_spacing.setRange(100, 200)
        self._line_spacing.setSuffix("%")
        self._line_spacing.setValue(115)
        self._line_spacing.valueChanged.connect(self._apply_line_spacing)
        bar.addWidget(QLabel("Zeilenabstand"))
        bar.addWidget(self._line_spacing)
        return bar

    def set_html(self, html: str) -> None:
        self._edit.setHtml(html)

    def to_html(self) -> str:
        return self._edit.toHtml()

    def page_count_estimate(self) -> int:
        """Schätzt A4-Seiten über QPrinter-Paginierung."""
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        doc = self._edit.document()
        doc.setPageSize(printer.pageRect(QPrinter.Unit.DevicePixel).size())
        return max(1, doc.pageCount())

    def export_pdf(self, path: Path) -> None:
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(path))
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        self._edit.document().print_(printer)

    def export_odt(self, path: Path) -> None:
        from PySide6.QtGui import QTextDocumentWriter

        writer = QTextDocumentWriter(str(path))
        writer.setFormat(b"odf")
        writer.write(self._edit.document())

    def _apply_font_family(self, family: str) -> None:
        fmt = QTextCharFormat()
        fmt.setFontFamilies([family])
        self._merge(fmt)

    def _apply_font_size(self, size: int) -> None:
        fmt = QTextCharFormat()
        fmt.setFontPointSize(float(size))
        self._merge(fmt)

    def _bold(self) -> None:
        fmt = QTextCharFormat()
        weight = (
            QFont.Weight.Normal
            if self._edit.fontWeight() == QFont.Weight.Bold
            else QFont.Weight.Bold
        )
        fmt.setFontWeight(weight)
        self._merge(fmt)

    def _italic(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self._edit.fontItalic())
        self._merge(fmt)

    def _underline(self) -> None:
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self._edit.fontUnderline())
        self._merge(fmt)

    def _align(self, alignment: Qt.AlignmentFlag) -> None:
        self._edit.setAlignment(alignment)

    def _bullet(self) -> None:
        cursor = self._edit.textCursor()
        cursor.createList(QTextListFormat.Style.ListDisc)

    def _apply_line_spacing(self, percent: int) -> None:
        cursor = self._edit.textCursor()
        block_fmt = cursor.blockFormat()
        # QTextBlockFormat.ProportionalHeight == 1
        block_fmt.setLineHeight(float(percent), 1)
        cursor.mergeBlockFormat(block_fmt)

    def _merge(self, fmt: QTextCharFormat) -> None:
        cursor = self._edit.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        cursor.mergeCharFormat(fmt)
        self._edit.mergeCurrentCharFormat(fmt)

    def _context_menu(self, pos) -> None:  # type: ignore[no-untyped-def]
        menu = self._edit.createStandardContextMenu()
        cursor = self._edit.cursorForPosition(pos)
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        word = cursor.selectedText()
        if word and not self._checker.check(word):
            menu.addSeparator()
            for suggestion in self._checker.suggest(word):
                act = menu.addAction(suggestion)
                act.triggered.connect(lambda _=False, s=suggestion, c=cursor: self._replace(c, s))
            add = menu.addAction(strings.SPELL_ADD)
            add.triggered.connect(lambda: self._checker.add(word))
        menu.exec(self._edit.mapToGlobal(pos))

    def _replace(self, cursor: QTextCursor, text: str) -> None:
        cursor.insertText(text)
