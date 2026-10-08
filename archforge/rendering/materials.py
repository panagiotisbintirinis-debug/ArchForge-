from __future__ import annotations

from typing import Dict, Mapping


# Built-in ArchForge surface library.
#
# These are intentionally texture-free PBR presets. A material id is stored on
# the authoritative entity, while this catalog provides stable visual defaults.
# Later texture maps can be added to the same records without changing projects.
#
# Ids are stable (saved projects store them) and never renamed; names and
# categories are what the user sees, in Greek. Generic types only, no brands:
# a quarry or place name (Θάσου, Πηλίου, Καρύστου) names a stone type.
# Colours are typical appearance (sRGB), not a supplier's sample; RAL numbers
# are the common powder-coat colours of Greek aluminium frames. Appearance
# only: no physical or thermal property is claimed here.
#
# ``use`` lists where the finish is normally applied (see ``MATERIAL_USES``).
# ``opacity`` < 1 makes the surface see-through (glass).
MATERIAL_USES = ("τοίχος", "πρόσοψη", "δάπεδο", "στέγη", "κούφωμα", "έπιπλο", "αυλή")

MATERIAL_PRESETS: Dict[str, dict] = {}


def _add(category: str, rows: Mapping[str, tuple]) -> None:
    for material_id, row in rows.items():
        name, color, roughness, metalness, use = row[:5]
        spec = {
            "name": name,
            "category": category,
            "color": color,
            "roughness": roughness,
            "metalness": metalness,
            "use": tuple(use.split()),
        }
        if len(row) > 5:
            spec["opacity"] = row[5]
        MATERIAL_PRESETS[material_id] = spec


# id: (name, colour, roughness, metalness, "uses"[, opacity])
_add("Χρώματα & σοβάδες", {
    "plaster_white": ("Λευκός σοβάς", "#e6e1d7", 0.82, 0.00, "τοίχος πρόσοψη"),
    "plaster_warm": ("Ζεστός ορυκτός σοβάς", "#d4c2a6", 0.86, 0.00, "τοίχος πρόσοψη"),
    "paint_charcoal": ("Χρώμα ανθρακί", "#44484b", 0.72, 0.00, "τοίχος πρόσοψη"),
    "paint_white_matt": ("Πλαστικό χρώμα λευκό ματ", "#f1efea", 0.86, 0.00, "τοίχος"),
    "paint_offwhite": ("Πλαστικό χρώμα εκρού", "#ece3cf", 0.86, 0.00, "τοίχος"),
    "paint_beige": ("Χρώμα μπεζ", "#d9c7a6", 0.85, 0.00, "τοίχος πρόσοψη"),
    "paint_ochre": ("Χρώμα ώχρα", "#c99a4e", 0.85, 0.00, "τοίχος πρόσοψη"),
    "paint_aegean_blue": ("Βερνικόχρωμα μπλε Αιγαίου", "#2f5f8a", 0.45, 0.00, "κούφωμα έπιπλο"),
    "enamel_white_satin": ("Βερνικόχρωμα λευκό σατινέ", "#eeece6", 0.38, 0.00, "κούφωμα έπιπλο τοίχος"),
    "limewash_white": ("Ασβέστης λευκός (ασβέστωμα)", "#f4f2ec", 0.94, 0.00, "τοίχος πρόσοψη αυλή"),
    "plaster_rubbed": ("Τριμμένος σοβάς", "#e3ddd0", 0.93, 0.00, "τοίχος πρόσοψη"),
    "plaster_cement_raw": ("Σοβάς τσιμεντοκονίας άβαφος", "#a9a69e", 0.95, 0.00, "τοίχος πρόσοψη"),
})

