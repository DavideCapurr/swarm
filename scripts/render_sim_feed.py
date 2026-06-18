#!/usr/bin/env python3
"""Render the synthetic SIM-labelled drone-POV viewport clip (CV-live video sub-step).

This is the **provenance + reproduction** record for
`frontend/public/sim-feed/drone-pov.mp4` and the
`sim/swarm_sim/cv/fixtures/sim_drone_pov/` fixtures. It builds a Langhe-vineyard
drone-POV scene — the same setting the demo scenarios model (Langhe, near Alba;
`sim/swarm_sim/world.py` `DEFAULT_DOCK` = 44.70 N, 8.03 E) — and renders it to a
PNG sequence. The clip is **explicitly synthetic** and is stamped `SIMULATED
FEED` in the Console; it is never passed off as a real camera (PDF §5.2).

Quality target (this revision): a **photorealistic** golden-hour render —
path-traced in Cycles (not the old EEVEE rasteriser), AgX tone-mapping, a
physically-based Nishita sky + a warm low sun for long raking shadows, gently
rolling terrain, trellised vine rows with leaf-level colour variation, a
back-view field figure with a walk cycle, and a low oblique drone camera with
depth-of-field. The subject stays **non-identifiable** (back view / distance),
the same privacy posture as the real `person_aerial/` fixtures.

Assets:
  - Sky    — procedural Nishita atmosphere (Blender Sky Texture); SwarmOS-authored,
             no download. Sun elevation/azimuth set for a late-afternoon look.
  - Ground — `aerial_grass_rock`, CC0-1.0 from Poly Haven
             (https://polyhaven.com/a/aerial_grass_rock), fetched via the public
             API so this script stays self-contained.

The terrain, vine rows, the figure and the camera path are SwarmOS-authored
geometry, dedicated to the public domain (CC0-1.0). The Poly Haven texture is
CC0-1.0 (no attribution required; recorded here for auditability).

Run (needs Blender ≥ 4.2; verified on 5.1.1) — Blender is **not** a repo/CI
dependency, this is an opt-in art tool, like the `[cv]` extra:

    blender --background --python scripts/render_sim_feed.py

then encode the PNG sequence to the browser clip with ffmpeg. A subtle vignette
+ light sensor grain are added at encode time (they need not loop):

    ffmpeg -y -framerate 24 -i /tmp/swarm_sim_feed/frames/frame_%04d.png \
        -vf "vignette=PI/5,noise=alls=4:allf=t,format=yuv420p" \
        -c:v libx264 -preset slow -movflags +faststart -crf 23 -an \
        frontend/public/sim-feed/drone-pov.mp4

The committed clip was produced exactly this way (1280x960, 60 frames, 24 fps,
Cycles GPU, 64 samples + OpenImageDenoise, AgX).
"""

from __future__ import annotations

import contextlib
import math
import os
import sys
import urllib.request

# ── Constants (the committed clip's exact parameters) ────────────────────────

OUT_DIR = os.environ.get("SWARM_SIM_FEED_OUT", "/tmp/swarm_sim_feed")
FRAMES_DIR = os.path.join(OUT_DIR, "frames")
CACHE_DIR = os.path.join(OUT_DIR, "assets")

RES_X, RES_Y = 1280, 960  # 4:3 — matches the Console viewport (aspect-[4/3])
FPS = 24
FRAME_START, FRAME_END = 1, 60
CYCLES_SAMPLES = 64  # + OpenImageDenoise → clean at this count

SUN_ELEV_DEG = 12.0  # low, late-afternoon golden hour → long shadows
SUN_AZ_DEG = 62.0  # rakes the rows from the front-left

TEX_ID = "aerial_grass_rock"
TEX_RES = "2k"
FOLIAGE_ID = "forest_leaves_02"  # CC0 leaf-litter → tiled small on the vine canopy
FOLIAGE_RES = "2k"

ROW_PITCH = 2.4  # m between vine rows
ALLEY_HALF = 1.2  # m — first row sits this far off the centre alley
ROW_HALF_LEN = 70.0  # m — rows run far enough to converge at the horizon
HEDGE_W, HEDGE_H = 0.34, 1.5  # m — a thin trellised vine wall, not a fat tube
WALK_SPAN = ROW_PITCH  # person advances exactly one row pitch → seamless loop
CAM_BACK, CAM_UP = 9.5, 4.0  # m — low oblique drone standoff (behind, above)
AIM_AHEAD = 7.0  # m — look down the alley; the figure sits in the lower third

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
        import json

        return json.loads(r.read().decode("utf-8"))


