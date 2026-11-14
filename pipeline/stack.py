"""T23: shift-and-stack along an object's motion.

Stack all frames twice: once as they are (stars sharp, movers smeared or repeated) and once shifted
so the chosen object stays put (the object sharp, stars smeared). With many frames a mover too
faint for any single frame can show up in the shifted stack: the standard trick for slow, faint
movers (T10 "Planet X mode" can feed it guessed motions instead of a label's known one).

    python -m pipeline.stack <target_dir> [--object <label id | detection id | known object name>]
                             [--out <png>]

Works on the display PNGs (8-bit, stretched), so the result is for looking at, not for photometry.
Without --object it uses the fastest-moving object in the target.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import shift as nd_shift


def tracks(target: dict) -> list[tuple[str, str, list[dict]]]:
    out = [(l["id"], l["name"], l["positions"]) for l in target.get("labels", [])]
    out += [(k["name"], k["name"], k["positions"]) for k in target.get("known_objects", [])]
    out += [(d["id"], d.get("matched_object") or d["id"], d["track"]) for d in target.get("detections", [])]
    return [t for t in out if len(t[2]) >= 2]


def extent(positions: list[dict]) -> float:
    xs, ys = [p["x"] for p in positions], [p["y"] for p in positions]
    return float(np.hypot(max(xs) - min(xs), max(ys) - min(ys)))


def load_frames(target_dir: Path, target: dict) -> dict[str, np.ndarray]:
    """frame id -> float image (NaN where the PNG is transparent = no data)."""
    out = {}
    for f in target["frames"]:
        im = Image.open(target_dir / f["image"]).convert("LA")
        a = np.asarray(im, dtype=float)
        img = a[..., 0]
        img[a[..., 1] == 0] = np.nan
        out[f["id"]] = img
    return out


def shift_and_stack(target_dir: Path, object_key: str | None = None) -> tuple[np.ndarray, np.ndarray, dict]:
    target = json.loads((target_dir / "target.json").read_text())
    cands = tracks(target)
    if not cands:
        raise SystemExit("no object with positions in this target")
    if object_key:
        match = [t for t in cands if object_key in (t[0], t[1])]
        if not match:
            raise SystemExit(f"no object {object_key!r}; try one of: {', '.join(t[0] for t in cands[:10])}")
        key, name, pos = match[0]
    else:
        key, name, pos = max(cands, key=lambda t: extent(t[2]))
    frames = load_frames(target_dir, target)
    by_frame = {p["frame_id"]: p for p in pos if p["frame_id"] in frames}
    ref = next(iter(by_frame.values()))
    plain, shifted = [], []
    for fid, p in by_frame.items():
        img = frames[fid]
        plain.append(img)
        # move the frame so the object lands on its reference position (rows = y, cols = x)
        dy, dx = ref["y"] - p["y"], ref["x"] - p["x"]
        filled = np.nan_to_num(img, nan=0.0)
        valid = nd_shift(np.isfinite(img).astype(float), (dy, dx), order=1, cval=0.0)
        moved = nd_shift(filled, (dy, dx), order=1, cval=0.0)
        moved[valid < 0.5] = np.nan
        shifted.append(moved)
    a = np.nanmedian(np.array(plain), axis=0)
    b = np.nanmedian(np.array(shifted), axis=0)
    info = {"object": name, "key": key, "frames": len(by_frame), "path_px": round(extent(pos), 2),
            "ref_xy": [ref["x"], ref["y"]], "synthetic": bool(target.get("synthetic"))}
    return a, b, info


def to_png(img: np.ndarray) -> Image.Image:
    fin = np.isfinite(img)
    lo, hi = (np.percentile(img[fin], [1, 99.8]) if fin.any() else (0, 1))
    x = np.clip((np.nan_to_num(img, nan=lo) - lo) / max(hi - lo, 1e-9), 0, 1)
    return Image.fromarray((x * 255).astype(np.uint8))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Shift-and-stack along an object's motion")
    ap.add_argument("target_dir", type=Path)
    ap.add_argument("--object", help="label id, detection id or known object name (default: fastest mover)")
    ap.add_argument("--out", type=Path, help="PNG with both stacks side by side (default: <target>/stack_<key>.png)")
    args = ap.parse_args(argv)
    a, b, info = shift_and_stack(args.target_dir, args.object)
    left, right = to_png(a), to_png(b)
    pad = 6
    sheet = Image.new("L", (left.width * 2 + pad, left.height), 40)
    sheet.paste(left, (0, 0)); sheet.paste(right, (left.width + pad, 0))
    out = args.out or args.target_dir / f"stack_{info['key']}.png"
    sheet = sheet.resize((sheet.width * 4, sheet.height * 4), Image.NEAREST)
    if info["synthetic"]:  # simulated input must be labelled on the picture itself
        from PIL import ImageDraw
        ImageDraw.Draw(sheet).text((8, 6), "SYNTHETIC - NOT SPHEREx DATA", fill=255)
    sheet.save(out)
    print(json.dumps(info), "->", out)
    print("left: plain median stack (stars sharp) · right: shifted along the object's path (object sharp)")


if __name__ == "__main__":
    main()
