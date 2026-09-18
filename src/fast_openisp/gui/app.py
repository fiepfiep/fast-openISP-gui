"""Application entry point: ``fast-openisp-gui [FILE]`` / ``fast-openISP.exe [FILE]``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from importlib import resources
from pathlib import Path

from fast_openisp import __version__


def _close_splash() -> None:
    """Close the PyInstaller splash screen, if any."""
    try:
        import pyi_splash  # ty: ignore[unresolved-import]  # only exists in the frozen exe
    except ImportError:
        return
    pyi_splash.close()


def _app_icon():
    from PySide6.QtGui import QIcon

    icon_file = resources.files("fast_openisp.gui") / "resources" / "icon.png"
    return QIcon(str(icon_file)) if icon_file.is_file() else QIcon()


def _self_test() -> int:
    """Run the smoke test. The windowed exe has no console, so results also go to a log file."""
    import tempfile
    import traceback

    log = Path(tempfile.gettempdir()) / "fast-openisp-self-test.log"
    try:
        from fast_openisp.selftest import run_self_test

        message, code = f"self-test passed: {run_self_test()}", 0
    except Exception:
        message, code = f"self-test failed:\n{traceback.format_exc()}", 1
    log.write_text(message + "\n", encoding="utf-8")
    if sys.stdout is not None:
        print(message)
    return code


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fast-openISP", description="fast-openISP GUI")
    parser.add_argument("file", nargs="?", help="Image (.raw/.tif/.dng) or config (.yaml) to open")
    parser.add_argument("--self-test", action="store_true", help="Run a smoke test and exit")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args(argv)

    if args.self_test:
        _close_splash()
        return _self_test()

    from PySide6.QtWidgets import QApplication

    from fast_openisp.gui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv[:1])
    assert isinstance(app, QApplication)
    app.setApplicationName("fast-openISP")
    app.setOrganizationName("fast-openISP")
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setWindowIcon(_app_icon())

    window = MainWindow()
    window.show()
    _close_splash()
    if args.file:
        window.open_path(Path(args.file))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
