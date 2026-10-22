# Timing & spacing charts — translated to Maya keys

A chart is a plan for where inbetweens fall between two extremes. In Maya you make a chart
real with **breakdown keys** and **tangents**, not by trusting default interpolation.

## Reading a chart (A and B are extremes, numbers are frames at 24fps)

```
A(1)  |  |    |        |              B(13)   ← slow OUT of A, snap INTO B  ("ease out")
A(1)              |        |    |  |  B(13)   ← snap OUT of A, slow INTO B  ("ease in")
A(1)  |  |    |      |     |    |  |  B(13)   ← slow both ends (soft)
A(1)     |     |     |     |     |    B(13)   ← even: mechanical / floaty (avoid)
```

## The three Maya moves that make a chart

1. **Breakdown key at the favouring point.** For "slow out of A, snap into B" over 1→13,
   add a key at frame 9 that is only ~35% of the way from A to B. For "snap out, slow in",
   put a key at frame 5 that is ~65% of the way.
2. **Tangent choice per key**: `auto`/`plateau` to avoid overshoot; `flat` at the top of
   an arc or a settle; `spline` for arcs you want to flow through; `linear` for constant
   speed (travel, mechanical); `step` for holds and for blocking.
3. **Weighted tangents** on the accent frame when you need a hard snap: lengthen the
   handle on the slow side and shorten it on the fast side.

## Percent-of-travel table (value at frame, A→B over 12 frames)

| Feel | f1 | f3 | f5 | f7 | f9 | f11 | f13 |
|---|---|---|---|---|---|---|---|
| Ease out (leaves slow, arrives fast) | 0 | 3 | 10 | 22 | 40 | 70 | 100 |
| Ease in (leaves fast, arrives slow) | 0 | 30 | 60 | 78 | 90 | 97 | 100 |
| Ease both | 0 | 6 | 22 | 50 | 78 | 94 | 100 |
| Anticipate then snap | 0 | −8 | −10 | 15 | 70 | 95 | 100 |
| Overshoot then settle | 0 | 35 | 85 | 110 | 104 | 99 | 100 |

Use these when keying with `set_keys`: compute values from the percentages so the
spacing is deliberate even before polishing in the Graph Editor.

## Ones and twos in 3D
Everything in Maya is "on ones" by default. To get the crispness of twos: key breakdowns
every 2 frames in the fast part and let the slow parts interpolate; **or** post-process
with stepped keys every 2 frames (the "stop-motion" look). Check fast actions frame by frame
— if a limb crosses more than a quarter of the screen in one frame, consider a smear or
an extra breakdown.

## Holds
- **Moving hold**: key the pose, then 8–12 frames later key a 2–5% drift in the same
  direction the body was going (plus a tiny head/eye change). Never a dead freeze.
- **Hold before an accent** makes the accent bigger. Hold after it lets the audience read.

## Typical durations (24fps)
| Action | Frames |
|---|---|
| Blink | 2 close + 3–4 open |
| Eye dart | 1–2 move, 4–8 hold |
| Head turn (casual) | 8–12 with blink mid-turn |
| Anticipation for a jump | 6–10 |
| Landing squash | 2–3 |
| Settle after a stop | 6–12 |
| Take (cartoon) | 12–20 |
| Walk step | 12 (see walks.md) |
| Breath cycle (idle) | 48–72 |
