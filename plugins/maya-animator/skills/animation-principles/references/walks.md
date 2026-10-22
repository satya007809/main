# Walks — key positions, tempos, and personality

Williams: "A walk is the first thing to learn, and the last thing to master."
Everything below is for 24 fps; scale frame counts for other rates.

## The four positions of one step (right foot forward example)

| Position | Body height | Legs | Arms (oppose legs) | Notes |
|---|---|---|---|---|
| **Contact** | mid (about to fall) | both feet on ground, stride widest, front leg straight heel-down, back leg toe-down | front arm (opposite side) back, back arm forward, both furthest | Key these FIRST for every step. |
| **Down** (recoil) | **lowest** | front knee bends, foot flat, weight lands, back heel lifts | arms passing, swinging through | Weight lives here. Deeper = heavier. |
| **Passing** | rising | free leg passes planted (bent, foot off ground), planted leg straight | arms near sides | Hips swing toward the forward-moving leg. |
| **Up** (push) | **highest** | planted toe pushes, free leg reaching forward | arms almost at next extreme | Smallest ground contact — the body is "launched". |

Then the next contact, mirrored. Two contacts (one left, one right) = a full cycle.

### Standard 12-frame step (normal walk), keys on:
```
f1  Contact (R fwd)      f4  Down     f7  Passing     f10 Up     f13 Contact (L fwd)
```
A full cycle is 24 frames (frame 1 = frame 25). Body Y: 1 mid → 4 low → 7 mid → 10 high → 13 mid.
Favour: body drops into Down FAST (2–3 frames) and rises to Up SLOWER. Make Down slightly
later than the mathematical centre for more weight.

### Tempo table (frames per step)

| Frames/step | Feel |
|---|---|
| 4 | sprint / cartoon run (needs ones) |
| 6 | run |
| 8 | brisk walk, jog, marching, eager |
| 10 | businesslike |
| 12 | natural walk |
| 16 | stroll, casual |
| 20 | tired, elderly, heavy |
| 24–32 | sneak, exhausted, very heavy creature, giant |

## Body mechanics to layer in

1. **Hips**: rotate (Y) toward the forward leg at contact; tilt (Z) *down* on the free-leg
   side at passing (the free hip drops); counter the spine so shoulders stay level-ish.
2. **Shoulders**: rotate opposite to hips (counter-twist) — forward arm's shoulder forward.
3. **Spine**: lean forward slightly for speed/urgency, back for pride/exhaustion.
4. **Head**: naturally bobs with the body; keep it level for a "steadicam" confident
   character; let it drop on the down for tired; nod against the beat for jaunty.
5. **Feet**: heel strikes first, rolls to flat on Down, lifts heel on Up, toe leaves last.
   Toe drags on the passing frame for tired/sneaky characters. Avoid "knee pops": the
   planted leg should be *almost* straight at Passing, not locked.
6. **Arms**: natural swing is from the shoulder with the elbow following 1–2 frames behind,
   hand 1–2 behind that (successive breaking). Hands drag and flop at the extremes.
7. **Overlap**: hair, coat, tail, ears, breasts, belly — offset by 2–4 frames behind the
   body's up/down, with a smaller amplitude settle.

## Personality walks (what to change)

| Walk | Tempo | Change |
|---|---|---|
| **Strut / proud** | 10–12 | Chest up, lean back, Up position exaggerated, head high and held level, hips swing wide, arms swing from the shoulder far. |
| **Sneak** | 16–32 | Deep bend at knees, torso forward, Up is extreme (tip-toe), long holds at Contact, arms and hands lead with fingers spread; add an eye-dart look-around on the hold. |
| **Tired / sad** | 16–24 | Low head, dropped shoulders, shallow Up, feet drag at Passing, arms hang barely swinging, drop into Down is heavy and slow to recover. |
| **Heavy / giant** | 20–32 | Very deep Down, long settle after each landing (4–8 frames), arms wide for balance, torso sways side-to-side, ground shake accent on the down. |
| **Happy / bouncy** | 8–12 | High Up, quick snappy Down, head bobs with the beat, arms swing freely, maybe a **double bounce**: two ups per step (an extra small up right after the down). |
| **Angry march** | 8 | Stomping Down with accent, fists, torso forward, arms chop rather than swing, head thrust. |
| **Female/sashay stereotype — use carefully** | 12–16 | Narrower stride, feet crossing the centre line, strong hip tilt, arms close, less shoulder counter. Make it a character choice, not a default. |
| **Drunk** | irregular | Vary step length and tempo every step, body leans past the feet, recovery stagger, head lags behind body by 3–4 frames. |

## Keying order in a rig (what to actually key)

1. Set timeline for the cycle (e.g. 1–25 for a 12-frame step).
2. **Root/COG**: translateZ (forward travel: linear across the cycle unless treadmill),
   translateY (mid–low–mid–high), rotateY (hips twist), rotateZ (hip tilt), rotateX (lean).
3. **Feet (IK)**: contacts; then the lift/plant; Down and Up rolls (heel/toe attrs).
4. **Chest/spine**: counter rotate against hips; lean.
5. **Arms (FK)**: shoulder keys opposite to legs; offset elbow +1, wrist +2.
6. **Head/neck**: counter or follow by choice; blink on every other contact if idle.
7. **Overlap**: tail/hair/cloth, offset +2…+4 frames, half amplitude.
8. Check **arcs** on wrists, head, feet with motion trails; check **ones/twos** spacing.

## Common faults & fixes

- *Floating*: the Down isn't low enough or arrives too slowly. Favour the down, deepen it.
- *Marching robot*: arms and legs are mirror images on the same frames; offset arm keys
  1–2 frames, vary amplitude L/R, add hip rotation.
- *Foot sliding*: planted foot's Z must move backward exactly as fast as root moves
  forward (or stay fixed in world if root travels). Check with a ground plane.
- *Knee pop*: passing leg hyper-extends. Keep ~5° bend.
- *Dead head*: add tiny counter-nod or let it lag 1–2 frames behind the body.
