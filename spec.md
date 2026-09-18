# fast-openISP GUI — Specification

Status: Draft v0.3 · 2026-09-18

## 1. Goal

A Windows desktop application (shipped as a `.exe`) for the fast-openISP software ISP.
The user loads a raw image (file dialog or drag & drop), toggles individual ISP modules
on/off, tunes their parameters, sees the result live, compares before/after, and exports
the result as PNG or JPEG.

## 2. Decisions

| Topic | Decision |
|---|---|
| Platform | **Windows 10/11 x64 only** |
| Distribution | **Single-file Windows exe** built with PyInstaller `--onefile` (see §13) |
| Python | `requires-python = ">=3.13"`; `.python-version` pinned to **3.13** (PySide6, rawpy and PyInstaller all well supported) |
| GUI toolkit | **PySide6** (Qt 6) |
| Parameter editing | Full per-module parameter editing, generated from typed parameter models; load/save YAML config |
| Config validation | **Pydantic v2** validates every YAML config on load (and every GUI edit) |
| Default colour | Identity CCM + grey-world AWB for sensors without calibration (e.g. mikros110) |
| Headerless `.raw` metadata | Pre-filled from the active config's `hardware` section, confirmed/overridden in an import dialog |
| Inputs | Headerless `.raw`, single-channel Bayer `.tif/.tiff`, `.dng` |
| Processing | Debounced auto re-run in a background thread on a downscaled preview; full resolution on export |
| Extras in v1 | Before/after compare |
| Module dependencies | Auto-disable dependents (greyed out, tooltip explains why) |
| Code layout | Single `src/fast_openisp/` package; free refactoring, **no backwards compatibility** required |
| Tooling | uv, ruff (lint + format), ty (type check), mkdocs (docs), pytest (tests) |
| Out | RGB-IR sensors, `.npz`/`.pgm` input, macOS/Linux |

## 3. Reference input: `raw/mikros110.tiff`

Findings from inspecting the file:

| Property | Value |
|---|---|
| Size | 1090 × 1096 (W × H), single page, uncompressed |
| Container | 16-bit greyscale TIFF (`BitsPerSample=16`, `Photometric=MinIsBlack`), written by tifffile |
| Actual data range | 8 … 1023 → **10-bit data, LSB-aligned** in a 16-bit container |
| CFA phases (mean) | (0,0)=224, (0,1)=354, (1,0)=355, (1,1)=338 → **BGGR** (confirmed) |
| Black level | **32 DN** (confirmed). Some pixels read below it (min 8, 0.1 pct ≈ 13) due to read noise; BLC clips these to 0 |

Consequences for the spec:
- `BitsPerSample` alone is not a reliable bit depth. The TIFF loader **infers bit depth
  from the data** (`ceil(log2(max + 1))`, clamped to 8–16) and pre-fills the import dialog
  with it; the user can override.
- A bundled `configs/mikros110.yaml` is added and used for the regression/acceptance tests:
  1090×1096, 10-bit, `bggr`, black level 32 DN on all channels,
  **identity CCM**, **AWB in `grey_world` mode**, other modules at `test.yaml` defaults.
- Dimensions are even, but loaders must still handle odd sizes by cropping the last
  row/column (CFA pipeline assumes even dimensions).

## 4. Project structure

```
fast-openISP/
├── pyproject.toml            # uv-managed, hatchling build backend
├── uv.lock
├── .python-version           # 3.13
├── mkdocs.yml
├── fast_openisp.spec         # PyInstaller spec
├── docs/
│   ├── index.md
│   ├── getting-started.md    # install exe / run from source with uv
│   ├── gui.md                # user guide with screenshots
│   ├── modules.md            # ISP module reference (generated from param models)
│   ├── development.md        # uv, ruff, ty, tests, building the exe
│   └── api.md                # mkdocstrings API reference
├── src/fast_openisp/
│   ├── __init__.py
│   ├── pipeline.py
│   ├── config.py             # typed config models + YAML load/save (replaces utils/yacs.py)
│   ├── modules/              # one file per ISP module
│   │   ├── base.py           # ISPModule base class, registry, dependency declaration
│   │   └── dpc.py … scl.py
│   ├── configs/              # bundled YAML configs (package data)
│   ├── io/
│   │   ├── loaders.py        # raw / tiff / dng → RawImage
│   │   └── export.py         # png / jpg writers
│   ├── cli.py                # batch CLI (no Qt import)
│   └── gui/
│       ├── __main__.py       # `python -m fast_openisp.gui`
│       ├── app.py            # QApplication bootstrap, main()
│       ├── main_window.py
│       ├── module_panel.py   # module list with enable toggles + param editors
│       ├── param_widgets.py  # widget factory driven by param models
│       ├── image_view.py     # zoom/pan viewer + before/after compare
│       ├── import_dialog.py  # raw metadata dialog
│       ├── export_dialog.py
│       ├── worker.py         # background pipeline runner
│       ├── state.py          # document model: image, config, dirty flag
│       └── resources/        # app icon (.ico), drop-zone graphics
├── tests/
└── raw/                      # sample data (not packaged into the exe)
```

