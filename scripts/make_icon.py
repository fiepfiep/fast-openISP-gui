"""Generate the application icon (a stylised 2×2 Bayer cell) as PNG and ICO."""

import sys
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPainterPath

OUT = Path(__file__).resolve().parents[1] / "src" / "fast_openisp" / "gui" / "resources"


def render(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    margin = size * 0.06
    cell = (size - 2 * margin) / 2
    gap = max(1.0, size * 0.03)
    colors = ["#e0433a", "#3fb04f", "#3fb04f", "#3a74e0"]  # R, G / G, B
    for index, color in enumerate(colors):
        x = margin + (index % 2) * cell
        y = margin + (index // 2) * cell
        path = QPainterPath()
        path.addRoundedRect(
            QRectF(x + gap / 2, y + gap / 2, cell - gap, cell - gap), size * 0.08, size * 0.08
        )
        painter.fillPath(path, QColor(color))
    painter.end()
    return image


def render_splash(width: int = 480, height: int = 240) -> QImage:
    """Splash screen shown by the one-file exe while it unpacks."""
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#1f2430"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.drawImage(QRectF(32, 56, 128, 128), render(256))
    font = QFont("Segoe UI", 26, QFont.Weight.DemiBold)
    painter.setFont(font)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(QRectF(184, 70, width - 200, 50), Qt.AlignmentFlag.AlignLeft, "fast-openISP")
    painter.setFont(QFont("Segoe UI", 11))
    painter.setPen(QColor("#aab2c0"))
    painter.drawText(
        QRectF(186, 122, width - 200, 30),
        Qt.AlignmentFlag.AlignLeft,
        "Software image signal processor",
    )
    painter.setPen(QColor("#ffffff"))
    painter.drawText(
        QRectF(186, 146, width - 200, 24), Qt.AlignmentFlag.AlignLeft, "Author: Philippe Baetens"
    )
    painter.setFont(QFont("Segoe UI", 8))
    painter.setPen(QColor("#8a93a3"))
    painter.drawText(
        QRectF(186, 170, width - 200, 20),
        Qt.AlignmentFlag.AlignLeft,
        "Based on fast-openISP by Qiu Jueqin and openISP",
    )
    painter.end()
    return image


def main() -> int:
    # Needs a real platform plugin (not offscreen) so fonts are available for the splash
    QGuiApplication(sys.argv)
    OUT.mkdir(parents=True, exist_ok=True)
    render(256).save(str(OUT / "icon.png"))
    render_splash().save(str(OUT / "splash.png"))
    # Qt's ICO writer stores a single size; 256 px scales well on Windows
    if not render(256).save(str(OUT / "icon.ico")):
        print("ICO writer unavailable", file=sys.stderr)
        return 1
    print(f"Wrote icons to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
