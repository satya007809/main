"""
Batch Blend — Analyze multiple reference images and blend their lighting.

Feed a mood board of images and get a combined lighting config that captures
the average mood across all references, with optional per-image weighting.

Usage:
    python batch_blend.py --images ref1.jpg ref2.jpg ref3.jpg --output blended.json
    python batch_blend.py --images ref1.jpg ref2.jpg --weights 0.7 0.3 --output blended.json
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional


def _deep_blend(configs: list[dict], weights: list[float]) -> dict:
    """
    Recursively blend multiple lighting configs by weighted average.

    Handles nested dicts, lists (element-wise blend), numbers (weighted avg),
    and strings (majority vote).
    """
    if not configs:
        return {}

    # Normalize weights
    total = sum(weights)
    weights = [w / total for w in weights]

    result = {}
    all_keys = set()
    for c in configs:
        if isinstance(c, dict):
            all_keys.update(c.keys())

    for key in all_keys:
        values = []
        value_weights = []
        for config, weight in zip(configs, weights):
            if isinstance(config, dict) and key in config:
                values.append(config[key])
                value_weights.append(weight)

        if not values:
            continue

        # Renormalize weights for available values
        w_total = sum(value_weights)
        value_weights = [w / w_total for w in value_weights]

        sample = values[0]

        if isinstance(sample, dict):
            # Recurse into nested dicts
            result[key] = _deep_blend(values, value_weights)

        elif isinstance(sample, list) and all(isinstance(v, (int, float)) for v in sample):
            # Blend numeric lists element-wise (e.g., RGB tint)
            length = len(sample)
            blended = [0.0] * length
            for vals, w in zip(values, value_weights):
                if len(vals) == length:
                    for i in range(length):
                        blended[i] += vals[i] * w
            result[key] = [round(v, 4) for v in blended]

        elif isinstance(sample, (int, float)):
            # Weighted average for numbers
            avg = sum(v * w for v, w in zip(values, value_weights))
            result[key] = round(avg, 4) if isinstance(sample, float) else round(avg)

        elif isinstance(sample, bool):
            # Majority vote for booleans
            true_weight = sum(w for v, w in zip(values, value_weights) if v)
            result[key] = true_weight > 0.5

        elif isinstance(sample, str):
            # Pick highest-weighted string, or combine descriptions
            if key == "description":
                result[key] = "Blended: " + " / ".join(
                    v for v in values if isinstance(v, str)
                )
            elif key == "mood":
                result[key] = "_".join(
                    v for v in values if isinstance(v, str)
                )[:50]
            else:
                # Majority vote
                vote_scores = {}
                for v, w in zip(values, value_weights):
                    vote_scores[v] = vote_scores.get(v, 0) + w
                result[key] = max(vote_scores, key=vote_scores.get)

        else:
            # Fallback: take highest-weighted value
            best_idx = value_weights.index(max(value_weights))
            result[key] = values[best_idx]

    return result


def blend_configs(configs: list[dict], weights: Optional[list[float]] = None) -> dict:
    """
    Blend multiple lighting configurations into one.

    Args:
        configs: List of lighting config dicts (from analyze_lighting.py)
        weights: Optional weights per config (default: equal weighting)

    Returns:
        Blended lighting config dict
    """
    if not configs:
        raise ValueError("No configs to blend")
    if len(configs) == 1:
        return configs[0]

    if weights is None:
        weights = [1.0] * len(configs)

    if len(weights) != len(configs):
        raise ValueError(f"Got {len(configs)} configs but {len(weights)} weights")

    return _deep_blend(configs, weights)


def analyze_and_blend(
    image_paths: list[str],
    weights: Optional[list[float]] = None,
    model: str = "claude-sonnet-4-20250514",
) -> dict:
    """
    Analyze multiple images and blend their lighting configs.

    Args:
        image_paths: Paths to reference images
        weights: Optional per-image weights
        model: Claude model to use
    """
    from analyze_lighting import analyze_image

    configs = []
    for i, path in enumerate(image_paths):
        print(f"[Blend] Analyzing image {i+1}/{len(image_paths)}: {path}", file=sys.stderr)
        config = analyze_image(Path(path), model=model)
        configs.append(config)

        mood = config.get("mood_metadata", {})
        print(f"  -> {mood.get('mood', '?')} ({mood.get('time_of_day', '?')})", file=sys.stderr)

    print(f"[Blend] Blending {len(configs)} configs...", file=sys.stderr)
    blended = blend_configs(configs, weights)

    mood = blended.get("mood_metadata", {})
    print(f"[Blend] Result: {mood.get('mood', '?')} ({mood.get('time_of_day', '?')})", file=sys.stderr)

    return blended


def main():
    parser = argparse.ArgumentParser(description="Analyze and blend lighting from multiple reference images")
    parser.add_argument("--images", "-i", nargs="+", required=True, help="Paths to reference images")
    parser.add_argument("--weights", "-w", nargs="+", type=float, default=None,
                        help="Per-image weights (default: equal)")
    parser.add_argument("--output", "-o", default=None, help="Output JSON file (default: stdout)")
    parser.add_argument("--model", "-m", default="claude-sonnet-4-20250514", help="Claude model to use")
    args = parser.parse_args()

    # Validate images exist
    for path in args.images:
        if not Path(path).exists():
            print(f"Error: Image not found: {path}", file=sys.stderr)
            sys.exit(1)

    blended = analyze_and_blend(args.images, args.weights, args.model)

    output_json = json.dumps(blended, indent=2)
    if args.output:
        Path(args.output).write_text(output_json)
        print(f"[Blend] Saved to: {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()
