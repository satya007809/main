"""
Example 3: Gaussian Splat Set Extension Workflow
==================================================
Nuke 17.0 Feature: Gaussian Splats for environment workflows

This example demonstrates a real-world set extension workflow:
- Import multiple Gaussian Splats (foreground scan + environment scan)
- Use Field nodes to blend splats at boundaries
- Combine with CG elements via ScanlineRender2
- Final composite with the original plate

This is the kind of workflow Nuke 17.0 was designed to enable:
matte painting and set extensions using captured Gaussian Splats.
"""


def build_set_extension_offline():
    """Generate set extension pipeline code for Nuke 17.0."""

    script = '''
import nuke

# ============================================================
# Set Extension with Gaussian Splats
# Nuke 17.0 Production Workflow
# ============================================================
# Scenario: Extend a practical set with a scanned environment.
# The foreground was shot on a stage, and the background
# environment was captured as a Gaussian Splat via photogrammetry.

# ==================== PLATE SETUP ====================

# Original camera footage
plate = nuke.createNode("Read")
plate.setName("OriginalPlate")
# plate["file"].setValue("/shots/sh010/plate/plate.####.exr")

# Matchmoved camera from 3D tracking
matchmove_cam = nuke.createNode("Camera3")
matchmove_cam.setName("MatchmoveCam")
matchmove_cam["translate"].setValue([0, 1.7, 0])
matchmove_cam["focal"].setValue(50)
# In production: import .chan or .fbx camera data

# ==================== SPLAT LAYERS ====================

# Layer 1: Background environment splat (distant buildings, sky)
env_splat = nuke.createNode("GeoImport")
env_splat.setName("EnvSplat_Background")
# env_splat["file"].setValue("/assets/env_scan/background.ply")

# Layer 2: Midground splat (street, vehicles, props)
mid_splat = nuke.createNode("GeoImport")
mid_splat.setName("EnvSplat_Midground")
# mid_splat["file"].setValue("/assets/env_scan/midground.ply")

# ==================== FIELD-BASED BLENDING ====================

# Create a FieldRamp to blend between mid and background
blend_field = nuke.createNode("FieldRamp")
blend_field.setName("DepthBlendField")
blend_field["start_point"].setValue([0, 0, 10])   # Near boundary
blend_field["end_point"].setValue([0, 0, 50])      # Far boundary

# Use FieldCrop to limit the environment to the set extension area
field_crop = nuke.createNode("FieldCrop")
field_crop.setName("SetExtensionBounds")
field_crop["min"].setValue([-50, -2, 5])
field_crop["max"].setValue([50, 30, 200])

# Grade the background splat to match plate color
env_grade = nuke.createNode("GeoGrade")
env_grade.setName("EnvColorMatch")
env_grade.setInput(0, env_splat)
env_grade.setInput(1, blend_field)
env_grade["gain"].setValue([0.95, 0.92, 1.05, 1.0])  # Warm up slightly
env_grade["lift"].setValue([0.01, 0.01, 0.02, 0.0])   # Atmospheric haze

# Grade midground
mid_grade = nuke.createNode("GeoGrade")
mid_grade.setName("MidColorMatch")
mid_grade.setInput(0, mid_splat)
mid_grade["gain"].setValue([1.0, 0.98, 1.02, 1.0])

# ==================== RENDER SPLATS ====================

# Render background environment
env_render = nuke.createNode("SplatRender")
env_render.setName("EnvRender")
env_render.setInput(0, env_grade)
env_render.setInput(1, matchmove_cam)
env_render["output_depth"].setValue(True)
env_render["motion_blur"].setValue(False)  # Static environment

# Render midground
mid_render = nuke.createNode("SplatRender")
mid_render.setName("MidRender")
mid_render.setInput(0, mid_grade)
mid_render.setInput(1, matchmove_cam)
mid_render["output_depth"].setValue(True)

# ==================== CG ELEMENT (USD) ====================

# Add a CG prop using the new USD 3D system
geo_read = nuke.createNode("GeoRead")
geo_read.setName("CG_Prop")
# geo_read["file"].setValue("/assets/cg/hero_prop.usd")

# Light the CG with new GeoLight nodes
dome_light = nuke.createNode("GeoDomeLight")
dome_light.setName("EnvLight")
# dome_light["texture"].setValue("/assets/hdri/set_env.exr")

distant_light = nuke.createNode("GeoDistantLight")
distant_light.setName("SunKey")
distant_light["rotate"].setValue([-45, 30, 0])
distant_light["intensity"].setValue(2.5)

# Render CG with ScanlineRender2 (now with raytracing!)
cg_render = nuke.createNode("ScanlineRender2")
cg_render.setName("CG_Render")
cg_render.setInput(0, nuke.createNode("Constant"))  # BG
cg_render.setInput(1, geo_read)
cg_render.setInput(2, matchmove_cam)
# ScanlineRender2 is now raytrace by default in Nuke 17.0

# ==================== FINAL COMPOSITE ====================

# Layer: Environment (far) + Midground + CG + Plate (near)
merge_env = nuke.createNode("Merge2")
merge_env.setName("Merge_EnvMid")
merge_env.setInput(0, env_render)
merge_env.setInput(1, mid_render)

merge_cg = nuke.createNode("Merge2")
merge_cg.setName("Merge_CG")
merge_cg.setInput(0, merge_env)
merge_cg.setInput(1, cg_render)

# Final over with original plate
merge_final = nuke.createNode("Merge2")
merge_final.setName("FinalComp")
merge_final.setInput(0, merge_cg)
merge_final.setInput(1, plate)
merge_final["operation"].setValue("over")

# Output
write = nuke.createNode("Write")
write.setName("FinalOutput")
write.setInput(0, merge_final)
# write["file"].setValue("/shots/sh010/comp/comp.####.exr")

viewer = nuke.createNode("Viewer")
viewer.setInput(0, merge_final)

print("Set extension pipeline complete!")
print("Layers: EnvSplat -> MidSplat -> CG -> Plate")
'''

    print("=" * 70)
    print("NUKE 17.0 - Gaussian Splat Set Extension Workflow")
    print("=" * 70)
    print(script)
    return script


if __name__ == "__main__":
    build_set_extension_offline()
