"""
AI Lighting — Automated Installer for Unreal Engine 5

Handles the full installation:
  1. Detects UE5 installation and project path
  2. Copies plugin + scripts to the right locations
  3. Installs anthropic SDK into UE5's Python
  4. Registers startup script for auto-loading
  5. Installs builtin presets

Usage:
    python install_ue5.py                          # Auto-detect everything
    python install_ue5.py --project /path/to/MyGame.uproject
    python install_ue5.py --ue-path "/Program Files/Epic Games/UE_5.4"
    python install_ue5.py --api-key sk-ant-xxx     # Also configure API key
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()

# Files to copy into the project's Scripts/ folder
SCRIPT_FILES = [
    "ai_lighting_widget.py",
    "analyze_lighting.py",
    "ue_lighting_applier.py",
    "preset_manager.py",
    "batch_blend.py",
    "lighting_schema.json",
    "requirements.txt",
]

PLUGIN_DIR_NAME = "AILighting"


# ---------------------------------------------------------------------------
# UE5 Detection
# ---------------------------------------------------------------------------

def find_ue5_installations() -> list[Path]:
    """Find UE5 installations on this machine."""
    candidates = []
    system = platform.system()

    if system == "Windows":
        search_roots = [
            Path("C:/Program Files/Epic Games"),
            Path("D:/Program Files/Epic Games"),
            Path(os.path.expandvars("%PROGRAMFILES%/Epic Games")),
        ]
        for root in search_roots:
            if root.exists():
                for d in root.iterdir():
                    if d.is_dir() and d.name.startswith("UE_5"):
                        candidates.append(d)

    elif system == "Darwin":  # macOS
        search_roots = [
            Path("/Users/Shared/Epic Games"),
            Path.home() / "Library/Application Support/Epic/UnrealEngine",
        ]
        for root in search_roots:
            if root.exists():
                for d in root.iterdir():
                    if d.is_dir() and "5." in d.name:
                        candidates.append(d)

    elif system == "Linux":
        search_roots = [
            Path("/opt/UnrealEngine"),
            Path.home() / "UnrealEngine",
            Path.home() / ".local/share/UnrealEngine",
        ]
        for root in search_roots:
            if root.exists():
                candidates.append(root)

    return sorted(set(candidates))


def find_ue5_python(ue_path: Path) -> Path:
    """Find UE5's bundled Python executable."""
    system = platform.system()
    base = ue_path / "Engine" / "Binaries" / "ThirdParty" / "Python3"

    if system == "Windows":
        candidates = [
            base / "Win64" / "python.exe",
            base / "Win64" / "python3.exe",
        ]
    elif system == "Darwin":
        candidates = [
            base / "Mac" / "bin" / "python3",
            base / "Mac" / "bin" / "python",
        ]
    else:
        candidates = [
            base / "Linux" / "bin" / "python3",
            base / "Linux" / "bin" / "python",
        ]

    for c in candidates:
        if c.exists():
            return c

    raise FileNotFoundError(
        f"Could not find UE5 Python at {base}.\n"
        f"Make sure the Python Editor Script Plugin is installed."
    )


def find_uproject_files(search_dir: Path = None) -> list[Path]:
    """Find .uproject files in common locations."""
    if search_dir:
        return list(search_dir.rglob("*.uproject"))

    candidates = []
    search_roots = [
        Path.home() / "Documents" / "Unreal Projects",
        Path.home() / "UE5Projects",
        Path.home() / "Projects",
        Path("D:/UE5Projects"),
        Path("D:/Projects"),
    ]
    for root in search_roots:
        if root.exists():
            # Only search 2 levels deep to avoid slow scans
            for d in root.iterdir():
                if d.is_dir():
                    candidates.extend(d.glob("*.uproject"))
    return sorted(candidates)


# ---------------------------------------------------------------------------
# Installation Steps
# ---------------------------------------------------------------------------

def copy_plugin(project_dir: Path) -> Path:
    """Copy the AILighting plugin to the project's Plugins/ directory."""
    src = SCRIPT_DIR / "ue_plugin" / PLUGIN_DIR_NAME
    dest = project_dir / "Plugins" / PLUGIN_DIR_NAME

    if dest.exists():
        print(f"  [plugin] Already exists at {dest}, updating...")
        shutil.rmtree(dest)

    shutil.copytree(src, dest)
    print(f"  [plugin] Copied to {dest}")
    return dest


