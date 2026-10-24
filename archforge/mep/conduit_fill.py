"""Geometric fill, using product diameters rather than bare copper sections.

The 30% limit is the owner's explicit project choice (24/10/2026), DESIGN_DEFAULT,
not a verified Greek code clause. Product dimensions below are MANUFACTURER_DATA;
Nexans outside diameters are nominal. Suitability, tolerances, pulling, grouping
and thermal checks still require the installation study.
"""
from __future__ import annotations

import math

DEFAULT_LIMIT = .30  # Owner explicitly selected 30%; not a regulatory claim.
DEFAULT_MAX_DN = 32  # Existing project's range; larger catalog sizes are selectable.

_KOUVIDIS = 'https://www.kouvidis.gr/conduit-systems/prostasia-kalodion/'
CONDUIT_PROFILES = {
    'conflex': {
        'name': 'KOUVIDIS CONFLEX ISR', 'status': 'MANUFACTURER_DATA',
        'bores': {16:10.1,20:13.5,25:17.8,32:23.6,40:30.7,50:39.0},
        'source': _KOUVIDIS+'vareos-typoy-1250nt/condur-conflex/conflex-diamorfosimos-kymatoeidis-solinas/',
        'basis': 'din min, product table, checked 24/10/2026. DN63 excluded: drawing and catalog disagree.',
    },
    'superflex_plus': {
        'name': 'KOUVIDIS SUPERFLEX PLUS', 'status': 'MANUFACTURER_DATA',
        'bores': {16:10.9,20:14.2,25:18.6,32:24.9},
        'source': 'https://www.kouvidis.gr/wp-content/uploads/2024/02/superlex-plus.pdf',
        'basis': 'din min, product data sheet 01/02/2024, single page, checked 24/10/2026.',
    },
    'supersol_plus': {
        'name': 'KOUVIDIS SUPERSOL PLUS (άκαμπτος)', 'status': 'MANUFACTURER_DATA',
        'bores': {16:13.4,20:17.5,25:22.1,32:28.4},
        'source': _KOUVIDIS+'elafroy-typoy-320nt/supersol-plus-superflex-plus/supersol-plus-akamptos-3stromatikos-solinas/',
        'basis': 'din min, product table, checked 24/10/2026.',
    },
    'geonflex': {
        'name': 'KOUVIDIS GEONFLEX N750 (υπόγειο)', 'status': 'MANUFACTURER_DATA',
        'bores': {50:40.0,63:49.8},
        'source': 'https://www.kouvidis.gr/wp-content/uploads/2024/03/catalogue-2025-1.pdf',
        'basis': 'Catalog 2025, printed pages 66–67, corrugated 2042050/2043050, 2042063/2043063; checked 24/10/2026.',
    },
}

_NEXANS = 'https://www.nexans.gr/en/products/Building-cables/'
WIRE_DIAMETERS = {
    1.5: {'outside_mm':3.2,'type':'H07V-U','part':'13004130',
          'source':_NEXANS+'H07V-U%2C-H05762/product~13004130~.html'},
    2.5: {'outside_mm':3.9,'type':'H07V-U','part':'13000671',
          'source':_NEXANS+'H07V-U%2C-H05762/product~13000671~.html'},
    4.0: {'outside_mm':4.4,'type':'ruNeasy H07V-U','part':'13006403',
          'source':_NEXANS+'ruNeasy-H036859/product~13006403~.html'},
    6.0: {'outside_mm':5.2,'type':'ruNeasy H07V-R','part':'13006408',
          'source':_NEXANS+'ruNeasy-H036859/product~13006408~.html'},
    10.0:{'outside_mm':6.7,'type':'H07V-R','part':'13000185',
          'source':'https://www.nexans.gr/.rest/catalog/v1/product/pdf/13000185'},
}
# Every row above: Nexans "Nominal outer diameter", MANUFACTURER_DATA,
# checked 24/10/2026. These are selected calculation products, not a universal
# diameter for every cable of the same copper section or a procurement mandate.


