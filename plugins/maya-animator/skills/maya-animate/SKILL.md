---
name: maya-animate
description: Drive a live Autodesk Maya session to animate any rigged character, creature or object through the maya-mcp bridge — discover rig controls, set the timeline, block poses on stepped keys, add breakdowns from timing charts, spline and polish (arcs, overlap, moving holds), then playblast for review. Use whenever the user wants Claude to animate, key, pose, time, retime, fix or review motion IN MAYA — "animate this rig walking", "block a jump on the dragon", "give the lamp a take", "retime this to feel heavier", "playblast it". Requires claude_bridge.py running inside Maya.
when_to_use: Any request to create or edit keyframe animation in Maya. Always load animation-principles alongside this skill for the craft; this skill is the hands.
allowed-tools: Read mcp__maya-mcp__execute_python mcp__maya-mcp__get_scene_summary mcp__maya-mcp__list_objects_by_type mcp__maya-mcp__get_object_attributes mcp__maya-mcp__set_object_attribute mcp__maya-mcp__scene_management mcp__maya-mcp__find_animation_controls mcp__maya-mcp__set_keys mcp__maya-mcp__get_keys mcp__maya-mcp__set_tangents mcp__maya-mcp__delete_keys mcp__maya-mcp__set_timeline mcp__maya-mcp__playblast
---

# Animating in Maya through maya-mcp

You are the animator; Maya is the pencil. Work pose-to-pose exactly as Williams does:
**plan → keys (stepped) → breakdowns (stepped) → spline → polish → playblast → revise.**
Never spline before breakdowns exist. Never key every frame.

## 0. Connect and look before touching anything
1. `get_scene_summary` — fps, range, what's in the scene. If it errors, tell the user to run
   `import claude_bridge; claude_bridge.start()` in Maya's Script Editor (file is in this
   plugin's `maya/` folder) and stop.
2. `find_animation_controls` — read the rig. Note: FK vs IK (IK feet usually have
   translate keyable; FK arms have rotate only), foot roll / heel / toe attributes,
   COG vs root, space switches, face controls.
3. `get_object_attributes` on the COG and one foot to learn axis conventions: which axis
   is **up** (Y in Maya default), which is **forward** for this rig (check the rig faces
   +Z or −Z by looking at a foot's translateZ vs the head's).
4. Say back a one-line plan: tempo (frames/step or total frames), the beats, which
   controls you'll key. Ask ONLY if the rig is ambiguous (e.g. two characters, no clear COG).

## 1. Plan the timing before keying
- Pick the idea (what is this walk/jump/take *about*?) and the tempo from
  `animation-principles` (walks.md tempo table, runs.md, timing-charts.md durations).
- Write the beat sheet as frames: e.g. `1 contact R · 4 down · 7 pass · 10 up · 13 contact L …`
- `set_timeline(start, end, fps)` to the cycle or shot length.

## 2. Blocking — keys and extremes on stepped tangents
Use `set_keys(keys, stepped_blocking=True)` with ALL the storytelling poses in one call
per control group. Key **every control you intend to use on every blocking frame** (a full
pose per key, even if a channel doesn't change) so later tangent work doesn't drift.
Order: COG/root → feet → chest/spine → head → arms → props → face.

Compute values deliberately. Example 12-frame walk step, root `translateY` with rest height h and
bounce amplitude a: contact `h`, down `h − a`, passing `h`, up `h + 0.7a` (the up is usually
slightly less extreme than the down). Hips rotateY ±8–12°, rotateZ ±4–6°, chest counter
−60% of hips.

Playblast the blocking (`playblast`) and read it as stepped poses: does the story read?
Fix poses now; it's cheap.

## 3. Breakdowns — the acting pass (still stepped)
Add ONE key between each pair of extremes at the favouring point from a timing chart
(timing-charts.md: ~35% of travel for ease-out/snap-in, ~65% for snap-out/ease-in).
Put arcs in here: a wrist breakdown is *off* the straight line between its extremes.
Add anticipations (2–6 frames before big moves) and overshoots (1–2 frames after accents).

## 4. Spline and clean
`set_tangents(nodes, "auto")` (or `plateau` for no-overshoot channels like feet Y on the
ground). Then fix:
- **Foot slide**: planted-foot translate must be constant in world space → `flat`/`linear`
  tangents between plant and lift; check with `get_keys`.
- **Knee pops / gimbal flips**: look at rotate curves for jumps > 180°.
- **Even spacing**: any channel whose curve is a straight diagonal between extremes needs
  a breakdown or a weighted tangent.

## 5. Polish — overlap, drag, holds, eyes
- Offset secondary chains later: for tail/hair/ears/cloth controls, re-key them 2–4 frames
  after the parent's keys with ~70% amplitude and a settle (use `execute_python` with
  `cmds.keyframe(..., e=True, relative=True, timeChange=2)` on those controls only).
- Successive breaking: shoulder key f, elbow f+1, wrist f+2, fingers f+3.
- Convert any freeze into a **moving hold** (2–5% drift key 8–12 frames later).
- Blink on head turns: eyes lead 2–4 frames, lids close 2, open 3–4.

## 6. Review loop
`playblast` → describe what you see in craft terms (weight, spacing, arcs, overlap) → fix →
repeat. Ask the user to watch the playblast file path you return and tell you what feels off;
translate their words into chart changes ("floaty" → deepen the down, favour it; "stiff" →
offset chains, add arcs, vary L/R; "mechanical" → kill even spacing, add moving holds).

## Snippets for `execute_python`

```python
# Shift keys of a list of controls later by N frames (overlap)
import maya.cmds as cmds
for c in ctrls: cmds.keyframe(c, e=True, relative=True, timeChange=N)

# Scale amplitude of a channel around its rest value (drag/settle 70%)
cmds.scaleKey(ctrl+'.rotateX', valueScale=0.7, valuePivot=rest)

# Make a cycle: infinity on all channels of ctrl
cmds.setInfinity(ctrl, pri='cycle', poi='cycle')          # 'cycleRelative' for travel

# Motion trail for arc checking
cmds.snapshot(ctrl, motionTrail=True, startTime=s, endTime=e, increment=1)

# Mirror a pose L→R at a frame (simple rigs: flip translateX, rotateY, rotateZ)
```

## Safety
- Work on a **new animation layer** or ask before deleting existing keys (`delete_keys`).
- Save (`scene_management("save_as", path)`) before large passes; name versions `_v001`.
- Never key locked/hidden channels; respect `keyable` lists from `find_animation_controls`.
- Prefer many small `set_keys` calls per body part over one giant call: easier to undo.