def _download(url: str, dest: str) -> str:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if not os.path.exists(dest):
        print(f"  fetching {url}")
        with _open(url, 120) as r, open(dest, "wb") as f:
            f.write(r.read())
    return dest


def fetch_texture_maps(tex_id: str, res: str) -> dict[str, str]:
    """Return {map_name: local_path} for the diffuse/normal/rough maps."""
    files = _fetch_json(f"{POLYHAVEN_API}/files/{tex_id}")
    wanted = {"Diffuse": "diffuse", "nor_gl": "normal", "Rough": "rough"}
    out: dict[str, str] = {}
    for key, short in wanted.items():
        entry = files.get(key, {}).get(res, {})
        fmt = "jpg" if "jpg" in entry else next(iter(entry), None)
        if not fmt:
            continue
        url = entry[fmt]["url"]
        out[short] = _download(
            url, os.path.join(CACHE_DIR, f"{tex_id}_{short}_{res}.{fmt}")
        )
    return out


# ── Small shader helpers (Principled input names moved in Blender 4.x) ────────


def _set_input(bsdf, value, *names) -> bool:
    for n in names:
        if n in bsdf.inputs:
            bsdf.inputs[n].default_value = value
            return True
    return False


def _principled(mat):
    return mat.node_tree.nodes.get("Principled BSDF")


# ── Scene construction (mirrors the committed render) ─────────────────────────


def build_scene() -> None:
    import bpy

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
    ):
        for b in list(block):
            block.remove(b)
    for h in list(bpy.app.handlers.frame_change_pre):
        if getattr(h, "__name__", "") == "_pose":
            bpy.app.handlers.frame_change_pre.remove(h)

    with contextlib.suppress(AttributeError):
        bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"

    _sky(scene)
    _sun()
    _terrain(fetch_texture_maps(TEX_ID, TEX_RES))
    _vine_rows(fetch_texture_maps(FOLIAGE_ID, FOLIAGE_RES))
    person = _figure()
    cam = _camera()
    _setup_render(scene)

    # Procedural animation: a frame-change handler poses the figure + drone each
    # frame from a formula, so a headless per-frame render and an interactive
    # scrub both stay in sync. Bound to object names, registered once.
    _register_pose(person, cam)
    scene.frame_set(FRAME_START)


def _sky(scene) -> None:
    """Procedural physically-based sky — a warm late-afternoon atmosphere.

    The atmospheric model is no download. Blender 5.x renamed Nishita to
    ``MULTIPLE_SCATTERING`` (same sun controls); pick the best model present and
    set each control defensively so the API rename can't break the build.
    """
    import bpy

    world = bpy.data.worlds.new("SimFeedSky")
    world.use_nodes = True
    scene.world = world
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    sky = nt.nodes.new("ShaderNodeTexSky")
    models = {e.identifier for e in sky.bl_rna.properties["sky_type"].enum_items}
    for choice in ("MULTIPLE_SCATTERING", "NISHITA", "SINGLE_SCATTERING"):
        if choice in models:
            sky.sky_type = choice
            break
    for attr, val in (
        ("sun_elevation", math.radians(SUN_ELEV_DEG)),
        ("sun_rotation", math.radians(SUN_AZ_DEG)),
        ("sun_intensity", 0.6),  # the Sun lamp carries the key; this lights the dome
        ("altitude", 230.0),  # Langhe hill country
        ("air_density", 0.7),  # less Rayleigh blue → warmer ambient on the ground
        ("dust_density", 1.6),  # warm horizon haze, but keep the sky clear
    ):
        with contextlib.suppress(Exception):
            setattr(sky, attr, val)
    nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def _sun() -> None:
    """A warm low key light aligned with the sky sun → long raking shadows."""
    import bpy

    light = bpy.data.lights.new("KeySun", "SUN")
    light.energy = 4.4
    light.color = (1.0, 0.79, 0.54)  # warm late-afternoon
    light.angle = math.radians(1.2)  # softly defined golden-hour shadows
    sun = bpy.data.objects.new("KeySun", light)
    bpy.context.scene.collection.objects.link(sun)
    sun.rotation_euler = (
        math.radians(90.0 - SUN_ELEV_DEG),
        0.0,
        math.radians(SUN_AZ_DEG),
    )


