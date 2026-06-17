#!/usr/bin/env python3
"""Render the synthetic SIM-labelled drone-POV viewport clip (CV-live video sub-step).

This is the **provenance + reproduction** record for
`frontend/public/sim-feed/drone-pov.mp4` and the
`sim/swarm_sim/cv/fixtures/sim_drone_pov/` fixtures. It builds a Langhe-vineyard
drone-POV scene — the same setting the demo scenarios model (Langhe, near Alba;
`sim/swarm_sim/world.py` `DEFAULT_DOCK` = 44.70 N, 8.03 E) — and renders it to a
PNG sequence. The clip is **explicitly synthetic** and is stamped `SIMULATED
FEED` in the Console; it is never passed off as a real camera (PDF §5.2).

Assets are CC0-1.0 from Poly Haven (https://polyhaven.com), fetched via the
public API so this script is self-contained:

  - HDRI    `alps_field`        — natural daylight (https://polyhaven.com/a/alps_field)
  - Texture `aerial_grass_rock` — grassy inter-row terrain
                                  (https://polyhaven.com/a/aerial_grass_rock)

Both are CC0-1.0 (no attribution required; recorded here for auditability). The
vine rows, the figure and the camera path are SwarmOS-authored geometry, also
dedicated to the public domain (CC0-1.0).

Run (needs Blender ≥ 4.2; verified on 5.1.1) — Blender is **not** a repo/CI
dependency, this is an opt-in art tool, like the `[cv]` extra:

    blender --background --python scripts/render_sim_feed.py

then encode the PNG sequence to the browser clip with ffmpeg:

    ffmpeg -y -framerate 24 -i /tmp/swarm_sim_feed/frames/frame_%04d.png \
        -c:v libx264 -pix_fmt yuv420p -movflags +faststart -crf 23 -an \
        frontend/public/sim-feed/drone-pov.mp4

The committed clip was produced exactly this way (640x480, 60 frames, 24 fps,
EEVEE, 16 TAA samples).
"""

from __future__ import annotations

import contextlib
import os
import sys
import urllib.request

# ── Constants (the committed clip's exact parameters) ────────────────────────

OUT_DIR = os.environ.get("SWARM_SIM_FEED_OUT", "/tmp/swarm_sim_feed")
FRAMES_DIR = os.path.join(OUT_DIR, "frames")
CACHE_DIR = os.path.join(OUT_DIR, "assets")

RES_X, RES_Y = 640, 480
FPS = 24
FRAME_START, FRAME_END = 1, 60
EEVEE_SAMPLES = 16

HDRI_ID = "alps_field"
HDRI_RES = "1k"
TEX_ID = "aerial_grass_rock"
TEX_RES = "2k"

POLYHAVEN_API = "https://api.polyhaven.com"


# ── Poly Haven CC0 asset fetch (public API) ──────────────────────────────────


def _fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as r:
        import json

        return json.loads(r.read().decode("utf-8"))


def _download(url: str, dest: str) -> str:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if not os.path.exists(dest):
        print(f"  fetching {url}")
        with urllib.request.urlopen(url, timeout=120) as r, open(dest, "wb") as f:
            f.write(r.read())
    return dest


def fetch_hdri() -> str:
    files = _fetch_json(f"{POLYHAVEN_API}/files/{HDRI_ID}")
    url = files["hdri"][HDRI_RES]["hdr"]["url"]
    return _download(url, os.path.join(CACHE_DIR, f"{HDRI_ID}_{HDRI_RES}.hdr"))


def fetch_texture_maps() -> dict[str, str]:
    """Return {map_name: local_path} for the diffuse/normal/rough maps."""
    files = _fetch_json(f"{POLYHAVEN_API}/files/{TEX_ID}")
    wanted = {"Diffuse": "diffuse", "nor_gl": "normal", "Rough": "rough"}
    out: dict[str, str] = {}
    for key, short in wanted.items():
        entry = files.get(key, {}).get(TEX_RES, {})
        fmt = "jpg" if "jpg" in entry else next(iter(entry), None)
        if not fmt:
            continue
        url = entry[fmt]["url"]
        out[short] = _download(
            url, os.path.join(CACHE_DIR, f"{TEX_ID}_{short}_{TEX_RES}.{fmt}")
        )
    return out


# ── Scene construction (mirrors the committed render) ─────────────────────────


def build_scene() -> None:
    import bpy

    scene = bpy.context.scene

    # Clean slate.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras):
        for b in list(block):
            block.remove(b)

    # Older Blender lacks this preference; the default interpolation is fine.
    with contextlib.suppress(AttributeError):
        bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"

    _world_from_hdri(fetch_hdri())
    _ground(fetch_texture_maps())
    _vine_rows()
    person, aim = _figure()
    _animate(person)
    _camera(aim)

    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = RES_X
    scene.render.resolution_y = RES_Y
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = FRAME_START, FRAME_END
    # EEVEE sample attribute name varies across Blender versions.
    with contextlib.suppress(AttributeError):
        scene.eevee.taa_render_samples = EEVEE_SAMPLES
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"