_add("Θερμοπρόσοψη & επενδύσεις", {
    "etics_white": ("Θερμοσοβάς λευκός", "#ece9e1", 0.90, 0.00, "πρόσοψη"),
    "etics_offwhite": ("Θερμοσοβάς εκρού", "#e6dcc4", 0.90, 0.00, "πρόσοψη"),
    "etics_sand": ("Θερμοσοβάς άμμου", "#d6c3a0", 0.90, 0.00, "πρόσοψη"),
    "etics_grey": ("Θερμοσοβάς γκρι", "#9c9d9a", 0.90, 0.00, "πρόσοψη"),
    "etics_anthracite": ("Θερμοσοβάς ανθρακί", "#4d5053", 0.90, 0.00, "πρόσοψη"),
    "etics_terracotta": ("Θερμοσοβάς κεραμιδί", "#b77356", 0.90, 0.00, "πρόσοψη"),
    "fibre_cement_grey": ("Πλάκα τσιμεντοσανίδας γκρι", "#8f918f", 0.84, 0.00, "πρόσοψη τοίχος"),
    "acm_silver": ("Αλουμινοσύνθετο πάνελ ασημί", "#b9bcbf", 0.30, 0.70, "πρόσοψη"),
    "acm_anthracite": ("Αλουμινοσύνθετο πάνελ ανθρακί RAL 7016", "#383e42", 0.35, 0.45, "πρόσοψη"),
    "wood_cladding_larch": ("Ξύλινη επένδυση λάρικας", "#b88a5c", 0.72, 0.00, "πρόσοψη τοίχος"),
    "wpc_brown": ("Επένδυση σύνθετου ξύλου καφέ", "#6d4c37", 0.70, 0.00, "πρόσοψη αυλή"),
    "facade_ceramic_terracotta": ("Κεραμικές πλάκες πρόσοψης τερακότα", "#b0623f", 0.70, 0.00, "πρόσοψη"),
    "facade_ceramic_grey": ("Κεραμικές πλάκες πρόσοψης γκρι", "#8e8b86", 0.65, 0.00, "πρόσοψη"),
    "facade_marble": ("Μάρμαρο πρόσοψης λευκό αμμοβολής", "#e2ded5", 0.62, 0.00, "πρόσοψη"),
})

_add("Πέτρα", {
    "limestone_light": ("Ανοιχτόχρωμος ασβεστόλιθος", "#c8bea6", 0.84, 0.00, "τοίχος πρόσοψη δάπεδο"),
    "stone_dark": ("Σκούρα πέτρα", "#5b5c58", 0.88, 0.00, "τοίχος πρόσοψη αυλή"),
    "stone_pelion": ("Πέτρα Πηλίου", "#7f7d72", 0.84, 0.01, "πρόσοψη αυλή στέγη"),
    "stone_karystos": ("Πλάκα Καρύστου", "#8e8f80", 0.72, 0.02, "δάπεδο αυλή πρόσοψη"),
    "sandstone": ("Ψαμμίτης", "#c2a679", 0.90, 0.00, "πρόσοψη τοίχος αυλή"),
    "stone_drywall": ("Ξερολιθιά", "#9b8f7a", 0.96, 0.00, "αυλή τοίχος"),
    "stone_cladding": ("Πέτρα επένδυσης πλακοειδής", "#a89a82", 0.92, 0.00, "πρόσοψη τοίχος"),
    "stone_poros": ("Πωρόλιθος", "#d6c9a6", 0.95, 0.00, "πρόσοψη τοίχος"),
})

_add("Τούβλο", {
    "brick_exposed": ("Εμφανές τούβλο", "#a4533a", 0.88, 0.00, "τοίχος πρόσοψη"),
    "brick_light": ("Τούβλο ανοιχτόχρωμο", "#c88a62", 0.88, 0.00, "τοίχος πρόσοψη"),
    "brick_dark": ("Τούβλο σκούρο", "#6e3527", 0.88, 0.00, "τοίχος πρόσοψη"),
    "brick_old": ("Παλαιό χειροποίητο τούβλο", "#9b5a43", 0.92, 0.00, "τοίχος πρόσοψη δάπεδο"),
})

_add("Σκυρόδεμα", {
    "concrete_smooth": ("Λείο σκυρόδεμα", "#aaa9a3", 0.76, 0.00, "τοίχος πρόσοψη δάπεδο"),
    "concrete_rough": ("Τραχύ σκυρόδεμα", "#989993", 0.94, 0.00, "τοίχος πρόσοψη αυλή"),
    "concrete_exposed": ("Εμφανές σκυρόδεμα ξυλοτύπου", "#9fa09b", 0.86, 0.00, "τοίχος πρόσοψη"),
    "concrete_polished": ("Λειασμένο σκυρόδεμα δαπέδου", "#a5a49e", 0.40, 0.00, "δάπεδο"),
    "concrete_troweled": ("Πατητή τσιμεντοκονία", "#b4b1aa", 0.55, 0.00, "δάπεδο τοίχος"),
})

