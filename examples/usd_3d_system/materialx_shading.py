"""
Example 4: MaterialX Standard Surface Shading Pipeline
========================================================
Nuke 17.0 Feature: MaterialX Shader Support in USD 3D System

This example demonstrates:
- Creating MaterialX Standard Surface materials
- Binding materials to USD geometry with GeoBindMaterial
- Setting up physically-based material properties
- Previewing in the Hydra Viewer
- Rendering through ScanlineRender2

New Nodes Used:
- GeoMaterialXStandardSurface (first MaterialX shader node in Nuke)
- GeoBindMaterial (assign materials to geometry prims)
- ScanlineRender2 (raytrace renderer)
"""


def build_materialx_pipeline_offline():
    """Generate a MaterialX shading pipeline for Nuke 17.0."""

    script = '''
import nuke

# ============================================================
# MaterialX Standard Surface Shading Pipeline
# Nuke 17.0 - First MaterialX Shader Support
# ============================================================
# The Autodesk Standard Surface model is now available natively
# in Nuke via MaterialX, enabling PBR material workflows that
# are compatible with other DCC tools (Maya, Houdini, etc.)

# --- 1. Import USD Geometry ---
geo_read = nuke.createNode("GeoRead")
geo_read.setName("HeroAsset")
# geo_read["file"].setValue("/assets/hero_character.usd")

# --- 2. Create MaterialX Standard Surface Materials ---

# Material A: Chrome/Metal surface
chrome_mat = nuke.createNode("GeoMaterialXStandardSurface")
chrome_mat.setName("ChromeMaterial")
chrome_mat["base_color"].setValue([0.8, 0.8, 0.85])
chrome_mat["metalness"].setValue(1.0)
chrome_mat["specular_roughness"].setValue(0.05)
chrome_mat["specular_color"].setValue([1.0, 1.0, 1.0])
chrome_mat["specular_IOR"].setValue(2.5)

# Material B: Rough concrete
concrete_mat = nuke.createNode("GeoMaterialXStandardSurface")
concrete_mat.setName("ConcreteMaterial")
concrete_mat["base_color"].setValue([0.35, 0.33, 0.30])
concrete_mat["metalness"].setValue(0.0)
concrete_mat["specular_roughness"].setValue(0.85)
concrete_mat["specular"].setValue(0.3)
# For texture maps, you'd connect a GeoTexture node:
# concrete_mat["base_color_texture"].setValue("/textures/concrete_diffuse.exr")

# Material C: Translucent skin/wax
skin_mat = nuke.createNode("GeoMaterialXStandardSurface")
skin_mat.setName("SkinMaterial")
skin_mat["base_color"].setValue([0.8, 0.5, 0.4])
skin_mat["metalness"].setValue(0.0)
skin_mat["specular_roughness"].setValue(0.4)
skin_mat["subsurface"].setValue(0.3)
skin_mat["subsurface_color"].setValue([0.9, 0.3, 0.2])
skin_mat["subsurface_radius"].setValue([1.0, 0.5, 0.25])
skin_mat["coat"].setValue(0.5)
skin_mat["coat_roughness"].setValue(0.1)

# Material D: Glass/transparent
glass_mat = nuke.createNode("GeoMaterialXStandardSurface")
glass_mat.setName("GlassMaterial")
glass_mat["base_color"].setValue([0.95, 0.97, 1.0])
glass_mat["metalness"].setValue(0.0)
glass_mat["specular_roughness"].setValue(0.0)
glass_mat["specular_IOR"].setValue(1.52)
glass_mat["transmission"].setValue(0.95)
glass_mat["transmission_color"].setValue([0.97, 0.99, 1.0])

# --- 3. Bind Materials to Geometry ---
# GeoBindMaterial allows overriding existing USD material assignments

bind_chrome = nuke.createNode("GeoBindMaterial")
bind_chrome.setName("BindChrome")
bind_chrome.setInput(0, geo_read)
bind_chrome.setInput(1, chrome_mat)
# bind_chrome["prim_path"].setValue("/World/Hero/MetalParts")

bind_concrete = nuke.createNode("GeoBindMaterial")
bind_concrete.setName("BindConcrete")
bind_concrete.setInput(0, bind_chrome)
bind_concrete.setInput(1, concrete_mat)
# bind_concrete["prim_path"].setValue("/World/Environment/Ground")

# --- 4. USD Lighting Setup ---
# New GeoLight nodes in Nuke 17.0

dome_light = nuke.createNode("GeoDomeLight")
dome_light.setName("HDRI_Dome")
dome_light["intensity"].setValue(1.0)
# dome_light["texture"].setValue("/hdri/studio_env.exr")

key_light = nuke.createNode("GeoDistantLight")
key_light.setName("KeyLight")
key_light["rotate"].setValue([-45, 30, 0])
key_light["intensity"].setValue(3.0)
key_light["color"].setValue([1.0, 0.95, 0.9])
# New in 17.0: Shadow controls
# key_light["shadow_enable"].setValue(True)
# key_light["shadow_color"].setValue([0.05, 0.05, 0.08])

rim_light = nuke.createNode("GeoSphereLight")
rim_light.setName("RimLight")
rim_light["translate"].setValue([-3, 2, 2])
rim_light["intensity"].setValue(5.0)
rim_light["color"].setValue([0.6, 0.7, 1.0])
rim_light["radius"].setValue(0.5)

fill_light = nuke.createNode("GeoDiskLight")
fill_light.setName("FillLight")
fill_light["translate"].setValue([2, 1, -3])
fill_light["intensity"].setValue(1.5)
fill_light["color"].setValue([0.9, 0.9, 1.0])

# --- 5. Camera ---
cam = nuke.createNode("Camera3")
cam.setName("RenderCam")
cam["translate"].setValue([0, 1.6, -4])
cam["rotate"].setValue([-5, 0, 0])
cam["focal"].setValue(50)

# --- 6. ScanlineRender2 (Raytrace by default in 17.0) ---
render = nuke.createNode("ScanlineRender2")
render.setName("MaterialXRender")
render.setInput(1, bind_concrete)  # Geometry
render.setInput(2, cam)            # Camera
# ScanlineRender2 now unifies ScanlineRender + RayRender
# Raytracing is enabled by default for accurate reflections

# --- 7. Output ---
viewer = nuke.createNode("Viewer")
viewer.setInput(0, render)

print("MaterialX shading pipeline complete!")
print("Materials: Chrome, Concrete, Skin, Glass")
print("Lights: Dome, Key (Distant), Rim (Sphere), Fill (Disk)")
print("Renderer: ScanlineRender2 (raytrace mode)")
'''

    print("=" * 70)
    print("NUKE 17.0 - MaterialX Standard Surface Shading Pipeline")
    print("=" * 70)
    print(script)
    return script


if __name__ == "__main__":
    build_materialx_pipeline_offline()
