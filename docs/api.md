# API reference

Minimal example:

```python
from fast_openisp.config import bundled_configs
from fast_openisp.io.export import save_image
from fast_openisp.io.loaders import load_tiff
from fast_openisp.pipeline import Pipeline

config = bundled_configs()["mikros110"]
raw = load_tiff("raw/mikros110.tiff", bayer_pattern="bggr")
result = Pipeline(config).execute(raw.bayer)
save_image(result.image, "mikros110.png")
print(result.awb_gains, result.timings)
```

## Configuration

::: fast_openisp.config
    options:
      members:
        - IspConfig
        - HardwareConfig
        - ModulesConfig
        - ModuleParams
        - ModuleInfo
        - MODULE_INFO
        - ConfigError
        - load_config
        - save_config
        - bundled_configs
        - resolve_enabled

## Pipeline

::: fast_openisp.pipeline

## Loading and exporting

::: fast_openisp.io.loaders

::: fast_openisp.io.export

## Imaging utilities

::: fast_openisp.imaging

## Module base classes

::: fast_openisp.modules.base