def _img_node(nt, mapping, path: str, non_color: bool):
    import bpy

    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = bpy.data.images.load(path)
    if non_color:
        node.image.colorspace_settings.name = "Non-Color"
    nt.links.new(mapping.outputs["Vector"], node.inputs["Vector"])
    return node


def _terrain(maps: dict[str, str]) -> None:
    """A large, gently rolling, grassy ground plane (Langhe is hilly)."""
    import bpy

    bpy.ops.mesh.primitive_plane_add(size=260.0, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "Ground"
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.subdivide(number_cuts=48)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()

    # Gentle hills via a Displace modifier on a clouds texture.
    htex = bpy.data.textures.new("TerrainHills", type="CLOUDS")
    htex.noise_scale = 0.7
    disp = ground.modifiers.new("hills", "DISPLACE")
    disp.texture = htex
    disp.texture_coords = "OBJECT"
    disp.strength = 5.0
    disp.mid_level = 0.5

    mat = bpy.data.materials.new("Terrain")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = _principled(mat)
    _set_input(bsdf, 1.0, "Roughness")  # dry, fully matte — no wet sheen
    _set_input(bsdf, 0.0, "Specular IOR Level", "Specular")

    texcoord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (42.0, 42.0, 42.0)
    nt.links.new(texcoord.outputs["UV"], mapping.inputs["Vector"])

    base = None
    if "diffuse" in maps:
        diff = _img_node(nt, mapping, maps["diffuse"], False)
        # Large-scale patches of dry soil so the ground is not a flat tile.
        var = nt.nodes.new("ShaderNodeTexNoise")
        var.inputs["Scale"].default_value = 1.2
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.52
        ramp.color_ramp.elements[1].position = 0.74
        nt.links.new(var.outputs["Fac"], ramp.inputs["Fac"])
        mix = nt.nodes.new("ShaderNodeMixRGB")
        mix.blend_type = "MULTIPLY"
        mix.inputs["Color2"].default_value = (0.5, 0.42, 0.26, 1.0)  # dry soil patches
        nt.links.new(diff.outputs["Color"], mix.inputs["Color1"])
        nt.links.new(ramp.outputs["Color"], mix.inputs["Fac"])
        base = mix.outputs["Color"]
    if base is not None:
        nt.links.new(base, bsdf.inputs["Base Color"])
    # Roughness stays a constant 1.0 — the CC0 rough map has glossy patches that
    # read as wet plastic under the sky, wrong for dry vineyard ground.
    if "normal" in maps:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = 1.5
        nt.links.new(_img_node(nt, mapping, maps["normal"], True).outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])

    ground.data.materials.append(mat)


