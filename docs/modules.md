# ISP modules

The pipeline has three domains:

1. **Bayer domain** (DPC → CNF): works on the raw mosaic, one color channel at a time.
2. **RGB domain** (CFA → GAC): CFA demosaics into linear RGB; GAC applies gamma and
   converts to 8 bit.
3. **YCbCr domain** (CSC → BCC): CSC converts to luma and chroma, so the filters that
   follow can work on luma (Y) and chroma (CbCr) separately.

SCL (scaler) resizes the final result.

## At a glance

| Module | What it does |
|---|---|
| **DPC** | Replaces pixels that differ strongly from all 8 same-color neighbours (hot or dead pixels). |
| **BLC** | Subtracts the sensor's black level from each channel; optional R→Gr / B→Gb crosstalk correction. |
| **AAF** | Light 3 × 3 smoothing per channel to reduce aliasing before demosaicing. |
| **AWB** | White balance: multiplies each channel by a gain (manual or grey-world). |
| **CNF** | Chroma noise filter: suppresses isolated red or blue noise in dark areas, depending on the AWB gains. |
| **CFA** | Demosaicing: interpolates full RGB from the mosaic (Malvar-He-Cutler or bilinear). |
| **CCM** | Color correction matrix: maps sensor RGB to the output color space. |
| **GAC** | Gain and gamma curve; converts linear data to 8-bit display values. |
| **CSC** | Converts RGB to YCbCr (BT.601). |
| **NLM** | Non-local means denoising of luma. Strong, but the slowest module. |
| **BNF** | Bilateral denoising of luma, which keeps edges sharp. |
| **CEH** | Local contrast enhancement (CLAHE) on luma. |
| **EEH** | Edge enhancement (sharpening) of luma. |
| **FCS** | False color suppression: reduces chroma along strong edges. |
| **HSC** | Hue rotation and saturation. |
| **BCC** | Brightness and contrast. |
| **SCL** | Resizes the result to a fixed output size. |

## Parameter reference

This section is generated from the configuration models in `fast_openisp.config`, so it
always matches the code.

<!-- MODULE_REFERENCE -->