def wire_bundle(sections):
    """Insulated outside diameter -> count, or None when a section has no data."""
    result = {}
    for section, count in sections.items():
        if int(count) != count or count < 0:
            raise ValueError('non-negative integer wire count required')
        row = WIRE_DIAMETERS.get(float(section))
        if row is None:
            return None
        diameter = row['outside_mm']
        result[diameter] = result.get(diameter, 0) + int(count)
    return result


def geometric_fill(inside_mm, outside_counts):
    """Actual area ratio (also volume ratio along the same length), not utilization.

    π/4 cancels: sum(n*d_out²) / D_in². A multicore cable must be supplied once
    with its jacket diameter; it must not be represented by bare copper mm².
    """
    inside_mm = float(inside_mm)
    if not math.isfinite(inside_mm) or inside_mm <= 0:
        raise ValueError('positive internal conduit diameter required')
    area = 0.0
    for diameter, count in outside_counts.items():
        diameter = float(diameter)
        if not math.isfinite(diameter) or diameter <= 0 or int(count) != count or count < 0:
            raise ValueError('positive outside diameters and non-negative integer counts required')
        area += count * diameter ** 2
    return area / inside_mm ** 2


def merge_wires(*parts):
    out = {}
    for part in parts:
        for diameter, count in part.items():
            out[diameter] = out.get(diameter, 0) + count
    return out


def allocate(lines, options, *, limit, max_dn):
    """Pack whole circuit bundles; choose smallest fitting DN within each pipe.

    Exact minimum-count packing is attempted with bounded search. On a large
    problem the valid first-fit solution is returned with optimal_count=False;
    it is never presented as a proved minimum. No line is silently split or lost.
    """
    if not math.isfinite(limit) or not 0 < limit < 1:
        raise ValueError('fill limit must be between zero and one')
    choices = sorted((dn, bore) for dn, bore in options.items() if dn <= max_dn)
    if not choices:
        return {'pipes': [], 'unsupported': sorted(lines), 'optimal_count': True}
    capacity = max(bore*bore for _, bore in choices) * limit
    weight = {cid: geometric_fill(1, wires) for cid, wires in lines.items()}
    unsupported = sorted(cid for cid, w in weight.items() if w <= 0 or w > capacity+1e-10)
    items = sorted((cid for cid in lines if cid not in unsupported), key=lambda cid: (-weight[cid],cid))
    bins = []
    for cid in items:
        hit = next((b for b in bins if sum(weight[c] for c in b)+weight[cid] <= capacity+1e-10), None)
        if hit is None:
            bins.append([cid])
        else:
            hit.append(cid)
    lower = max(1, math.ceil((sum(weight[c] for c in items)-1e-10)/capacity)) if items else 0
    optimal = len(bins) == lower
    visits = 0
    for target in range(lower, len(bins)):
        trial, used, memo = [], [], set()
        def search(index):
            nonlocal visits
            visits += 1
            if visits > 100000:
                return False
            if index == len(items):
                return True
            state = (index, tuple(sorted(round(v, 10) for v in used)))
            if state in memo:
                return False
            memo.add(state)
            cid = items[index]; w = weight[cid]; seen = set()
            for i, value in enumerate(used):
                if value in seen or value+w > capacity+1e-10:
                    continue
                seen.add(value); used[i] += w; trial[i].append(cid)
                if search(index+1):return True
                trial[i].pop(); used[i] -= w
            if len(trial) < target:
                trial.append([cid]); used.append(w)
                if search(index+1):return True
                trial.pop(); used.pop()
            return False
        if search(0):
            bins = trial; optimal = True; break
        if visits > 100000:
            break
    else:
        optimal = True  # every smaller count was either ruled out or unnecessary
    pipes = []
    for group in bins:
        wires = merge_wires(*(lines[cid] for cid in group))
        dn, bore = next((dn,bore) for dn,bore in choices if geometric_fill(bore,wires) <= limit+1e-12)
        pipes.append({'dn':dn,'inner_mm':bore,'lines':sorted(group),
                      'diameters':wires,'fill':geometric_fill(bore,wires)})
    return {'pipes':pipes,'unsupported':unsupported,'optimal_count':optimal}
