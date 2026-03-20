"""
NukeSession - High-level session manager for Nuke 17.0 workflows.

Provides a fluent API for building node graphs, managing scripts,
and executing complex compositing operations remotely.
"""

from .connector import NukeConnector


class NukeSession:
    """High-level session wrapper around NukeConnector for building node graphs."""

    def __init__(self, host="localhost", port=50007):
        self.conn = NukeConnector(host=host, port=port)
        self._node_counter = 0

    def connect(self):
        return self.conn.connect()

    def close(self):
        self.conn.close()

    # --- Script Management ---

    def new_script(self):
        """Clear the current script."""
        return self.conn.execute("nuke.scriptClear()")

    def open_script(self, path):
        """Open a Nuke script."""
        return self.conn.execute(f"nuke.scriptOpen('{path}')")

    def save_script(self, path=None):
        """Save the current script."""
        if path:
            return self.conn.execute(f"nuke.scriptSaveAs('{path}')")
        return self.conn.execute("nuke.scriptSave()")

    # --- Node Creation (Nuke 17.0 New Nodes) ---

    def create_node(self, node_type, name=None, **knobs):
        """Create any node with optional name and knob settings."""
        code_lines = [f"n = nuke.createNode('{node_type}')"]
        if name:
            code_lines.append(f"n.setName('{name}')")
        for k, v in knobs.items():
            if isinstance(v, str):
                code_lines.append(f"n['{k}'].setValue('{v}')")
            else:
                code_lines.append(f"n['{k}'].setValue({v})")
        code_lines.append("result = n.name()")
        return self.conn.execute("\n".join(code_lines))

    def create_splat_render(self, name=None, **knobs):
        """Create a SplatRender node (Nuke 17.0 - Gaussian Splats)."""
        return self.create_node("SplatRender", name=name, **knobs)

    def create_geo_delete_points(self, name=None, **knobs):
        """Create a GeoDeletePoints node (Nuke 17.0)."""
        return self.create_node("GeoDeletePoints", name=name, **knobs)

    def create_geo_grade(self, name=None, **knobs):
        """Create a GeoGrade node (Nuke 17.0 - splat color correction)."""
        return self.create_node("GeoGrade", name=name, **knobs)

    def create_field_shape(self, shape_type="Sphere", name=None, **knobs):
        """Create a Field shape node (Nuke 17.0)."""
        return self.create_node(f"Field{shape_type}", name=name, **knobs)

    def create_field_math(self, name=None, **knobs):
        """Create a FieldMath node (Nuke 17.0)."""
        return self.create_node("FieldMath", name=name, **knobs)

    def create_field_mix(self, name=None, **knobs):
        """Create a FieldMix node (Nuke 17.0)."""
        return self.create_node("FieldMix", name=name, **knobs)

    def create_field_invert(self, name=None, **knobs):
        """Create a FieldInvert node (Nuke 17.0)."""
        return self.create_node("FieldInvert", name=name, **knobs)

    def create_scanline_render2(self, name=None, **knobs):
        """Create ScanlineRender2 with raytrace support (Nuke 17.0)."""
        return self.create_node("ScanlineRender2", name=name, **knobs)

    def create_geo_light(self, light_type="Distant", name=None, **knobs):
        """Create a GeoLight node (Nuke 17.0 USD lighting)."""
        return self.create_node(f"Geo{light_type}Light", name=name, **knobs)

    def create_geo_bind_material(self, name=None, **knobs):
        """Create GeoBindMaterial node (Nuke 17.0 MaterialX)."""
        return self.create_node("GeoBindMaterial", name=name, **knobs)

    def create_geo_materialx(self, name=None, **knobs):
        """Create a MaterialX Standard Surface node (Nuke 17.0)."""
        return self.create_node("GeoMaterialXStandardSurface", name=name, **knobs)

    # --- Connection Helpers ---

    def connect_nodes(self, target_node, source_node, input_index=0):
        """Connect source_node into target_node's input."""
        code = (
            f"nuke.toNode('{target_node}').setInput("
            f"{input_index}, nuke.toNode('{source_node}'))"
        )
        return self.conn.execute(code)

    def set_knob(self, node_name, knob_name, value):
        """Set a knob value on an existing node."""
        if isinstance(value, str):
            code = f"nuke.toNode('{node_name}')['{knob_name}'].setValue('{value}')"
        else:
            code = f"nuke.toNode('{node_name}')['{knob_name}'].setValue({value})"
        return self.conn.execute(code)

    def get_knob(self, node_name, knob_name):
        """Get a knob value from a node."""
        return self.conn.execute(
            f"nuke.toNode('{node_name}')['{knob_name}'].value()"
        )

    # --- Execution ---

    def render(self, node_name, first_frame=1, last_frame=100):
        """Render a node's frame range."""
        return self.conn.execute(
            f"nuke.execute(nuke.toNode('{node_name}'), {first_frame}, {last_frame})"
        )

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()
        return False