`pipeline.py`, `demo.py`, `main.py`, `utils/` and the root `modules/`/`configs/` are
moved or deleted; `demo.py` is replaced by the CLI.

## 5. Library refactor

Refactoring is allowed where it helps the GUI, typing, or clarity:

- **Typed config** (`config.py`): replace the custom yacs `Config` with Pydantic v2 models.
  Pydantic is the single source of truth for YAML checking:
  - `IspConfig.model_validate(yaml.safe_load(...))` on every load; models use
    `extra="forbid"` so typos in keys are errors, not silently ignored.
  - Cross-field validators: Bayer pattern valid, black levels < 2^bit_depth, image
    dimensions even, CCM shape 3×4, module order fixed, enabled modules satisfy
    dependencies (warning in GUI, error in CLI).
  - Validation errors are reported with the YAML path (e.g. `modules.awb.params.r_gain:
    Input should be less than or equal to 8.0`) in a GUI dialog / CLI stderr.
  - A JSON Schema is exported (`fast-openisp schema > config.schema.json`) so editors like
    VS Code can validate/autocomplete YAML configs.
  - `HardwareConfig` (width, height, bit_depth, bayer_pattern as `Literal`).
  - One `Params` model per module with `Field(ge=, le=, description=, json_schema_extra={"unit": "×1024"})`.
    These constraints drive the GUI widgets (ranges, step, tooltips, units), so no separate
    GUI schema file is needed.
  - `IspConfig` = hardware + ordered `modules: dict[name, ModuleConfig(enabled, params)]`.
  - YAML load/save with round-trip of module order. Existing YAML format may change;
    bundled configs are migrated.
  - Fixed-point parameters (`×1024`, `×256`) become real numbers in the YAML and GUI
    (e.g. gain `1.586`, CCM entries `1.25`); modules convert to fixed point internally,
    so numerical output is unchanged.
- **AWB modes**: `awb.mode: manual | grey_world`.
  - `grey_world`: gains computed per run from the black-level-corrected Bayer planes:
    `r_gain = mean(G) / mean(R)`, `b_gain = mean(G) / mean(B)`, `gr_gain = gb_gain = 1`
    (G = mean of Gr and Gb), excluding pixels within 2 % of saturation. Because preview
    downscaling is block averaging, the preview's plane means match the full-res means
    (up to the saturation mask), so preview and export use effectively the same gains.
  - The GUI shows the computed gains read-only, with a **"Freeze as manual"** button that
    copies them into manual mode.
- **CNF gains** are no longer separate parameters: CNF reads the effective R/B gains
  that AWB used for the current run (this replaces the YAML anchor link).
- **CCM default**: identity (`[[1,0,0,0],[0,1,0,0],[0,0,1,0]]`) for configs without
  calibration; a "Reset to identity" button in the CCM editor.
- **Modules** (`modules/base.py`):
  - `ISPModule` abstract base with `name`, `full_name`, `requires: tuple[str, ...]`,
    `Params` type, and `execute(data: PipelineData) -> None`.
  - Registry built by explicit list in pipeline order (no dynamic `importlib` / `sys.path`
    manipulation — keeps PyInstaller happy).
  - `PipelineData`: a typed dataclass (`bayer`, `rgb_image`, `y_image`, `cbcr_image`,
    `edge_map`, …) instead of an untyped dict.
- **Pipeline**:
  - `Pipeline(config).execute(bayer, *, progress=None, cancel=None) -> np.ndarray` returning
    uint8 RGB. `progress(module_name, index, total)` callback; `cancel()` checked between modules.
  - Saturation-value computation moves into a pure function.
  - Dependency validation exposed as `resolve_enabled(config) -> set[str]` for the GUI.
  - Remove multiprocessing `batch_run` (the CLI loops; parallelism is not needed for v1).
