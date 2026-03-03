# CorridorKey installation guide for Nuke

This repository now contains a quick install guide for using **CorridorKey** in The Foundry Nuke.

## What you need
- A compatible Nuke version installed.
- Access to the plugin repository: `https://github.com/nikopueringer/CorridorKey`

## Install steps

### 1) Download CorridorKey
Use one of these options:

- **Git (recommended):**
  ```bash
  git clone https://github.com/nikopueringer/CorridorKey.git
  ```
- **ZIP:** Download from GitHub and extract it.

### 2) Put the plugin in your `.nuke` directory
Copy the CorridorKey plugin folder/files into your user `.nuke` path:

- **Windows:** `C:\Users\<you>\.nuke\`
- **macOS:** `/Users/<you>/.nuke/`
- **Linux:** `/home/<you>/.nuke/`

If the repo has a folder such as `gizmos`, `python`, or `plugins`, copy those into matching subfolders in `.nuke`.

### 3) Update `menu.py`
Open (or create) `menu.py` inside `.nuke` and add plugin paths, for example:

```python
import nuke

# Point this to where CorridorKey is located
nuke.pluginAddPath('./CorridorKey')
```

If CorridorKey provides a specific startup snippet in its docs, prefer that exact snippet.

### 4) Restart Nuke
Close and relaunch Nuke so it picks up new plugin paths.

### 5) Verify installation
- Check if CorridorKey appears in your node menu/toolset.
- Or open Nuke's Script Editor and test importing any module exposed by CorridorKey.

## Troubleshooting
- Ensure the plugin files are not nested too deeply (e.g., avoid `.nuke/CorridorKey/CorridorKey/...`).
- Confirm `menu.py` has no syntax errors.
- On macOS/Linux, verify file permissions allow Nuke to read the plugin files.
- If Nuke shows startup errors, inspect the Script Editor output for missing module/path messages.

## Optional: keep CorridorKey updated
If you cloned with Git:

```bash
git -C ~/.nuke/CorridorKey pull
```

(Adjust path for Windows/macOS as needed.)
