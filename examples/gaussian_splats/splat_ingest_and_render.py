"""
Example 1: Gaussian Splat Ingest & Render Pipeline
====================================================
Nuke 17.0 Feature: Native Gaussian Splat support

This example demonstrates:
- Importing a .ply Gaussian Splat file into Nuke's 3D system
- Setting up a Camera for the SplatRender node
- Rendering the splat to 2D with depth, motion blur, and Deep output
- Compositing the rendered splat over a background plate

New Nodes Used:
- GeoImport (for .ply splat files)
- SplatRender (renders splats to 2D pixels)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def build_splat_render_pipeline(session):
    """Build a complete Gaussian Splat ingest-to-render pipeline in Nuke 17.0."""

    code = '''
import nuke

# --- Step 1: Import the Gaussian Splat (.ply file) ---
geo_import = nuke.createNode("GeoImport")
geo_import.setName("SplatImport")
# In production, set: geo_import["file"].setValue("/path/to/scene.ply")

# --- Step 2: Create a Camera for rendering ---
camera = nuke.createNode("Camera3")
camera.setName("SplatCamera")
camera["translate"].setValue([0, 1.5, -5])
camera["rotate"].setValue([-10, 0, 0])
camera["focal"].setValue(35)

# --- Step 3: SplatRender - The star of Nuke 17.0 ---
# SplatRender converts 3D Gaussian Splats into 2D pixels
# It supports: motion blur, depth output, and Deep output
splat_render = nuke.createNode("SplatRender")
splat_render.setName("SplatRender_Main")

# Connect geo input and camera
splat_render.setInput(0, geo_import)   # Geometry/Splat input
splat_render.setInput(1, camera)       # Camera input

# Configure render settings
# Enable depth output for compositing
splat_render["output_depth"].setValue(True)
# Enable motion blur for animated splats
splat_render["motion_blur"].setValue(True)
splat_render["shutter"].setValue(0.5)

# --- Step 4: Background plate ---
bg_read = nuke.createNode("Read")
bg_read.setName("BackgroundPlate")
# bg_read["file"].setValue("/path/to/plate.####.exr")

# --- Step 5: Composite splat over background ---
merge = nuke.createNode("Merge2")
merge.setName("SplatComposite")
merge.setInput(0, bg_read)        # B input (background)
merge.setInput(1, splat_render)    # A input (splat render)
merge["operation"].setValue("over")

# --- Step 6: Extract depth for downstream use ---
shuffle_depth = nuke.createNode("Shuffle2")
shuffle_depth.setName("ExtractDepth")
shuffle_depth.setInput(0, splat_render)
# Shuffle depth channel to rgba for visualization
shuffle_depth["in1"].setValue("depth")

# --- Step 7: Output ---
write_node = nuke.createNode("Write")
write_node.setName("SplatOutput")
write_node.setInput(0, merge)
# write_node["file"].setValue("/path/to/output/splat_comp.####.exr")

# Organize nodes
for i, node in enumerate(nuke.allNodes()):
    node.setXYpos(0, i * 80)

result = "Gaussian Splat render pipeline created successfully!"
'''
    return session.conn.execute(code)


def build_splat_render_pipeline_offline():
    """
    Generate the Nuke Python code for the pipeline (no live connection needed).
    Can be copy-pasted into Nuke's Script Editor.
    """
    print("=" * 70)
    print("NUKE 17.0 - Gaussian Splat Ingest & Render Pipeline")
    print("=" * 70)
    print()
    print("Copy the following into Nuke 17.0's Script Editor:")
    print("-" * 70)

    script = '''
import nuke

# ============================================
# Gaussian Splat Ingest & Render Pipeline
# Nuke 17.0 New Feature Demonstration
# ============================================

# 1. Import Gaussian Splat
geo_import = nuke.createNode("GeoImport")
geo_import.setName("SplatImport")
# Set your .ply file path:
# geo_import["file"].setValue("/path/to/your/gaussian_splat.ply")

# 2. Camera Setup
cam = nuke.createNode("Camera3")
cam.setName("RenderCam")
cam["translate"].setValue([0, 1.5, -5])
cam["rotate"].setValue([-10, 0, 0])
cam["focal"].setValue(35)

# 3. SplatRender (NEW in Nuke 17.0)
# Renders Gaussian Splats to 2D with motion blur, depth, and Deep output
splat_render = nuke.createNode("SplatRender")
splat_render.setName("MainSplatRender")
splat_render.setInput(0, geo_import)
splat_render.setInput(1, cam)
splat_render["output_depth"].setValue(True)
splat_render["motion_blur"].setValue(True)
splat_render["shutter"].setValue(0.5)

# 4. Composite over background
bg = nuke.createNode("Constant")
bg.setName("BGPlaceholder")
bg["color"].setValue([0.2, 0.3, 0.4, 1.0])

merge = nuke.createNode("Merge2")
merge.setName("FinalComp")
merge.setInput(0, bg)
merge.setInput(1, splat_render)

# 5. Viewer
viewer = nuke.createNode("Viewer")
viewer.setInput(0, merge)

print("Splat render pipeline built successfully!")
'''
    print(script)
    return script


if __name__ == "__main__":
    print("Running in OFFLINE mode (no Nuke connection)")
    print("This generates code you can paste into Nuke 17.0's Script Editor.")
    print()
    build_splat_render_pipeline_offline()
