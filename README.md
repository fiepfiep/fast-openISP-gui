# Fast Open Image Signal Processor (fast-openISP)

As told by its name, fast-openISP is a **faster** (and bugs-fixed) re-implementation of
the [openISP](https://github.com/cruxopen/openISP) project.

Compared to C-style code in the official openISP repo, fast-openISP uses pure matrix implementations based on Numpy, and
increases processing speed **over 300 times**.

Here is the running time in my Ryzen 7 1700 8-core 3.00GHz machine with the 1920x1080 input Bayer array:

|Module             |openISP |fast-openISP|
|:-----------------:|:------:|:----------:|
|DPC                |20.57s  |0.29s       |
|BLC                |11.75s  |0.02s       |
|AAF                |16.87s  |0.08s       |
|AWB                |7.54s   |0.02s       |
|CNF                |73.99s  |0.25s       |
|CFA                |40.71s  |0.20s       |
|CCM                |56.85s  |0.06s       |
|GAC                |25.71s  |0.07s       |
|CSC                |60.32s  |0.06s       |
|NLM                |1600.95s|5.37s       |
|BNF                |801.24s |0.75s       |
|CEH<sup>*</sup>    |-       |0.14s       |
|EEH                |68.60s  |0.24s       |
|FCS                |25.07s  |0.08s       |
|HSC                |56.34s  |0.07s       |
|BBC                |27.92s  |0.03s       |
|End-to-end pipeline|2894.41s|7.82s       |

> <sup>*</sup> CEH module is not included in the official openISP pipeline.


# Desktop GUI

This fork adds a Windows desktop GUI (PySide6), shipped as a single `fast-openISP.exe`:

- open headerless `.raw`, single-channel Bayer `.tif`/`.tiff` and `.dng` files, or drag and drop them
- enable/disable each ISP module (dependent modules are switched off automatically)
- edit every parameter, with instant preview on a downscaled image in the background
- before/after split view
- export full-resolution PNG or JPEG
- YAML configs checked with Pydantic; grey-world auto white balance

Full documentation is in [`docs/`](docs/index.md) (`uv run mkdocs serve`).

# Usage

With [uv](https://docs.astral.sh/uv/) (installs Python 3.13 and all dependencies):

```
uv sync
uv run fast-openisp-gui                                   # start the GUI
uv run fast-openisp run raw/mikros110.tiff -c mikros110   # command line → raw/mikros110.png
```

From Python:

```python
from fast_openisp.config import bundled_configs
from fast_openisp.io.loaders import load_tiff
from fast_openisp.pipeline import Pipeline

config = bundled_configs()["mikros110"]
raw = load_tiff("raw/mikros110.tiff", bayer_pattern="bggr")
image = Pipeline(config).execute(raw.bayer).image  # (H, W, 3) uint8 RGB
```

Build the Windows exe with `.\scripts\build_exe.ps1` (see [docs/building.md](docs/building.md)).

# Algorithms

All modules in fast-openISP
reproduce [processing algorithms](https://github.com/cruxopen/openISP/blob/master/docs/Image%20Signal%20Processor.pdf)
in openISP, except for EEH and BCC modules. In addition, a CEH (contrast enhancement) module with [CLAHE](https://en.wikipedia.org/wiki/Adaptive_histogram_equalization#Contrast_Limited_AHE) is 
added into the fast-openISP pipeline.

### EEH (edge enhancement)

The official openISP uses
an [asymmetric kernel](https://github.com/cruxopen/openISP/blob/49de48282e66bdb283779394a23c9c0d6ba238ff/isp_pipeline.py#L150-L164)
to extract edge map. In fast-openISP, however, we use the subtraction between the original and the gaussian filtered
Y-channel as the edge estimation, which reduces the artifact when the enhancement gain is large.

### BCC (brightness & contrast control)

The official openISP enhances the image contrast by pixel-wise enlarging the difference between pixel values and a
constant integer (128). In fast-openISP, we use the median value of the whole frame instead of a constant.


# Parameters

Tunable parameters in fast-openISP are differently named from those in openISP, but they are all self-explained,
and no doubt you can easily tell the counterparts in two repos. All parameters are managed in a yaml
in [`src/fast_openisp/configs`](src/fast_openisp/configs), one file per camera. Gains and matrices are real
numbers (e.g. `r_gain: 1.5`); see [docs/configuration.md](docs/configuration.md) and
[docs/modules.md](docs/modules.md).

# Demo

|Bayer Input|
|:-------------------------:|
|<img src='assets/dpc.jpg' width='580'>| 


|CFA Interpolation|
|:-------------------------:|
|<img src='assets/cfa.jpg' width='580'>| 


|Color Correction|
|:-------------------------:|
|<img src='assets/ccm.jpg' width='580'>| 


|Gamma Correction|
|:-------------------------:|
|<img src='assets/gac.jpg' width='580'>| 


|Non-local Means & Bilateral Filter|
|:-------------------------:|
|<img src='assets/bnf.jpg' width='580'>| 


|Contrast Enhancement|
|:-------------------------:|
|<img src='assets/ceh.jpg' width='580'>| 


|Edge Enhancement|
|:-------------------------:|
|<img src='assets/eeh.jpg' width='580'>| 


|Hue & Saturation Control|
|:-------------------------:|
|<img src='assets/hsc.jpg' width='580'>| 


|Brightness & Contrast Control|
|:-------------------------:|
|<img src='assets/bcc.jpg' width='580'>| 


# License

Copyright 2021 Qiu Jueqin.

Licensed under [MIT](http://opensource.org/licenses/MIT).
