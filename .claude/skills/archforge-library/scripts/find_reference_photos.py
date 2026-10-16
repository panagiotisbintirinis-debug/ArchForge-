#!/usr/bin/env python3
"""Find openly licensed reference photos of an object type and save thumbnails.

Photo-built library objects start from pictures that anyone can see and
reuse: Openverse (CC / public-domain images, including Wikimedia Commons and
Flickr CC) is searched for a generic object name ("armchair", "pedestal
basin"), and small thumbnails are written to a scratch folder together with
``sources.json`` (title, creator, licence, page URL).

The photos are reference only: look at them, write a primitive spec
(``build_model.py`` / ``archforge/library/catalog*.py``), verify with
``asset_preview.py``.  Never commit the photos, never use them as textures,
and put the chosen photo's page URL in the spec's ``reference`` field.

Network: needs ``api.openverse.org`` and the thumbnail hosts
(``api.openverse.org`` serves thumbnails itself).  In the cloud sandbox these
must be in the environment's allowed domains.

Usage:
    python find_reference_photos.py "pedestal basin" --out DIR [--count 8]
"""
import argparse
import json
import pathlib
import urllib.parse
import urllib.request

API = "https://api.openverse.org/v1/images/"
OPEN_LICENCES = {"cc0", "pdm", "by", "by-sa"}          # no NC / ND
# Openverse answers 403 to the default "Python-urllib" agent: name ourselves.
HEADERS = {"User-Agent": "ArchForge-reference-finder/1.0 (library reference photos)"}


def fetch(url, opener=urllib.request.urlopen):
    return opener(urllib.request.Request(url, headers=HEADERS), timeout=30)


def search(query, count=8, opener=urllib.request.urlopen):
    params = urllib.parse.urlencode({"q": query, "page_size": max(1, min(count * 2, 40)),
                                     "license": ",".join(sorted(OPEN_LICENCES)), "mature": "false"})
    with fetch(f"{API}?{params}", opener) as response:
        data = json.load(response)
    return pick(data.get("results", []), count)


def pick(results, count):
    """Keep openly licensed results with a thumbnail and a page to credit."""
    out = []
    for r in results:
        if str(r.get("license", "")).lower() not in OPEN_LICENCES:
            continue
        thumb = r.get("thumbnail") or r.get("url")
        page = r.get("foreign_landing_url") or r.get("url")
        if not thumb or not page:
            continue
        out.append({"id": r.get("id"), "title": r.get("title") or "", "creator": r.get("creator") or "",
                    "license": f"{r.get('license', '')} {r.get('license_version', '')}".strip(),
                    "page": page, "thumbnail": thumb, "source": r.get("source") or r.get("provider") or ""})
        if len(out) >= count:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--out", required=True)
    ap.add_argument("--count", type=int, default=8)
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    found = search(a.query, a.count)
    for k, item in enumerate(found):
        name = out / f"{k:02d}.jpg"
        try:
            with fetch(item["thumbnail"]) as response:
                name.write_bytes(response.read())
            item["file"] = name.name
        except OSError as exc:
            item["error"] = str(exc)
    (out / "sources.json").write_text(json.dumps(found, ensure_ascii=False, indent=2), encoding="utf-8")
    for item in found:
        print(item.get("file", "-"), item["license"], item["page"])


if __name__ == "__main__":
    main()