def _leaf_material(maps: dict[str, str]):
    """Vine canopy from a real CC0 leaf texture (colour + normal) so the wall
    reads as a mass of leaves, not draped fabric — tiled small, tinted toward a
    warm vine green, with macro sun/shade clumps.
    """
    import bpy

    mat = bpy.data.materials.new("VineCanopy")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = _principled(mat)
    _set_input(bsdf, 0.9, "Roughness")
    _set_input(bsdf, 0.08, "Specular IOR Level", "Specular")  # faint leaf glint

    texcoord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (2.2, 2.2, 2.2)  # ~0.45 m leaf tile
    nt.links.new(texcoord.outputs["Object"], mapping.inputs["Vector"])

    def img(path, non_color):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(path)
        if non_color:
            n.image.colorspace_settings.name = "Non-Color"
        nt.links.new(mapping.outputs["Vector"], n.inputs["Vector"])
        return n

    if "diffuse" in maps:
        diff = img(maps["diffuse"], False)
        tint = nt.nodes.new("ShaderNodeMixRGB")
        tint.blend_type = "MULTIPLY"
        tint.inputs["Fac"].default_value = 0.6
        tint.inputs["Color2"].default_value = (0.45, 0.62, 0.18, 1.0)  # vine green
        nt.links.new(diff.outputs["Color"], tint.inputs["Color1"])
        # Macro sun/shade clumps so rows are not a flat repeat.
        macro = nt.nodes.new("ShaderNodeTexNoise")
        macro.inputs["Scale"].default_value = 6.0
        nt.links.new(texcoord.outputs["Object"], macro.inputs["Vector"])
        mramp = nt.nodes.new("ShaderNodeValToRGB")
        mramp.color_ramp.elements[0].position = 0.30
        mramp.color_ramp.elements[0].color = (0.55, 0.55, 0.55, 1.0)
        mramp.color_ramp.elements[1].position = 0.75
        mramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
        nt.links.new(macro.outputs["Fac"], mramp.inputs["Fac"])
        clump = nt.nodes.new("ShaderNodeMixRGB")
        clump.blend_type = "MULTIPLY"
        clump.inputs["Fac"].default_value = 0.8
        nt.links.new(tint.outputs["Color"], clump.inputs["Color1"])
        nt.links.new(mramp.outputs["Color"], clump.inputs["Color2"])
        nt.links.new(clump.outputs["Color"], bsdf.inputs["Base Color"])
    if "rough" in maps:
        nt.links.new(img(maps["rough"], True).outputs["Color"], bsdf.inputs["Roughness"])
    if "normal" in maps:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = 1.6  # strong leaf relief
        nt.links.new(img(maps["normal"], True).outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def _wood_material():
    import bpy

    mat = bpy.data.materials.new("TrellisWood")
    mat.use_nodes = True
    bsdf = _principled(mat)
    bsdf.inputs["Base Color"].default_value = (0.20, 0.13, 0.07, 1.0)
    _set_input(bsdf, 0.85, "Roughness")
    return mat


def _one_side(name: str, sign: int, leaf, wood) -> None:
    """Build one arrayed hedge + trellis-post run on the +/- side of the alley."""
    import bpy

    # Canopy wall — subdivided + lightly displaced for an irregular leaf line.
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(sign * ALLEY_HALF, 0.0, HEDGE_H * 0.5))
    hedge = bpy.context.active_object
    hedge.name = f"Hedge_{name}"
    hedge.scale = (HEDGE_W, ROW_HALF_LEN, HEDGE_H)
    bpy.context.view_layer.objects.active = hedge
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.subdivide(number_cuts=24)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.shade_smooth()
    # Fine fractal clumps ruffle the silhouette into foliage (small, not big
    # cloth folds) while keeping the wall thin.
    ctex = bpy.data.textures.new(f"HedgeClump_{name}", type="MUSGRAVE")
    with contextlib.suppress(Exception):
        ctex.noise_scale = 0.13
    d1 = hedge.modifiers.new("clumps", "DISPLACE")
    d1.texture = ctex
    d1.texture_coords = "OBJECT"
    d1.strength = 0.16
    # …and a very fine layer breaks the edge at leaf scale.
    ftex = bpy.data.textures.new(f"HedgeLeaf_{name}", type="DISTORTED_NOISE")
    with contextlib.suppress(Exception):
        ftex.noise_scale = 0.035
    d2 = hedge.modifiers.new("ruffle", "DISPLACE")
    d2.texture = ftex
    d2.texture_coords = "OBJECT"
    d2.strength = 0.05
    hedge.data.materials.append(leaf)
    arr = hedge.modifiers.new("rows", "ARRAY")
    arr.use_relative_offset = False
    arr.use_constant_offset = True
    arr.constant_offset_displace = (sign * ROW_PITCH, 0.0, 0.0)
    arr.count = 14
    hedge.location.z -= 0.30  # sink the base so gentle terrain hides the bottom

    # Trellis end-posts poking just above the canopy.
    bpy.ops.mesh.primitive_cylinder_add(radius=0.045, depth=HEDGE_H + 0.5, vertices=8,
                                         location=(sign * ALLEY_HALF, -ROW_HALF_LEN + 3, (HEDGE_H + 0.5) * 0.5))
    post = bpy.context.active_object
    post.name = f"Post_{name}"
    post.data.materials.append(wood)
    parr_y = post.modifiers.new("along", "ARRAY")
    parr_y.use_relative_offset = False
    parr_y.use_constant_offset = True
    parr_y.constant_offset_displace = (0.0, 9.0, 0.0)
    parr_y.count = 16
    parr_x = post.modifiers.new("across", "ARRAY")
    parr_x.use_relative_offset = False
    parr_x.use_constant_offset = True
    parr_x.constant_offset_displace = (sign * ROW_PITCH, 0.0, 0.0)
    parr_x.count = 14
    post.location.z -= 0.30


