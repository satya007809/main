"""
AI Lighting — UE5 Editor Utility Widget

A full editor panel for analyzing reference images and applying AI-generated
lighting to your Unreal Engine scene. Supports drag-and-drop, before/after
comparison, presets, and batch blending.

Usage:
    Run this script inside UE5's Python console, or register it as an
    Editor Utility Widget via the plugin.

    In UE5 Python console:
        exec(open('/path/to/ai_lighting_widget.py').read())
"""

import json
import sys
import os
from pathlib import Path

try:
    import unreal
except ImportError:
    unreal = None
    print("[AILighting] 'unreal' module not available — running in dry-run mode.")

# ---------------------------------------------------------------------------
# Widget Registration
# ---------------------------------------------------------------------------

WIDGET_NAME = "AI Lighting"
TOOL_MENU_ENTRY = "AI Lighting Panel"


def register_menu_entry():
    """Register the AI Lighting panel in the Tools menu."""
    menus = unreal.ToolMenus.get()
    tools_menu = menus.find_menu("LevelEditor.MainMenu.Tools")
    if not tools_menu:
        return

    entry = unreal.ToolMenuEntry(
        name="AILightingPanel",
        type=unreal.MultiBlockType.MENU_ENTRY,
    )
    entry.set_label(TOOL_MENU_ENTRY)
    entry.set_tool_tip("Open the AI Lighting panel to generate lighting from reference images")
    entry.set_string_command(
        type=unreal.ToolMenuStringCommandType.PYTHON,
        custom_type="",
        string="import ai_lighting_widget; ai_lighting_widget.open_panel()",
    )
    tools_menu.add_menu_entry("AILighting", entry)
    menus.refresh_all_widgets()
    print(f"[AILighting] Menu entry registered under Tools > {TOOL_MENU_ENTRY}")


# ---------------------------------------------------------------------------
# Panel / Slate UI (Editor Utility Widget approach)
# ---------------------------------------------------------------------------