_add("Μάρμαρα", {
    "marble_thassos": ("Λευκό Θάσου", "#f3f2ee", 0.22, 0.00, "δάπεδο τοίχος έπιπλο"),
    "marble_dionysos": ("Μάρμαρο Διονύσου", "#e4e3df", 0.28, 0.00, "δάπεδο τοίχος πρόσοψη"),
    "marble_kavala": ("Μάρμαρο Καβάλας", "#e6e1d6", 0.28, 0.00, "δάπεδο τοίχος"),
    "marble_black": ("Μαύρο μάρμαρο", "#1f1f21", 0.20, 0.00, "δάπεδο έπιπλο"),
    "marble_grey": ("Γκρι μάρμαρο", "#8d8e8c", 0.28, 0.00, "δάπεδο τοίχος"),
    "marble_beige": ("Μπεζ μάρμαρο", "#dfcfb0", 0.28, 0.00, "δάπεδο τοίχος"),
})

_add("Πλακάκια", {
    "ceramic_light": ("Ανοιχτό κεραμικό πλακάκι", "#d9d7cf", 0.36, 0.00, "δάπεδο τοίχος"),
    "terracotta": ("Πήλινο πλακάκι τερακότα", "#a9583d", 0.78, 0.00, "δάπεδο αυλή"),
    "slate_tile": ("Πλακάκι σχιστόλιθου", "#555c61", 0.70, 0.01, "δάπεδο τοίχος"),
    "porcelain_matt_white": ("Πορσελάνη ματ λευκή", "#e5e3dc", 0.55, 0.00, "δάπεδο τοίχος"),
    "porcelain_gloss_white": ("Πορσελάνη γυαλιστερή λευκή", "#f0eee9", 0.10, 0.00, "δάπεδο τοίχος"),
    "tile_wood_look": ("Πλακάκι τύπου ξύλου", "#a57c56", 0.60, 0.00, "δάπεδο αυλή"),
    "tile_cement_look": ("Πλακάκι τύπου τσιμέντου", "#a3a19b", 0.66, 0.00, "δάπεδο τοίχος"),
    "tile_mosaic_glass": ("Γυάλινη ψηφίδα μπλε", "#3f7fa0", 0.15, 0.00, "τοίχος δάπεδο"),
    "tile_bath_white": ("Πλακάκι μπάνιου λευκό", "#f2f1ed", 0.10, 0.00, "τοίχος"),
    "tile_hydraulic": ("Τσιμεντοπλακάκι διακοσμητικό", "#8f9a9a", 0.62, 0.00, "δάπεδο"),
})

_add("Ξύλα", {
    "wood_oak": ("Δρυς φυσική", "#b98755", 0.64, 0.00, "δάπεδο έπιπλο κούφωμα"),
    "wood_walnut": ("Καρυδιά", "#6b4632", 0.66, 0.00, "έπιπλο δάπεδο κούφωμα"),
    "wood_weathered": ("Παλαιωμένο ξύλο", "#817667", 0.88, 0.00, "πρόσοψη αυλή έπιπλο"),
    "wood_oak_light": ("Δρυς λευκασμένη", "#d1b48c", 0.60, 0.00, "δάπεδο έπιπλο"),
    "wood_pine": ("Πεύκο", "#d3a96e", 0.70, 0.00, "έπιπλο στέγη κούφωμα"),
    "wood_teak": ("Τικ", "#9a6a3c", 0.60, 0.00, "αυλή έπιπλο δάπεδο"),
    "wood_beech": ("Οξιά", "#c99a6c", 0.60, 0.00, "έπιπλο δάπεδο"),
    "melamine_white": ("Μελαμίνη λευκή", "#eeede8", 0.45, 0.00, "έπιπλο"),
    "lacquer_white": ("Λάκα λευκή γυαλιστερή", "#f3f2ee", 0.15, 0.00, "έπιπλο"),
})