def _vine_rows(maps: dict[str, str]) -> None:
    leaf = _leaf_material(maps)
    wood = _wood_material()
    _one_side("R", +1, leaf, wood)
    _one_side("L", -1, leaf, wood)


def _figure():
    """A back-view field worker: smooth low-poly body, sun hat, pack, walk rig.

    Kept non-identifiable on purpose — distance + back view, no facial detail —
    the same privacy posture as the real `person_aerial/` fixtures.
    """
    import bpy

    scene = bpy.context.scene
    person = bpy.data.objects.new("Person", None)
    scene.collection.objects.link(person)
    person.location = (0.0, 0.0, 0.0)

    cloth = bpy.data.materials.new("FieldCloth")
    cloth.use_nodes = True
    cb = _principled(cloth)
    cb.inputs["Base Color"].default_value = (0.05, 0.07, 0.10, 1.0)  # dark workwear
    _set_input(cb, 0.75, "Roughness")
    hatm = bpy.data.materials.new("StrawHat")
    hatm.use_nodes = True
    hb = _principled(hatm)
    hb.inputs["Base Color"].default_value = (0.32, 0.25, 0.11, 1.0)  # straw
    _set_input(hb, 0.85, "Roughness")
    packm = bpy.data.materials.new("Pack")
    packm.use_nodes = True
    pb = _principled(packm)
    pb.inputs["Base Color"].default_value = (0.10, 0.13, 0.09, 1.0)  # olive pack
    _set_input(pb, 0.7, "Roughness")

    def joint(name, loc):
        e = bpy.data.objects.new(name, None)
        scene.collection.objects.link(e)
        e.parent = person
        e.location = loc
        return e

    def limb(parent, name, radius, length, mat, taper=0.8):
        # Cylinder whose top sits at the joint; rotating the joint swings it.
        bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=length, vertices=12,
                                             location=(0, 0, 0))
        o = bpy.context.active_object
        o.name = name
        o.parent = parent
        o.matrix_parent_inverse.identity()
        o.location = (0, 0, -length / 2)
        for v in o.data.vertices:
            if v.co.z < 0:
                v.co.x *= taper
                v.co.y *= taper
        o.modifiers.new("smooth", "SUBSURF").levels = 1
        bpy.ops.object.shade_smooth()
        o.data.materials.append(mat)
        return o

    def blob(parent, name, radius, loc, mat, scale=(1, 1, 1)):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=(0, 0, 0), segments=24, ring_count=16)
        o = bpy.context.active_object
        o.name = name
        o.parent = parent
        o.matrix_parent_inverse.identity()
        o.location = loc
        o.scale = scale
        bpy.ops.object.shade_smooth()
        o.data.materials.append(mat)
        return o

    # Torso + hips as tapered blobs.
    blob(person, "hips", 0.20, (0.0, 0.0, 0.95), cloth, scale=(1.1, 0.7, 0.9))
    blob(person, "torso", 0.22, (0.0, -0.02, 1.30), cloth, scale=(1.15, 0.7, 1.25))
    blob(person, "neck", 0.07, (0.0, 0.0, 1.58), cloth, scale=(1, 1, 1.2))
    blob(person, "head", 0.115, (0.0, 0.0, 1.72), cloth, scale=(0.95, 1.05, 1.1))
    # Straw sun hat (low crown + brim) — also hides any face detail.
    blob(person, "hat_crown", 0.13, (0.0, 0.0, 1.78), hatm, scale=(1, 1, 0.6))
    bpy.ops.mesh.primitive_cylinder_add(radius=0.23, depth=0.02, vertices=24, location=(0, 0, 0))
    brim = bpy.context.active_object
    brim.name = "hat_brim"
    brim.parent = person
    brim.matrix_parent_inverse.identity()
    brim.location = (0.0, 0.0, 1.74)
    bpy.ops.object.shade_smooth()
    brim.data.materials.append(hatm)
    # Field pack on the back — the camera is behind (looking +Y), so -Y faces it.
    blob(person, "pack", 0.16, (0.0, -0.18, 1.28), packm, scale=(1.0, 0.6, 1.3))

    hip_l = joint("hip_l", (-0.11, 0.0, 0.86))
    hip_r = joint("hip_r", (0.11, 0.0, 0.86))
    sh_l = joint("sh_l", (-0.24, 0.0, 1.46))
    sh_r = joint("sh_r", (0.24, 0.0, 1.46))
    limb(hip_l, "leg_l", 0.085, 0.86, cloth)
    limb(hip_r, "leg_r", 0.085, 0.86, cloth)
    limb(sh_l, "arm_l", 0.058, 0.62, cloth)
    limb(sh_r, "arm_r", 0.058, 0.62, cloth)
    return person


