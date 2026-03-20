"""
Example 5: GeoPython Node - Direct USD Stage Manipulation
==========================================================
Nuke 17.0 Feature: GeoPython node for USD scripting

This example demonstrates:
- Using GeoPython to create USD prims programmatically
- Building procedural geometry via USD Python API
- Creating custom USD attributes and schemas
- Editing parameters directly in the 3D scene graph

New Nodes Used:
- GeoPython (direct Python access to USD stage data)
"""


def build_geo_python_examples_offline():
    """Generate GeoPython USD scripting examples for Nuke 17.0."""

    script = '''
import nuke

# ============================================================
# GeoPython: Direct USD Stage Manipulation
# Nuke 17.0 - Scriptable USD in the Node Graph
# ============================================================
# GeoPython lets you write Python that directly edits the USD
# stage flowing through the node, giving you full control over
# prims, attributes, schemas, and relationships.

# --- Example A: Procedural Scatter ---
# Scatter instances of a prop across a surface

scatter_node = nuke.createNode("GeoPython")
scatter_node.setName("ProceduralScatter")
scatter_node["code"].setValue("""
from pxr import Usd, UsdGeom, Gf, Sdf
import random

stage = geo.GetStage()
random.seed(42)

# Create an Xform to hold all instances
scatter_root = UsdGeom.Xform.Define(stage, "/World/ScatteredProps")

# Scatter 50 instances across a ground plane
for i in range(50):
    x = random.uniform(-10, 10)
    z = random.uniform(-10, 10)
    y = random.uniform(0, 0.1)  # Slight height variation
    rot_y = random.uniform(0, 360)
    scale = random.uniform(0.8, 1.2)

    instance_path = f"/World/ScatteredProps/instance_{i:03d}"
    instance = UsdGeom.Xform.Define(stage, instance_path)

    # Set transform
    xform_ops = instance.AddTranslateOp()
    xform_ops.Set(Gf.Vec3d(x, y, z))

    rot_op = instance.AddRotateYOp()
    rot_op.Set(rot_y)

    scale_op = instance.AddScaleOp()
    scale_op.Set(Gf.Vec3f(scale, scale, scale))

    # Add a reference to the source asset
    # instance.GetPrim().GetReferences().AddReference("/assets/rock.usd")

    # Add custom attribute for LOD selection
    lod_attr = instance.GetPrim().CreateAttribute(
        "custom:lodLevel", Sdf.ValueTypeNames.Int
    )
    dist_from_center = (x**2 + z**2) ** 0.5
    lod_attr.Set(0 if dist_from_center < 5 else 1 if dist_from_center < 8 else 2)
""")

# --- Example B: Dynamic USD Light Rig ---
# Create a ring of lights programmatically

light_rig = nuke.createNode("GeoPython")
light_rig.setName("DynamicLightRig")
light_rig["code"].setValue("""
from pxr import Usd, UsdLux, UsdGeom, Gf
import math

stage = geo.GetStage()

# Create light rig root
rig = UsdGeom.Xform.Define(stage, "/World/LightRig")

# Parameters
num_lights = 8
radius = 5.0
height = 3.0
base_intensity = 500.0

# Create a ring of sphere lights
for i in range(num_lights):
    angle = (2.0 * math.pi * i) / num_lights
    x = radius * math.cos(angle)
    z = radius * math.sin(angle)

    light_path = f"/World/LightRig/RingLight_{i:02d}"
    light = UsdLux.SphereLight.Define(stage, light_path)
    light.AddTranslateOp().Set(Gf.Vec3d(x, height, z))
    light.CreateRadiusAttr(0.3)
    light.CreateIntensityAttr(base_intensity)

    # Alternate warm and cool colors
    if i % 2 == 0:
        light.CreateColorAttr(Gf.Vec3f(1.0, 0.9, 0.8))  # Warm
    else:
        light.CreateColorAttr(Gf.Vec3f(0.8, 0.9, 1.0))  # Cool

# Add a top-down key light
key = UsdLux.DistantLight.Define(stage, "/World/LightRig/TopKey")
key.CreateIntensityAttr(2.0)
key.CreateAngleAttr(1.0)
key.AddRotateXYZOp().Set(Gf.Vec3f(-60, 20, 0))
""")

# --- Example C: USD Attribute Inspector ---
# Query and print USD stage info

inspector = nuke.createNode("GeoPython")
inspector.setName("StageInspector")
inspector["code"].setValue("""
from pxr import Usd, UsdGeom

stage = geo.GetStage()

# Traverse the stage and report on all prims
print("=" * 50)
print("USD Stage Inspector")
print("=" * 50)
for prim in stage.Traverse():
    prim_type = prim.GetTypeName() or "Untyped"
    num_attrs = len(prim.GetAttributes())
    num_children = len(prim.GetChildren())
    print(f"  {prim.GetPath()} [{prim_type}] "
          f"attrs={num_attrs} children={num_children}")

    # Report materials
    if prim.HasAPI("MaterialBindingAPI"):
        from pxr import UsdShade
        binding = UsdShade.MaterialBindingAPI(prim)
        mat, rel = binding.ComputeBoundMaterial()
        if mat:
            print(f"    -> Material: {mat.GetPath()}")

print(f"\\nTotal prims: {len(list(stage.Traverse()))}")
print("=" * 50)
""")

# Connect the examples in a chain
light_rig.setInput(0, scatter_node)
inspector.setInput(0, light_rig)

# Render
cam = nuke.createNode("Camera3")
cam.setName("GeoPyCam")
cam["translate"].setValue([0, 5, -12])
cam["rotate"].setValue([-20, 0, 0])

render = nuke.createNode("ScanlineRender2")
render.setName("GeoPyRender")
render.setInput(1, inspector)
render.setInput(2, cam)

viewer = nuke.createNode("Viewer")
viewer.setInput(0, render)

print("GeoPython examples created!")
print("  A: ProceduralScatter - 50 scattered instances with LOD")
print("  B: DynamicLightRig - 8-light ring rig via USD API")
print("  C: StageInspector - USD stage traversal and reporting")
'''

    print("=" * 70)
    print("NUKE 17.0 - GeoPython: Direct USD Stage Manipulation")
    print("=" * 70)
    print(script)
    return script


if __name__ == "__main__":
    build_geo_python_examples_offline()
