#!/usr/bin/env python3
"""
Nuke 17.0 Exploration - Main Launcher
=======================================
Run examples in offline mode (generates code for Nuke's Script Editor)
or connect to a running Nuke instance.

Usage:
    python run_examples.py                  # Interactive menu
    python run_examples.py --list           # List all examples
    python run_examples.py --example 1      # Run specific example
    python run_examples.py --connect        # Connect to Nuke and run
    python run_examples.py --reference      # Show new node reference
"""

import argparse
import sys

from examples.gaussian_splats.splat_ingest_and_render import (
    build_splat_render_pipeline_offline,
    build_splat_render_pipeline,
)
from examples.gaussian_splats.field_nodes_splat_masking import (
    build_field_masking_pipeline_offline,
)
from examples.gaussian_splats.splat_set_extension import (
    build_set_extension_offline,
)
from examples.usd_3d_system.materialx_shading import (
    build_materialx_pipeline_offline,
)
from examples.usd_3d_system.geo_python_usd_scripting import (
    build_geo_python_examples_offline,
)
from examples.annotations_gsv.annotations_review_system import (
    build_annotations_review_offline,
)
from examples.annotations_gsv.graph_scope_variables import (
    build_gsv_multishot_offline,
)
from examples.performance_pipeline.aces2_hdr_pipeline import (
    build_aces2_pipeline_offline,
)
from examples.performance_pipeline.deep_compositing_optimized import (
    build_deep_comp_pipeline_offline,
)
from utils.nuke_17_node_reference import print_reference


EXAMPLES = [
    ("Gaussian Splat Ingest & Render Pipeline", build_splat_render_pipeline_offline),
    ("Field Nodes: Non-Destructive Splat Masking", build_field_masking_pipeline_offline),
    ("Gaussian Splat Set Extension Workflow", build_set_extension_offline),
    ("MaterialX Standard Surface Shading", build_materialx_pipeline_offline),
    ("GeoPython: USD Stage Manipulation", build_geo_python_examples_offline),
    ("Enhanced Annotations Review System", build_annotations_review_offline),
    ("Graph Scope Variables: Multishot Pipeline", build_gsv_multishot_offline),
    ("ACES 2.0 HDR/SDR Color Pipeline", build_aces2_pipeline_offline),
    ("Optimized Deep Compositing Pipeline", build_deep_comp_pipeline_offline),
]


def show_menu():
    """Display the interactive example menu."""
    print()
    print("=" * 70)
    print("  NUKE 17.0 EXPLORATION - Unique Examples & Workflows")
    print("=" * 70)
    print()
    print("  Examples (generates code you can paste into Nuke 17.0):")
    print()

    categories = {
        "Gaussian Splats (NEW)": [0, 1, 2],
        "USD 3D System (NEW)": [3, 4],
        "Annotations & GSVs (ENHANCED)": [5, 6],
        "Performance & Pipeline": [7, 8],
    }

    for cat, indices in categories.items():
        print(f"  --- {cat} ---")
        for i in indices:
            print(f"    [{i + 1}] {EXAMPLES[i][0]}")
        print()

    print("  [R] Node Reference - All new Nuke 17.0 nodes")
    print("  [C] Connect to Nuke - Run examples on a live Nuke instance")
    print("  [A] Run ALL examples")
    print("  [Q] Quit")
    print()

    return input("  Select an option: ").strip()


def run_example(index):
    """Run a specific example by index (0-based)."""
    if 0 <= index < len(EXAMPLES):
        name, func = EXAMPLES[index]
        print(f"\nRunning: {name}")
        func()
    else:
        print(f"Invalid example number. Choose 1-{len(EXAMPLES)}")


def connect_and_run():
    """Connect to a running Nuke instance and run an example."""
    from nuke_connection import NukeConnector

    host = input("  Nuke host [localhost]: ").strip() or "localhost"
    port_str = input("  Nuke port [50007]: ").strip() or "50007"
    port = int(port_str)

    print(f"\nConnecting to Nuke at {host}:{port}...")
    print("(Make sure you've started the server in Nuke's Script Editor:")
    print("  from nuke_connection.server import start_server")
    print(f"  start_server(port={port})")
    print()

    conn = NukeConnector(host=host, port=port)
    if conn.connect():
        print("Connected! You can now run examples on the live Nuke instance.")
        # Run splat pipeline as a demo
        from nuke_connection import NukeSession
        session = NukeSession(host=host, port=port)
        session.conn = conn
        build_splat_render_pipeline(session)
        conn.close()
    else:
        print("Could not connect. Running in offline mode instead.")


def main():
    parser = argparse.ArgumentParser(description="Nuke 17.0 Exploration Examples")
    parser.add_argument("--list", action="store_true", help="List all examples")
    parser.add_argument("--example", type=int, help="Run specific example (1-9)")
    parser.add_argument("--connect", action="store_true", help="Connect to Nuke")
    parser.add_argument("--reference", action="store_true", help="Show node reference")
    parser.add_argument("--all", action="store_true", help="Run all examples")
    args = parser.parse_args()

    if args.list:
        print("\nAvailable Examples:")
        for i, (name, _) in enumerate(EXAMPLES):
            print(f"  [{i + 1}] {name}")
        return

    if args.reference:
        print_reference()
        return

    if args.example:
        run_example(args.example - 1)
        return

    if args.connect:
        connect_and_run()
        return

    if args.all:
        for i in range(len(EXAMPLES)):
            run_example(i)
            print("\n" + "=" * 70 + "\n")
        return

    # Interactive mode
    while True:
        choice = show_menu()
        if choice.upper() == "Q":
            print("Goodbye!")
            break
        elif choice.upper() == "R":
            print_reference()
        elif choice.upper() == "C":
            connect_and_run()
        elif choice.upper() == "A":
            for i in range(len(EXAMPLES)):
                run_example(i)
                print()
        elif choice.isdigit():
            run_example(int(choice) - 1)
        else:
            print("Invalid option.")


if __name__ == "__main__":
    main()
