# Creatures, quadrupeds, birds, flexible things

## Quadrupeds — think "two bipeds in a row"
Front legs ≈ arms (shoulder/elbow/wrist/paw), back legs ≈ legs (hip/knee/ankle/paw).
The back half runs the same cycle as the front half, **offset by roughly ¼ to ½ of a step**,
and the spine connects them.

| Gait | Frames/step (24fps) | Pattern | Spine |
|---|---|---|---|
| **Walk** (4-beat) | 12–16 per leg | Each foot lands separately: LH, LF, RH, RF. Always 2–3 feet down. | Nearly flat; gentle side-to-side sway |
| **Trot** (2-beat) | 8 | Diagonal pairs land together (LF+RH, then RF+LH). Short flight. | Flat, bouncing |
| **Canter** (3-beat) | 8–10 | Asymmetric rocking; a leading leg | Rocks fore-aft |
| **Gallop** (4-beat, fast) | 4–6 | Rear pair pushes, flight, front pair catches, back legs swing *under* | **Flexes and extends** — coils on gather, stretches in flight |
| **Bound / pronk** | 6–10 | Both back legs push together, both front land together (rabbit, squirrel) | Strong arch |

Notes:
- **Dogs/cats/horses/deer** are digitigrade/unguligrade: the "foot" is what reads as the
  lower leg; the heel (hock) is high. Hoof/paw contact rolls heel-to-toe just like a foot.
- Head: in a walk the head **bobs down** as each front foot lands (horses nod); in a gallop
  it reaches forward in flight and pulls back on the catch.
- Tail = flexible chain, 2–4 frames behind the hips, with a settle. Up/curled = happy/alert.
- Ears: 1–3 frames behind the head, flop on landings.
- Weight scales: elephant ≈ 32-frame steps, nearly no up-and-down, long settles, legs stay
  almost column-straight. Mouse ≈ 4–6 frame scurry, lots of stop-start, no overlap time.

## Birds
- Flap = **successive breaking of joints**: shoulder leads, elbow follows, wrist follows,
  primaries (fingertips) last — each 1–2 frames later; reverse on the upstroke.
- **Downstroke** fast and powerful (wing flat, cupped), **upstroke** slower with the wing
  folded/feathered to cut air. Body rises on downstroke (lags 1–2 frames), drops on up.
- Hover (hummingbird) = figure-8 wrist path on ones; soar = held wing with tiny tip drift
  (moving hold) and body banking into turns (eyes/head lead the bank).
- Small birds: sharp head jerks, 1–2 frame hops with no inbetweens, long holds.

## Insects, fish, snakes
- Insects: legs alternate in tripods; motions are **pops** (1-frame moves) and holds.
- Fish: S-wave travels head → tail, tail lags; body banks into turns; fins overlap.
- Snakes/tentacles: a **travelling wave** from the base. Key the base, copy to each
  segment with +1…+2 frame offset and slightly larger amplitude toward the tip.

## Flexible objects (rope, flag, hair, cloth, a dragon's tail)
Straight-ahead thinking: the driver moves, each link follows one or two frames later with
drag, and the free end **overshoots** and settles. The free end is always the last to
stop. Wave amplitude *increases* toward the free end; frequency is set by the driver.
In Maya: key the root chain control, then shift each downstream control's keys later
(dope sheet) and scale their values up slightly; or use a simple expression/offset.

## Inanimate "characters" (a lamp, a ball, a car)
Give it a **head** (where it looks from), a **spine** (how it bends) and **feet** (how it
pushes). Then it obeys all the rules above. A bouncing ball is the whole system in one:
squash on contact (accent), stretch on the fast frames, parabolas, spacing bunched at
the apex, shorter and quicker bounces as energy dies, a final settle wobble.
