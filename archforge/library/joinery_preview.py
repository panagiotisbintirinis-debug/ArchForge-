"""Front elevations of presets, derived from the same boxes as 3D fixtures.

No library asset or second Document is stored. Wall thickness here is a
DESIGN_DEFAULT preview context, not a product specification.
"""
from archforge.architecture import joinery


def preview_boxes(key):
    pr = joinery.preset(key)
    params = dict(pr['params'], width=pr['width'], height=pr['height'])
    return [(lo, hi, joinery.material_look(params, pr['kind'], role).get('color', '#a9cddd'))
            for role, lo, hi in joinery.joinery_boxes(pr['kind'], params, 0.25)]
