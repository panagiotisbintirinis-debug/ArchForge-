#!/usr/bin/env python3
"""Fetch furniture-like CC0/CC-BY models from the Khronos glTF sample assets.

Source: https://github.com/KhronosGroup/glTF-Sample-Assets (raw.githubusercontent.com
is reachable from the agent sandbox; Poly Haven/ambientCG/Kenney are not).
Each model's metadata.json carries SPDX licences and artists; only models
whose every legal entry is CC0-1.0, CC-BY-4.0 or a Khronos legal mark are
accepted, and the attribution is stored in the asset provenance.

Downloads the plain glTF variant (.gltf + .bin + base-colour textures only),
imports it into the ArchForge asset store (plan symbol included) and runs a
size plausibility check against the expected range for its category.

Usage:
    python fetch_khronos.py --random 3 [--seed 7]
    python fetch_khronos.py --models SheenChair,GlamVelvetSofa
    (set ARCHFORGE_DATA to choose the asset store; --cache DIR for downloads)
"""
import argparse
import json
import pathlib
import random
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4]))
from archforge.library.assets import store_asset  # noqa: E402
from archforge.library.gltf import drop_ground_planes, read_gltf  # noqa: E402

RAW = "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models"
OK_LICENSES = {"CC0-1.0", "CC-BY-4.0", "LicenseRef-LegalMark-Khronos"}

# Curated: name -> (Greek label, category, expected (min, max) cm for W, D, H).
CATALOG = {
    "SheenChair": ("Καρέκλα σαλονιού βελούδινη", ("Έπιπλα", "Καθίσματα"), ((40, 110), (40, 110), (60, 120))),
    "ChairDamaskPurplegold": ("Καρέκλα damask", ("Έπιπλα", "Καθίσματα"), ((40, 110), (40, 110), (60, 120))),
    "GlamVelvetSofa": ("Καναπές καμπύλος βελούδινος", ("Έπιπλα", "Καναπέδες"), ((140, 320), (70, 130), (60, 125))),
    "SheenWoodLeatherSofa": ("Καναπές chesterfield", ("Έπιπλα", "Καναπέδες"), ((140, 320), (70, 130), (60, 125))),
    "SpecularSilkPouf": ("Πουφ δαπέδου", ("Έπιπλα", "Καθίσματα"), ((35, 90), (35, 90), (15, 50))),
    "CommercialRefrigerator": ("Ψυγείο βιτρίνα", ("Συσκευές",), ((50, 200), (50, 100), (150, 230))),
    "AnisotropyBarnLamp": ("Φωτιστικό οροφής barn", ("Φωτισμός",), ((15, 80), (15, 80), (15, 120))),
    "IridescenceLamp": ("Φωτιστικό επιτραπέζιο", ("Φωτισμός",), ((10, 70), (10, 70), (20, 90))),
    "LightsPunctualLamp": ("Φωτιστικό δαπέδου τοξωτό", ("Φωτισμός",), ((20, 150), (20, 150), (120, 220))),
    "GlassVaseFlowers": ("Βάζο με λουλούδια", ("Διακόσμηση",), ((5, 80), (5, 80), (10, 120))),
    "DiffuseTransmissionPlant": ("Φυτό σε γλάστρα", ("Διακόσμηση", "Φυτά"), ((10, 150), (10, 150), (10, 250))),
    "Lantern": ("Φανοστάτης", ("Εξωτερικά",), ((20, 150), (20, 150), (150, 500))),
}


def _get(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        with urllib.request.urlopen(url, timeout=120) as r:
            dest.write_bytes(r.read())
    return dest


def fetch(name, cache):
    meta = json.loads(_get(f"{RAW}/{name}/metadata.json", cache / name / "metadata.json").read_text())
    legal = meta.get("legal", [])
    licenses = {x.get("license") for x in legal}
    if not legal or not licenses <= OK_LICENSES:
        raise ValueError(f"{name}: licence not accepted: {sorted(map(str, licenses))}")
    gltf = _get(f"{RAW}/{name}/glTF/{name}.gltf", cache / name / f"{name}.gltf")
    doc = json.loads(gltf.read_text())
    for b in doc.get("buffers", []):
        _get(f"{RAW}/{name}/glTF/{b['uri']}", cache / name / b["uri"])
    base_color_images = set()
    for m in doc.get("materials", []):
        info = m.get("pbrMetallicRoughness", {}).get("baseColorTexture")
        if info:
            tex = doc["textures"][info["index"]]
            # Plain PNG/JPEG source only; WebP/KTX2 variants live in extensions.
            if "source" in tex:
                base_color_images.add(tex["source"])
    for i in base_color_images:
        uri = doc["images"][i].get("uri")
        if uri and not uri.startswith("data:"):
            _get(f"{RAW}/{name}/glTF/{uri}", cache / name / uri)
    parts, dropped = drop_ground_planes(read_gltf(gltf))
    tris = [t for p, _c, _m in parts for t in p]
    colors = [c for p, c, _m in parts for _t in p]
    label, category, expected = CATALOG.get(name, (name, ("Εισαγωγές",), None))
    provenance = {
        "source": f"https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/{name}",
        "license": " AND ".join(sorted(l for l in licenses if not l.startswith("LicenseRef"))),
        "attribution": "; ".join(f"{x.get('artist', '?')} ({x.get('license')})" for x in legal
                                 if not str(x.get("license", "")).startswith("LicenseRef")),
        "redistributable": True,
    }
    part_names = {c: m for _p, c, m in parts if m}
    asset_id, size = store_asset(label, tris, provenance, colors=colors, category=category, part_names=part_names)
    issues = [f"dropped display base: {', '.join(dropped)}"] if dropped else []
    if expected:
        bad = [f"{axis}={value * 100:.0f} cm outside {lo}-{hi} cm"
               for axis, value, (lo, hi) in zip("WDH", size, expected) if not lo <= value * 100 <= hi]
        if bad:
            issues.append("SIZE CHECK FAILED: " + "; ".join(bad))
    return asset_id, size, issues


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--random", type=int)
    ap.add_argument("--seed", type=int)
    ap.add_argument("--models")
    ap.add_argument("--cache", default=str(pathlib.Path.home() / ".cache" / "archforge-khronos"))
    a = ap.parse_args(argv)
    names = a.models.split(",") if a.models else random.Random(a.seed).sample(sorted(CATALOG), a.random or 3)
    for name in names:
        try:
            asset_id, size, issues = fetch(name, pathlib.Path(a.cache))
        except Exception as exc:  # report and continue with the next model
            print(f"{name}: FAILED {exc}")
            continue
        state = " | ".join(issues) if issues else "size ok"
        print(f"{name}: {asset_id}  {size[0] * 100:.0f} x {size[1] * 100:.0f} x {size[2] * 100:.0f} cm  {state}")


if __name__ == "__main__":
    main()
