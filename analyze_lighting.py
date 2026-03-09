"""
Image-to-Lighting Analyzer

Analyzes a reference image using Claude's vision capabilities and extracts
structured lighting parameters compatible with Unreal Engine.

Usage:
    python analyze_lighting.py --image reference.jpg --output lighting_config.json
"""

import argparse
import base64
import json
import sys
from pathlib import Path

import anthropic

LIGHTING_ANALYSIS_PROMPT = """Analyze this reference image and extract lighting parameters for recreating a similar mood in Unreal Engine 5.

Return a JSON object with EXACTLY this structure (no markdown, no explanation, just valid JSON):

{
  "directional_light": {
    "rotation_pitch": <float, sun elevation: -90=overhead, 0=horizon>,
    "rotation_yaw": <float, 0-360 azimuth, estimate from shadow direction>,
    "intensity_lux": <float, sunny=100000, overcast=10000, twilight=1000, night=0.5>,
    "color_temperature_kelvin": <float, sunrise=3000, noon=5500, overcast=7000, blue_hour=9000>,
    "light_source_angle": <float, 0-5, sharp shadows=0.2, soft=2.0>
  },
  "sky_atmosphere": {
    "rayleigh_scattering_scale": <float, 0-5, default 1.0, increase for bluer sky>,
    "mie_scattering_scale": <float, 0-5, default 1.0, increase for hazy/glowy sun>,
    "absorption_scale": <float, 0-5, default 1.0>
  },
  "sky_light": {
    "intensity_scale": <float, 0-10, how much ambient fill>,
    "tint": [<R>, <G>, <B>] (0-1 normalized, tint the ambient light)
  },
  "exponential_height_fog": {
    "enabled": <bool>,
    "fog_density": <float, 0-1>,
    "fog_color": [<R>, <G>, <B>] (0-1 normalized),
    "fog_height_falloff": <float, 0-5>,
    "start_distance": <float, cm from camera>,
    "volumetric_fog": <bool>
  },
  "post_process": {
    "exposure_compensation": <float, -10 to 10>,
    "bloom_intensity": <float, 0-8>,
    "white_balance_temp": <float, Kelvin>,
    "vignette_intensity": <float, 0-1>,
    "saturation": <float, 0-2, 1=normal>,
    "contrast": <float, 0-2, 1=normal>
  },
  "mood_metadata": {
    "time_of_day": "<dawn|sunrise|morning|noon|afternoon|golden_hour|sunset|blue_hour|dusk|night|midnight>",
    "mood": "<short_mood_description>",
    "weather": "<clear|partly_cloudy|overcast|foggy|rainy|stormy|snowy|hazy>",
    "indoor_outdoor": "<outdoor|indoor|mixed>",
    "description": "<brief natural language description of the lighting>"
  }
}

Be precise with numerical values. Base them on real-world photographic and cinematographic principles."""


def encode_image(image_path: Path) -> tuple[str, str]:
    """Read and base64-encode an image file. Returns (base64_data, media_type)."""
    suffix = image_path.suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    media_type = media_types.get(suffix)
    if not media_type:
        raise ValueError(f"Unsupported image format: {suffix}. Use JPG, PNG, GIF, or WebP.")

    with open(image_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    return data, media_type


def analyze_image(image_path: Path, model: str = "claude-sonnet-4-20250514") -> dict:
    """Send an image to Claude Vision and extract lighting parameters."""
    client = anthropic.Anthropic()
    image_data, media_type = encode_image(image_path)

    message = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": LIGHTING_ANALYSIS_PROMPT,
                    },
                ],
            }
        ],
    )

    response_text = message.content[0].text.strip()

    # Handle case where model wraps JSON in markdown code block
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        response_text = "\n".join(lines)

    return json.loads(response_text)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze a reference image and extract UE5 lighting parameters"
    )
    parser.add_argument("--image", "-i", required=True, help="Path to reference image")
    parser.add_argument("--output", "-o", default=None, help="Output JSON file path (default: stdout)")
    parser.add_argument("--model", "-m", default="claude-sonnet-4-20250514", help="Claude model to use")
    parser.add_argument("--pretty", action="store_true", default=True, help="Pretty-print JSON output")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"Error: Image not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing: {image_path}", file=sys.stderr)
    config = analyze_image(image_path, model=args.model)

    indent = 2 if args.pretty else None
    output_json = json.dumps(config, indent=indent)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output_json)
        print(f"Lighting config saved to: {output_path}", file=sys.stderr)
    else:
        print(output_json)

    # Print mood summary
    mood = config.get("mood_metadata", {})
    print(f"\nMood: {mood.get('mood', 'unknown')}", file=sys.stderr)
    print(f"Time: {mood.get('time_of_day', 'unknown')}", file=sys.stderr)
    print(f"Description: {mood.get('description', 'N/A')}", file=sys.stderr)


if __name__ == "__main__":
    main()
