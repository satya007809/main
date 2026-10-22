# maya-animator — Claude Code plugin

Let Claude Code animate characters, creatures and objects **inside your running Maya**,
using the craft of Richard Williams' *The Animator's Survival Kit* (timing charts, walks,
runs, weight, anticipation, overlap, takes, dialogue, quadrupeds).

```
Claude Code  ──MCP (stdio)──▶  mcp/maya_mcp_server.py  ──TCP 127.0.0.1:7005──▶  claude_bridge.py inside Maya
```

## What's inside

| Path | Purpose |
|---|---|
| `skills/animation-principles/` | The *craft*: distilled Survival Kit knowledge + reference tables (walks, runs, charts, dialogue, creatures). |
| `skills/maya-animate/` | The *hands*: the Maya workflow (discover rig → block → breakdowns → spline → polish → playblast). |
| `mcp/maya_mcp_server.py` | MCP server exposing `maya-mcp` tools: `execute_python`, `get_scene_summary`, `find_animation_controls`, `set_keys`, `get_keys`, `set_tangents`, `delete_keys`, `set_timeline`, `playblast`, … Compatible with the other `maya-*` skills that expect `mcp__maya-mcp__*`. |
| `maya/claude_bridge.py` | Tiny server that runs inside Maya and executes Claude's Python on the main thread. |
| `maya/userSetup.py` | Optional auto-start for the bridge. |
| `commands/animate.md` | `/maya-animator:animate …` slash command. |

## Install (on the PC that runs Maya)

Requirements: Claude Code, Autodesk Maya 2022+ (Python 3), and a system Python 3.10+.

1. **Add the marketplace and install the plugin** in Claude Code:
   ```
   /plugin marketplace add satya007809/main
   /plugin install maya-animator@satya-film-tools
   ```
   (If you prefer the terminal: `claude plugin marketplace add satya007809/main` then
   `claude plugin install maya-animator@satya-film-tools`.)

2. **Install the MCP server's dependency** with the Python that Claude Code will launch
   (`python` on your PATH):
   ```
   pip install mcp
   ```

3. **Start the bridge in Maya.** Script Editor → Python tab:
   ```python
   import sys
   sys.path.append(r"<plugin folder>\maya")   # e.g. C:\Users\you\.claude\plugins\marketplaces\satya-film-tools\plugins\maya-animator\maya
   import claude_bridge; claude_bridge.start()
   ```
   You should see `[claude_bridge] listening on 127.0.0.1:7005`. To auto-start with Maya,
   copy `claude_bridge.py` and `userSetup.py` into `Documents\maya\<version>\scripts\`.

4. **Restart Claude Code** (so `.mcp.json` loads) and try:
   ```
   /maya-animator:animate a proud 12-frame strut on the selected rig, one cycle
   ```

## Using it

Plain language works too — the skills trigger on animation intent:

- "Block a heavy jump on the troll rig, 48 frames, land on frame 30."
- "This walk feels floaty — fix the weight."
- "Give the lamp a double-take when the ball enters frame 40."
- "Animate the horse from walk to gallop over 3 seconds."
- "Review my keys on `cog_ctrl` and tell me what's wrong with the spacing."

Claude will read the rig, state a beat sheet in frames, key stepped poses, add
breakdowns from timing charts, spline, polish overlap/arcs, playblast, and critique itself.

## Refining the knowledge from the book

The `animation-principles` skill is written from the book's content in our own words.
To deepen it from your scanned copy, run Claude Code locally with the PDF and ask it to
read a chapter (it can view page images) and extend the matching `references/*.md` — keep
the notes as paraphrased craft, not reproduced pages.

## Security

The bridge executes Python sent to it. It binds to `127.0.0.1` only. Don't expose the
port on a network; stop it with `claude_bridge.stop()` when not in use.

## License

MIT for the code in this plugin. *The Animator's Survival Kit* © Richard Williams; this
plugin contains no text or images from the book, only paraphrased principles.
