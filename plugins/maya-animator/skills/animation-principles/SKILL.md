---
name: animation-principles
description: The craft of character and creature animation distilled from Richard Williams' The Animator's Survival Kit — timing and spacing charts, keys/extremes/breakdowns/inbetweens, ones vs twos, slow-in/slow-out and favouring, anticipation, overlapping action and successive breaking of joints, weight, squash and stretch, arcs, walks (contact/down/passing/up, 8-24 frame cycles, strut, sneak, double bounce, attitude walks), runs, takes and accents, dialogue phrasing, eyes and blinks, quadrupeds, birds and flexible objects. Use whenever animating or critiquing motion of any character, creature or object in Maya or any other tool — "make it walk", "give it weight", "it feels floaty", "add a take", "block this jump", "animate the dog running", "why does this look mechanical".
when_to_use: Before planning or keying ANY performance animation, and when reviewing existing keys. Pair with the maya-animate skill when the target is Autodesk Maya.
---

# Animation Principles (Survival Kit distilled)

Williams' core claim: **animation is timing and spacing**. Timing = *which frame* a pose
lands on. Spacing = *how far apart* the inbetweens are. Everything else (weight, snap,
softness, personality) is a consequence of those two. Decide them on purpose, before keying.

## The working method — always in this order

1. **Thumbnail the idea.** What is the action *about*? One sentence. A walk is never
   just a walk; it is a tired walk, a proud walk, a sneaking walk.
2. **Keys (storytelling poses).** The fewest poses that tell the story. Push them:
   clear silhouette, line of action, asymmetry, no twinning.
3. **Extremes.** The furthest points of each action (the contact of a foot, the top of
   a jump, the deepest squash). Often the same as keys, not always.
4. **Breakdowns (passing positions).** The *one* drawing between two extremes that
   decides the path and the favouring. This is where the acting lives: the breakdown
   is not the mathematical middle — it leans toward one extreme, overshoots, or
   adds an arc.
5. **Inbetweens with charts.** Only now fill in, following a timing chart.
6. **Polish**: overlap, drag, arcs, moving holds, secondary action, eyes.

Blocking in Maya = keys + extremes on stepped tangents. Breakdowns = the keys you add
next, still stepped. Only then spline. Never spline a blocking pass with no breakdowns:
Maya's even interpolation is exactly the "mechanical" feel Williams warns about.

## Timing charts — the heart of it

A chart between extremes A and B tells where each inbetween sits:

```
A ---- B           evenly spaced: mechanical, floaty, no weight. Almost never right.
A -|-|--|---- B    slow out of A (ease out), snap into B
A ----|--|-|- B    snap out of A, slow in to B (ease in)
A -|-|-|---|-|-|- B  slow both ends (soft, floaty — ok for gentle actions only)
```

- **Favouring**: a breakdown placed close to A "favours A": the character *stays* in A's
  feel and then snaps to B. Favouring one side is how you get crispness and weight.
- **Slow in / slow out** = more inbetweens bunched near a pose. Hold ≠ freeze: use a
  **moving hold** (tiny drift over 6–12 frames) so the character stays alive.
- **Ones vs twos** (at 24 fps): twos (a new pose every 2 frames) is the default for
  most body animation and reads perfectly well; ones for fast actions, broad sweeps,
  camera moves, and anything crossing the screen quickly. In Maya this becomes:
  key breakdowns every 2 frames in fast sections, let spline interpolate elsewhere, but
  check on 2s with the timeline step so spacing is deliberate.
- **Williams' rule of thumb for weight**: the more frames a body takes to *leave* a pose
  and the fewer it takes to *arrive*, the heavier and more forceful it reads. Reverse it
  (fast leave, slow arrive) for light, floaty, dreamy things.

## Principles, one line each (what to actually do in a rig)

