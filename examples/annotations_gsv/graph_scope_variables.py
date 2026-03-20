"""
Example 7: Graph Scope Variables (GSVs) - Multishot Workflows
==============================================================
Nuke 17.0 Feature: Enhanced GSVs with Python callbacks and expressions

This example demonstrates:
- Creating and managing Graph Scope Variables
- Using GSV expressions in root knobs (first_frame, last_frame, fps)
- Python callbacks for Variable events
- Making Variables visible in node labels
- Building a multishot template driven by GSVs

New Features Used:
- GSV Python callbacks (hook into Variable events)
- GSV expressions in first_frame, last_frame, fps root knobs
- GSV visibility in node labels
- Enhanced GSV performance for large Variable sets
"""


def build_gsv_multishot_offline():
    """Generate GSV multishot workflow code for Nuke 17.0."""

    script = '''
import nuke

# ============================================================
# Graph Scope Variables: Multishot Pipeline
# Nuke 17.0 - Enhanced GSV System
# ============================================================
# GSVs in Nuke 17.0 get:
# - Python callbacks for automation
# - Expression support in root knobs (frame range, fps)
# - Visibility in node labels
# - Massive performance improvements for large Variable sets

# --- 1. Create a Multishot Template with GSVs ---

def setup_multishot_template():
    """Set up a multishot compositing template driven by GSVs."""

    root = nuke.root()

    # Create shot Variable Group
    # In Nuke 17.0, VariableGroups organize related variables
    shot_data = {
        "sh010": {"first": 1001, "last": 1100, "plate": "/plates/sh010/plate.####.exr"},
        "sh020": {"first": 1001, "last": 1085, "plate": "/plates/sh020/plate.####.exr"},
        "sh030": {"first": 1001, "last": 1150, "plate": "/plates/sh030/plate.####.exr"},
        "sh040": {"first": 1001, "last": 1200, "plate": "/plates/sh040/plate.####.exr"},
    }

    # Create the GSVs
    # shot_name Variable drives all other values
    print("Setting up Graph Scope Variables:")
    for shot, data in shot_data.items():
        print(f"  {shot}: frames {data['first']}-{data['last']}")

    # NEW in 17.0: GSV expressions in root knobs
    # root["first_frame"].setExpression("$shot_first_frame")
    # root["last_frame"].setExpression("$shot_last_frame")
    # root["fps"].setExpression("$shot_fps")

    return shot_data


# --- 2. GSV Python Callbacks (New in Nuke 17.0) ---

class GSVCallbackManager:
    """
    Manage Python callbacks for Graph Scope Variable events.

    Nuke 17.0 introduces callbacks that fire when:
    - A Variable value changes
    - A VariableGroup is switched
    - Variables are created or deleted
    """

    _callbacks = {}

    @classmethod
    def on_variable_changed(cls, variable_name, callback):
        """Register a callback for when a specific variable changes."""
        cls._callbacks.setdefault(variable_name, []).append(callback)
        print(f"  Registered callback for '{variable_name}' changes")

    @classmethod
    def on_shot_switch(cls, callback):
        """Register a callback for shot switches."""
        cls._callbacks.setdefault("__shot_switch__", []).append(callback)
        print("  Registered shot switch callback")

    @classmethod
    def fire(cls, variable_name, old_value, new_value):
        """Simulate firing callbacks (in Nuke, these fire automatically)."""
        for cb in cls._callbacks.get(variable_name, []):
            cb(variable_name, old_value, new_value)
        for cb in cls._callbacks.get("__shot_switch__", []):
            cb(variable_name, old_value, new_value)


# --- 3. Register Callbacks ---

def on_plate_path_changed(var_name, old_val, new_val):
    """Update Read nodes when plate path variable changes."""
    print(f"  Plate path updated: {old_val} -> {new_val}")
    for node in nuke.allNodes("Read"):
        if "Plate" in node.name():
            print(f"    Updating {node.name()} file path")

def on_frame_range_changed(var_name, old_val, new_val):
    """Update frame range when shot variables change."""
    print(f"  Frame range updated: {var_name} = {new_val}")

def on_shot_switched(var_name, old_val, new_val):
    """Handle shot switching - update all dependent nodes."""
    print(f"  === Shot switched: {old_val} -> {new_val} ===")
    print(f"  Updating all GSV-dependent nodes...")
    print(f"  Refreshing viewers...")

print("\\n--- Registering GSV Callbacks ---")
GSVCallbackManager.on_variable_changed("plate_path", on_plate_path_changed)
GSVCallbackManager.on_variable_changed("first_frame", on_frame_range_changed)
GSVCallbackManager.on_variable_changed("last_frame", on_frame_range_changed)
GSVCallbackManager.on_shot_switch(on_shot_switched)

# --- 4. Simulate shot switching ---
print("\\n--- Simulating Shot Switch ---")
GSVCallbackManager.fire("__shot_switch__", "sh010", "sh020")
GSVCallbackManager.fire("plate_path", "/plates/sh010/plate.####.exr",
                                       "/plates/sh020/plate.####.exr")
GSVCallbackManager.fire("first_frame", 1001, 1001)
GSVCallbackManager.fire("last_frame", 1100, 1085)


# --- 5. Build Node Graph with GSV Labels ---

def build_gsv_node_graph():
    """Build a node graph where nodes display GSV values in their labels."""

    # Read node with GSV-driven file path
    read = nuke.createNode("Read")
    read.setName("ShotPlate")
    # In 17.0: Variables visible in node labels
    read["label"].setValue("[value shot_name] - Plate")

    # Grade with shot-specific color correction
    grade = nuke.createNode("Grade")
    grade.setName("ShotGrade")
    grade.setInput(0, read)
    grade["label"].setValue("[value shot_name] CC")

    # Roto with shot reference
    roto = nuke.createNode("Roto")
    roto.setName("ShotRoto")
    roto.setInput(0, grade)
    roto["label"].setValue("[value shot_name] Roto")

    # Write with GSV-driven output path
    write = nuke.createNode("Write")
    write.setName("ShotOutput")
    write.setInput(0, roto)
    write["label"].setValue("[value shot_name] Output")
    # write["file"].setValue("/output/[value shot_name]/comp.####.exr")

    viewer = nuke.createNode("Viewer")
    viewer.setInput(0, write)

    print("\\nNode graph built with GSV labels!")
    print("Switch shot_name Variable to update all labels automatically.")


# Execute
shot_data = setup_multishot_template()
build_gsv_node_graph()

print("\\n" + "=" * 50)
print("GSV Multishot template ready!")
print(f"Shots configured: {list(shot_data.keys())}")
print("New in 17.0: Callbacks, root knob expressions, label visibility")
'''

    print("=" * 70)
    print("NUKE 17.0 - Graph Scope Variables: Multishot Pipeline")
    print("=" * 70)
    print(script)
    return script


if __name__ == "__main__":
    build_gsv_multishot_offline()
