# Image-to-Lighting: AI-Powered Lighting Recreation for Unreal Engine

An exploration of using AI vision models to analyze reference images and automatically recreate matching lighting setups in Unreal Engine.

## Concept

Feed the system any image or visual reference, and it will:
1. **Analyze** the image's lighting characteristics (mood, color palette, direction, intensity, time of day)
2. **Generate** a structured lighting parameter set
3. **Apply** those parameters to your Unreal Engine scene automatically

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  Reference   │────▶│  Vision Model    │────▶│  Lighting Parameter │
│  Image       │     │  (Claude/GPT-4V) │     │  Extraction         │
└─────────────┘     └──────────────────┘     └────────┬────────────┘
                                                       │
                                                       ▼
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  UE Scene   │◀────│  UE Python/BP    │◀────│  JSON Light Config  │
│  Updated    │     │  Scripting API   │     │  (Structured Output)│
└─────────────┘     └──────────────────┘     └─────────────────────┘
```

## Components

- **`analyze_lighting.py`** — Python script that sends a reference image to a vision-capable AI model and extracts structured lighting parameters
- **`ue_lighting_applier.py`** — Unreal Engine Python script that reads the JSON config and applies lighting to the scene
- **`FEASIBILITY.md`** — Detailed feasibility analysis and technical approach

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Analyze a reference image
python analyze_lighting.py --image reference.jpg --output lighting_config.json

# In Unreal Engine Python console:
# exec(open('ue_lighting_applier.py').read())
```

## Status

**Phase: Feasibility Exploration**

See [FEASIBILITY.md](FEASIBILITY.md) for the full technical analysis.
