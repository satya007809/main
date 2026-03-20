# Nuke 17.0 Exploration - Unique Examples & Workflows

A comprehensive collection of **Foundry Nuke 17.0** examples demonstrating all major new features, with a socket-based connection module for controlling Nuke remotely.

## What's New in Nuke 17.0

| Feature | Description |
|---------|-------------|
| **Gaussian Splats** | Native import, render, and export of Gaussian Splats with SplatRender node |
| **Field Nodes** | Volumetric masking system (FieldSphere, FieldMath, FieldMix, etc.) |
| **USD 3D Overhaul** | Modernized USD-based 3D system with non-destructive workflows |
| **MaterialX Shaders** | First MaterialX Standard Surface node for PBR materials |
| **GeoLight Nodes** | USD lighting (Distant, Disk, Dome, Sphere lights) with shadow controls |
| **ScanlineRender2** | Unified raytrace renderer (replaces ScanlineRender + RayRender) |
| **GeoPython** | Direct Python access to USD stage data in the node graph |
| **Enhanced Annotations** | Dodge, Burn, Clone brushes + Annotations Panel + Python API |
| **Graph Scope Variables** | Python callbacks, root knob expressions, label visibility |
| **ACES 2.0** | Native HDR/SDR configs with YCbCr Rec.2020 MOV support |
| **Deep Compositing** | Up to 1.88x faster rendering |
| **BigCat (NukeX)** | Train custom AI models on large VFX datasets |

## Project Structure

```
nuke-17-exploration/
├── nuke_connection/           # Socket-based Nuke connectivity
│   ├── connector.py           #   NukeConnector client
│   ├── server.py              #   Server to run INSIDE Nuke
│   └── session.py             #   High-level NukeSession API
├── examples/
│   ├── gaussian_splats/       # Gaussian Splat workflows
│   │   ├── 01_splat_ingest_and_render.py
│   │   ├── 02_field_nodes_splat_masking.py
│   │   └── 03_splat_set_extension.py
│   ├── usd_3d_system/         # USD / MaterialX / Lighting
│   │   ├── 01_materialx_shading.py
│   │   └── 02_geo_python_usd_scripting.py
│   ├── annotations_gsv/       # Annotations & Graph Scope Variables
│   │   ├── 01_annotations_review_system.py
│   │   └── 02_graph_scope_variables.py
│   └── performance_pipeline/  # ACES 2.0, Deep Compositing
│       ├── 01_aces2_hdr_pipeline.py
│       └── 02_deep_compositing_optimized.py
├── utils/
│   └── nuke_17_node_reference.py  # Complete new node reference
└── run_examples.py            # Main launcher (interactive menu)
```

## Quick Start

### Offline Mode (no Nuke needed)
Generate code to paste into Nuke 17.0's Script Editor:

```bash
python run_examples.py                  # Interactive menu
python run_examples.py --example 1      # Run specific example
python run_examples.py --all            # Run all examples
python run_examples.py --reference      # New node reference
```

### Live Connection to Nuke 17.0

**Step 1:** In Nuke's Script Editor, start the server:
```python
import sys
sys.path.append('/path/to/this/repo')
from nuke_connection.server import start_server
start_server(port=50007)
```

**Step 2:** From your terminal:
```bash
python run_examples.py --connect
```

**Step 3:** Or use the Python API directly:
```python
from nuke_connection import NukeConnector

with NukeConnector(host="localhost", port=50007) as conn:
    conn.connect()
    conn.execute("nuke.createNode('SplatRender')")
    nodes = conn.get_all_nodes()
    print(nodes)
```

## Examples Overview

### 1-3: Gaussian Splats (Brand New in 17.0)
- **Splat Ingest & Render**: Import .ply, set up SplatRender with depth/motion blur/Deep
- **Field Masking**: FieldSphere + FieldMath + FieldInvert + GeoDeletePoints pipeline
- **Set Extension**: Multi-layer splat comp (BG scan + midground + CG + plate)

### 4-5: USD 3D System (Major Overhaul)
- **MaterialX Shading**: Chrome, concrete, skin, glass materials + 4-light rig
- **GeoPython USD**: Procedural scatter, dynamic light rig, stage inspector

### 6-7: Annotations & GSVs (Enhanced)
- **Annotations Review**: Automated review system with brush presets
- **Graph Scope Variables**: Multishot template with callbacks and label visibility

### 8-9: Performance & Pipeline
- **ACES 2.0**: HDR/SDR/VP delivery pipeline with YCbCr Rec.2020
- **Deep Compositing**: Multi-element deep comp leveraging 1.88x speed boost

## Requirements

- **Nuke 17.0v1** (for running inside Nuke)
- **Python 3.11+** (for offline mode and connection client)
- VFX Reference Platform 2025 compatible