def _world_from_hdri(hdr_path: str) -> None:
    import bpy

    world = bpy.data.worlds.new("SimFeedWorld")
    world.use_nodes = True
    bpy.context.scene.world = world
    nt = world.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(hdr_path)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def _ground(maps: dict[str, str]) -> None:
    import bpy

    bpy.ops.mesh.primitive_plane_add(size=120.0, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.name = "Ground"

    mat = bpy.data.materials.new("aerial_grass_rock")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    texcoord = nt.nodes.new("ShaderNodeTexCoord")
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (12.0, 12.0, 12.0)
    nt.links.new(texcoord.outputs["UV"], mapping.inputs["Vector"])

    def img(path: str, non_color: bool):
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(path)
        if non_color:
            node.image.colorspace_settings.name = "Non-Color"
        nt.links.new(mapping.outputs["Vector"], node.inputs["Vector"])
        return node

    if "diffuse" in maps:
        nt.links.new(img(maps["diffuse"], False).outputs["Color"], bsdf.inputs["Base Color"])
    if "rough" in maps:
        nt.links.new(img(maps["rough"], True).outputs["Color"], bsdf.inputs["Roughness"])
    if "normal" in maps:
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(img(maps["normal"], True).outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])

    ground.data.materials.append(mat)


def _vine_rows() -> None:
    import bpy

    mat = bpy.data.materials.new("VineGreen")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.06, 0.16, 0.045, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.92

    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-30.0, 0.0, 1.05))
    row = bpy.context.active_object
    row.name = "VineRow"
    row.scale = (0.6, 64.0, 1.10)
    bpy.context.view_layer.objects.active = row
    bpy.ops.object.transform_apply(scale=True)
    row.data.materials.append(mat)

    arr = row.modifiers.new("rows", "ARRAY")
    arr.count = 26
    arr.use_relative_offset = True
    arr.relative_offset_displace = (4.0, 0.0, 0.0)  # 0.6 m * 4.0 = 2.4 m pitch


def _figure():
    import bpy

    mat = bpy.data.materials.new("FigureDark")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.03, 0.04, 0.06, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.7

    scene = bpy.context.scene
    person = bpy.data.objects.new("Person", None)
    scene.collection.objects.link(person)

    def part(kind, name, radius, depth, loc):
        if kind == "cyl":
            bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=loc, vertices=16)
        else:
            bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=loc, segments=16, ring_count=10)
        o = bpy.context.active_object
        o.name = name
        o.data.materials.append(mat)
        o.parent = person
        return o

    part("cyl", "leg_l", 0.09, 0.85, (-0.12, 0, 0.42))
    part("cyl", "leg_r", 0.09, 0.85, (0.12, 0, 0.42))
    part("cyl", "torso", 0.17, 0.62, (0.0, 0, 1.16))
    part("cyl", "arm_l", 0.06, 0.60, (-0.26, 0, 1.18))
    part("cyl", "arm_r", 0.06, 0.60, (0.26, 0, 1.18))
    part("sph", "head", 0.13, 0.0, (0.0, 0, 1.60))

    aim = bpy.data.objects.new("PersonAim", None)
    scene.collection.objects.link(aim)
    aim.parent = person
    aim.location = (0.0, 0.0, 1.2)
    return person, aim


def _animate(person) -> None:
    person.rotation_euler = (0.0, 0.0, 0.0)
    person.keyframe_insert("rotation_euler", frame=FRAME_START)
    person.keyframe_insert("rotation_euler", frame=FRAME_END)
    for i, f in enumerate((1, 15, 30, 45, 60)):
        y = -3.0 + 8.0 * (f - 1) / (FRAME_END - 1)
        z = 0.05 if i % 2 == 1 else 0.0
        person.location = (0.0, y, z)
        person.keyframe_insert("location", frame=f)


def _camera(aim) -> None:
    import bpy

    cam_data = bpy.data.cameras.new("DroneCam")
    cam_data.lens = 28
    cam = bpy.data.objects.new("DroneCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    trk = cam.constraints.new("TRACK_TO")
    trk.target = aim
    trk.track_axis = "TRACK_NEGATIVE_Z"
    trk.up_axis = "UP_Y"
    for f, loc in ((FRAME_START, (-1.5, -13.0, 8.0)), (FRAME_END, (1.5, -11.0, 7.0))):
        cam.location = loc
        cam.keyframe_insert("location", frame=f)


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
