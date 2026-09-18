"""Dialog to confirm raw metadata (size, bit depth, Bayer pattern) when importing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fast_openisp.config import BAYER_PATTERNS
from fast_openisp.io.loaders import ByteOrder, raw_size_candidates


@dataclass(frozen=True)
class ImportSettings:
    width: int
    height: int
    bit_depth: int
    bayer_pattern: str
    byte_order: ByteOrder = "little"
    remember: bool = False


class ImportDialog(QDialog):
    """``headerless=True`` for .raw files (editable size, file-size check), else TIFF."""

    def __init__(
        self,
        path: Path,
        defaults: ImportSettings,
        *,
        headerless: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Import {path.name}")
        self.headerless = headerless
        self.file_size = path.stat().st_size if headerless else 0

        layout = QVBoxLayout(self)
        intro = QLabel(
            "Headerless raw file: confirm the sensor layout."
            if headerless
            else "Single-channel TIFF: confirm the bit depth (inferred from the data) and "
            "Bayer pattern."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        self.width_spin = QSpinBox()
        self.width_spin.setRange(2, 65536)
        self.width_spin.setValue(defaults.width)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(2, 65536)
        self.height_spin.setValue(defaults.height)
        self.width_spin.setEnabled(headerless)
        self.height_spin.setEnabled(headerless)
        self.bit_depth = QSpinBox()
        self.bit_depth.setRange(8, 16)
        self.bit_depth.setSuffix(" bit")
        self.bit_depth.setValue(defaults.bit_depth)
        self.pattern = QComboBox()
        for pattern in BAYER_PATTERNS:
            self.pattern.addItem(pattern.upper(), pattern)
        self.pattern.setCurrentIndex(max(0, self.pattern.findData(defaults.bayer_pattern)))
        self.byte_order = QComboBox()
        self.byte_order.addItem("Little endian", "little")
        self.byte_order.addItem("Big endian", "big")
        self.byte_order.setCurrentIndex(0 if defaults.byte_order == "little" else 1)

        form.addRow("Width", self.width_spin)
        form.addRow("Height", self.height_spin)
        form.addRow("Bit depth", self.bit_depth)
        form.addRow("Bayer pattern", self.pattern)
        if headerless:
            form.addRow("Byte order", self.byte_order)
            self.suggestions = QComboBox()
            candidates = raw_size_candidates(self.file_size)
            self.suggestions.addItem("–", None)
            for w, h in candidates:
                self.suggestions.addItem(f"{w} × {h}", (w, h))
            self.suggestions.setEnabled(bool(candidates))
            self.suggestions.currentIndexChanged.connect(self._apply_suggestion)
            form.addRow("Matching sizes", self.suggestions)
        layout.addLayout(form)

        self.error = QLabel()
        self.error.setStyleSheet("color: #d04040;")
        self.error.setWordWrap(True)
        layout.addWidget(self.error)

        self.remember = QCheckBox(
            "Don't ask again for files of this size"
            if headerless
            else "Don't ask again for TIFFs of this size"
        )
        layout.addWidget(self.remember)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.width_spin.valueChanged.connect(self._validate)
        self.height_spin.valueChanged.connect(self._validate)
        self._validate()

    def _apply_suggestion(self) -> None:
        size = self.suggestions.currentData()
        if size:
            self.width_spin.setValue(size[0])
            self.height_spin.setValue(size[1])

    def _validate(self) -> None:
        ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        if not self.headerless:
            self.error.clear()
            ok_button.setEnabled(True)
            return
        expected = self.width_spin.value() * self.height_spin.value() * 2
        if expected != self.file_size:
            self.error.setText(
                f"File is {self.file_size:,} bytes; {self.width_spin.value()} × "
                f"{self.height_spin.value()} × 16 bit needs {expected:,} bytes."
            )
            ok_button.setEnabled(False)
        else:
            self.error.clear()
            ok_button.setEnabled(True)

    def settings(self) -> ImportSettings:
        return ImportSettings(
            width=self.width_spin.value(),
            height=self.height_spin.value(),
            bit_depth=self.bit_depth.value(),
            bayer_pattern=str(self.pattern.currentData()),
            byte_order="big" if self.byte_order.currentData() == "big" else "little",
            remember=self.remember.isChecked(),
        )
