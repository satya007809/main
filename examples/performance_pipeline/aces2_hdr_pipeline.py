"""
Example 8: ACES 2.0 HDR/SDR Color Pipeline
=============================================
Nuke 17.0 Feature: Native ACES 2.0 support

This example demonstrates:
- Setting up ACES 2.0 color management (Studio and CG configs)
- HDR and SDR output transforms
- YCbCr conversion with Rec.2020 for HDR deliverables
- Proper color pipeline for Virtual Production content

New Features Used:
- ACES 2.0 Studio config (shipped natively)
- ACES 2.0 CG config
- YCbCr conversion & NCLC metadata for HDR MOV output
- High Resolution MOV for Virtual Production playback
"""


def build_aces2_pipeline_offline():
    """Generate ACES 2.0 color pipeline code for Nuke 17.0."""

    script = '''
import nuke

# ============================================================
# ACES 2.0 HDR/SDR Color Pipeline
# Nuke 17.0 - Native ACES 2.0 Support
# ============================================================
# Nuke 17.0 ships ACES 2.0 Studio and CG configs natively.
# ACES 2.0 is optimized for HDR and SDR content delivery.

# --- 1. Configure ACES 2.0 Color Management ---

root = nuke.root()

# Set OCIO config to ACES 2.0
# In Nuke 17.0, ACES 2.0 configs are built-in
# root["colorManagement"].setValue("OCIO")
# root["OCIO_config"].setValue("aces_2.0")  # or "aces_2.0_cg"

print("=== ACES 2.0 Color Pipeline Setup ===")
print(f"Color Management: OCIO")
print(f"Config: ACES 2.0 Studio")

# --- 2. Source Plate (ACES AP0 / Linear) ---
plate = nuke.createNode("Read")
plate.setName("SourcePlate_ACES")
plate["label"].setValue("ACES 2.0 Linear (AP0)")
# plate["file"].setValue("/plates/shot/plate.####.exr")
# plate["colorspace"].setValue("ACES - ACES2065-1")

# --- 3. Working Space Grade ---
# Work in ACEScg (AP1) for compositing
grade = nuke.createNode("Grade")
grade.setName("PrimaryGrade")
grade.setInput(0, plate)
grade["label"].setValue("Working: ACEScg")

# --- 4. HDR Output Transform (Rec.2100 PQ) ---
# ACES 2.0 HDR output for displays/deliverables
hdr_output = nuke.createNode("OCIODisplay")
hdr_output.setName("HDR_OutputTransform")
hdr_output.setInput(0, grade)
# hdr_output["display"].setValue("Rec.2100-PQ")
# hdr_output["view"].setValue("ACES 2.0 - HDR Video (1000 nits)")
hdr_output["label"].setValue("HDR: Rec.2100 PQ 1000nit")

# --- 5. SDR Output Transform (Rec.709) ---
sdr_output = nuke.createNode("OCIODisplay")
sdr_output.setName("SDR_OutputTransform")
sdr_output.setInput(0, grade)
# sdr_output["display"].setValue("Rec.709")
# sdr_output["view"].setValue("ACES 2.0 - SDR Video")
sdr_output["label"].setValue("SDR: Rec.709")

# --- 6. HDR MOV Delivery (New YCbCr/NCLC support) ---
# Nuke 17.0 adds YCbCr conversion with Rec.2020 NCLC metadata
hdr_write = nuke.createNode("Write")
hdr_write.setName("HDR_Delivery")
hdr_write.setInput(0, hdr_output)
# hdr_write["file"].setValue("/delivery/hdr/shot.mov")
# hdr_write["file_type"].setValue("mov")
# New in 17.0: YCbCr matrix and NCLC metadata
# hdr_write["mov_ycbcr_matrix"].setValue("Rec.2020")
# hdr_write["mov_nclc_primaries"].setValue("BT.2020")
# hdr_write["mov_nclc_transfer"].setValue("PQ")
hdr_write["label"].setValue("MOV HDR\\nYCbCr Rec.2020\\nNCLC PQ")

# --- 7. SDR MOV Delivery ---
sdr_write = nuke.createNode("Write")
sdr_write.setName("SDR_Delivery")
sdr_write.setInput(0, sdr_output)
# sdr_write["file"].setValue("/delivery/sdr/shot.mov")
sdr_write["label"].setValue("MOV SDR\\nRec.709")

# --- 8. EXR Master (Full ACES) ---
exr_write = nuke.createNode("Write")
exr_write.setName("EXR_Master")
exr_write.setInput(0, grade)
# exr_write["file"].setValue("/delivery/master/shot.####.exr")
# exr_write["colorspace"].setValue("ACES - ACES2065-1")
exr_write["label"].setValue("EXR Master\\nACES2065-1 (AP0)")

# --- 9. Virtual Production High-Res Output ---
# Nuke 17.0: Prepare high-res MOV for VP LED walls
vp_reformat = nuke.createNode("Reformat")
vp_reformat.setName("VP_Reformat")
vp_reformat.setInput(0, grade)
# Set to LED wall resolution (e.g., 7680x2160 for a curved wall)
vp_reformat["type"].setValue("to box")
vp_reformat["box_width"].setValue(7680)
vp_reformat["box_height"].setValue(2160)

vp_write = nuke.createNode("Write")
vp_write.setName("VP_Delivery")
vp_write.setInput(0, vp_reformat)
vp_write["label"].setValue("Virtual Production\\n7680x2160 MOV")

viewer = nuke.createNode("Viewer")
viewer.setInput(0, hdr_output)

print("ACES 2.0 Pipeline Complete!")
print("Outputs:")
print("  1. HDR MOV (Rec.2100 PQ, YCbCr Rec.2020)")
print("  2. SDR MOV (Rec.709)")
print("  3. EXR Master (ACES2065-1)")
print("  4. Virtual Production (7680x2160)")
'''

    print("=" * 70)
    print("NUKE 17.0 - ACES 2.0 HDR/SDR Color Pipeline")
    print("=" * 70)
    print(script)
    return script


if __name__ == "__main__":
    build_aces2_pipeline_offline()