def copy_scripts(project_dir: Path) -> Path:
    """Copy Python scripts to the project's Scripts/ directory."""
    dest_dir = project_dir / "Scripts" / "AILighting"
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for filename in SCRIPT_FILES:
        src = SCRIPT_DIR / filename
        if src.exists():
            shutil.copy2(src, dest_dir / filename)
            copied += 1
        else:
            print(f"  [scripts] Warning: {filename} not found in {SCRIPT_DIR}")

    # Also copy presets directory
    presets_src = SCRIPT_DIR / "presets"
    presets_dest = dest_dir / "presets"
    presets_dest.mkdir(exist_ok=True)
    if presets_src.exists():
        for f in presets_src.glob("*.json"):
            shutil.copy2(f, presets_dest / f.name)

    print(f"  [scripts] Copied {copied} files to {dest_dir}")
    return dest_dir


def install_pip_deps(ue_python: Path) -> bool:
    """Install the anthropic SDK into UE5's Python."""
    print(f"  [pip] Installing anthropic SDK using {ue_python}...")
    try:
        result = subprocess.run(
            [str(ue_python), "-m", "pip", "install", "anthropic"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print("  [pip] anthropic SDK installed successfully.")
            return True
        else:
            print(f"  [pip] Warning: pip install returned code {result.returncode}")
            print(f"  [pip] stderr: {result.stderr[:500]}")
            return False
    except FileNotFoundError:
        print(f"  [pip] Error: Could not run {ue_python}")
        return False
    except subprocess.TimeoutExpired:
        print("  [pip] Error: pip install timed out after 120s")
        return False


def configure_startup_script(project_dir: Path, scripts_dir: Path):
    """
    Create an init_unreal.py that auto-loads the widget on editor startup.
    Users add this path to Project Settings → Python → Startup Scripts.
    """
    init_path = scripts_dir / "init_unreal.py"
    widget_path = scripts_dir / "ai_lighting_widget.py"

    init_content = f'''"""Auto-generated by AI Lighting installer. Loads the AI Lighting widget on startup."""
import sys
import os

# Add scripts directory to Python path
scripts_dir = r"{scripts_dir}"
if scripts_dir not in sys.path:
    sys.path.insert(0, scripts_dir)

# Set API key if configured
api_key_file = os.path.join(scripts_dir, ".api_key")
if os.path.exists(api_key_file):
    with open(api_key_file) as f:
        key = f.read().strip()
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key

# Import and register
try:
    import ai_lighting_widget
    ai_lighting_widget.register_menu_entry()
    print("[AILighting] Ready! Use Tools > AI Lighting Panel or quick_apply() in Python console.")
except Exception as e:
    print(f"[AILighting] Startup warning: {{e}}")
'''

    init_path.write_text(init_content)
    print(f"  [startup] Created {init_path}")
    print(f"  [startup] Add this path to: Edit > Project Settings > Python > Startup Scripts")
    return init_path


def save_api_key(scripts_dir: Path, api_key: str):
    """Save API key to a local file (gitignored)."""
    key_file = scripts_dir / ".api_key"
    key_file.write_text(api_key)

    # Add to .gitignore if present
    gitignore = scripts_dir / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(".api_key\n")
    else:
        content = gitignore.read_text()
        if ".api_key" not in content:
            gitignore.write_text(content.rstrip() + "\n.api_key\n")

    print(f"  [api-key] Saved to {key_file}")


def install_builtin_presets(scripts_dir: Path):
    """Install builtin presets."""
    # Import and run from source
    sys.path.insert(0, str(SCRIPT_DIR))
    from preset_manager import install_builtin_presets as _install, PresetManager
    manager = PresetManager(scripts_dir / "presets")
    _install(scripts_dir / "presets")


# ---------------------------------------------------------------------------
# Interactive Prompts
# ---------------------------------------------------------------------------

def prompt_choice(prompt: str, options: list[str]) -> int:
    """Prompt user to pick from a numbered list."""
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        print(f"  {i}) {opt}")
    while True:
        try:
            choice = int(input("\nEnter number: "))
            if 1 <= choice <= len(options):
                return choice - 1
        except (ValueError, EOFError):
            pass
        print(f"Please enter a number between 1 and {len(options)}")


def prompt_path(prompt: str, must_exist: bool = True) -> Path:
    """Prompt user for a file/directory path."""
    while True:
        try:
            raw = input(f"\n{prompt}: ").strip().strip('"').strip("'")
        except EOFError:
            sys.exit(1)
        if not raw:
            continue
        path = Path(raw).resolve()
        if must_exist and not path.exists():
            print(f"  Path does not exist: {path}")
            continue
        return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Install AI Lighting into your UE5 project",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--project", "-p", type=str, help="Path to your .uproject file")
    parser.add_argument("--ue-path", type=str, help="Path to UE5 installation root")
    parser.add_argument("--api-key", type=str, help="Anthropic API key")
    parser.add_argument("--skip-pip", action="store_true", help="Skip pip install step")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts")
    args = parser.parse_args()

    print("=" * 60)
    print("  AI Lighting — UE5 Installer")
    print("=" * 60)

    # --- Resolve UE5 path ---
    ue_path = None
    if args.ue_path:
        ue_path = Path(args.ue_path).resolve()
        if not ue_path.exists():
            print(f"Error: UE5 path does not exist: {ue_path}")
            sys.exit(1)
    else:
        installations = find_ue5_installations()
        if installations:
            if len(installations) == 1:
                ue_path = installations[0]
                print(f"\nFound UE5: {ue_path}")
            else:
                idx = prompt_choice(
                    "Multiple UE5 installations found:",
                    [str(p) for p in installations] + ["Enter path manually"],
                )
                if idx < len(installations):
                    ue_path = installations[idx]
                else:
                    ue_path = prompt_path("Enter UE5 installation path")
        else:
            print("\nNo UE5 installation auto-detected.")
            ue_path = prompt_path("Enter UE5 installation path (e.g. C:/Program Files/Epic Games/UE_5.4)")

    # --- Resolve project path ---
    if args.project:
        uproject = Path(args.project).resolve()
    else:
        uprojects = find_uproject_files()
        if uprojects:
            idx = prompt_choice(
                "Found UE5 projects:",
                [str(p) for p in uprojects] + ["Enter path manually"],
            )
            if idx < len(uprojects):
                uproject = uprojects[idx]
            else:
                uproject = prompt_path("Enter path to your .uproject file")
        else:
            uproject = prompt_path("Enter path to your .uproject file")

    project_dir = uproject.parent
    print(f"\nProject: {uproject.name}")
    print(f"Directory: {project_dir}")
    print(f"UE5: {ue_path}")

    # --- Confirm ---
    if not args.yes:
        print("\nThis will:")
        print(f"  1. Copy plugin to     {project_dir / 'Plugins' / PLUGIN_DIR_NAME}")
        print(f"  2. Copy scripts to    {project_dir / 'Scripts' / 'AILighting'}")
        if not args.skip_pip:
            print(f"  3. Install anthropic SDK into UE5 Python")
        print(f"  4. Create startup script for auto-loading")
        try:
            confirm = input("\nProceed? [Y/n] ").strip().lower()
        except EOFError:
            confirm = "y"
        if confirm and confirm != "y":
            print("Aborted.")
            sys.exit(0)

    # --- Run installation ---
    print("\nInstalling...\n")

    # 1. Plugin
    print("[1/5] Copying plugin...")
    copy_plugin(project_dir)

    # 2. Scripts
    print("\n[2/5] Copying scripts...")
    scripts_dir = copy_scripts(project_dir)

    # 3. Pip
    if not args.skip_pip:
        print("\n[3/5] Installing Python dependencies...")
        try:
            ue_python = find_ue5_python(ue_path)
            install_pip_deps(ue_python)
        except FileNotFoundError as e:
            print(f"  [pip] Skipped: {e}")
            print("  [pip] You can install manually later:")
            print(f'  [pip]   "<UE5_Python>" -m pip install anthropic')
    else:
        print("\n[3/5] Skipping pip install (--skip-pip)")

    # 4. Startup script
    print("\n[4/5] Configuring startup script...")
    init_path = configure_startup_script(project_dir, scripts_dir)

    # 5. API key + presets
    print("\n[5/5] Final setup...")
    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        save_api_key(scripts_dir, api_key)
    else:
        print("  [api-key] No API key provided. Set it later:")
        print(f'  [api-key]   echo "sk-ant-xxx" > {scripts_dir / ".api_key"}')
        print("  [api-key]   Or set ANTHROPIC_API_KEY env var before launching UE5")

    install_builtin_presets(scripts_dir)

    # --- Done ---
    print("\n" + "=" * 60)
    print("  Installation complete!")
    print("=" * 60)
    print(f"""
Next steps:

  1. Open your project in UE5
  2. Enable the plugin:
     Edit > Plugins > search "AI Lighting" > Enable > Restart
  3. Enable Python scripting:
     Edit > Plugins > search "Python Editor Script" > Enable > Restart
  4. Register the startup script:
     Edit > Project Settings > Plugins > Python > Additional Paths
     Add: {scripts_dir}
     Then under Startup Scripts, add:
     {init_path}
  5. Restart the editor

  After restart, you'll see "Tools > AI Lighting Panel" in the menu bar.
  Or use the Python console:
     quick_apply("C:/path/to/reference.jpg")
""")


if __name__ == "__main__":
    main()
