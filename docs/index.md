# fast-openISP

fast-openISP is a software **image signal processor** (ISP) written in Python and NumPy. It
turns raw Bayer sensor data into a finished RGB image, using the same processing stages as
the hardware ISP in a camera: dead pixel correction, black level, white balance, demosaicing,
color correction, gamma, noise reduction, contrast and edge enhancement.

The project has three parts:

- **A desktop GUI for Windows**, shipped as a single `fast-openISP.exe`. You can load a raw
  image, turn each ISP module on or off, tune its parameters, see the result straight away,
  compare before and after, and export to PNG or JPEG.
- **A command-line tool** (`fast-openisp`) for scripted processing.
- **A Python library** (`fast_openisp`) with a typed configuration and pipeline API.

## Features

- Inputs: headerless `.raw`, single-channel Bayer `.tif`/`.tiff`, and `.dng`, opened from a
  dialog or by drag and drop.
- 17 ISP modules. Modules that depend on another module are switched off automatically when
  that module is off.
- Every parameter can be edited, with controls built from the configuration schema.
- Configurations are YAML files, checked with [Pydantic](https://docs.pydantic.dev) when
  loaded.
- Grey-world auto white balance for sensors without a calibration.
- Fast preview: the image is shrunk to a preview size and processed in the background after
  each change. Export always runs at full resolution.
- Before/after comparison with a split view.

## Pipeline

```
Bayer ─► DPC ─► BLC ─► AAF ─► AWB ─► CNF ─► CFA ─► CCM ─► GAC ─► CSC ─► NLM ─► BNF ─► CEH ─► EEH ─► FCS ─► HSC ─► BCC ─► SCL ─► RGB
        └──────────── Bayer domain ────────────┘      └ RGB domain ┘      └──────────────── YCbCr domain ─────────────────┘
```

See [ISP modules](modules.md) for what each stage does and its parameters.

## Credits

**Author:** Philippe Baetens (GUI, packaging, typed configuration, grey-world AWB, DNG/TIFF
support).

This project builds on the original work:

- [fast-openISP](https://github.com/QiuJueqin/fast-openISP) by Qiu Jueqin (MIT license),
  which provides the ISP algorithms. It is a NumPy reimplementation that runs over 300 times
  faster than
- [openISP](https://github.com/cruxopen/openISP), the original open-source ISP pipeline.
