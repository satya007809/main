#!/usr/bin/env python
"""
maya_mcp_server.py — MCP server (stdio) that lets Claude Code drive a running Maya.

Talks to claude_bridge.py inside Maya over localhost (default 127.0.0.1:7005).
Exposes the generic tools the maya-* skills expect (execute_python, get_scene_summary,
list_objects_by_type, get_object_attributes, set_object_attribute, scene_management)
plus animation tools (find_animation_controls, set_keys, get_keys, set_tangents,
delete_keys, set_timeline, playblast).

Install deps once:  pip install -r requirements.txt
Run by Claude Code via the plugin's .mcp.json; no need to start it by hand.
"""
import json
import os
import socket
import struct
import textwrap
from typing import Any, Optional

try:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP

HOST = os.environ.get("MAYA_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("MAYA_BRIDGE_PORT", "7005"))
TIMEOUT = float(os.environ.get("MAYA_BRIDGE_TIMEOUT", "600"))

mcp = FastMCP("maya-mcp")


# --------------------------------------------------------------------------- transport
def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Maya bridge closed the connection")
        buf += chunk
    return buf


def maya_run(code: str) -> dict:
    """Send Python to Maya, return the bridge's response dict."""
    code = textwrap.dedent(code)
    try:
        with socket.create_connection((HOST, PORT), timeout=TIMEOUT) as sock:
            body = json.dumps({"code": code}).encode("utf-8")
            sock.sendall(struct.pack(">Q", len(body)) + body)
            (length,) = struct.unpack(">Q", _recv_exact(sock, 8))
            return json.loads(_recv_exact(sock, length).decode("utf-8"))
    except (ConnectionRefusedError, socket.timeout, OSError) as exc:
        return {
            "ok": False,
            "error": (
                f"Cannot reach Maya at {HOST}:{PORT} ({exc}). In Maya's Script Editor run:\n"
                "    import claude_bridge; claude_bridge.start()\n"
                "(claude_bridge.py is in the plugin's maya/ folder; add that folder to "
                "sys.path or copy the file into your Maya scripts directory)."
            ),
        }


def _fmt(resp: dict) -> str:
    """Render a bridge response for the model: stdout, then result or error."""
    parts = []
    if resp.get("stdout"):
        parts.append(resp["stdout"].rstrip())
    if resp.get("ok"):
        if resp.get("result") is not None:
            parts.append(json.dumps(resp["result"], indent=2, default=str))
        if not parts:
            parts.append("OK")
    else:
        parts.append("ERROR:\n" + str(resp.get("error", "unknown error")))
    return "\n".join(parts)


# --------------------------------------------------------------------------- generic tools
@mcp.tool()
def execute_python(code: str) -> str:
    """Run arbitrary Python inside Maya (maya.cmds / pymel / OpenMaya available).
    Assign to a variable named `result` to return a value; print() output is returned too.
    The namespace persists between calls, so helpers you define stay available."""
    return _fmt(maya_run(code))


@mcp.tool()
def get_scene_summary() -> str:
    """Scene file, units, frame range, fps, selection and counts of transforms, meshes,
    joints, cameras, anim curves and references."""
    return _fmt(maya_run("""
        import maya.cmds as cmds
        fps_map = {"game":15,"film":24,"pal":25,"ntsc":30,"show":48,"palf":50,"ntscf":60}
        unit = cmds.currentUnit(q=True, time=True)
        fps = fps_map.get(unit) or (float(unit.replace("fps","")) if unit.endswith("fps") else unit)
        result = {
            "scene": cmds.file(q=True, sceneName=True) or "(untitled)",
            "linear_unit": cmds.currentUnit(q=True, linear=True),
            "fps": fps,
            "range": {"start": cmds.playbackOptions(q=True, min=True),
                      "end": cmds.playbackOptions(q=True, max=True),
                      "anim_start": cmds.playbackOptions(q=True, ast=True),
                      "anim_end": cmds.playbackOptions(q=True, aet=True),
                      "current": cmds.currentTime(q=True)},
            "selection": cmds.ls(sl=True) or [],
            "counts": {t: len(cmds.ls(type=t) or []) for t in
                       ["transform","mesh","joint","camera","animCurve","reference","nurbsCurve"]},
            "top_level": (cmds.ls(assemblies=True) or [])[:50],
        }
    """))


@mcp.tool()
def list_objects_by_type(object_type: str = "transform", pattern: str = "*", limit: int = 200) -> str:
    """List nodes of a Maya node type (transform, joint, mesh, nurbsCurve, camera, animCurve...)
    whose name matches a glob pattern."""
    return _fmt(maya_run(f"""
        import maya.cmds as cmds
        nodes = cmds.ls({pattern!r}, type={object_type!r}, long=False) or []
        result = {{"count": len(nodes), "nodes": nodes[:{int(limit)}]}}
    """))


@mcp.tool()
def get_object_attributes(node: str, keyable_only: bool = True) -> str:
    """Attributes of a node with current values, lock state and whether they are animated."""
    return _fmt(maya_run(f"""
        import maya.cmds as cmds
        node = {node!r}
        if not cmds.objExists(node):
            raise RuntimeError("No such node: " + node)
        attrs = cmds.listAttr(node, keyable=True) if {keyable_only} else cmds.listAttr(node, scalar=True) or []
        out = {{}}
        for a in attrs or []:
            plug = node + "." + a
            try:
                out[a] = {{
                    "value": cmds.getAttr(plug),
                    "locked": cmds.getAttr(plug, lock=True),
                    "animated": bool(cmds.keyframe(plug, q=True, keyframeCount=True)),
                    "type": cmds.getAttr(plug, type=True),
                }}
            except Exception as e:
                out[a] = {{"error": str(e)}}
        result = out
    """))


@mcp.tool()
def set_object_attribute(node: str, attribute: str, value: Any) -> str:
    """Set a single attribute (no keyframe). value may be a number, bool, string or list of 3 numbers."""
    return _fmt(maya_run(f"""
        import maya.cmds as cmds
        plug = {node!r} + "." + {attribute!r}
        v = {value!r}
        if isinstance(v, (list, tuple)):
            cmds.setAttr(plug, *v)
        elif isinstance(v, str):
            cmds.setAttr(plug, v, type="string")
        else:
            cmds.setAttr(plug, v)
        result = cmds.getAttr(plug)
    """))


@mcp.tool()
def scene_management(action: str, path: Optional[str] = None, force: bool = False) -> str:
    """action: new | open | save | save_as | import | reference | undo | redo.
    `path` is required for open/save_as/import/reference."""
    return _fmt(maya_run(f"""
        import maya.cmds as cmds
        action, path, force = {action!r}, {path!r}, {force}
        if action == "new":
            result = cmds.file(new=True, force=force)
        elif action == "open":
            result = cmds.file(path, open=True, force=force)
        elif action == "save":
            result = cmds.file(save=True, force=force)
        elif action == "save_as":
            cmds.file(rename=path); result = cmds.file(save=True, force=force)
        elif action == "import":
            result = cmds.file(path, i=True, returnNewNodes=True)
        elif action == "reference":
            result = cmds.file(path, reference=True, namespace=path.split("/")[-1].split(".")[0])
        elif action == "undo":
            cmds.undo(); result = "undone"
        elif action == "redo":
            cmds.redo(); result = "redone"
        else:
            raise ValueError("unknown action " + action)
    """))


# --------------------------------------------------------------------------- animation tools
@mcp.tool()
def find_animation_controls(root: Optional[str] = None) -> str:
    """Discover a rig's animation controls: nurbsCurve transforms with keyable channels
    (typical *_ctrl / *_CTL / *_con), grouped by a guessed body part, plus any joints
    if the rig has no controls (FK-on-skeleton). Pass `root` to limit to one character."""
    return _fmt(maya_run(f"""
        import maya.cmds as cmds, re
        root = {root!r}
        shapes = cmds.ls(type="nurbsCurve", long=True) or []
        ctrls = sorted({{cmds.listRelatives(s, parent=True, fullPath=True)[0] for s in shapes}})
        if root:
            r = cmds.ls(root, long=True)
            ctrls = [c for c in ctrls if r and c.startswith(r[0])]
        groups = {{"root_body":[], "spine_head":[], "arm_L":[], "arm_R":[], "leg_L":[], "leg_R":[],
                  "face":[], "tail_extra":[], "other":[]}}
        def side(n):
            if re.search(r"(^|[_:])(l|lf|lft|left)([_:]|$)|_L($|_)|^L_", n, re.I): return "L"
            if re.search(r"(^|[_:])(r|rt|rgt|right)([_:]|$)|_R($|_)|^R_", n, re.I): return "R"
            return ""
        for c in ctrls:
            n = c.split("|")[-1]; low = n.lower(); s = side(n)
            keyable = cmds.listAttr(c, keyable=True, unlocked=True) or []
            if not keyable: continue
            entry = {{"name": n, "path": c, "keyable": keyable}}
            if any(k in low for k in ["cog","hip","pelvis","root","body","master","global","world"]): g="root_body"
            elif any(k in low for k in ["spine","chest","torso","neck","head"]): g="spine_head"
            elif any(k in low for k in ["arm","hand","wrist","elbow","shoulder","clav","finger","thumb"]): g="arm_"+(s or "L")
            elif any(k in low for k in ["leg","foot","ankle","knee","toe","heel","ball","hoof","paw"]): g="leg_"+(s or "L")
            elif any(k in low for k in ["jaw","mouth","lip","eye","brow","lid","cheek","tongue"]): g="face"
            elif any(k in low for k in ["tail","ear","wing","fin","antenna"]): g="tail_extra"
            else: g="other"
            groups[g].append(entry)
        joints = []
        if not ctrls:
            joints = cmds.ls(type="joint") or []
        result = {{"control_count": len(ctrls), "groups": {{k:v for k,v in groups.items() if v}},
                   "joints_if_no_controls": joints[:200]}}
    """))


@mcp.tool()
def set_keys(keys: list, tangent: str = "auto", stepped_blocking: bool = False) -> str:
    """Batch-set keyframes. keys = [{"node":"L_foot_ctrl","attr":"translateY","frame":12,"value":3.5}, ...]
    tangent: auto | spline | linear | flat | step | plateau.
    stepped_blocking=True forces step tangents (pose-to-pose blocking)."""
    return _fmt(maya_run(f"""
        import maya.cmds as cmds
        keys, tangent, stepped = {keys!r}, {tangent!r}, {stepped_blocking}
        itt = ott = ("step" if stepped else tangent)
        if itt == "step": itt = "clamped"   # Maya: in-tangent for step keys is clamped/auto
        n = 0; errors = []
        for k in keys:
            plug = k["node"] + "." + k["attr"]
            try:
                cmds.setKeyframe(plug, time=k["frame"], value=k["value"],
                                 inTangentType=itt, outTangentType=ott)
                n += 1
            except Exception as e:
                errors.append({{"key": k, "error": str(e)}})
        result = {{"keys_set": n, "errors": errors}}
    """))


@mcp.tool()
def get_keys(node: str, attrs: Optional[list] = None) -> str:
    """Return keyframe times/values (and tangent types) for a node's animated channels."""
    return _fmt(maya_run(f"""
        import maya.cmds as cmds
        node, attrs = {node!r}, {attrs!r}
        attrs = attrs or (cmds.listAttr(node, keyable=True) or [])
        out = {{}}
        for a in attrs:
            plug = node + "." + a
            times = cmds.keyframe(plug, q=True, timeChange=True)
            if not times: continue
            vals = cmds.keyframe(plug, q=True, valueChange=True)
            itt = cmds.keyTangent(plug, q=True, inTangentType=True)
            ott = cmds.keyTangent(plug, q=True, outTangentType=True)
            out[a] = [{{"frame": t, "value": v, "in": i, "out": o}} for t, v, i, o in zip(times, vals, itt, ott)]
        result = out
    """))


@mcp.tool()
def set_tangents(nodes: list, tangent: str = "auto", start: Optional[float] = None,
                 end: Optional[float] = None, attrs: Optional[list] = None) -> str:
    """Change tangent type on existing keys (e.g. convert stepped blocking to spline/auto).
    tangent: auto | spline | linear | flat | step | plateau | clamped."""
    return _fmt(maya_run(f"""
        import maya.cmds as cmds
        nodes, tangent, start, end, attrs = {nodes!r}, {tangent!r}, {start!r}, {end!r}, {attrs!r}
        plugs = [n + "." + a for n in nodes for a in (attrs or (cmds.listAttr(n, keyable=True) or []))]
        kw = {{}}
        if start is not None or end is not None:
            kw["time"] = (start if start is not None else -1e9, end if end is not None else 1e9)
        changed = 0
        for p in plugs:
            if cmds.keyframe(p, q=True, keyframeCount=True):
                if tangent == "step":
                    cmds.keyTangent(p, inTangentType="clamped", outTangentType="step", **kw)
                else:
                    cmds.keyTangent(p, inTangentType=tangent, outTangentType=tangent, **kw)
                changed += 1
        result = {{"channels_changed": changed}}
    """))


@mcp.tool()
def delete_keys(nodes: list, start: Optional[float] = None, end: Optional[float] = None,
                attrs: Optional[list] = None) -> str:
    """Delete keys on nodes (all channels or `attrs`), optionally within [start, end]."""
    return _fmt(maya_run(f"""
        import maya.cmds as cmds
        nodes, start, end, attrs = {nodes!r}, {start!r}, {end!r}, {attrs!r}
        kw = {{}}
        if start is not None or end is not None:
            kw["time"] = (start if start is not None else -1e9, end if end is not None else 1e9)
        for n in nodes:
            targets = [n + "." + a for a in attrs] if attrs else [n]
            for t in targets:
                cmds.cutKey(t, clear=True, **kw)
        result = "deleted"
    """))


@mcp.tool()
def set_timeline(start: float, end: float, fps: Optional[int] = None, current: Optional[float] = None) -> str:
    """Set playback range (and optionally fps: 24/25/30/60, and current frame)."""
    return _fmt(maya_run(f"""
        import maya.cmds as cmds
        fps = {fps!r}
        if fps:
            cmds.currentUnit(time={{24:"film",25:"pal",30:"ntsc",48:"show",50:"palf",60:"ntscf"}}.get(fps, str(fps)+"fps"))
        cmds.playbackOptions(min={start}, max={end}, ast={start}, aet={end})
        if {current!r} is not None:
            cmds.currentTime({current!r})
        result = {{"start": {start}, "end": {end}, "fps": cmds.currentUnit(q=True, time=True)}}
    """))


@mcp.tool()
def playblast(path: str, start: Optional[float] = None, end: Optional[float] = None,
              width: int = 960, height: int = 540, camera: Optional[str] = None) -> str:
    """Write a playblast movie/image sequence so the animation can be reviewed.
    `path` without extension; Maya picks the format (qt/avi/image). Returns the file path."""
    return _fmt(maya_run(f"""
        import maya.cmds as cmds
        kw = dict(filename={path!r}, forceOverwrite=True, format="qt", compression="H.264",
                  percent=100, quality=90, viewer=False, showOrnaments=False,
                  widthHeight=({int(width)}, {int(height)}))
        if {start!r} is not None: kw["startTime"] = {start!r}
        if {end!r} is not None: kw["endTime"] = {end!r}
        cam = {camera!r}
        if cam:
            panel = cmds.getPanel(withFocus=True)
            if cmds.getPanel(typeOf=panel) == "modelPanel":
                cmds.modelPanel(panel, e=True, camera=cam)
        try:
            result = cmds.playblast(**kw)
        except RuntimeError:
            kw.pop("compression"); kw["format"] = "image"; kw["compression"] = "png"
            result = cmds.playblast(**kw)
    """))


if __name__ == "__main__":
    mcp.run()
