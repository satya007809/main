"""
Example 2: Field Nodes for Non-Destructive Splat Masking
=========================================================
Nuke 17.0 Feature: Field Nodes system

This example demonstrates the new Field Nodes system for:
- Creating volumetric masks with FieldShape nodes
- Combining fields with FieldMath and FieldMix
- Inverting fields with FieldInvert
- Using fields to non-destructively mask Gaussian Splats
- Deleting points with GeoDeletePoints driven by fields

New Nodes Used:
- FieldSphere, FieldCube, FieldRamp (volumetric field shapes)
- FieldMath (math operations on fields)
- FieldMix (interpolate between fields)
- FieldInvert (invert a field)
- FieldCrop (crop a field to a bounding region)
- GeoDeletePoints (non-destructive point deletion)
- GeoGrade (color correct splats)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def build_field_masking_pipeline_offline():
    """
    Generate Nuke 17.0 Field Nodes pipeline code.
    Demonstrates isolating and manipulating parts of a Gaussian Splat
    using the new volumetric Field system.
    """

    script = '''
import nuke

# ============================================================
# Field Nodes: Non-Destructive Gaussian Splat Masking
# Nuke 17.0 New Feature Demonstration
# ============================================================
# Use Case: You have a scanned environment as a Gaussian Splat
# and need to isolate a specific region (e.g., remove a trash can,
# isolate a building, mask a character).

# --- 1. Import the Gaussian Splat ---
splat = nuke.createNode("GeoImport")
splat.setName("EnvironmentSplat")
# splat["file"].setValue("/path/to/environment_scan.ply")

# --- 2. Create Field Shapes for Volumetric Masking ---

# Sphere field - isolate a region of interest (e.g., a prop)
field_sphere = nuke.createNode("FieldSphere")
field_sphere.setName("IsolationSphere")
field_sphere["center"].setValue([2.0, 0.5, 1.0])
field_sphere["radius"].setValue(1.5)
# The field outputs a 0-1 value based on distance from center

# Cube field - define a floor plane exclusion zone
field_cube = nuke.createNode("FieldCube")
field_cube.setName("FloorExclusion")
field_cube["center"].setValue([0, -0.5, 0])
field_cube["size"].setValue([20, 1.0, 20])

# Ramp field - gradient falloff from top to bottom
field_ramp = nuke.createNode("FieldRamp")
field_ramp.setName("HeightGradient")
field_ramp["start_point"].setValue([0, 0, 0])
field_ramp["end_point"].setValue([0, 5, 0])

# --- 3. Combine Fields with FieldMath ---
# Subtract the floor zone from the sphere to get "above ground only"
field_math = nuke.createNode("FieldMath")
field_math.setName("CombinedMask")
field_math.setInput(0, field_sphere)
field_math.setInput(1, field_cube)
field_math["operation"].setValue("subtract")
# Result: sphere mask minus the floor = floating region mask

# --- 4. Blend Fields with FieldMix ---
# Mix between the combined mask and the height gradient for soft edges
field_mix = nuke.createNode("FieldMix")
field_mix.setName("SoftEdgeMask")
field_mix.setInput(0, field_math)
field_mix.setInput(1, field_ramp)
field_mix["mix"].setValue(0.7)

# --- 5. Invert the Field ---
# Create the inverse mask (everything EXCEPT our region)
field_invert = nuke.createNode("FieldInvert")
field_invert.setName("InvertedMask")
field_invert.setInput(0, field_mix)

# --- 6. GeoDeletePoints - Remove unwanted splats ---
# Use the inverted field to DELETE everything outside our region
delete_points = nuke.createNode("GeoDeletePoints")
delete_points.setName("CleanupDelete")
delete_points.setInput(0, splat)         # Geometry input
delete_points.setInput(1, field_invert)  # Field mask input
# Points where the field value > threshold get deleted

# --- 7. GeoGrade - Color correct the isolated splats ---
geo_grade = nuke.createNode("GeoGrade")
geo_grade.setName("SplatColorCorrect")
geo_grade.setInput(0, delete_points)     # Cleaned geometry
geo_grade.setInput(1, field_mix)         # Use field as mask
geo_grade["gain"].setValue([1.2, 1.1, 1.0, 1.0])
geo_grade["gamma"].setValue([1.1, 1.0, 0.9, 1.0])

# --- 8. Render the result ---
cam = nuke.createNode("Camera3")
cam.setName("FieldDemoCam")
cam["translate"].setValue([0, 2, -8])
cam["rotate"].setValue([-15, 0, 0])

splat_render = nuke.createNode("SplatRender")
splat_render.setName("MaskedSplatRender")
splat_render.setInput(0, geo_grade)
splat_render.setInput(1, cam)
splat_render["output_depth"].setValue(True)

viewer = nuke.createNode("Viewer")
viewer.setInput(0, splat_render)

print("Field masking pipeline built! Nodes created:")
print("  - FieldSphere, FieldCube, FieldRamp (shape generators)")
print("  - FieldMath (combine), FieldMix (blend), FieldInvert (invert)")
print("  - GeoDeletePoints (cleanup), GeoGrade (color correct)")
print("  - SplatRender (final output)")
'''

    print("=" * 70)
    print("NUKE 17.0 - Field Nodes: Non-Destructive Splat Masking")
    print("=" * 70)
    print()
    print("Copy the following into Nuke 17.0's Script Editor:")
    print("-" * 70)
    print(script)
    return script


def build_field_masking_pipeline(session):
    """Build the field masking pipeline via a live Nuke connection."""
    return session.conn.execute(
        build_field_masking_pipeline_offline().split("import nuke", 1)[1]
    )


if __name__ == "__main__":
    build_field_masking_pipeline_offline()