_add("Δάπεδα", {
    "floor_terrazzo": ("Μωσαϊκό λευκό-γκρι", "#c9c4ba", 0.40, 0.00, "δάπεδο"),
    "floor_terrazzo_warm": ("Μωσαϊκό κρεμ-κόκκινο", "#c7ad94", 0.40, 0.00, "δάπεδο"),
    "floor_vinyl_oak": ("Βινυλικό δάπεδο τύπου δρυός", "#b08a62", 0.55, 0.00, "δάπεδο"),
    "floor_laminate_oak": ("Δάπεδο λάμινετ δρυς", "#b8916a", 0.50, 0.00, "δάπεδο"),
    "floor_parquet_herringbone": ("Παρκέτο δρυς ψαροκόκαλο", "#a87a4c", 0.55, 0.00, "δάπεδο"),
    "floor_carpet_grey": ("Μοκέτα γκρι", "#7f7f7c", 1.00, 0.00, "δάπεδο"),
    "floor_carpet_beige": ("Μοκέτα μπεζ", "#b9a88e", 1.00, 0.00, "δάπεδο"),
})

_add("Μέταλλα & κουφώματα", {
    "steel_brushed": ("Ανοξείδωτο βουρτσισμένο", "#aeb5b9", 0.34, 0.82, "έπιπλο κούφωμα"),
    "steel_black": ("Σίδηρος μαύρος", "#33383d", 0.44, 0.78, "κούφωμα έπιπλο αυλή"),
    "aluminium": ("Αλουμίνιο φυσικό", "#c5c9ca", 0.30, 0.88, "κούφωμα πρόσοψη"),
    "copper": ("Χαλκός", "#b8714c", 0.38, 0.84, "στέγη έπιπλο"),
    "brass": ("Ορείχαλκος", "#d6b46a", 0.30, 0.90, "έπιπλο κούφωμα"),
    "alu_anodized_bronze": ("Αλουμίνιο ανοδιωμένο μπρονζέ", "#5f4b39", 0.35, 0.80, "κούφωμα"),
    "alu_ral9016": ("Αλουμίνιο λευκό RAL 9016", "#f1f0ea", 0.40, 0.10, "κούφωμα"),
    "alu_ral7016": ("Αλουμίνιο ανθρακί RAL 7016", "#383e42", 0.45, 0.15, "κούφωμα"),
    "alu_ral9005": ("Αλουμίνιο μαύρο RAL 9005", "#141416", 0.45, 0.15, "κούφωμα"),
    "alu_ral8017": ("Αλουμίνιο καφέ RAL 8017", "#45322e", 0.45, 0.15, "κούφωμα"),
    "alu_ral6005": ("Αλουμίνιο πράσινο RAL 6005", "#114232", 0.45, 0.15, "κούφωμα"),
    "alu_woodgrain": ("Αλουμίνιο απομίμηση ξύλου", "#7a5034", 0.55, 0.05, "κούφωμα"),
    "pvc_white": ("Συνθετικό κούφωμα λευκό", "#f2f2ee", 0.35, 0.00, "κούφωμα"),
})

_add("Γυαλί", {
    "glass_clear": ("Γυαλί διαφανές", "#c8dde3", 0.03, 0.10, "κούφωμα έπιπλο πρόσοψη", 0.25),
    "glass_frosted": ("Γυαλί αμμοβολής", "#dfe6e8", 0.60, 0.00, "κούφωμα έπιπλο", 0.70),
    "glass_tinted_grey": ("Γυαλί φιμέ γκρι", "#4c5558", 0.05, 0.10, "κούφωμα πρόσοψη", 0.45),
    "glass_tinted_bronze": ("Γυαλί φιμέ μπρονζέ", "#6b5440", 0.05, 0.10, "κούφωμα πρόσοψη", 0.45),
    "glass_mirror": ("Καθρέφτης", "#d0d6d8", 0.02, 0.95, "τοίχος έπιπλο"),
})

