# Release notes

## v0.2.0 — first GUI release

The first release of **fast-openISP GUI**: a Windows desktop application and Python package
built on [fast-openISP](https://github.com/QiuJueqin/fast-openISP) by Qiu Jueqin and
[openISP](https://github.com/cruxopen/openISP).

**Download:** `fast-openISP-0.2.0-win64.zip`. Unzip it and run `fast-openISP.exe`; Python
does not need to be installed.

The zip contains:

| Path | Content |
|---|---|
| `fast-openISP.exe` | The application (single file, about 86 MB) |
| `README.txt` | Quick start |
| `configs/` | Bundled YAML configurations: `mikros110`, `mira220_rgb`, `test`, `nikon_d3x`, `nikon_d3200` |
| `raw/` | Sample images: `mikros110.tiff` (10-bit BGGR), `test.RAW` (10-bit RGGB), `mira220_rgb.dng` (12-bit GRBG) |

### New: desktop GUI

- **Open images** from the file menu, the recent-files list, or by **drag and drop**:
    - headerless `.raw`
    - single-channel Bayer `.tif` / `.tiff` (bit depth worked out from the data)
    - `.dng` (Bayer pattern, black level, bit depth and as-shot white balance read from the file)
- **Import dialog** for `.raw` and `.tif`:
    - confirms size, bit depth, Bayer pattern and byte order
    - checks the file size and suggests matching resolutions
    - can remember answers per file size
- **Enable or disable any of the 17 ISP modules.** Modules that depend on another one are
  switched off and greyed out automatically, and come back as you had them when it is
  re-enabled.
- **Edit every parameter** with controls generated from the configuration schema (number
  boxes, drop-down lists and a 3 × 4 colour matrix editor), with range checks and
  per-module reset.
- **Live preview:** processing runs in the background on a Bayer-preserving downscale
  (longest edge 1024 px, adjustable) and restarts 250 ms after each edit. An optional
  full-resolution preview is available.
- **Before/after comparison:**
    - Processed / Before / Split view (F2 / F3 / F4), with a draggable divider
    - hold **B** to show the input temporarily
- **Export** to PNG or JPEG (quality setting, 4:4:4) at full resolution, with progress and
  cancel, and optionally the YAML config alongside.
- **Sensor panel** to change the bit depth and Bayer pattern of the loaded image.
- **Status bar** with the pixel position and RGB value under the cursor, zoom level, and
  processing time (hover for the slowest modules).
- Remembers the window layout, last config, recent files and folders between sessions.
- Splash screen and About dialog with credits.

### New: processing

- **Grey-world auto white balance** (`awb.mode: grey_world`), ignoring nearly saturated
  pixels, with a **Freeze as manual** button to lock in the estimated gains.
- **CNF follows the AWB gains** that were actually applied, instead of a separate copy in
  the config.
- **New bundled config `mikros110`**: 1090 × 1096, 10-bit BGGR, black level 32, identity
  colour matrix, grey-world AWB.
- Output is **bit-identical** to the original fast-openISP for the same parameters. This is
  checked by regression tests against reference images made with the original code.

### New: command line and Python API

- `fast-openisp run INPUT -c CONFIG -o OUT.png|jpg` processes an image without the GUI.
- `fast-openisp configs` lists the bundled configurations.
- `fast-openisp schema` prints a JSON Schema for editor autocompletion.
- A typed Python API: `Pipeline(config).execute(bayer)` returns the image, the white-balance
  gains applied, and the time spent in each module. It supports progress reporting and
  cancellation.

### Changed (compared with the original fast-openISP)

- **Configuration format.** Configurations are checked with Pydantic: unknown keys and
  out-of-range values are rejected with messages that name the field. Gains and matrices
  are **real numbers** (`r_gain: 1.586`) instead of fixed-point integers (`1624`).
  Configs in the original format are **converted automatically** when loaded.
- Code moved into the `src/fast_openisp` package (`pipeline.py`, `modules/`, `configs/`,
  `io/`, `gui/`). `demo.py` is replaced by the CLI.
- Module dependencies now also cover CFA (CCM, GAC and SCL need demosaicing).
- Modules take the image size from the data, so one config works for both previews and
  full-size images.
- Fixed: the HDR saturation value was computed with the BLC settings even when BLC was
  disabled.
- Python ≥ 3.13; the project is managed with uv; checked with ruff and ty; documentation
  built with mkdocs-material.

### Documentation

Published at <https://fiepfiep.github.io/fast-openISP-gui/>:

- user guide: the GUI, input formats, configuration files, CLI
- **ISP blocks explained**: each block with its equations, based on the openISP design
  document
- module parameter reference generated from the code, and API reference
- developer guide and exe build/release instructions

### Known issues

- The exe is **not code-signed**. Windows SmartScreen may warn: choose *More info → Run
  anyway*. Startup takes a few seconds because the single-file exe unpacks itself first.
- Neighbourhood filters (NLM, BNF, EEH, DPC, AAF) look stronger in the downscaled preview
  than in the full-resolution export. Use *View → Full-resolution preview* to see the exact
  result.
- The CLI does not apply a DNG's as-shot white balance (the GUI does, as a menu option). Use
  a config with suitable AWB gains, or `grey_world` mode.
- NLM is slow at full resolution (about 3 s for a 1.2 MP image).
- Lens shading correction (from openISP) is not implemented. `color_checker.pgm` (PGM) is
  not a supported input format.
- The GUI test suite hangs when all GUI tests run in one session (they pass one by one), so
  CI runs only the regression tests.

### Credits

Author: **Philippe Baetens**. ISP algorithms from
[fast-openISP](https://github.com/QiuJueqin/fast-openISP) by Qiu Jueqin (MIT license), a fast
reimplementation of [openISP](https://github.com/cruxopen/openISP). GUI built with Qt for
Python (PySide6, LGPLv3).