def _camera():
    import bpy

    cam_data = bpy.data.cameras.new("DroneCam")
    cam_data.lens = 44
    cam_data.sensor_width = 36
    cam_data.dof.use_dof = True
    cam_data.dof.aperture_fstop = 4.0  # gentle background fall-off, deep enough
    cam = bpy.data.objects.new("DroneCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    aim = bpy.data.objects.new("CamAim", None)
    bpy.context.scene.collection.objects.link(aim)
    trk = cam.constraints.new("TRACK_TO")
    trk.target = aim
    trk.track_axis = "TRACK_NEGATIVE_Z"
    trk.up_axis = "UP_Y"
    cam_data.dof.focus_object = aim
    return cam


def _register_pose(person, cam):
    import bpy

    def _pose(scene):
        f = scene.frame_current
        # Divide by the full period (not N-1) so the last frame is one step
        # before the start, not a duplicate of it — a clean loop.
        t = (f - FRAME_START) / (FRAME_END - FRAME_START + 1)  # 0..<1
        ph = 2.0 * math.tau * t  # two stride cycles; rows are periodic → seamless

        y = WALK_SPAN * t
        bob = 0.035 * abs(math.sin(ph))
        person.location = (0.0, y, bob)
        person.rotation_euler = (0.0, 0.0, 0.0)

        swing = 0.5
        for nm, s in (("hip_l", +1), ("hip_r", -1)):
            o = bpy.data.objects.get(nm)
            if o:
                o.rotation_euler = (s * swing * math.sin(ph), 0.0, 0.0)
        for nm, s in (("sh_l", -1), ("sh_r", +1)):
            o = bpy.data.objects.get(nm)
            if o:
                o.rotation_euler = (s * 0.32 * math.sin(ph), 0.0, 0.0)

        aim = bpy.data.objects.get("CamAim")
        if aim:
            aim.location = (0.0, y + AIM_AHEAD, 1.2)
        # Gentle, integer-cycle handheld drift so the loop stays seamless.
        cam.location = (
            0.22 * math.sin(math.tau * t),
            y - CAM_BACK,
            CAM_UP + 0.16 * math.sin(math.tau * t + 1.0),
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
            d.use = d.type == "METAL"
        scene.cycles.device = "GPU"
    scene.cycles.samples = CYCLES_SAMPLES
    scene.cycles.use_denoising = True
    with contextlib.suppress(Exception):
        scene.cycles.denoiser = "OPENIMAGEDENOISE"
    # Outdoor scene: cap bounces (big speed-up, no visible loss) + reuse the BVH
    # between frames so the animation render does not rebuild it every frame.
    scene.cycles.max_bounces = 4
    scene.cycles.diffuse_bounces = 2
    scene.cycles.glossy_bounces = 2
    scene.cycles.transmission_bounces = 2
    scene.cycles.volume_bounces = 0
    with contextlib.suppress(Exception):
        scene.cycles.use_persistent_data = True

    scene.view_settings.view_transform = "AgX"
    with contextlib.suppress(Exception):
        scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.25  # keep contrast; avoid a washed look

    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = FRAME_START, FRAME_END
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"


def render() -> None:
    import bpy

    os.makedirs(FRAMES_DIR, exist_ok=True)
    scene = bpy.context.scene
    for f in range(FRAME_START, FRAME_END + 1):
        scene.frame_set(f)
        scene.render.filepath = os.path.join(FRAMES_DIR, f"frame_{f:04d}.png")
        bpy.ops.render.render(write_still=True)
    print(f"rendered {FRAME_END - FRAME_START + 1} frames → {FRAMES_DIR}")
    print("now encode with ffmpeg (see module docstring).")


def main() -> int:
    try:
        import bpy  # noqa: F401
    except ImportError:
        print(
            "this script must run inside Blender:\n"
            "  blender --background --python scripts/render_sim_feed.py",
            file=sys.stderr,
        )
        return 2
    build_scene()
    render()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
