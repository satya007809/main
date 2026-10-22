# Runs, jumps and fast actions

## Runs

A run is NOT a fast walk. The differences:
- There is a **flight phase** (both feet off the ground) in every step.
- Only one foot ever touches the ground.
- Body leans forward; the faster the run, the more lean and the lower the bounce.
- Arms pump from the shoulder with elbows bent ~90°, hands pass hip and shoulder height.
- Stride length grows with speed; up-and-down shrinks.

### Positions per step
**Contact** (foot strikes under/ahead of body, body lowest about to absorb) →
**Down/compress** (knee bends, deepest) → **Push** (leg extends, body highest launch) →
**Flight** (both feet off, free leg swinging through, body at peak then dropping) → next Contact.

### Tempo

| Frames/step | Feel | Keys |
|---|---|---|
| 8 | jog | Contact f1, Down f3, Push f5, Flight f7 |
| 6 | run | Contact f1, Down f2, Push f4, Flight f5 |
| 4 | fast run | Contact f1, Down f2, Push f3, Flight f4 — animate on ONES |
| 3 | cartoon scramble | Only contact + flight; use smear/stretch on the flight frame |

A 4-frame run needs genuinely different spacing: the body moves a large distance per frame,
so add **stretch** on the flight frame along the travel direction and **squash** on contact.
Legs often blur: a smear pose (elongated leg / multiple-limb feel) on the single flight frame
is legitimate even in 3D (scale the limb along its length for one frame).

### Cartoon run variants
- **Double bounce**: an extra small up in the flight.
- **Scissor legs**: legs cross wide in flight for comic speed.
- **Lean past the feet**: the body is ahead of the legs — the "running from something" look.
- **Head stays level** on a sprint hero; **head bobs** on a comic panic run.

## Jumps

1. **Anticipation**: crouch (deep, 4–8 frames in, slow), arms back, head down.
2. **Launch**: legs extend in 2–3 frames (fast!), arms swing up/forward, body stretched;
   the last ground frame is the most stretched.
3. **Flight**: body follows a **parabola**; spacing is wide at launch, bunches at the apex,
   widens on the fall. Limbs settle into the "shape" of the jump at the apex.
4. **Landing**: contact is 1 frame, then deep **squash** over 2–3 frames (knees, spine,
   head drops), arms forward/down, then **recovery** slow (6–12 frames) with overshoot.
5. **Overlap**: hair/cloth/tail lag 2–4 frames throughout; they continue *up* when the body
   starts down at the apex, and slam down after the landing.

Heavier = longer anticipation, faster launch, deeper squash, longer recovery.

## Fast actions: hits, throws, snaps

- Put the **extreme on the accent frame**. The biggest spacing gap is on the frame *before*
  the hit — one or two frames where the limb travels most of its distance.
- A one-frame **overshoot** past the final pose, then settle back 3–6 frames.
- **Anticipation is proportional**: a big punch winds up 6–10 frames; a flick 2.
- After impact, the *receiving* object reacts one frame after the striker.
- Use **step tangents** for 1–2 frames on the fastest part if spline smoothing kills the snap,
  or add a breakdown key on the frame before the accent to force the spacing.