- Numerical output must stay identical to the current implementation for the same
  parameters (regression test, §14).

## 6. Dependencies (pyproject.toml)

- Runtime: `numpy`, `opencv-python-headless`, `pyyaml`, `scikit-image` (drop if unused
  after refactor), `pydantic`, `PySide6-Essentials` (smaller than full PySide6), `tifffile`,
  `rawpy`.
- Dev group: `ruff`, `ty`, `pytest`, `pytest-qt`, `pyinstaller`.
- Docs group: `mkdocs`, `mkdocs-material`, `mkdocstrings[python]`.
- Entry points:
  - `[project.gui-scripts] fast-openisp-gui = "fast_openisp.gui.app:main"`
  - `[project.scripts] fast-openisp = "fast_openisp.cli:main"`

## 7. Input handling

All loaders return:

```python
@dataclass(frozen=True)
class RawImage:
    bayer: np.ndarray  # (H, W) uint16, even dims
    bit_depth: int  # e.g. 10, 12, 14
    bayer_pattern: BayerPattern  # "rggb" | "bggr" | "grbg" | "gbrg"
    black_level: tuple[int, int, int, int] | None  # r, gr, gb, b (DNG only)
    as_shot_wb: tuple[float, float, float] | None  # DNG only
    source_path: Path
```

| Format | Extension(s) | Loader | Metadata source |
|---|---|---|---|
| Headerless raw | `.raw` | `np.fromfile(dtype=uint16)` | Import dialog pre-filled from config `hardware` (width, height, bit depth, Bayer pattern, byte order). File-size mismatch shows an inline error and suggests matching resolutions. |
| Bayer TIFF | `.tif`, `.tiff` | `tifffile` | Width/height from TIFF; bit depth **inferred from data** (see §3); Bayer pattern from config. Confirmed in the import dialog. Multi-channel / multi-page / float TIFFs are rejected with a clear message. MSB-aligned data (values multiples of 2^(16−n)) is detected and shifted down. |
| DNG | `.dng` | `rawpy` (`raw_image_visible`) | Dimensions, CFA pattern, black levels, white level (→ bit depth), as-shot WB. Non-Bayer DNGs (linear/demosaiced, X-Trans) are rejected. No dialog. |

- Import dialog has "Don't ask again for files of this size" which remembers the
  metadata per (extension, width, height) in `QSettings`.
- For DNG, metadata is applied to the working config (`hardware.*`, `blc.*`); a checkbox
  "Use as-shot white balance" writes AWB gains.

### Drag & drop
- Main window accepts a single dropped file with a supported extension; a highlight
  overlay is shown while dragging.
- Dropping a `.yaml` loads it as the active config.
- Unsupported files → status-bar message, ignored. Multiple files → first supported one.
- Files can also be opened by dropping onto the `.exe` / passing a path on the command line.

## 8. Main window layout

```
┌───────────────────────────────────────────────────────────────────────────┐
│ File  Config  View  Help                                                  │
├──────────────────────┬────────────────────────────────────────────────────┤
│ Config: mikros110  ▾ │                                                    │
│ ──────────────────── │                                                    │
│ ☑ DPC  Dead pixel    │                                                    │
│ ☑ BLC  Black level  ▸│            Image view (zoom / pan)                 │
│ ☑ AAF  Anti-alias    │         [ Processed | Before | Split ]             │
│ ☑ AWB  White bal.   ▾│                                                    │
│    Mode [grey world▾]│                                                    │
│    R 1.586  B 1.953  │                                                    │
│ ☑ CNF ...            │                                                    │
│ ...                  │                                                    │
│ [Reset module]       │                                                    │
├──────────────────────┴────────────────────────────────────────────────────┤
│ mikros110.tiff · 1090×1096 · 10-bit BGGR · preview 1:1 · 184 ms  [Export] │
└───────────────────────────────────────────────────────────────────────────┘
```

- **Left dock – Module panel**: all modules in fixed pipeline order
  (DPC, BLC, AAF, AWB, CNF, CFA, CCM, GAC, CSC, NLM, BNF, CEH, EEH, FCS, HSC, BCC, SCL).
  Each row: enable checkbox, short name, full name, expand arrow for parameters,
  per-module "Reset" button.
- **Center – Image view**: `QGraphicsView`; fit-to-window, 100%, wheel zoom, drag to pan,
  pixel coordinates + value under cursor in the status bar.
  Empty state: "Drop a .raw, .tif or .dng file here".
