#!/usr/bin/env python3
"""Render the synthetic SIM-labelled drone-POV viewport clips (CV-live video sub-step).

This is the **provenance + reproduction** record for the
`frontend/public/sim-feed/*.mp4` clips and the
`sim/swarm_sim/cv/fixtures/sim_drone_pov/` fixtures. It builds a Langhe-vineyard
drone-POV scene — the same setting the demo scenarios model (Langhe, near Alba;
`sim/swarm_sim/world.py` `DEFAULT_DOCK` = 44.70 N, 8.03 E) — and renders it to a
PNG sequence. The clips are **explicitly synthetic** and are stamped `SIMULATED
FEED` in the Console; they are never passed off as a real camera (PDF §5.2).

**One clip per demo scenario** (`SWARM_SIM_FEED_SCENARIO`, default `standby`).
Every scenario is the *same* photoreal vineyard; it only adds the one honest
ambient element that scenario is about:

  - `standby`   → `drone-pov.mp4`     — calm patrol, no figure (the universal
                                        default; reproduces the prior clip).
  - `wildfire`  → `wildfire-pov.mp4`  — a grey smoke plume rising from the rows.
                                        Sim-modelled *visual* only (wildfire CV
                                        is deferred, `cv_enabled:false`), so it
                                        never stands in for a detection — it just
                                        shows the smoke the SMOKE anomaly reports.
  - `intrusion` → `intrusion-pov.mp4` — one non-identifiable figure in the alley.
  - `search`    → `search-pov.mp4`    — the same figure, smaller + off-axis,
                                        under a higher, wider sweep.

The figure is a low-poly **SwarmOS-authored proxy** (CC0), shown back-view and
at drone distance: deliberately not a real person's likeness and carrying no
recognisable face. It is pure viewport ambiance and **never** feeds the CV
`person` score — that stays on the real CC0 fixtures (honest-sim: a synthetic
figure is never a real detection).

Quality target: genuinely **photorealistic**, because every world element is a
real CC0 photoscanned asset rather than hand-faked geometry:

  - **Vines are real plant models.** Each vine row is thousands of *instances*
    of a real CC0 Poly Haven shrub model (`shrub_01`) — actual leaf geometry
    with alpha cutouts — stacked five-high into tall leafy walls. Instancing
    shares one mesh, so the whole field is cheap to render. Each instance gets a
    slightly different tint (via Object-Info colour) so the rows are not a flat
    repeat.
  - **A Langhe landscape**, not just rows: a treeline of real CC0 tree instances
    and soft rolling green hills sit on the horizon behind the vineyard.
  - **Golden-hour light.** A real CC0 partly-cloudy sky HDRI is warm-tinted for
    the camera and dimmed for lighting (Light-Path mix), with a warm low sun for
    long raking shadows.
  - Path-traced in **Cycles** (Metal GPU, 96 samples + OIDN, AgX).

The drone holds station over the rows, looking down the vineyard to the horizon,
with a gentle integer-cycle in-place sway (no net travel) so each 60-frame clip
loops cleanly. The scenario element (smoke / figure) likewise stays in place
with near-zero net travel so the loop survives (the billowing smoke has a soft,
deliberate seam).

Assets (all CC0-1.0; fetched from the public Poly Haven API at render time, so
nothing is committed to the repo):
  - Sky    — `kloofendal_48d_partly_cloudy_puresky` HDRI (Poly Haven).
  - Ground — `aerial_grass_rock` texture (Poly Haven).
  - Vines  — `shrub_01` 3D model (Poly Haven), instanced.
  - Trees  — `island_tree_01` 3D model (Poly Haven), instanced.

The terrain, hills, row layout, posts, camera path, the smoke plume and the
proxy figure are SwarmOS-authored, dedicated to the public domain (CC0-1.0).
Poly Haven assets are CC0-1.0 (no attribution; recorded in the LICENSES files).

Run (needs Blender ≥ 4.2; verified on 5.x; the glTF importer ships with Blender)
— Blender is **not** a repo/CI dependency, this is an opt-in art tool, like the
`[cv]` extra. Render each scenario, then encode its PNG sequence to the matching
clip (the script prints the exact ffmpeg line for the selected scenario):

    for s in standby wildfire intrusion search; do
        SWARM_SIM_FEED_SCENARIO=$s blender --background \
            --python scripts/render_sim_feed.py
    done

A subtle vignette + light sensor grain are added at the ffmpeg encode stage, e.g.

    ffmpeg -y -framerate 24 -i /tmp/swarm_sim_feed/wildfire/frames/frame_%04d.png \
        -vf "vignette=PI/5,noise=alls=4:allf=t,format=yuv420p" \
        -c:v libx264 -preset slow -movflags +faststart -crf 23 -an \
        frontend/public/sim-feed/wildfire-pov.mp4

The committed clips were produced exactly this way (1280x960, 60 frames, 24 fps,
Cycles GPU, 96 samples + OpenImageDenoise, AgX). `SWARM_SIM_FEED_SAMPLES` /
`SWARM_SIM_FEED_FRAMES` override samples/frame-count for cheap previews only.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import random
import sys
import urllib.request

# ── Constants (the committed clip's exact parameters) ────────────────────────

# Which clip to render. Every scenario is the *same* Langhe vineyard drone-POV;
# the scenario only adds the one honest SIMULATED-FEED element it is about (see
# the "Scenario variants" block below). `standby` reproduces the universal
# `drone-pov.mp4` exactly.
SCENARIO = os.environ.get("SWARM_SIM_FEED_SCENARIO", "standby").strip().lower()

OUT_DIR = os.environ.get("SWARM_SIM_FEED_OUT", "/tmp/swarm_sim_feed")
# Frames go to a per-scenario sub-dir so several scenarios can be rendered in
# one session without clobbering each other's PNG sequence. The asset + model
# caches are shared (the CC0 downloads are identical across scenarios).
FRAMES_DIR = os.path.join(OUT_DIR, SCENARIO, "frames")
CACHE_DIR = os.path.join(OUT_DIR, "assets")
MODEL_DIR = os.path.join(OUT_DIR, "models")

RES_X, RES_Y = 1280, 960  # 4:3 — matches the Console viewport (aspect-[4/3])
FPS = 24
# The committed clips are 60 frames at 96 spp. Both are overridable from the
# environment *only* to allow cheap low-sample previews while iterating on a
# scene; every committed asset uses the defaults below.
FRAME_START = 1
FRAME_END = int(os.environ.get("SWARM_SIM_FEED_FRAMES", "60"))
CYCLES_SAMPLES = int(os.environ.get("SWARM_SIM_FEED_SAMPLES", "96"))  # +OIDN

# Golden-hour key light: warm, low, behind the camera so the vine foliage stays
# lit while shadows rake the rows.
SUN_ELEV_DEG = 15.0
SUN_AZ_DEG = 208.0
WORLD_ROT_Z_DEG = 60.0  # orient the HDRI so its bright zone sits behind the rows
SKY_WARM_TINT = (1.0, 0.82, 0.6)  # multiply the visible sky toward golden
SKY_WARM_FAC = 0.8
BG_CAM_STRENGTH = 1.0  # bright sky for the camera
BG_LIT_STRENGTH = 0.5  # dimmed for lighting → the warm sun dominates shadows
EXPOSURE = 0.4

# Poly Haven CC0 assets (fetched via the public API; nothing is committed).
HDRI_ID = "kloofendal_48d_partly_cloudy_puresky"
HDRI_RES = "2k"
GROUND_ID = "aerial_grass_rock"
GROUND_RES = "2k"
SHRUB_ID = "shrub_01"  # real CC0 plant model, instanced into the vine rows
SHRUB_RES = "1k"
TREE_ID = "island_tree_01"  # real CC0 tree model, instanced into the treeline
TREE_RES = "1k"

# Vineyard layout — rows on both sides of the centre alley, viewed down-row.
ROW_PITCH = 2.25  # m between vine rows
ALLEY_HALF = 1.12  # m — first row sits this far off the centre alley
N_ROWS = 7  # rows per side
ROW_Y0 = -4.5  # m — rows start just ahead of the camera (keeps the near lens clear)
ROW_LEN = 46.0  # m — rows run far enough to converge at the horizon
PLANT_STEP = 0.34  # m — spacing of plant clumps along a row
PLANT_W, PLANT_H = 1.05, 0.78  # m — one instanced plant's footprint / height
STACK_Z = (0.28, 0.62, 0.96, 1.30, 1.62)  # five stacked layers → a tall wall
PLANT_SEED = 7  # deterministic plant scatter

# Treeline + rolling hills on the horizon (Langhe context).
TREE_COUNT = 20
TREE_SEED = 17
TREE_Y = (58.0, 84.0)  # m — band the treeline sits in
TREE_X = 48.0  # m — half-width the treeline spreads across
TREE_H = 7.0  # m — normalised tree height
# (x, y, radius_x, radius_y, height) low broad smooth mounds → soft green ridge.
HILL_SPECS = (
    (-34.0, 104.0, 62.0, 42.0, 20.0),
    (26.0, 116.0, 72.0, 50.0, 27.0),
    (-6.0, 134.0, 90.0, 58.0, 33.0),
    (70.0, 112.0, 55.0, 40.0, 19.0),
    (-82.0, 120.0, 62.0, 44.0, 22.0),
)

CAM_UP, CAM_Y = 3.2, -6.0  # m — low drone standoff over the alley
AIM_Y, AIM_Z = 38.0, 1.8  # m — look down the rows toward the converging horizon

# ── Scenario variants ────────────────────────────────────────────────────────
# Each demo scenario gets a drone-POV clip whose viewport matches what the
# operator is verifying — but every added element is honest SIMULATED-FEED
# ambiance, never a stand-in for a real detection:
#   standby   — calm patrol, nothing added (the universal default clip).
#   wildfire  — a grey smoke plume rising from the rows. Sim-modelled *visual*
#               only: wildfire CV stays deferred (cv_enabled:false), so the
#               plume never substitutes for a CV score — it just shows the
#               smoke the SMOKE anomaly already reports.
#   intrusion — one non-identifiable figure in the centre alley.
#   search    — the same figure, smaller + off-axis, under a higher, wider sweep.
# The figure is a low-poly SwarmOS-authored proxy (CC0) shown *back-view* and at
# drone distance: it is deliberately NOT a real person's likeness and carries no
# recognisable face, so it reads as "someone is in the rows" without identifying
# anyone. It is pure viewport ambiance and never feeds the CV `person` score —
# that stays on the real CC0 fixtures (honest-sim: a synthetic figure is never a
# real detection).
KNOWN_SCENARIOS = ("standby", "wildfire", "intrusion", "search")

# Per-scenario drone framing — (cam_height_m, cam_y_m, aim_y_m, aim_z_m, lens_mm).
# standby/wildfire keep the original low horizon look (the smoke rises down-row);
# the figure scenarios use a higher, steeper view that looks *into* the alley so
# the person is clearly on open ground (a more overtly drone-like angle, which
# also visually distinguishes them from the standby horizon shot).
CAM_RIG = {
    "standby": (3.2, -6.0, 38.0, 1.8, 30),
    "wildfire": (3.2, -6.0, 38.0, 1.8, 30),
    # Intrusion: a low drone looking down the open lane at the figure, which
    # stands clear on the soil with the vineyard behind it (large + unmistakable).
    "intrusion": (3.2, -3.5, 13.0, 0.7, 30),
    # Search: a higher, wider sweep — the subject is a small distant find.
    "search": (13.0, 1.0, 30.0, 0.5, 28),
}

# Figure scenarios push the vine rows apart so there is a clear central path the
# person stands in (a real-vineyard-narrow alley would hide them at this angle),
# with a worked-soil access lane down it for high contrast against the figure.
ALLEY_HALF_FIG = 2.6  # m — half-width of the widened centre path
ALLEY_LANE_HALF = 1.7  # m — half-width of the brown soil lane within it
# Intrusion pushes the vine rows back so the foreground is open lane: the figure
# stands clear on the soil with the vineyard wall as a backdrop (no near canopy
# to occlude it). Search keeps the normal start (its subject is far downrange).
ROW_Y0_FIG = 9.0  # m — where the rows begin in the intrusion shot

# Smoke plume (wildfire) — off the centre alley, mid-distance, so it reads as
# rising from the vineyard ahead. Local metres in the camera frame.
SMOKE_POS = (3.2, 25.0)  # (x, y)
SMOKE_BASE_Z = 0.35
SMOKE_HEIGHT = 11.0
SMOKE_RADIUS = 1.6

# Figure (intrusion/search) — stands/shifts in the alley, back to the camera.
FIGURE_POS = (0.0, 4.0)  # intrusion: close on the soil lane → large + unmistakable
FIGURE_POS_SEARCH = (1.5, 44.0)  # search: a small distant subject on the headland

POLYHAVEN_API = "https://api.polyhaven.com"
# Poly Haven's CDN rejects the default Python-urllib User-Agent (HTTP 403), so
# requests carry an explicit one — keeps this reproduction self-contained.
_UA = "swarmos-sim-feed/1.0 (+https://polyhaven.com; CC0 asset fetch)"


# ── Poly Haven CC0 asset fetch (public API) ──────────────────────────────────


def _open(url: str, timeout: int):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": _UA}), timeout=timeout
    )


def _fetch_json(url: str) -> dict:
    with _open(url, 60) as r:
        return json.loads(r.read().decode("utf-8"))


def _download(url: str, dest: str) -> str:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if not os.path.exists(dest):
        print(f"  fetching {url}")
        with _open(url, 300) as r, open(dest, "wb") as f:
            f.write(r.read())
    return dest


def fetch_hdri(hdri_id: str, res: str) -> str:
    """Download a single-res .hdr (or .exr) sky HDRI; return the local path."""
    entry = _fetch_json(f"{POLYHAVEN_API}/files/{hdri_id}")["hdri"][res]
    file = entry.get("hdr") or entry.get("exr")
    ext = os.path.splitext(file["url"])[1]
    return _download(file["url"], os.path.join(CACHE_DIR, f"{hdri_id}_{res}{ext}"))


def fetch_texture_maps(tex_id: str, res: str) -> dict[str, str]:
    """Return {map_name: local_path} for the diffuse/normal maps."""
    files = _fetch_json(f"{POLYHAVEN_API}/files/{tex_id}")
    wanted = {"Diffuse": "diffuse", "nor_gl": "normal"}
    out: dict[str, str] = {}
    for key, short in wanted.items():
        entry = files.get(key, {}).get(res, {})
        fmt = "jpg" if "jpg" in entry else next(iter(entry), None)
        if not fmt:
            continue
        out[short] = _download(
            entry[fmt]["url"], os.path.join(CACHE_DIR, f"{tex_id}_{short}_{res}.{fmt}")
        )
    return out


def fetch_model_gltf(model_id: str, res: str) -> str:
    """Download a Poly Haven glTF model + its .bin/textures; return the .gltf."""
    entry = _fetch_json(f"{POLYHAVEN_API}/files/{model_id}")["gltf"][res]["gltf"]
    base = os.path.join(MODEL_DIR, f"{model_id}_{res}")
    main = _download(entry["url"], os.path.join(base, os.path.basename(entry["url"])))
    for rel, info in entry.get("include", {}).items():
        _download(info["url"], os.path.join(base, rel))
    return main


# ── Small shader helpers (Principled input names moved in Blender 4.x) ────────


def _set_input(bsdf, value, *names) -> bool:
    for n in names:
        if n in bsdf.inputs:
            bsdf.inputs[n].default_value = value
            return True
    return False


def _principled(mat):
    return mat.node_tree.nodes.get("Principled BSDF")


def _img_node(nt, mapping, path: str, non_color: bool):
    import bpy

    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = bpy.data.images.load(path)
    if non_color:
        node.image.colorspace_settings.name = "Non-Color"
    nt.links.new(mapping.outputs["Vector"], node.inputs["Vector"])
    return node


def _wire_object_colour(obj) -> None:
    """Multiply each material's base colour by the per-object colour, so linked
    instances (which all share one mesh + material) can each be tinted by just
    setting ``instance.color`` — cheap per-plant tonal variation.
    """
    for mat in obj.data.materials:
        if not mat or not mat.use_nodes:
            continue
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue
        bc = bsdf.inputs.get("Base Color")
        if not bc or not bc.links:
            continue
        src = bc.links[0].from_socket
        oi = nt.nodes.new("ShaderNodeObjectInfo")
        mul = nt.nodes.new("ShaderNodeMixRGB")
        mul.blend_type = "MULTIPLY"
        mul.inputs["Fac"].default_value = 1.0
        nt.links.new(src, mul.inputs["Color1"])
        nt.links.new(oi.outputs["Color"], mul.inputs["Color2"])
        nt.links.new(mul.outputs["Color"], bc)


def _import_master(model_id: str, res: str, height_m: float, name: str):
    """Import a CC0 model, join its parts, normalise height, hide the source.

    Returns the master object whose mesh data every instance links to.
    """
    import bpy

    gltf = fetch_model_gltf(model_id, res)
    before = {o.name for o in bpy.data.objects}
    bpy.ops.import_scene.gltf(filepath=gltf)
    parts = [o for o in bpy.data.objects if o.name not in before and o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    if len(parts) > 1:
        bpy.ops.object.join()
    master = bpy.context.active_object
    master.name = name
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    d = master.dimensions
    s = height_m / max(d.z, 1e-6)
    master.scale = (s, s, s)
    master.location = (320.0, 320.0, 0.0)  # parked off-camera
    master.hide_render = True  # only its instances are rendered
    _wire_object_colour(master)
    return master


# ── Scene construction (mirrors the committed render) ─────────────────────────


def build_scene() -> None:
    import bpy

    if SCENARIO not in KNOWN_SCENARIOS:
        raise SystemExit(
            f"unknown SWARM_SIM_FEED_SCENARIO={SCENARIO!r}; "
            f"expected one of {', '.join(KNOWN_SCENARIOS)}"
        )

    scene = bpy.context.scene

    # Clean slate.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.lights,
        bpy.data.cameras,
        bpy.data.textures,
        bpy.data.images,
        bpy.data.worlds,
    ):
        for b in list(block):
            with contextlib.suppress(Exception):
                block.remove(b)
    # Drop any animation handlers a previous build left behind (a re-run in the
    # same Blender session would otherwise stack them).
    for h in list(bpy.app.handlers.frame_change_pre):
        if getattr(h, "__name__", "") in ("_pose", "_gait", "_smoke_anim"):
            bpy.app.handlers.frame_change_pre.remove(h)

    with contextlib.suppress(AttributeError):
        bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"

    _sky(scene, fetch_hdri(HDRI_ID, HDRI_RES))
    _sun()
    terrain_mat = _terrain(fetch_texture_maps(GROUND_ID, GROUND_RES))
    _hills()
    _treeline()
    master = _import_master(SHRUB_ID, SHRUB_RES, PLANT_H, "ShrubMaster")
    if SCENARIO == "intrusion":
        _vine_rows(master, ALLEY_HALF_FIG, ROW_Y0_FIG)  # rows back → open foreground
    elif SCENARIO == "search":
        _vine_rows(master, ALLEY_HALF_FIG, ROW_Y0)
    else:
        _vine_rows(master, ALLEY_HALF, ROW_Y0)

    # Scenario-specific element (honest SIMULATED-FEED ambiance only).
    if SCENARIO == "wildfire":
        _smoke_plume(SMOKE_POS)
    elif SCENARIO == "intrusion":
        _alley_lane(-5.0, ROW_Y0_FIG + ROW_LEN)
        _walker(FIGURE_POS, scale=1.12)
    elif SCENARIO == "search":
        _walker(FIGURE_POS_SEARCH, scale=1.4)

    cam = _camera()
    _setup_render(scene)

    _register_pose(cam)
    scene.frame_set(FRAME_START)
    return terrain_mat


def _sky(scene, hdri_path: str) -> None:
    """Real CC0 sky HDRI, warm-tinted for golden hour, with a Light-Path trick.

    The camera sees a warm-tinted, bright HDRI (golden clouds); everything else
    is lit by a dimmed copy, so the warm Sun lamp dominates and rakes the rows
    rather than the flat overhead light a full-strength midday HDRI would give.
    """
    import bpy

    world = bpy.data.worlds.new("SimFeedSky")
    world.use_nodes = True
    scene.world = world
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(hdri_path)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(WORLD_ROT_Z_DEG))
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])

    warm = nt.nodes.new("ShaderNodeMixRGB")
    warm.blend_type = "MULTIPLY"
    warm.inputs["Fac"].default_value = SKY_WARM_FAC
    warm.inputs["Color2"].default_value = (*SKY_WARM_TINT, 1.0)
    nt.links.new(env.outputs["Color"], warm.inputs["Color1"])

    bg_cam = nt.nodes.new("ShaderNodeBackground")
    bg_cam.inputs["Strength"].default_value = BG_CAM_STRENGTH
    bg_lit = nt.nodes.new("ShaderNodeBackground")
    bg_lit.inputs["Strength"].default_value = BG_LIT_STRENGTH
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(warm.outputs["Color"], bg_cam.inputs["Color"])
    nt.links.new(warm.outputs["Color"], bg_lit.inputs["Color"])
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg_lit.outputs["Background"], mix.inputs[1])
    nt.links.new(bg_cam.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])


def _sun() -> None:
    """A warm, low key light behind the camera → lit foliage + long shadows."""
    import bpy

    light = bpy.data.lights.new("KeySun", "SUN")
    light.energy = 4.6
    light.color = (1.0, 0.80, 0.52)  # golden hour
    light.angle = math.radians(1.4)
    sun = bpy.data.objects.new("KeySun", light)
    bpy.context.scene.collection.objects.link(sun)
    sun.rotation_euler = (
        math.radians(90.0 - SUN_ELEV_DEG),
        0.0,
        math.radians(SUN_AZ_DEG),
    )


def _terrain(maps: dict[str, str]):
    """A large, gently rolling, green grassy ground plane (Langhe is hilly).

    Returns the grass material (reused to texture the distant hills).
    """
    import bpy

    bpy.ops.mesh.primitive_plane_add(size=400.0, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "Ground"
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.subdivide(number_cuts=64)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()

    htex = bpy.data.textures.new("TerrainHills", type="CLOUDS")
    htex.noise_scale = 0.55
    disp = ground.modifiers.new("hills", "DISPLACE")
    disp.texture = htex
    disp.texture_coords = "OBJECT"
    disp.strength = 3.0
    disp.mid_level = 0.5

    mat = bpy.data.materials.new("Terrain")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = _principled(mat)
    _set_input(bsdf, 1.0, "Roughness")
    _set_input(bsdf, 0.0, "Specular IOR Level", "Specular")

    texcoord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (80.0, 80.0, 80.0)
    nt.links.new(texcoord.outputs["UV"], mapping.inputs["Vector"])

    if "diffuse" in maps:
        diff = _img_node(nt, mapping, maps["diffuse"], False)
        green = nt.nodes.new("ShaderNodeMixRGB")
        green.blend_type = "MULTIPLY"
        green.inputs["Fac"].default_value = 0.7
        green.inputs["Color2"].default_value = (0.19, 0.25, 0.10, 1.0)
        nt.links.new(diff.outputs["Color"], green.inputs["Color1"])
        nt.links.new(green.outputs["Color"], bsdf.inputs["Base Color"])
    if "normal" in maps:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = 1.2
        nt.links.new(
            _img_node(nt, mapping, maps["normal"], True).outputs["Color"],
            nm.inputs["Color"],
        )
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])

    ground.data.materials.append(mat)
    return mat


def _hills() -> None:
    """Soft, low, broad rolling hills as a green ridge on the far horizon."""
    import bpy

    hill = bpy.data.materials.new("Hill")
    hill.use_nodes = True
    hb = _principled(hill)
    hb.inputs["Base Color"].default_value = (0.27, 0.33, 0.21, 1.0)  # hazy green
    _set_input(hb, 1.0, "Roughness")

    for i, (x, y, rx, ry, h) in enumerate(HILL_SPECS):
        bpy.ops.mesh.primitive_ico_sphere_add(
            subdivisions=4, radius=1.0, location=(x, y, -h * 0.70)
        )
        m = bpy.context.active_object
        m.name = f"Hill_{i}"
        m.scale = (rx, ry, h)
        bpy.ops.object.shade_smooth()
        m.data.materials.append(hill)


def _treeline() -> None:
    """Scatter a band of real CC0 tree instances on the horizon behind the rows."""
    import bpy

    tree = _import_master(TREE_ID, TREE_RES, TREE_H, "TreeMaster")
    coll = bpy.context.scene.collection
    rng = random.Random(TREE_SEED)
    for i in range(TREE_COUNT):
        o = tree.copy()  # linked instance
        coll.objects.link(o)
        o.location = (
            rng.uniform(-TREE_X, TREE_X),
            rng.uniform(*TREE_Y),
            -0.6,
        )
        o.rotation_euler = (0.0, 0.0, rng.uniform(0.0, math.tau))
        s = rng.uniform(0.7, 1.25)
        o.scale = (tree.scale[0] * s, tree.scale[1] * s, tree.scale[2] * s)
        o.color = (
            rng.uniform(0.78, 0.98),
            rng.uniform(0.88, 1.02),
            rng.uniform(0.60, 0.82),
            1.0,
        )
        o.hide_render = False
        o.name = f"Tree_{i}"


def _flat_material(name: str, rgb, rough: float):
    import bpy

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = _principled(mat)
    bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    _set_input(bsdf, rough, "Roughness")
    return mat


def _vine_rows(master, alley_half: float = ALLEY_HALF, row_y0: float = ROW_Y0) -> None:
    """Rows on both sides of the centre alley, each a tall wall of stacked
    instances. Each instance is a linked copy of the shrub master (shared mesh →
    cheap) with a slightly different per-plant tint. Posts and worked-soil strips
    give the trellis structure. ``alley_half`` widens the central path and
    ``row_y0`` is where the rows begin — pushed back in the intrusion shot so the
    figure stands clear on the open foreground lane.
    """
    import bpy

    coll = bpy.context.scene.collection
    soil = _flat_material("RowSoil", (0.17, 0.11, 0.07), 1.0)
    wood = _flat_material("Post", (0.22, 0.17, 0.12), 0.85)
    rng = random.Random(PLANT_SEED)
    ms = master.scale

    def instance(x, y, z, sc):
        o = master.copy()  # linked: shares master.data → a Cycles instance
        coll.objects.link(o)
        o.location = (x, y, z)
        o.rotation_euler = (0.0, 0.0, rng.uniform(0.0, math.tau))
        o.scale = (ms[0] * sc, ms[1] * sc, ms[2] * sc)
        o.color = (  # green/warm tonal variation per plant
            rng.uniform(0.82, 1.05),
            rng.uniform(0.92, 1.08),
            rng.uniform(0.62, 0.90),
            1.0,
        )
        o.hide_render = False

    for sign in (-1, 1):
        for k in range(N_ROWS):
            x = sign * (alley_half + k * ROW_PITCH)

            # Worked-soil strip under the row.
            bpy.ops.mesh.primitive_plane_add(
                size=1.0, location=(x, row_y0 + ROW_LEN / 2, 0.02)
            )
            s = bpy.context.active_object
            s.name = f"Soil_{sign}_{k}"
            s.scale = (0.5, ROW_LEN / 2, 1.0)
            bpy.ops.object.transform_apply(scale=True)
            s.data.materials.append(soil)

            # Five stacked layers of plant instances → a continuous tall wall.
            y = row_y0
            while y < row_y0 + ROW_LEN:
                jx = rng.uniform(-0.05, 0.05)
                for zc in STACK_Z:
                    instance(
                        x + jx, y + rng.uniform(-0.1, 0.1), zc, rng.uniform(0.95, 1.2)
                    )
                y += PLANT_STEP

            # Trellis posts every 6 m (one cylinder + a Y array per row).
            bpy.ops.mesh.primitive_cylinder_add(
                radius=0.03, depth=2.0, vertices=6, location=(x, row_y0, 1.0)
            )
            p = bpy.context.active_object
            p.name = f"Post_{sign}_{k}"
            p.data.materials.append(wood)
            arr = p.modifiers.new("along", "ARRAY")
            arr.use_relative_offset = False
            arr.use_constant_offset = True
            arr.constant_offset_displace = (0.0, 6.0, 0.0)
            arr.count = int(ROW_LEN / 6.0) + 1


def _alley_lane(y_start: float, y_end: float) -> None:
    """A worked-soil access lane down the centre alley (figure scenarios) so the
    figure stands on a high-contrast brown surface, not lost in the green — and
    it reads as a real vineyard headland/access path.
    """
    import bpy

    soil = _flat_material("AlleySoil", (0.20, 0.14, 0.09), 1.0)
    bpy.ops.mesh.primitive_plane_add(
        size=1.0, location=(0.0, (y_start + y_end) / 2.0, 0.015)
    )
    lane = bpy.context.active_object
    lane.name = "AlleyLane"
    lane.scale = (ALLEY_LANE_HALF, (y_end - y_start) / 2.0, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    lane.data.materials.append(soil)


def _walker(pos, *, scale: float = 1.0) -> None:
    """One low-poly, back-view, non-identifiable figure in the centre alley.

    Authored entirely from primitives (CC0, SwarmOS-original): torso, head, two
    arms and two legs in a muted slate/earth palette (no red — PDF §5.2). It
    faces *away* from the camera and carries no recognisable face, so it reads as
    "someone is in the rows" without identifying anyone. It is pure SIMULATED-
    FEED ambiance and never feeds the CV `person` score — that stays on the real
    CC0 fixtures (honest-sim: a synthetic figure is never a real detection).

    A frame handler gives it a subtle integer-cycle weight-shift + arm sway with
    near-zero net travel, so the 60-frame clip still loops seamlessly.
    """
    import bpy

    x0, y0 = pos
    coll = bpy.context.scene.collection
    skin = _flat_material("FigSkin", (0.42, 0.31, 0.25), 0.6)
    jacket = _flat_material("FigJacket", (0.15, 0.17, 0.21), 0.8)  # muted slate
    trousers = _flat_material("FigTrousers", (0.19, 0.18, 0.16), 0.85)

    root = bpy.data.objects.new(f"Walker_{SCENARIO}", None)
    coll.objects.link(root)
    root.location = (x0, y0, 0.0)
    bpy.context.view_layer.update()
    # Keep each part exactly where it is built (world space); the root only adds
    # the per-frame bob on top. Without this inverse, parenting would re-apply
    # the root offset and place the figure at twice the intended distance.
    parent_inv = root.matrix_world.inverted()

    def part(prim, mat, loc, scl, **kw):
        getattr(bpy.ops.mesh, prim)(location=(x0 + loc[0], y0 + loc[1], loc[2]), **kw)
        o = bpy.context.active_object
        o.scale = scl
        bpy.ops.object.shade_smooth()
        o.data.materials.append(mat)
        o.parent = root
        o.matrix_parent_inverse = parent_inv
        return o

    s = scale
    part(  # torso
        "primitive_cylinder_add", jacket, (0.0, 0.0, 1.16 * s),
        (0.20 * s, 0.13 * s, 0.34 * s), vertices=16, radius=1.0, depth=1.0,
    )
    part(  # head
        "primitive_uv_sphere_add", skin, (0.0, 0.0, 1.63 * s),
        (0.115 * s, 0.115 * s, 0.135 * s), segments=18, ring_count=12, radius=1.0,
    )
    for sx in (-1, 1):  # legs
        part(
            "primitive_cylinder_add", trousers, (0.085 * s * sx, 0.0, 0.46 * s),
            (0.075 * s, 0.075 * s, 0.46 * s), vertices=12, radius=1.0, depth=1.0,
        )
    arms = [
        part(
            "primitive_cylinder_add", jacket, (0.215 * s * sx, 0.0, 1.06 * s),
            (0.052 * s, 0.052 * s, 0.30 * s), vertices=10, radius=1.0, depth=1.0,
        )
        for sx in (-1, 1)
    ]

    def _gait(scene):
        f = scene.frame_current
        t = (f - FRAME_START) / (FRAME_END - FRAME_START + 1)
        a = math.sin(math.tau * t)
        # Weight-shift + bob with near-zero net travel → loop-clean.
        root.location = (x0 + 0.03 * s * a, y0 + 0.05 * s * a, 0.018 * s * abs(a))
        root.rotation_euler = (0.0, 0.0, 0.04 * a)
        for i, arm in enumerate(arms):  # counter-phase arm sway
            arm.rotation_euler = (0.16 * (a if i == 0 else -a), 0.0, 0.0)

    _gait.__name__ = "_gait"
    bpy.app.handlers.frame_change_pre.append(_gait)
    _gait(bpy.context.scene)


def _smoke_plume(pos) -> None:
    """A grey smoke column rising from the rows — a noise-driven Principled
    Volume in a tapered cone domain, with **no fluid bake** so it renders
    headlessly and reproducibly.

    It is a sim-modelled *visual* only: wildfire CV stays deferred
    (cv_enabled:false), so the plume never substitutes for a detection — it just
    shows the smoke the SMOKE anomaly already reports. Grey, never a red/orange
    fire glow (PDF §5.2). A frame handler scrolls the noise upward so the column
    churns and rises (a soft loop seam is acceptable for billowing smoke).
    """
    import bpy

    x0, y0 = pos
    bpy.ops.mesh.primitive_cone_add(
        radius1=SMOKE_RADIUS,
        radius2=SMOKE_RADIUS * 2.6,  # widens as it rises
        depth=SMOKE_HEIGHT,
        vertices=28,
        location=(x0, y0, SMOKE_BASE_Z + SMOKE_HEIGHT / 2.0),
    )
    dom = bpy.context.active_object
    dom.name = "SmokePlume"

    mat = bpy.data.materials.new("Smoke")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (0.58, 0.58, 0.60, 1.0)  # cool grey smoke

    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.name = "SmokeMap"
    mp.inputs["Scale"].default_value = (1.0, 1.0, 0.45)  # stretch noise vertically
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.7
    noise.inputs["Detail"].default_value = 6.0
    noise.inputs["Roughness"].default_value = 0.6
    ramp = nt.nodes.new("ShaderNodeValToRGB")  # carve wisps: clamp low noise → 0
    ramp.color_ramp.elements[0].position = 0.42
    ramp.color_ramp.elements[1].position = 0.72

    # Vertical falloff: dense near the base, thinning to nothing at the top.
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    fall = nt.nodes.new("ShaderNodeMapRange")
    fall.inputs["From Min"].default_value = 0.0
    fall.inputs["From Max"].default_value = 1.0
    fall.inputs["To Min"].default_value = 1.0
    fall.inputs["To Max"].default_value = 0.0

    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    dens = nt.nodes.new("ShaderNodeMath")
    dens.operation = "MULTIPLY"
    dens.inputs[1].default_value = 7.0  # overall density scale

    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], noise.inputs["Vector"])
    nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], fall.inputs["Value"])
    nt.links.new(ramp.outputs["Color"], mul.inputs[0])
    nt.links.new(fall.outputs["Result"], mul.inputs[1])
    nt.links.new(mul.outputs["Value"], dens.inputs[0])
    nt.links.new(dens.outputs["Value"], vol.inputs["Density"])
    nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
    dom.data.materials.append(mat)

    def _smoke_anim(scene):
        f = scene.frame_current
        t = (f - FRAME_START) / (FRAME_END - FRAME_START + 1)
        m = nt.nodes.get("SmokeMap")
        if m:
            # Scroll the noise down in object space → the smoke reads as rising;
            # a touch of lateral drift gives the column some life.
            m.inputs["Location"].default_value = (0.12 * math.sin(math.tau * t), 0.0, -1.0 * t)

    _smoke_anim.__name__ = "_smoke_anim"
    bpy.app.handlers.frame_change_pre.append(_smoke_anim)
    _smoke_anim(bpy.context.scene)


def _camera():
    import bpy

    cam_h, cam_y, aim_y, aim_z, lens = CAM_RIG.get(SCENARIO, CAM_RIG["standby"])
    cam_data = bpy.data.cameras.new("DroneCam")
    cam_data.lens = lens
    cam_data.sensor_width = 36
    cam_data.dof.use_dof = True
    cam_data.dof.aperture_fstop = 4.0
    cam = bpy.data.objects.new("DroneCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    aim = bpy.data.objects.new("CamAim", None)
    bpy.context.scene.collection.objects.link(aim)
    aim.location = (0.0, aim_y, aim_z)
    trk = cam.constraints.new("TRACK_TO")
    trk.target = aim
    trk.track_axis = "TRACK_NEGATIVE_Z"
    trk.up_axis = "UP_Y"
    cam_data.dof.focus_object = aim
    cam.location = (0.0, cam_y, cam_h)
    return cam


def _register_pose(cam):
    import bpy

    # Sway around wherever the camera + aim were actually placed (so the search
    # variant's higher standoff is respected) rather than the standby constants.
    base = tuple(cam.location)
    aim = bpy.data.objects.get("CamAim")
    aim_base = tuple(aim.location) if aim else (0.0, AIM_Y, AIM_Z)

    def _pose(scene):
        f = scene.frame_current
        # Divide by the full period (not N-1) so the last frame is one step
        # before the start — a clean loop. The drone holds station with a
        # gentle integer-cycle sway, so there is no net travel to break the loop.
        t = (f - FRAME_START) / (FRAME_END - FRAME_START + 1)  # 0..<1
        cam.location = (
            base[0] + 0.16 * math.sin(math.tau * t),
            base[1] + 0.45 * math.sin(math.tau * t),
            base[2] + 0.10 * math.sin(math.tau * t + 1.0),
        )
        if aim:
            aim.location = (
                aim_base[0] + 0.10 * math.sin(math.tau * t + 0.5),
                aim_base[1],
                aim_base[2],
            )

    _pose.__name__ = "_pose"
    bpy.app.handlers.frame_change_pre.append(_pose)
    _pose(bpy.context.scene)


def _setup_render(scene) -> None:
    import bpy

    scene.render.engine = "CYCLES"
    # Metal GPU when present; harmless on CPU-only hosts.
    with contextlib.suppress(Exception):
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.refresh_devices()
        for d in prefs.devices:
            d.use = d.type in ("METAL", "CPU")
        scene.cycles.device = "GPU"
    scene.cycles.samples = CYCLES_SAMPLES
    scene.cycles.use_denoising = True
    with contextlib.suppress(Exception):
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
    # Outdoor scene: cap bounces (big speed-up, no visible loss) + reuse the BVH
    # between frames so the animation render does not rebuild it every frame.
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 2
    scene.cycles.transmission_bounces = 4  # alpha-cut leaves are transmissive
    # The wildfire plume needs one volume bounce to scatter the warm sun softly;
    # the figure/standby scenes have no volume, so 0 keeps them fast.
    scene.cycles.volume_bounces = 1 if SCENARIO == "wildfire" else 0
    with contextlib.suppress(Exception):
        scene.cycles.use_persistent_data = True

    scene.view_settings.view_transform = "AgX"
    with contextlib.suppress(Exception):
        scene.view_settings.look = "AgX - Base Contrast"
    scene.view_settings.exposure = EXPOSURE

    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = FRAME_START, FRAME_END
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"


def clip_name() -> str:
    """The committed clip filename for the selected scenario."""
    return "drone-pov.mp4" if SCENARIO == "standby" else f"{SCENARIO}-pov.mp4"


def render() -> None:
    import bpy

    os.makedirs(FRAMES_DIR, exist_ok=True)
    scene = bpy.context.scene
    for f in range(FRAME_START, FRAME_END + 1):
        scene.frame_set(f)
        scene.render.filepath = os.path.join(FRAMES_DIR, f"frame_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    print(f"rendered {FRAME_END - FRAME_START + 1} frames ({SCENARIO}) → {FRAMES_DIR}")
    print("now encode this scenario's PNG sequence to the browser clip:")
    print(
        f'  ffmpeg -y -framerate {FPS} -i {FRAMES_DIR}/frame_%04d.png \\\n'
        f'      -vf "vignette=PI/5,noise=alls=4:allf=t,format=yuv420p" \\\n'
        f"      -c:v libx264 -preset slow -movflags +faststart -crf 23 -an \\\n"
        f"      frontend/public/sim-feed/{clip_name()}"
    )


def main() -> int:
    try:
        import bpy  # noqa: F401
    except ImportError:
        print(
            "this script must run inside Blender:\n"
            "  SWARM_SIM_FEED_SCENARIO=wildfire blender --background "
            "--python scripts/render_sim_feed.py",
            file=sys.stderr,
        )
        return 2
    print(f"[render_sim_feed] scenario={SCENARIO} → {clip_name()}")
    build_scene()
    render()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
