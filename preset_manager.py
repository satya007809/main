"""
Preset Manager — Save, load, and browse lighting presets.

Presets are stored as JSON files in the presets/ directory. Each preset
contains the full lighting config plus metadata about the source image.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


DEFAULT_PRESET_DIR = Path(__file__).parent / "presets"


class PresetManager:
    def __init__(self, preset_dir: Optional[Path] = None):
        self.preset_dir = preset_dir or DEFAULT_PRESET_DIR
        self.preset_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_name(self, name: str) -> str:
        """Convert a display name to a safe filename."""
        name = name.lower().strip()
        name = re.sub(r'[^\w\s-]', '', name)
        name = re.sub(r'[\s]+', '_', name)
        return name[:64]

    def save(self, config: dict, name: str, source_image: str = "", tags: list = None) -> Path:
        """Save a lighting config as a named preset."""
        preset = {
            "name": name,
            "created": datetime.now().isoformat(),
            "source_image": source_image,
            "tags": tags or [],
            "config": config,
        }

        filename = self._sanitize_name(name) + ".json"
        path = self.preset_dir / filename

        # Avoid overwriting — add suffix if exists
        counter = 1
        while path.exists():
            filename = f"{self._sanitize_name(name)}_{counter}.json"
            path = self.preset_dir / filename
            counter += 1

        path.write_text(json.dumps(preset, indent=2))
        print(f"[Presets] Saved: {name} -> {path.name}")
        return path

    def load(self, name_or_file: str) -> dict:
        """Load a preset by name or filename. Returns the lighting config."""
        # Try exact filename first
        path = self.preset_dir / name_or_file
        if not path.exists():
            path = self.preset_dir / (name_or_file + ".json")
        if not path.exists():
            # Search by sanitized name
            path = self.preset_dir / (self._sanitize_name(name_or_file) + ".json")
        if not path.exists():
            raise FileNotFoundError(f"Preset not found: {name_or_file}")

        preset = json.loads(path.read_text())
        print(f"[Presets] Loaded: {preset.get('name', path.stem)}")
        return preset["config"]

    def list_presets(self) -> list[dict]:
        """List all available presets with metadata."""
        presets = []
        for path in sorted(self.preset_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                mood = data.get("config", {}).get("mood_metadata", {})
                presets.append({
                    "file": path.name,
                    "name": data.get("name", path.stem),
                    "created": data.get("created", ""),
                    "tags": data.get("tags", []),
                    "mood": mood.get("mood", ""),
                    "time_of_day": mood.get("time_of_day", ""),
                    "description": mood.get("description", ""),
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return presets

    def print_presets(self):
        """Pretty-print all available presets."""
        presets = self.list_presets()
        if not presets:
            print("[Presets] No presets saved yet.")
            return

        print(f"\n[Presets] {len(presets)} preset(s) available:\n")
        print(f"  {'Name':<25} {'Mood':<20} {'Time':<15} {'Tags'}")
        print(f"  {'─'*25} {'─'*20} {'─'*15} {'─'*20}")
        for p in presets:
            tags = ", ".join(p["tags"]) if p["tags"] else ""
            print(f"  {p['name']:<25} {p['mood']:<20} {p['time_of_day']:<15} {tags}")
        print()

    def delete(self, name_or_file: str) -> bool:
        """Delete a preset by name or filename."""
        path = self.preset_dir / name_or_file
        if not path.exists():
            path = self.preset_dir / (name_or_file + ".json")
        if not path.exists():
            path = self.preset_dir / (self._sanitize_name(name_or_file) + ".json")
        if not path.exists():
            print(f"[Presets] Not found: {name_or_file}")
            return False

        name = path.stem
        path.unlink()
        print(f"[Presets] Deleted: {name}")
        return True

    def search(self, query: str) -> list[dict]:
        """Search presets by name, mood, tags, or description."""
        query_lower = query.lower()
        results = []
        for preset in self.list_presets():
            searchable = " ".join([
                preset.get("name", ""),
                preset.get("mood", ""),
                preset.get("time_of_day", ""),
                preset.get("description", ""),
                " ".join(preset.get("tags", [])),
            ]).lower()
            if query_lower in searchable:
                results.append(preset)
        return results


# Builtin presets for common lighting scenarios
BUILTIN_PRESETS = {
    "golden_hour": {
        "directional_light": {
            "rotation_pitch": -10.0,
            "rotation_yaw": 220.0,
            "intensity_lux": 60000,
            "color_temperature_kelvin": 3200,
            "light_source_angle": 1.5,
        },
        "sky_atmosphere": {
            "rayleigh_scattering_scale": 1.5,
            "mie_scattering_scale": 2.0,
            "absorption_scale": 1.0,
        },
        "sky_light": {
            "intensity_scale": 1.2,
            "tint": [1.0, 0.9, 0.75],
        },
        "exponential_height_fog": {
            "enabled": True,
            "fog_density": 0.015,
            "fog_color": [1.0, 0.85, 0.6],
            "fog_height_falloff": 0.15,
            "start_distance": 500,
            "volumetric_fog": True,
        },
        "post_process": {
            "exposure_compensation": 0.5,
            "bloom_intensity": 1.0,
            "white_balance_temp": 5500,
            "vignette_intensity": 0.2,
            "saturation": 1.15,
            "contrast": 1.05,
        },
        "mood_metadata": {
            "time_of_day": "golden_hour",
            "mood": "warm_cinematic",
            "weather": "clear",
            "indoor_outdoor": "outdoor",
            "description": "Warm golden hour light with long shadows and atmospheric haze",
        },
    },
    "blue_hour": {
        "directional_light": {
            "rotation_pitch": 5.0,
            "rotation_yaw": 200.0,
            "intensity_lux": 800,
            "color_temperature_kelvin": 9500,
            "light_source_angle": 2.0,
        },
        "sky_atmosphere": {
            "rayleigh_scattering_scale": 2.0,
            "mie_scattering_scale": 0.5,
            "absorption_scale": 1.5,
        },
        "sky_light": {
            "intensity_scale": 2.0,
            "tint": [0.6, 0.65, 0.9],
        },
        "exponential_height_fog": {
            "enabled": True,
            "fog_density": 0.03,
            "fog_color": [0.4, 0.45, 0.7],
            "fog_height_falloff": 0.1,
            "start_distance": 200,
            "volumetric_fog": True,
        },
        "post_process": {
            "exposure_compensation": 1.5,
            "bloom_intensity": 0.8,
            "white_balance_temp": 8000,
            "vignette_intensity": 0.35,
            "saturation": 0.9,
            "contrast": 1.1,
        },
        "mood_metadata": {
            "time_of_day": "blue_hour",
            "mood": "cool_melancholic",
            "weather": "clear",
            "indoor_outdoor": "outdoor",
            "description": "Cool blue twilight with soft ambient lighting and deep shadows",
        },
    },
    "overcast_dramatic": {
        "directional_light": {
            "rotation_pitch": -40.0,
            "rotation_yaw": 180.0,
            "intensity_lux": 8000,
            "color_temperature_kelvin": 7000,
            "light_source_angle": 4.0,
        },
        "sky_atmosphere": {
            "rayleigh_scattering_scale": 0.5,
            "mie_scattering_scale": 3.0,
            "absorption_scale": 0.8,
        },
        "sky_light": {
            "intensity_scale": 3.0,
            "tint": [0.8, 0.82, 0.85],
        },
        "exponential_height_fog": {
            "enabled": True,
            "fog_density": 0.05,
            "fog_color": [0.6, 0.62, 0.65],
            "fog_height_falloff": 0.05,
            "start_distance": 0,
            "volumetric_fog": False,
        },
        "post_process": {
            "exposure_compensation": 0.0,
            "bloom_intensity": 0.3,
            "white_balance_temp": 6800,
            "vignette_intensity": 0.15,
            "saturation": 0.8,
            "contrast": 1.2,
        },
        "mood_metadata": {
            "time_of_day": "afternoon",
            "mood": "dramatic_overcast",
            "weather": "overcast",
            "indoor_outdoor": "outdoor",
            "description": "Heavy overcast sky with diffused light, desaturated colors, and moody contrast",
        },
    },
    "moonlit_night": {
        "directional_light": {
            "rotation_pitch": -30.0,
            "rotation_yaw": 120.0,
            "intensity_lux": 0.5,
            "color_temperature_kelvin": 10000,
            "light_source_angle": 0.5,
        },
        "sky_atmosphere": {
            "rayleigh_scattering_scale": 0.3,
            "mie_scattering_scale": 0.2,
            "absorption_scale": 1.0,
        },
        "sky_light": {
            "intensity_scale": 0.3,
            "tint": [0.5, 0.55, 0.8],
        },
        "exponential_height_fog": {
            "enabled": True,
            "fog_density": 0.01,
            "fog_color": [0.15, 0.18, 0.3],
            "fog_height_falloff": 0.2,
            "start_distance": 100,
            "volumetric_fog": True,
        },
        "post_process": {
            "exposure_compensation": 3.0,
            "bloom_intensity": 1.5,
            "white_balance_temp": 9000,
            "vignette_intensity": 0.5,
            "saturation": 0.6,
            "contrast": 1.3,
        },
        "mood_metadata": {
            "time_of_day": "night",
            "mood": "mysterious_moonlit",
            "weather": "clear",
            "indoor_outdoor": "outdoor",
            "description": "Clear moonlit night with cool blue tones, high contrast, and subtle fog",
        },
    },
}


def install_builtin_presets(preset_dir: Optional[Path] = None):
    """Save all builtin presets to the preset directory."""
    manager = PresetManager(preset_dir)
    for name, config in BUILTIN_PRESETS.items():
        display_name = name.replace("_", " ").title()
        path = manager.preset_dir / f"{name}.json"
        if not path.exists():
            manager.save(config, display_name, tags=["builtin"])
    print(f"[Presets] {len(BUILTIN_PRESETS)} builtin presets installed.")
