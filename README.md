# Image-to-Lighting: AI-Powered Lighting Recreation for Unreal Engine

An AI tool that analyzes reference images and automatically recreates matching lighting setups in Unreal Engine 5. Drop an image, get realistic lighting.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Reference   │────▶│  Claude Vision   │────▶│  Lighting Parameter │
│  Image(s)    │     │  API             │     │  Extraction         │
└─────────────┘     └──────────────────┘     └────────┬────────────┘
                                                       │
                                                       ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  UE5 Scene  │◀────│  Editor Widget / │◀────│  JSON Light Config  │
│  Updated    │     │  Python API      │     │  + Preset Library   │
└─────────────┘     └──────────────────┘     └─────────────────────┘
```

## Features

- **Image Analysis** — Extract lighting parameters from any reference photo using Claude Vision
- **One-Click Apply** — Apply generated lighting to your UE5 scene instantly (with undo)
- **Before/After** — Snapshot current lighting, apply new, toggle between them
- **Preset Library** — Save, load, search, and browse lighting presets. Ships with 4 builtins (Golden Hour, Blue Hour, Overcast Dramatic, Moonlit Night)
- **Batch Blending** — Analyze a mood board of multiple images and blend their lighting with custom weights
- **UE5 Plugin** — Editor Utility Widget with menu integration

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set your API key
export ANTHROPIC_API_KEY="your-key-here"

# Analyze a single reference image
python analyze_lighting.py --image sunset_ref.jpg --output lighting_config.json

# Blend a mood board (multiple images)
python batch_blend.py --images ref1.jpg ref2.jpg ref3.jpg --output blended.json
python batch_blend.py --images warm.jpg cool.jpg --weights 0.7 0.3 --output blended.json
```

## In Unreal Engine

```python
# Quick apply from a reference image
exec(open('ai_lighting_widget.py').read())
quick_apply("/path/to/reference.jpg")

# Or use the interactive file picker
interactive()

# Before/after comparison
panel = open_panel()
panel.save_before_snapshot()       # Save current state
panel.analyze_from_path("ref.jpg") # Analyze new reference
panel.apply_current()              # Apply new lighting
panel.toggle_before_after()        # Toggle comparison
```

## Preset Library

```python
from preset_manager import PresetManager, install_builtin_presets

# Install the 4 builtin presets
install_builtin_presets()

# Browse presets
manager = PresetManager()
manager.print_presets()

# Save current config as preset
manager.save(config, "My Sunset", tags=["exterior", "warm"])

# Load and apply a preset
config = manager.load("golden_hour")

# Search presets
results = manager.search("warm")
```

### Builtin Presets

| Preset | Mood | Time | Description |
|---|---|---|---|
| Golden Hour | warm_cinematic | golden_hour | Warm light with long shadows and atmospheric haze |
| Blue Hour | cool_melancholic | blue_hour | Cool blue twilight with soft ambient lighting |
| Overcast Dramatic | dramatic_overcast | afternoon | Heavy overcast, diffused light, moody contrast |
| Moonlit Night | mysterious_moonlit | night | Clear moonlit night with cool blue tones |

## Components

| File | Purpose |
|---|---|
| `analyze_lighting.py` | Image → Claude Vision → JSON lighting config |
| `ue_lighting_applier.py` | JSON config → UE5 scene lighting |
| `ai_lighting_widget.py` | Editor panel with before/after, file picker, presets |
| `preset_manager.py` | Save/load/search/browse lighting presets |
| `batch_blend.py` | Multi-image analysis and weighted blending |
| `lighting_schema.json` | JSON schema for lighting parameters |
| `ue_plugin/` | UE5 plugin descriptor |
| `presets/` | Saved lighting presets |
| `FEASIBILITY.md` | Detailed technical feasibility analysis |

## Requirements

- Python 3.10+
- `anthropic` Python SDK
- Unreal Engine 5.x (for scene application)
- `ANTHROPIC_API_KEY` environment variable

## Status

**Phase: Working Prototype**

See [FEASIBILITY.md](FEASIBILITY.md) for the full technical analysis.
