"""Install the original, shipped lighting assets through the existing user catalogue.

Geometry, light sources, capabilities and icons are the delivered content pack,
not generated substitutes. Existing user assets and thumbnails are preserved.
"""
from pathlib import Path
import shutil

from archforge.library import assets


def seed_lights():
    source = Path(__file__).resolve().parent / 'content' / 'lights'
    definitions = sorted((source / 'assets').glob('*.json'))
    if not definitions:
        raise FileNotFoundError('Δεν βρέθηκαν τα ενσωματωμένα 3D φωτιστικά')
    destination = assets.asset_dir()
    thumbs = destination / 'thumbs'
    thumbs.mkdir(parents=True, exist_ok=True)
    installed = []
    for definition in definitions:
        target = destination / definition.name
        if not target.exists():
            # Exclusive creation preserves user content even if two windows start together.
            try:
                with target.open('xb') as out:
                    out.write(definition.read_bytes())
            except FileExistsError:
                pass
            else:
                assets._CACHE.pop(definition.stem, None)
                installed.append(definition.stem)
        for size in (40, 80):
            icon = source / 'icons' / f'{definition.stem}_{size}.png'
            target_icon = thumbs / icon.name
            if not target_icon.exists():
                with icon.open('rb') as inp:
                    try:
                        with target_icon.open('xb') as out:
                            shutil.copyfileobj(inp, out)
                    except FileExistsError:
                        pass
    return installed
