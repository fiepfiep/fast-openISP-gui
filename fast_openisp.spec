# PyInstaller spec: single-file, windowed fast-openISP.exe
# Build with:  uv run pyinstaller fast_openisp.spec --noconfirm --clean
# ruff: noqa
import re
from pathlib import Path

from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VarFileInfo,
    VarStruct,
    VSVersionInfo,
)

ROOT = Path(SPECPATH)
PACKAGE = ROOT / "src" / "fast_openisp"
RESOURCES = PACKAGE / "gui" / "resources"

version_text = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
VERSION = re.search(r'__version__ = "([^"]+)"', version_text).group(1)
numbers = tuple(int(part) for part in (VERSION.split(".") + ["0"] * 4)[:4])

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=numbers, prodvers=numbers),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    "040904B0",
                    [
                        StringStruct("CompanyName", "fast-openISP"),
                        StringStruct("FileDescription", "fast-openISP image signal processor"),
                        StringStruct("FileVersion", VERSION),
                        StringStruct("InternalName", "fast-openISP"),
                        StringStruct("OriginalFilename", "fast-openISP.exe"),
                        StringStruct("ProductName", "fast-openISP"),
                        StringStruct("ProductVersion", VERSION),
                        StringStruct("LegalCopyright", "MIT license"),
                    ],
                )
            ]
        ),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

# Qt modules the app does not use (PySide6-Essentials already omits most add-ons)
EXCLUDES = [
    "tkinter",
    "PySide6.QtNetwork",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPdf",
    "PySide6.QtSvg",
    "PySide6.QtXml",
    "PySide6.QtDBus",
    "PySide6.QtConcurrent",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtUiTools",
    "PySide6.QtMultimedia",
    "PySide6.QtWebEngineCore",
    "PySide6.Qt3DCore",
    "matplotlib",
    "IPython",
    "pytest",
]

# Large Qt files that a widgets-only app does not need
DROP_PATTERNS = (
    "opengl32sw.dll",  # software OpenGL fallback (~20 MB)
    "PySide6/translations",
    "PySide6\\translations",
    "Qt6Quick",
    "Qt6Qml",
    "Qt6Pdf",
    "Qt6Network",
    "Qt6VirtualKeyboard",
)

a = Analysis(
    [str(PACKAGE / "gui" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    datas=[
        (str(PACKAGE / "configs" / "*.yaml"), "fast_openisp/configs"),
        (str(RESOURCES / "icon.png"), "fast_openisp/gui/resources"),
    ],
    hiddenimports=["fast_openisp.selftest"],
    excludes=EXCLUDES,
    noarchive=False,
)
a.binaries = [b for b in a.binaries if not any(p in b[0] for p in DROP_PATTERNS)]
a.datas = [d for d in a.datas if not any(p in d[0] for p in DROP_PATTERNS)]

pyz = PYZ(a.pure)

splash = Splash(
    str(RESOURCES / "splash.png"),
    binaries=a.binaries,
    datas=a.datas,
    text_pos=(186, 200),
    text_size=9,
    text_color="#aab2c0",
    minify_script=True,
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    splash,
    splash.binaries,
    name="fast-openISP",
    icon=str(RESOURCES / "icon.ico"),
    version=version_info,
    console=False,
    upx=False,
    debug=False,
    strip=False,
    runtime_tmpdir=None,
)