- **Status bar**: file name, dimensions, bit depth, Bayer pattern, preview scale,
  last run duration, busy indicator, **Export** button.
- **Menus**:
  - File: Open… (Ctrl+O), Export… (Ctrl+E), Recent files, Quit.
  - Config: bundled configs, Load YAML…, Save YAML (Ctrl+S), Save YAML As…, Revert.
  - View: Fit (Ctrl+0), 100% (Ctrl+1), Processed / Before / Split, Full-res preview.
  - Help: About (version, licenses), Documentation (opens hosted/bundled mkdocs site).
- Window geometry, last config, last directories and recent files persist via `QSettings`.
- Light/dark follows the Windows theme (Qt 6 Fusion + system palette).

## 9. Module enable/disable & dependencies

- Dependencies come from each module's `requires`. Current graph:
  - CSC → GAC
  - NLM, BNF, CEH, EEH, HSC, BCC → CSC
  - FCS → CSC, EEH
- Disabling a module auto-disables and greys out all transitive dependents; tooltip e.g.
  "Requires CSC (disabled)". Dependents' previous state is remembered and restored when
  the prerequisite is re-enabled.
- With CFA disabled, the Bayer data is shown as greyscale.

## 10. Parameter editing

Widgets are generated from each module's Pydantic `Params` model:

| Field type | Widget |
|---|---|
| `int` with bounds | `QSpinBox` (+ slider when range is bounded) |
| `float` with bounds | `QDoubleSpinBox` + slider |
| `bool` | `QCheckBox` |
| `Literal[...]` / `Enum` (e.g. `cfa.mode`) | `QComboBox` |
| fixed-length tuple (e.g. `ceh.tiles`) | row of spin boxes |
| matrix (e.g. `ccm.ccm` 3×4) | grid of spin boxes, with "rows sum to 1.0" indicator |
| no params | "No parameters" label |

- Field `description` → tooltip; `unit` extra → suffix.
- Invalid input is impossible by construction (bounded widgets); model validation errors
  are still shown inline.
- Every edit marks the config dirty (`*` in title) and schedules a re-run.
- Real-number display for all fixed-point params (e.g. AWB gain 1.586, not 1624).

## 11. Processing model

- The worker receives an immutable snapshot of the config (Pydantic `model_copy(deep=True)`)
  and builds a fresh `Pipeline` per run.
- Runs execute on a `QThreadPool` worker; the UI never blocks.
- **Debounce** 250 ms after the last edit. A newer request cancels the running one
  (cancel flag checked between modules) and stale results are dropped via a generation counter.
- **Preview**: the Bayer input is downscaled by an integer factor so the longest edge ≤
  **1024 px** (configurable in settings), preserving the CFA layout (per-plane block averaging, then
  re-mosaicked); preview config dimensions are adjusted accordingly. At 1090×1096 the
  reference image is processed at factor 2.
  - Spatial filters (NLM, BNF, EEH, DPC) behave differently at preview scale; a
    "Full-res preview" toggle forces full-resolution runs.
- **Before image** is cached per loaded file (does not depend on parameters).
- Module errors are caught, shown in a dismissible banner, and the last good image stays.

## 12. Before/after compare

- **Before** = input Bayer, black-level-free linear scaling to 8-bit, fast OpenCV
  bilinear demosaic, simple 2.2 gamma for visibility — no other processing.
- View modes: *Processed*, *Before*, *Split* (draggable vertical divider).
  Holding `B` temporarily shows Before.
- Zoom/pan is synchronised across modes.

## 13. Export & Windows executable

### Image export
- **Export** button (status bar), File → Export…, Ctrl+E → export dialog:
  format (PNG / JPEG), JPEG quality (default 95), "Save config alongside" checkbox.
- Default name `<input-stem>.png` in the last export directory.
- Export runs the pipeline at **full resolution** in the worker with a cancellable
  progress dialog.
- PNG: 8-bit RGB. JPEG: 4:4:4 chroma. Written via OpenCV (`imencode` + `Path.write_bytes`
  so non-ASCII Windows paths work).
- "Save config alongside" writes `<name>.yaml` for reproducibility.

