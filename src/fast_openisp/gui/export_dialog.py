"""Export options: file path, format, JPEG quality, save config alongside."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

FORMATS = {"png": ("PNG image", ".png"), "jpg": ("JPEG image", ".jpg")}


@dataclass(frozen=True)
class ExportOptions:
    path: Path
    jpeg_quality: int
    save_config: bool


class ExportDialog(QDialog):
    def __init__(
        self,
        default_path: Path,
        *,
        jpeg_quality: int = 95,
        save_config: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export image")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        info = QLabel("The image is processed at full resolution before it is saved.")
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QFormLayout()
        self.format = QComboBox()
        for key, (label, _suffix) in FORMATS.items():
            self.format.addItem(label, key)
        suffix = default_path.suffix.lower()
        self.format.setCurrentIndex(1 if suffix in (".jpg", ".jpeg") else 0)

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(str(default_path))
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse)

        quality_row = QHBoxLayout()
        self.quality = QSlider(Qt.Orientation.Horizontal)
        self.quality.setRange(50, 100)
        self.quality.setValue(jpeg_quality)
        self.quality_label = QLabel(str(jpeg_quality))
        self.quality_label.setMinimumWidth(28)
        self.quality.valueChanged.connect(lambda v: self.quality_label.setText(str(v)))
        quality_row.addWidget(self.quality, 1)
        quality_row.addWidget(self.quality_label)

        self.save_config = QCheckBox("Save the configuration alongside (.yaml)")
        self.save_config.setChecked(save_config)

        form.addRow("Format", self.format)
        form.addRow("File", path_row)
        form.addRow("JPEG quality", quality_row)
        layout.addLayout(form)
        layout.addWidget(self.save_config)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.format.currentIndexChanged.connect(self._format_changed)
        self._format_changed()

    def _suffix(self) -> str:
        return FORMATS[str(self.format.currentData())][1]

    def _format_changed(self) -> None:
        self.quality.setEnabled(self._suffix() == ".jpg")
        path = Path(self.path_edit.text())
        if path.name and path.suffix.lower() not in (self._suffix(), ".jpeg"):
            self.path_edit.setText(str(path.with_suffix(self._suffix())))

    def _browse(self) -> None:
        filters = "PNG image (*.png);;JPEG image (*.jpg *.jpeg)"
        selected = "JPEG image (*.jpg *.jpeg)" if self._suffix() == ".jpg" else "PNG image (*.png)"
        path, chosen = QFileDialog.getSaveFileName(
            self, "Export image", self.path_edit.text(), filters, selected
        )
        if path:
            self.format.setCurrentIndex(1 if chosen.startswith("JPEG") else 0)
            self.path_edit.setText(path)
            self._format_changed()

    def options(self) -> ExportOptions:
        path = Path(self.path_edit.text())
        if path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            path = path.with_suffix(self._suffix())
        return ExportOptions(
            path=path, jpeg_quality=self.quality.value(), save_config=self.save_config.isChecked()
        )
