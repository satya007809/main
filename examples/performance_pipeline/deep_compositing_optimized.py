"""
Example 9: Optimized Deep Compositing Pipeline
================================================
Nuke 17.0 Feature: Up to 1.88x faster deep composite rendering

This example demonstrates:
- Building deep compositing workflows leveraging 17.0 performance gains
- Deep merge, deep holdout, and deep recolor operations
- Integrating SplatRender deep output with CG deep renders
- Efficient multi-layer deep comp with the new speed improvements

Performance Note:
Nuke 17.0 offers up to 1.88x faster deep composite rendering to disk
and in the Nuke viewer, making complex deep workflows more practical.
"""


def build_deep_comp_pipeline_offline():
    """Generate optimized deep compositing pipeline for Nuke 17.0."""

    script = '''
import nuke

# ============================================================
# Optimized Deep Compositing Pipeline
# Nuke 17.0 - 1.88x Faster Deep Rendering
# ============================================================
# Deep compositing in 17.0 is significantly faster for both
# disk rendering and viewer display. This makes it practical
# for more complex multi-element deep workflows.

# --- 1. Deep CG Renders (multiple layers) ---

# Hero character deep render
deep_hero = nuke.createNode("DeepRead")
deep_hero.setName("DeepCG_Hero")
deep_hero["label"].setValue("Hero Character\\nDeep EXR")
# deep_hero["file"].setValue("/cg/hero/deep_hero.####.exr")

# Environment deep render
deep_env = nuke.createNode("DeepRead")
deep_env.setName("DeepCG_Environment")
deep_env["label"].setValue("Environment\\nDeep EXR")
# deep_env["file"].setValue("/cg/env/deep_env.####.exr")

# FX elements (particles, smoke, etc.)
deep_fx = nuke.createNode("DeepRead")
deep_fx.setName("DeepCG_FX")
deep_fx["label"].setValue("FX Elements\\nDeep EXR")
# deep_fx["file"].setValue("/cg/fx/deep_fx.####.exr")

# --- 2. Gaussian Splat Deep Output (New in 17.0!) ---
# SplatRender can output Deep data for integration
# (Simulated here with a placeholder)

splat_import = nuke.createNode("GeoImport")
splat_import.setName("EnvSplat")

cam = nuke.createNode("Camera3")
cam.setName("DeepCompCam")
cam["translate"].setValue([0, 1.7, -5])
cam["focal"].setValue(35)

splat_render = nuke.createNode("SplatRender")
splat_render.setName("SplatDeepRender")
splat_render.setInput(0, splat_import)
splat_render.setInput(1, cam)
splat_render["output_depth"].setValue(True)
# SplatRender outputs Deep data for compositing with CG

# Convert to deep if needed
splat_to_deep = nuke.createNode("DeepFromImage")
splat_to_deep.setName("SplatToDeep")
splat_to_deep.setInput(0, splat_render)

# --- 3. Deep Merge All Elements ---
# With 1.88x speed improvement, complex merges are now practical

# Merge hero + environment
deep_merge1 = nuke.createNode("DeepMerge")
deep_merge1.setName("Merge_HeroEnv")
deep_merge1.setInput(0, deep_hero)
deep_merge1.setInput(1, deep_env)

# Add FX layer
deep_merge2 = nuke.createNode("DeepMerge")
deep_merge2.setName("Merge_AddFX")
deep_merge2.setInput(0, deep_merge1)
deep_merge2.setInput(1, deep_fx)

# Add splat environment
deep_merge3 = nuke.createNode("DeepMerge")
deep_merge3.setName("Merge_AddSplat")
deep_merge3.setInput(0, deep_merge2)
deep_merge3.setInput(1, splat_to_deep)

# --- 4. Deep Operations ---

# Deep holdout - occlude elements behind a surface
deep_holdout = nuke.createNode("DeepHoldout")
deep_holdout.setName("OcclusionHoldout")
deep_holdout.setInput(0, deep_merge3)
# Input 1: holdout geometry

# Deep color correct
deep_recolor = nuke.createNode("DeepRecolor")
deep_recolor.setName("DeepRecolor_Hero")
deep_recolor.setInput(0, deep_hero)
# Recolor with a graded flat render for better control

# Deep expression for custom depth-based effects
deep_expr = nuke.createNode("DeepExpression")
deep_expr.setName("DepthFog")
deep_expr.setInput(0, deep_merge3)
# Apply exponential fog based on deep depth
# deep_expr["chans0"].setValue("rgba")
# deep_expr["expr0"].setValue("r * exp(-deep.front * 0.05)")

# --- 5. Flatten to 2D ---
deep_to_image = nuke.createNode("DeepToImage")
deep_to_image.setName("FlattenDeep")
deep_to_image.setInput(0, deep_merge3)

# --- 6. Post-flatten compositing ---
# Background plate
bg_plate = nuke.createNode("Read")
bg_plate.setName("BGPlate")

final_merge = nuke.createNode("Merge2")
final_merge.setName("FinalOver")
final_merge.setInput(0, bg_plate)
final_merge.setInput(1, deep_to_image)

# --- 7. Output ---
write = nuke.createNode("Write")
write.setName("DeepCompOutput")
write.setInput(0, final_merge)
write["label"].setValue("Deep Comp Final")

# Also write the full deep for downstream
deep_write = nuke.createNode("DeepWrite")
deep_write.setName("DeepArchive")
deep_write.setInput(0, deep_merge3)
deep_write["label"].setValue("Deep Archive\\nAll Layers Merged")

viewer = nuke.createNode("Viewer")
viewer.setInput(0, final_merge)

print("Deep compositing pipeline complete!")
print("Elements: Hero CG + Environment CG + FX + Gaussian Splat")
print("Operations: DeepMerge, DeepHoldout, DeepRecolor, DeepExpression")
print("Nuke 17.0: Up to 1.88x faster deep rendering!")
'''

    print("=" * 70)
    print("NUKE 17.0 - Optimized Deep Compositing Pipeline")
    print("=" * 70)
    print(script)
    return script


if __name__ == "__main__":
    build_deep_comp_pipeline_offline()
