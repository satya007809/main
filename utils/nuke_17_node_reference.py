"""
Nuke 17.0 New Node Quick Reference
====================================
A comprehensive reference of all new and updated nodes in Nuke 17.0.
"""

NUKE_17_NEW_NODES = {
    # === Gaussian Splat Nodes ===
    "SplatRender": {
        "category": "Gaussian Splats",
        "description": "Renders Gaussian Splats to 2D pixels with motion blur, depth, and Deep output",
        "inputs": ["geometry/splat", "camera"],
        "key_knobs": ["output_depth", "motion_blur", "shutter"],
        "new_in": "17.0",
    },
    "GeoDeletePoints": {
        "category": "Gaussian Splats",
        "description": "Non-destructively delete point data (splats) using field masks",
        "inputs": ["geometry", "field_mask"],
        "key_knobs": ["threshold"],
        "new_in": "17.0",
    },
    "GeoGrade": {
        "category": "Gaussian Splats",
        "description": "Color correct Gaussian Splats with masking support",
        "inputs": ["geometry", "field_mask"],
        "key_knobs": ["gain", "gamma", "lift", "offset"],
        "new_in": "17.0",
    },

    # === Field Nodes ===
    "FieldSphere": {
        "category": "Fields",
        "description": "Generates a spherical volumetric field",
        "inputs": [],
        "key_knobs": ["center", "radius"],
        "new_in": "17.0",
    },
    "FieldCube": {
        "category": "Fields",
        "description": "Generates a cubic volumetric field",
        "inputs": [],
        "key_knobs": ["center", "size"],
        "new_in": "17.0",
    },
    "FieldRamp": {
        "category": "Fields",
        "description": "Generates a gradient ramp field between two points",
        "inputs": [],
        "key_knobs": ["start_point", "end_point"],
        "new_in": "17.0",
    },
    "FieldCrop": {
        "category": "Fields",
        "description": "Crops a field to a bounding region",
        "inputs": ["field"],
        "key_knobs": ["min", "max"],
        "new_in": "17.0",
    },
    "FieldImage": {
        "category": "Fields",
        "description": "Creates a field from a 2D image",
        "inputs": ["image"],
        "key_knobs": [],
        "new_in": "17.0",
    },
    "FieldMath": {
        "category": "Fields",
        "description": "Performs math operations (add, subtract, multiply, etc.) on fields",
        "inputs": ["field_a", "field_b"],
        "key_knobs": ["operation"],
        "new_in": "17.0",
    },
    "FieldMix": {
        "category": "Fields",
        "description": "Interpolates between two fields",
        "inputs": ["field_a", "field_b"],
        "key_knobs": ["mix"],
        "new_in": "17.0",
    },
    "FieldInvert": {
        "category": "Fields",
        "description": "Inverts a field (1 - field_value)",
        "inputs": ["field"],
        "key_knobs": [],
        "new_in": "17.0",
    },
    "FieldConstant": {
        "category": "Fields",
        "description": "Generates a field with a constant value",
        "inputs": [],
        "key_knobs": ["value"],
        "new_in": "17.0",
    },

    # === USD / 3D System ===
    "GeoMaterialXStandardSurface": {
        "category": "USD Materials",
        "description": "MaterialX Standard Surface shader (Autodesk Standard Surface model)",
        "inputs": [],
        "key_knobs": ["base_color", "metalness", "specular_roughness", "specular_IOR",
                       "transmission", "subsurface", "coat"],
        "new_in": "17.0",
    },
    "GeoBindMaterial": {
        "category": "USD Materials",
        "description": "Bind/override materials on USD geometry prims",
        "inputs": ["geometry", "material"],
        "key_knobs": ["prim_path"],
        "new_in": "17.0 (enhanced)",
    },
    "GeoDistantLight": {
        "category": "USD Lighting",
        "description": "USD Distant (directional) light",
        "inputs": [],
        "key_knobs": ["intensity", "color", "rotate", "shadow_enable"],
        "new_in": "17.0",
    },
    "GeoDiskLight": {
        "category": "USD Lighting",
        "description": "USD Disk area light",
        "inputs": [],
        "key_knobs": ["intensity", "color", "translate", "radius"],
        "new_in": "17.0",
    },
    "GeoDomeLight": {
        "category": "USD Lighting",
        "description": "USD Dome (environment) light with HDRI texture support",
        "inputs": [],
        "key_knobs": ["intensity", "color", "texture"],
        "new_in": "17.0",
    },
    "GeoSphereLight": {
        "category": "USD Lighting",
        "description": "USD Sphere (point) light",
        "inputs": [],
        "key_knobs": ["intensity", "color", "translate", "radius"],
        "new_in": "17.0",
    },
    "GeoPython": {
        "category": "USD Scripting",
        "description": "Direct Python access to USD stage data for scripted edits",
        "inputs": ["geometry"],
        "key_knobs": ["code"],
        "new_in": "17.0",
    },

    # === Rendering ===
    "ScanlineRender2": {
        "category": "3D Rendering",
        "description": "Unified raytrace renderer (replaces ScanlineRender + RayRender). "
                       "Raytrace by default, includes UV unwrap projection mode.",
        "inputs": ["background", "geometry", "camera"],
        "key_knobs": ["raytrace", "uv_unwrap"],
        "new_in": "17.0 (major update)",
    },
}


def print_reference():
    """Print the full Nuke 17.0 node reference."""
    categories = {}
    for name, info in NUKE_17_NEW_NODES.items():
        cat = info["category"]
        categories.setdefault(cat, []).append((name, info))

    print("=" * 70)
    print("NUKE 17.0 - NEW NODE REFERENCE")
    print("=" * 70)

    for cat, nodes in sorted(categories.items()):
        print(f"\n{'─' * 50}")
        print(f"  {cat}")
        print(f"{'─' * 50}")
        for name, info in nodes:
            print(f"\n  {name} (new in {info['new_in']})")
            print(f"    {info['description']}")
            if info["inputs"]:
                print(f"    Inputs: {', '.join(info['inputs'])}")
            if info["key_knobs"]:
                print(f"    Key knobs: {', '.join(info['key_knobs'])}")

    print(f"\n{'=' * 70}")
    print(f"Total new/updated nodes: {len(NUKE_17_NEW_NODES)}")


if __name__ == "__main__":
    print_reference()