| Principle | In practice |
|---|---|
| Squash & stretch | Scale/offset along the direction of motion; volume stays constant. Stretch on the fast frames (the "smear" frame), squash on contact. Even on rigid rigs: compress the spine/knees on landings. |
| Anticipation | Move *away* first, briefly (2–6 frames), before the main action. Bigger action → bigger anticipation. Can be a small one (eyes/brows) before a big one (body). |
| Staging | One idea per pose; clear silhouette from the camera. |
| Straight-ahead vs pose-to-pose | Block pose-to-pose for acting; use straight-ahead thinking for chaotic things (fire, cloth, a flailing tail) and for the *breakdowns* of flexible parts. |
| Follow-through & overlap | Nothing stops at once. Appendages (hair, tail, coat, ears, fingers) arrive late and settle after. Offset their keys 1–4 frames later than the parent. |
| Successive breaking of joints | A whip/arm/tail is a chain: shoulder leads, elbow follows, wrist last, fingers last of all. Each joint's key is offset 1–2 frames further down the chain. |
| Drag | The leading part moves first; trailing parts lag, then catch up and overshoot. |
| Slow in / slow out | Chart it (above). Not on everything — a punch has no slow-in on the hit. |
| Arcs | Almost all organic motion travels on arcs. Check the wrist/head/foot paths in the viewport (motion trail). Straight lines read as mechanical or deliberate. |
| Secondary action | A supporting action that adds meaning (tapping a foot while waiting) — never competes with the main action. |
| Timing | See charts. Fast = few frames; weighty = asymmetric charts. |
| Exaggeration | Push the key poses 10–20% past "real", then pull back the inbetweens if it breaks. |
| Solid posing | Weight over the supporting foot; line of action is a single C or S curve; avoid twins (mirror-identical left/right). |
| Appeal | Clarity + asymmetry + contrast of shapes (big/small, straight/curved). |

## Weight

Weight is read from: (1) how long the body takes to **start** moving; (2) how deep the
**down** position goes on each contact; (3) how much **recovery** follows (settle, overshoot
then return); (4) how slowly heavy parts **catch up**. Give a heavy creature a lower,
slower down, a delayed up, and a visible settle of 4–8 frames after every landing. Give
a light one a shallow down, quick up, and almost no settle.

## The take and the accent

- **Take**: anticipation *down/in* (eyes close, head drops, 2–4 frames) → **pop** up/out
  past the final pose (1–2 frames, stretched) → settle back into the held reaction
  pose (4–8 frames). Scale: an eye-flick take is 3 frames; a cartoon take is 12+.
- **Accent**: the frame of maximum force in any action (the hit, the stomp, the landed
  syllable). Put the extreme ON the accent frame and the biggest spacing gap just before
  it. Williams: "the accent is where the energy goes".

## Walks (the biggest chapter — see references/walks.md)

The four positions per step: **Contact** (both feet on the ground, legs widest, body
*lowest-ish* about to drop), **Down** (weight lands, knees bend, body lowest), **Passing**
(free leg passes the planted one, body highest-ish rising), **Up** (push off, body at its
highest, before the next contact). Key the contacts first, then downs, then passing, then
ups. Standard tempos at 24 fps: 12 frames per step = normal walk; 8 = brisk/jog-walk;
16 = stroll; 6 = run; 4 = sprint; 20–32 = tired or sneaking. Arms oppose the legs; the
hips rotate toward the forward leg; shoulders counter-rotate; the head bobs *down* on the
down and *up* on the up unless you choose otherwise (a "character" walk is exactly where
you break these rules on purpose).

## Runs (references/runs.md)

Fewer frames per step (4–8), only one foot on the ground at a time or none; the body
leans forward; the arms pump; there is a genuine flight phase. The faster the run, the
lower the up-and-down and the longer the stride. 4-frame runs need ones.

## Dialogue & acting (references/dialogue-acting.md)

Body first, mouth last. Hit the accented syllable with the body/head 2 frames **before**
the sound (lead the audio). Mouths: a few clear shapes, change them on the accents only,
never flap every frame. Blink on head turns and on thought changes. The eyes lead every
look by 2–4 frames; the head follows; the body follows that.

## Creatures (references/creatures.md)

Quadrupeds: front legs ≈ arms, back legs ≈ legs, offset by roughly a quarter cycle; the
spine flexes in the gallop, stays flat in a walk. Birds: wings "flap" with successive
breaking of joints (shoulder → elbow → wrist → feather tips) and a slow upstroke /
fast downstroke. Flexible objects (rope, flag, tail): straight-ahead wave through the
chain with each segment one or two frames behind the last.

## Review checklist (run this on every pass)

- Is there one clear idea per pose and one accent per action?
- Are charts asymmetric (favouring)? Any evenly spaced stretch is a suspect.
- Does the body leave poses slowly and arrive fast (or vice versa) *on purpose*?
- Do appendages overlap/follow through by 1–4 frames? Do joints break successively?
- Do wrists, head, feet travel on arcs? (Motion trail.)
- Is there a moving hold instead of a freeze?
- Does the weight read in the down position and the settle?
- Did a blink/eye-dart precede each head turn?
