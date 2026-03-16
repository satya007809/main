# Best ComfyUI Face Swap Models - Research & Suggestions

## Top Models & Nodes

### 1. ReActor Node (Most Popular)

The go-to choice for speed and simplicity.

**Required Models:**
- `inswapper_128.onnx` — core face swap model
- `retinaface_resnet50` — face detection
- `face_yolov8m.pt` — face masking (Ultralytics)
- `sam_vit_b_01ec64.pth` — SAM segmentation

**Face Restoration Models:**
- `GFPGANv1.4` — solid general-purpose restoration
- `CodeFormer` (`codeformer.pth`) — best quality restoration
- `GPEN-BFR-512/1024/2048.onnx` — high-res detail recovery

**Key Nodes:** ReActorFaceSwap, ReActorFaceSwapOpt, ReActorOptions, ReActorFaceBoost, ReActorMaskHelper

**Model Paths:**
- Face restoration: `ComfyUI/models/facerestore_models/`
- Ultralytics: `ComfyUI/models/ultralytics/bbox/`
- SAM: `ComfyUI/models/sams/`
- Saved faces: `ComfyUI/models/reactor/faces/`

**Pros:** Fast (10x speed boost), simple setup, save face models as `.safetensors` for reuse
**Cons:** Weaker hair handling

GitHub: https://github.com/Gourieff/ComfyUI-ReActor

---

### 2. IPAdapter FaceID Plus V2 (Best for Character Consistency)

Uses CLIP encoding + ControlNet for face-consistent image generation.

**Setup Tips:**
- Choose IPAdapter model matching your checkpoint
- Input face should be centered, square crop preferred (224x224 internal resize)
- Use 35+ steps (10 more than normal)
- CFG should be lower than usual
- Weight < 0.8, noise adjustable down to 0.01

**Pros:** Better hair preservation, works with animals, generates consistent characters
**Cons:** Slower, requires more tuning

---

### 3. Flux Klein Face Swap (Newest)

Uses Black Forest Labs FLUX.2 Klein 9B FP8 diffusion transformer.

**Pros:** Best quality for lighting, emotion, and texture consistency
**Cons:** Heavy model (9B params), more complex setup

Reference: https://www.runcomfy.com/comfyui-workflows/flux-klein-face-swap-in-comfyui-seamless-ai-face-replacement

---

### 4. InstantID FaceSwap

Uses InstantID + ControlNet with SDXL checkpoints. Supports custom keypoints (KPS) for text-to-image and image-to-image generation.

GitHub: https://github.com/nosiu/comfyui-instantId-faceswap

---

### 5. DeepFuze (Video + Lipsync)

Comprehensive tool for face swap + lipsyncing + voice cloning + video generation.

---

## Recommendation Matrix

| Use Case | Best Choice |
|---|---|
| Quick single face swap | ReActor |
| Character consistency across images | IPAdapter FaceID Plus V2 |
| Highest quality single swap | Flux Klein |
| Video face swap + lipsync | DeepFuze |
| Maximum control (ControlNet) | InstantID |

## Quick Start Recommendation

**Start with ReActor + CodeFormer** — covers 90% of face swap needs with minimal setup.

## All Known ComfyUI Face Swap Nodes

1. ComfyUI-Reactor-Node
2. ComfyUI-DeepFuze
3. ComfyUI-InstantId-FaceSwap
4. ComfyUI_FaceShaper
5. CharacterFaceSwap
6. ComfyUI-InstaSwap
7. ComfyUI-Faceless-Node
8. ComfyUI-FaceSwap
9. ComfyUI_Windows_Portable_for_Faceswap

## Sources

- https://github.com/Gourieff/ComfyUI-ReActor
- https://www.comflowy.com/blog/face-swap
- https://www.mimicpc.com/learn/all-face-swap-nodes-for-comfyui
- https://civitai.com/articles/5915/fastest-face-swap-in-comfyui
- https://www.runcomfy.com/comfyui-workflows/flux-klein-face-swap-in-comfyui-seamless-ai-face-replacement
- https://github.com/nosiu/comfyui-instantId-faceswap
- https://comfyui.org/en/face-swap-revolution-with-reactor-and-rife