class AILightingPanel:
    """
    Manages the AI Lighting editor panel.

    Since UE5's Python Slate bindings are limited, this uses the
    EditorUtilityWidget approach: a Python-driven backend that communicates
    with a UMG widget blueprint, OR a fully Python-scripted workflow using
    editor dialogs.
    """

    def __init__(self):
        self.current_config = None
        self.snapshot_before = None
        self.preset_dir = Path(__file__).parent / "presets"
        self.preset_dir.mkdir(exist_ok=True)
        self._history = []

    # -- Image Input --------------------------------------------------------

    def prompt_image_file(self) -> str:
        """Open a file dialog for the user to select a reference image."""
        if not unreal:
            return ""
        result = unreal.EditorDialog.open_file_dialog(
            title="Select Reference Image",
            default_path="",
            default_file="",
            file_types="Image Files (*.jpg *.jpeg *.png *.webp)|*.jpg;*.jpeg;*.png;*.webp",
        )
        if result:
            return result[0]
        return ""

    def analyze_from_path(self, image_path: str, api_key: str = "") -> dict:
        """Analyze a reference image and return lighting config."""
        # Import the analyzer module
        analyzer_dir = Path(__file__).parent
        if str(analyzer_dir) not in sys.path:
            sys.path.insert(0, str(analyzer_dir))
        from analyze_lighting import analyze_image

        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key

        config = analyze_image(Path(image_path))
        self.current_config = config
        self._history.append(config)
        return config

    # -- Apply Lighting -----------------------------------------------------

    def apply_current(self):
        """Apply the current lighting config to the scene."""
        if not self.current_config:
            print("[AILighting] No config loaded. Analyze an image first.")
            return
        if not unreal:
            print("[AILighting] Dry-run: would apply config to scene.")
            print(json.dumps(self.current_config, indent=2))
            return

        analyzer_dir = Path(__file__).parent
        if str(analyzer_dir) not in sys.path:
            sys.path.insert(0, str(analyzer_dir))
        from ue_lighting_applier import (
            apply_directional_light,
            apply_sky_atmosphere,
            apply_sky_light,
            apply_fog,
            apply_post_process,
        )

        config = self.current_config
        mood = config.get("mood_metadata", {})
        print(f"\n[AILighting] Applying: {mood.get('mood', 'unknown')} "
              f"({mood.get('time_of_day', '?')})")

        with unreal.ScopedEditorTransaction("AI Lighting Apply") as trans:
            apply_directional_light(config.get("directional_light"))
            apply_sky_atmosphere(config.get("sky_atmosphere"))
            apply_sky_light(config.get("sky_light"))
            apply_fog(config.get("exponential_height_fog"))
            apply_post_process(config.get("post_process"))

        print("[AILighting] Done! Ctrl+Z to undo.")

    # -- Before/After Snapshots ---------------------------------------------

    def capture_snapshot(self) -> dict:
        """Capture current scene lighting state for before/after comparison."""
        if not unreal:
            print("[AILighting] Dry-run: snapshot captured.")
            return {"snapshot": "dry_run"}

        snapshot = {}
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        all_actors = subsystem.get_all_level_actors()

        # Capture directional light
        dir_lights = unreal.EditorFilterLibrary.by_class(all_actors, unreal.DirectionalLight)
        if dir_lights:
            light = dir_lights[0]
            comp = light.get_component_by_class(unreal.DirectionalLightComponent)
            rot = light.get_actor_rotation()
            snapshot["directional_light"] = {
                "rotation_pitch": rot.pitch,
                "rotation_yaw": rot.yaw,
                "intensity_lux": comp.get_editor_property("intensity"),
                "color_temperature_kelvin": comp.get_editor_property("temperature"),
                "light_source_angle": comp.get_editor_property("light_source_angle"),
            }

        # Capture sky atmosphere
        sky_atmos = unreal.EditorFilterLibrary.by_class(all_actors, unreal.SkyAtmosphere)
        if sky_atmos:
            comp = sky_atmos[0].get_component_by_class(unreal.SkyAtmosphereComponent)
            snapshot["sky_atmosphere"] = {
                "rayleigh_scattering_scale": comp.get_editor_property("rayleigh_scattering_scale"),
                "mie_scattering_scale": comp.get_editor_property("mie_scattering_scale"),
                "absorption_scale": comp.get_editor_property("absorption_scale"),
            }

        # Capture post-process
        pp_volumes = unreal.EditorFilterLibrary.by_class(all_actors, unreal.PostProcessVolume)
        if pp_volumes:
            settings = pp_volumes[0].get_editor_property("settings")
            snapshot["post_process"] = {
                "exposure_compensation": settings.get_editor_property("auto_exposure_bias"),
                "bloom_intensity": settings.get_editor_property("bloom_intensity"),
                "white_balance_temp": settings.get_editor_property("white_temp"),
                "vignette_intensity": settings.get_editor_property("vignette_intensity"),
            }

        return snapshot

    def save_before_snapshot(self):
        """Save current lighting state as the 'before' reference."""
        self.snapshot_before = self.capture_snapshot()
        print("[AILighting] 'Before' snapshot saved.")

    def restore_before_snapshot(self):
        """Restore the 'before' lighting state."""
        if not self.snapshot_before:
            print("[AILighting] No 'before' snapshot available.")
            return
        self.current_config = self.snapshot_before
        self.apply_current()
        print("[AILighting] Restored 'before' state.")

    def toggle_before_after(self):
        """Toggle between before and after lighting states."""
        if not self.snapshot_before or not self._history:
            print("[AILighting] Need both a 'before' snapshot and a generated config.")
            return

        current_snapshot = self.capture_snapshot()

        # Simple heuristic: compare directional light pitch to decide which state we're in
        before_pitch = self.snapshot_before.get("directional_light", {}).get("rotation_pitch", 0)
        current_pitch = current_snapshot.get("directional_light", {}).get("rotation_pitch", 0)
        latest_pitch = self._history[-1].get("directional_light", {}).get("rotation_pitch", 0)

        if abs(current_pitch - latest_pitch) < 1.0:
            # Currently showing 'after', switch to 'before'
            self.current_config = self.snapshot_before
            self.apply_current()
            print("[AILighting] Showing: BEFORE")
        else:
            # Currently showing 'before', switch to 'after'
            self.current_config = self._history[-1]
            self.apply_current()
            print("[AILighting] Showing: AFTER")

    # -- Viewport Screenshot ------------------------------------------------

    def take_viewport_screenshot(self, output_path: str = "") -> str:
        """Capture a viewport screenshot for visual comparison."""
        if not unreal:
            print("[AILighting] Dry-run: would take screenshot.")
            return ""

        if not output_path:
            project_dir = unreal.Paths.project_saved_dir()
            output_path = str(Path(project_dir) / "AILighting" / "screenshot.png")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        unreal.AutomationLibrary.take_high_res_screenshot(
            res_x=1920, res_y=1080, filename=output_path
        )
        print(f"[AILighting] Screenshot saved: {output_path}")
        return output_path


# ---------------------------------------------------------------------------
# Convenience: one-shot workflow
# ---------------------------------------------------------------------------

_panel = None


def open_panel() -> AILightingPanel:
    """Open/get the AI Lighting panel instance."""
    global _panel
    if _panel is None:
        _panel = AILightingPanel()
    return _panel


def quick_apply(image_path: str):
    """One-liner: analyze image and apply lighting immediately."""
    panel = open_panel()
    panel.save_before_snapshot()
    print(f"[AILighting] Analyzing: {image_path}")
    panel.analyze_from_path(image_path)
    panel.apply_current()


def interactive():
    """Open file picker, analyze, and apply."""
    panel = open_panel()
    panel.save_before_snapshot()
    image_path = panel.prompt_image_file()
    if not image_path:
        print("[AILighting] No image selected.")
        return
    print(f"[AILighting] Analyzing: {image_path}")
    panel.analyze_from_path(image_path)
    panel.apply_current()