### Windows exe
- Built with **PyInstaller `--onefile`** from `fast_openisp.spec` → a single
  `dist/fast-openISP.exe`.
  - Windowed (no console), app icon, version resource from the `pyproject.toml` version.
  - Bundles `fast_openisp/configs/*.yaml` as data, resolved at runtime via
    `importlib.resources` (works both from source and from the `_MEIPASS` temp dir).
  - Excludes unused Qt modules (WebEngine, QML/Quick, Multimedia, 3D) and unused Qt
    plugins/translations; UPX disabled (it breaks Qt DLLs and triggers antivirus).
    Target exe size < 120 MB.
  - Start-up: a one-file exe unpacks to `%TEMP%` on every launch (~2–4 s for Qt). A
    **PyInstaller splash screen** is shown during unpacking and closed
    (`pyi_splash.close()`) once the main window is up.
- Build command: `uv run pyinstaller fast_openisp.spec --noconfirm`, wrapped in
  `scripts/build_exe.ps1` which also runs the smoke test below.
- Smoke test: `fast-openISP.exe --self-test` runs the pipeline on synthetic
  mikros110-sized BGGR data, writes a PNG to temp, and exits 0.
- Known risk: unsigned one-file PyInstaller exes are sometimes flagged by Windows
  Defender/SmartScreen; code signing is out of scope for v1 but the spec keeps the
  build reproducible so signing can be added later.
- Optional (not v1): code signing, installer, `.tiff/.dng` file associations.

## 14. Quality & tooling

- **Format/lint**: `uv run ruff format`, `uv run ruff check`; rules `E, F, I, UP, B, SIM,
  NPY, PTH, RUF`; line length 100; target `py313`.
- **Types**: `uv run ty check` must pass for the whole `src/` tree (the refactor removes
  the untyped yacs config and dict dataflow).
- **Tests**: `uv run pytest`, GUI smoke tests with `pytest-qt` (`QT_QPA_PLATFORM=offscreen`).
  - Regression: before refactoring, golden PNGs are generated with the current code for
    `configs/test.yaml` + `raw/test.RAW` and for `mikros110.tiff`; the refactored pipeline
    must reproduce them bit-identically.
  - Loaders: raw size mismatch, TIFF bit-depth inference (10-bit in 16-bit container),
    MSB-aligned detection, multi-channel rejection, DNG metadata mapping.
  - Config: YAML round-trip, Pydantic validation errors (unknown key, out-of-range, bad CCM shape).
  - Grey-world AWB: known gains recovered on synthetic data; preview and full-res gains equal.
  - Dependencies: disabling GAC disables CSC and all dependents; re-enable restores state.
  - Preview downscale preserves CFA phase statistics.
  - GUI: drop file → image shown; toggle module → re-run; export writes a file.
- **Docs**: `uv run mkdocs serve` / `uv run mkdocs build --strict`; module reference
  generated from the Pydantic models.
- CI (GitHub Actions, `windows-latest`): ruff, ty, pytest, mkdocs build, PyInstaller build
  + `--self-test`, upload the exe as artifact.

## 15. Resolved decisions

Resolved: mikros110 is BGGR with black level 32 DN; identity CCM + grey-world AWB by default; Pydantic validates
YAML; preview max edge 1024 px; single-file exe; CNF follows AWB gains; fixed-point params
shown as real numbers.

No open questions remain.

## 16. Acceptance criteria

1. The single `fast-openISP.exe` launches on a clean Windows 11 machine without Python installed.
2. Dropping `raw/mikros110.tiff` opens the import dialog pre-filled with 1090×1096, 10-bit
   and BGGR; confirming shows a grey-world balanced, identity-CCM a processed preview in < 1 s.
3. Dropping `raw/test.RAW` (with `test.yaml`) and a Bayer DNG shows processed previews;
   DNG metadata appears in the status bar and config.
4. Unchecking a module re-runs the pipeline and updates the image; unchecking CSC greys
   out NLM, BNF, CEH, EEH, FCS, HSC, BCC.
5. Editing a parameter (e.g. GAC gamma) updates the preview after the debounce.
6. Split view shows before/after with a draggable divider.
7. Export produces full-resolution PNG and JPEG identical to `fast-openisp` CLI output for
   the same config.
8. Loading a YAML with an unknown key or out-of-range value shows a Pydantic validation
   error naming the offending field; nothing is applied.
9. `ruff format --check`, `ruff check`, `ty check`, `pytest`, `mkdocs build --strict`, and
   the exe self-test all pass.

## 17. Out of scope (v1)

Batch processing in the GUI, intermediate-result viewer, per-module timing panel,
RGB-IR / X-Trans / non-Bayer sensors, `.npz`/`.pgm` input, histogram/scopes, undo/redo,
GPU acceleration, macOS/Linux, installer and code signing.