_add("Υφάσματα & δέρματα", {
    "fabric_linen": ("Λινό φυσικό", "#cbbfa8", 0.96, 0.00, "έπιπλο"),
    "fabric_grey": ("Ύφασμα γκρι", "#7b7d80", 0.96, 0.00, "έπιπλο"),
    "fabric_blue": ("Ύφασμα μπλε", "#3b4f6e", 0.96, 0.00, "έπιπλο"),
    "fabric_velvet_green": ("Βελούδο πράσινο", "#2f4f3e", 0.80, 0.00, "έπιπλο"),
    "leather_brown": ("Δέρμα καφέ", "#6b4329", 0.55, 0.00, "έπιπλο"),
    "leather_black": ("Δέρμα μαύρο", "#1e1c1b", 0.50, 0.00, "έπιπλο"),
    "leather_cognac": ("Δέρμα κονιάκ", "#8e5530", 0.55, 0.00, "έπιπλο"),
    "rattan": ("Ψάθα φυσική", "#c7a874", 0.85, 0.00, "έπιπλο αυλή"),
})

_add("Στέγες & δώματα", {
    "roof_clay": ("Πήλινο κεραμίδι", "#8d4b36", 0.82, 0.00, "στέγη"),
    "roof_membrane_dark": ("Ασφαλτική μεμβράνη σκούρα", "#42474b", 0.90, 0.00, "στέγη"),
    "zinc_seam": ("Ψευδάργυρος με όρθια ραφή", "#808b90", 0.48, 0.72, "στέγη πρόσοψη"),
    "roof_tile_byzantine": ("Κεραμίδι βυζαντινό", "#a35a3c", 0.80, 0.00, "στέγη"),
    "roof_tile_byzantine_aged": ("Κεραμίδι βυζαντινό παλαιωμένο", "#8a5843", 0.86, 0.00, "στέγη"),
    "roof_tile_french": ("Κεραμίδι γαλλικό", "#b0573a", 0.75, 0.00, "στέγη"),
    "roof_membrane_white": ("Λευκή ψυχρή μεμβράνη δώματος", "#e8e8e3", 0.70, 0.00, "στέγη"),
    "roof_membrane_slate": ("Ασφαλτική μεμβράνη με ψηφίδα", "#7c7f80", 0.95, 0.00, "στέγη"),
    "roof_slate": ("Σχιστόπλακες στέγης", "#6f6e68", 0.80, 0.01, "στέγη"),
    "roof_gravel": ("Χαλίκι προστασίας δώματος", "#aaa59a", 0.97, 0.00, "στέγη"),
})

_add("Περιβάλλων χώρος", {
    "garden_paver_grey": ("Πλάκα κήπου τσιμέντου γκρι", "#a19f99", 0.90, 0.00, "αυλή"),
    "garden_paver_beige": ("Πλάκα κήπου μπεζ", "#c9b897", 0.90, 0.00, "αυλή"),
    "garden_cobble_granite": ("Κυβόλιθος γρανίτη", "#7f7d79", 0.85, 0.00, "αυλή"),
    "garden_cobble_concrete": ("Κυβόλιθος τσιμέντου κόκκινος", "#8f5546", 0.90, 0.00, "αυλή"),
    "garden_pebbles": ("Βότσαλο θαλάσσης", "#b3aba0", 0.60, 0.00, "αυλή δάπεδο"),
    "garden_gravel_white": ("Χαλίκι διακοσμητικό λευκό", "#ddd8cd", 0.95, 0.00, "αυλή"),
    "garden_lawn": ("Γκαζόν", "#5f8a3a", 0.95, 0.00, "αυλή"),
    "garden_deck": ("Ξύλινο δάπεδο εξωτερικού χώρου", "#8a6040", 0.75, 0.00, "αυλή"),
})

def material_categories():
    # In the order declared above, not alphabetical: paints first, garden last.
    return tuple(dict.fromkeys(str(spec["category"]) for spec in MATERIAL_PRESETS.values()))


def materials_in_category(category: str):
    category = str(category)
    return tuple(
        (material_id, dict(spec))
        for material_id, spec in MATERIAL_PRESETS.items()
        if spec.get("category") == category
    )


def materials_for_use(use: str):
    """Materials normally applied to ``use`` (one of ``MATERIAL_USES``)."""
    return tuple(
        (material_id, dict(spec))
        for material_id, spec in MATERIAL_PRESETS.items()
        if use in spec.get("use", ())
    )


def material_spec(material_id: str | None) -> Mapping[str, object] | None:
    if not material_id:
        return None
    spec = MATERIAL_PRESETS.get(str(material_id))
    return None if spec is None else dict(spec)
