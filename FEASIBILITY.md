# Feasibility Analysis: Image-to-Lighting for Unreal Engine

## Summary

Using AI vision models to extract lighting characteristics from reference images and automatically apply them in Unreal Engine is **highly feasible** with current technology. This document outlines the technical approach, challenges, and implementation strategy.

---

## 1. Core Technical Approach

### Step 1: Image Analysis via Vision Model

Modern vision-capable LLMs (Claude, GPT-4V) can analyze images and extract:

| Lighting Property | Extractable? | Confidence |
|---|---|---|
| Primary light direction | Yes | High |
| Color temperature (warm/cool) | Yes | High |
| Time of day | Yes | High |
| Overall mood/atmosphere | Yes | High |
| Shadow softness/hardness | Yes | Medium |
| Light intensity ratios | Yes | Medium |
| Number of light sources | Yes | Medium |
| Volumetric/fog density | Approximate | Medium |
| Specific lux values | No — relative only | Low |

### Step 2: Structured Output Generation

The vision model outputs a JSON schema mapping to UE lighting parameters:

```json
{
  "directional_light": {
    "rotation_pitch": -45.0,
    "rotation_yaw": 180.0,
    "intensity_lux": 100000,
    "color_temperature_kelvin": 5500,
    "light_source_angle": 1.0
  },
  "sky_atmosphere": {
    "time_of_day_solar_angle": -30.0,
    "rayleigh_scattering_scale": 1.0,
    "mie_scattering_scale": 0.5,
    "absorption_scale": 1.0
  },
  "sky_light": {
    "intensity_scale": 1.0,
    "tint": [1.0, 0.95, 0.9]
  },
  "exponential_height_fog": {
    "enabled": true,
    "fog_density": 0.02,
    "fog_color": [0.5, 0.6, 0.7],
    "start_distance": 1000
  },
  "post_process": {
    "exposure_compensation": 0.0,
    "bloom_intensity": 0.5,
    "color_grading_lut_hint": "warm_golden_hour",
    "vignette_intensity": 0.3,
    "white_balance_temp": 6000
  },
  "mood_metadata": {
    "time_of_day": "golden_hour",
    "mood": "warm_cinematic",
    "weather": "clear",
    "season_hint": "autumn"
  }
}
```

### Step 3: UE Application via Python Scripting

Unreal Engine's Python API (`unreal` module) provides full control:

- `unreal.DirectionalLightComponent` — sun direction, intensity, color
- `unreal.SkyAtmosphereComponent` — atmospheric scattering
- `unreal.SkyLightComponent` — ambient/sky lighting
- `unreal.ExponentialHeightFogComponent` — fog/haze
- `unreal.PostProcessVolume` — color grading, bloom, exposure

---

## 2. Implementation Approaches

### Approach A: API-Based (Recommended for v1)

```
Reference Image → Claude Vision API → JSON Config → UE Python Script
```

**Pros:** Highest quality analysis, no training needed, works immediately
**Cons:** Requires internet, API costs, ~2-5s latency per image

### Approach B: Local Model

```
Reference Image → Fine-tuned Local Model → JSON Config → UE Python Script
```

**Pros:** Offline, fast (<1s), no API costs
**Cons:** Requires training data collection, lower quality, significant ML effort

### Approach C: Hybrid

Use API for high-quality analysis, cache results, and optionally fine-tune a local model on accumulated data over time.

---

## 3. Key Challenges & Mitigations

### Challenge 1: Absolute vs. Relative Values
**Problem:** Images don't contain absolute light intensity values.
**Mitigation:** Use a calibrated baseline (e.g., "sunny day = 100,000 lux") and express other conditions as ratios. Provide presets the user can scale.

### Challenge 2: Scene Geometry Mismatch
**Problem:** Reference image lighting works for *that specific scene* — your UE scene has different geometry.
**Mitigation:** Extract *mood and atmosphere* rather than exact light positions. Focus on directional light, sky, and post-processing — these transfer well across scenes.

### Challenge 3: Consistency Across Prompts
**Problem:** Same image might produce slightly different parameters across API calls.
**Mitigation:** Use structured output mode, pin specific model versions, apply parameter clamping/rounding.

### Challenge 4: Complex Multi-Light Setups
**Problem:** Interior scenes with many practical lights are hard to decompose from a single image.
**Mitigation:** Start with exterior/natural lighting (single dominant light source). Interior scenes can be v2 with multi-light decomposition.

---

## 4. Phased Roadmap

### Phase 1: Proof of Concept (Current)
- [x] Feasibility analysis
- [ ] Python script to analyze reference images via Claude Vision API
- [ ] JSON schema for UE lighting parameters
- [ ] Basic UE Python script to apply parameters

### Phase 2: UE Plugin
- [ ] Editor Utility Widget with drag-and-drop image input
- [ ] Real-time preview of lighting changes
- [ ] Undo/redo support
- [ ] Parameter fine-tuning sliders

### Phase 3: Advanced Features
- [ ] Multi-image blending (blend moods from multiple references)
- [ ] Video reference support (extract lighting keyframes)
- [ ] Interior multi-light decomposition
- [ ] Local model option for offline use

---

## 5. Verdict

| Criteria | Assessment |
|---|---|
| Technical feasibility | **Strong** — all components exist |
| Time to MVP | **1-2 weeks** for basic pipeline |
| Quality of results | **Good for exteriors**, decent for interiors |
| Market need | **High** — lighting is time-consuming and skill-intensive |
| Competitive landscape | Early stage — few polished tools exist |

**Recommendation:** Build the API-based approach first (Approach A). It requires the least effort, produces the highest quality results, and validates the concept quickly.
