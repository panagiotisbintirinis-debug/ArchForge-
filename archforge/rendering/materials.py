from __future__ import annotations

from typing import Dict, Mapping


# Built-in ArchForge surface library.
#
# These are image-free PBR presets. A material id is stored on the
# authoritative entity, while this catalog provides stable visual defaults.
# Stone, brick, tile and marble presets also carry a procedural ``pattern``
# (joints at real size, see rendering/patterns.py); no image files needed.
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
MATERIAL_USES = ("τοίχος", "πρόσοψη", "δάπεδο", "στέγη", "κούφωμα", "έπιπλο", "πάγκος", "αυλή")

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
    "marble_thassos": ("Λευκό Θάσου", "#f3f2ee", 0.22, 0.00, "δάπεδο τοίχος έπιπλο πάγκος"),
    "marble_dionysos": ("Μάρμαρο Διονύσου", "#e4e3df", 0.28, 0.00, "δάπεδο τοίχος πρόσοψη"),
    "marble_kavala": ("Μάρμαρο Καβάλας", "#e6e1d6", 0.28, 0.00, "δάπεδο τοίχος"),
    "marble_black": ("Μαύρο μάρμαρο", "#1f1f21", 0.20, 0.00, "δάπεδο έπιπλο πάγκος"),
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
    "lacquer_white": ("Λάκα λευκή γυαλιστερή", "#f3f2ee", 0.15, 0.00, "έπιπλο"),
})

# Melamine boards (chipboard with a decor paper) and kitchen worktops: generic
# decors only. The decor CODE a contractor orders by belongs to his supplier,
# so it is typed by the user per surface («Κωδικός», ui/material_codes.py) or
# comes with his own materials (rendering/user_materials.py), never shipped here.
_add("Μελαμίνες", {
    "melamine_white": ("Μελαμίνη λευκή", "#eeede8", 0.45, 0.00, "έπιπλο"),
    "melamine_white_matt": ("Μελαμίνη λευκή ματ", "#ecebe5", 0.70, 0.00, "έπιπλο"),
    "melamine_cream": ("Μελαμίνη κρεμ", "#e6dcc6", 0.55, 0.00, "έπιπλο"),
    "melamine_mocha": ("Μελαμίνη μόκα", "#8c7462", 0.55, 0.00, "έπιπλο"),
    "melamine_light_grey": ("Μελαμίνη γκρι ανοιχτή", "#c4c4c0", 0.55, 0.00, "έπιπλο"),
    "melamine_anthracite": ("Μελαμίνη ανθρακί", "#46494c", 0.55, 0.00, "έπιπλο"),
    "melamine_black": ("Μελαμίνη μαύρη", "#1f1f20", 0.55, 0.00, "έπιπλο"),
    "melamine_oak_natural": ("Μελαμίνη δρυς φυσική", "#b88d5e", 0.62, 0.00, "έπιπλο"),
    "melamine_oak_light": ("Μελαμίνη δρυς ανοιχτή", "#d4b994", 0.62, 0.00, "έπιπλο"),
    "melamine_oak_dark": ("Μελαμίνη δρυς σκούρα", "#6f5137", 0.62, 0.00, "έπιπλο"),
    "melamine_walnut": ("Μελαμίνη καρυδιά", "#6e4b35", 0.60, 0.00, "έπιπλο"),
    "melamine_teak": ("Μελαμίνη τικ", "#9b6b40", 0.60, 0.00, "έπιπλο"),
    "melamine_birch": ("Μελαμίνη σημύδα", "#dcc49e", 0.60, 0.00, "έπιπλο"),
    "melamine_wenge": ("Μελαμίνη βέγκε (σκούρο εξωτικό ξύλο)", "#3d2c22", 0.60, 0.00, "έπιπλο"),
    "melamine_concrete": ("Μελαμίνη τύπου τσιμέντου", "#a3a19c", 0.72, 0.00, "έπιπλο"),
    "melamine_stone_grey": ("Μελαμίνη τύπου πέτρας γκρι", "#8d8a84", 0.70, 0.00, "έπιπλο"),
    "melamine_marble_white": ("Μελαμίνη τύπου μαρμάρου λευκή", "#ebe9e4", 0.45, 0.00, "έπιπλο"),
})

_add("Πάγκοι κουζίνας", {
    "worktop_laminate_white": ("Πάγκος λαμινέιτ λευκός", "#eceae4", 0.50, 0.00, "πάγκος έπιπλο"),
    "worktop_laminate_oak": ("Πάγκος λαμινέιτ ξύλου δρυς", "#b48a5c", 0.55, 0.00, "πάγκος έπιπλο"),
    "worktop_laminate_stone": ("Πάγκος λαμινέιτ πέτρας γκρι", "#8f8c86", 0.55, 0.00, "πάγκος έπιπλο"),
    "worktop_compact_black": ("Πάγκος κόμπακτ μαύρος", "#202022", 0.45, 0.00, "πάγκος έπιπλο"),
    "worktop_compact_white": ("Πάγκος κόμπακτ λευκός", "#efeee9", 0.45, 0.00, "πάγκος έπιπλο"),
    "worktop_quartz_white": ("Πάγκος χαλαζία λευκός", "#f1f0eb", 0.20, 0.00, "πάγκος έπιπλο"),
    "worktop_quartz_grey": ("Πάγκος χαλαζία γκρι", "#9d9c98", 0.22, 0.00, "πάγκος έπιπλο"),
    "worktop_quartz_veined": ("Πάγκος χαλαζία λευκός με νερά", "#efeeea", 0.20, 0.00, "πάγκος έπιπλο"),
    "worktop_granite_black": ("Πάγκος γρανίτη μαύρος", "#232325", 0.18, 0.00, "πάγκος έπιπλο"),
    "worktop_granite_grey": ("Πάγκος γρανίτη γκρι", "#8a8985", 0.22, 0.00, "πάγκος έπιπλο"),
    "worktop_granite_speckled": ("Πάγκος γρανίτη πιτσιλωτός (αλατοπίπερο)", "#b9b7b2", 0.22, 0.00, "πάγκος έπιπλο"),
    "worktop_sintered_white": ("Πάγκος κεραμικός λευκός με νερά", "#f0efeb", 0.25, 0.00, "πάγκος έπιπλο"),
    "worktop_sintered_dark": ("Πάγκος κεραμικός σκούρος με νερά", "#3a3a3b", 0.28, 0.00, "πάγκος έπιπλο"),
    "worktop_solid_oak": ("Πάγκος μασίφ ξύλο δρυς", "#b58450", 0.55, 0.00, "πάγκος έπιπλο"),
    "worktop_solid_walnut": ("Πάγκος μασίφ ξύλο καρυδιάς", "#6a4530", 0.55, 0.00, "πάγκος έπιπλο"),
    "worktop_stainless": ("Πάγκος ανοξείδωτος", "#b7bdc1", 0.30, 0.85, "πάγκος έπιπλο"),
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

# Visible patterns (rendering/patterns.py): joints at real size in metres.
# Stones: a different masonry per stone type; tiles: the usual Greek sizes
# (60x60, 30x60, 20x20, metro 7.5x15, wood-look 20x120, cement-look 60x120).
def _p(kind, w, h, joint, joint_color, variation, offset=0.0, veins=0.0):
    pattern = {"type": kind, "unit_w": w, "unit_h": h, "joint": joint,
               "joint_color": joint_color, "offset": offset, "variation": variation}
    if veins:
        pattern["veins"] = veins
    return pattern


_PATTERNS = {
    # Πέτρα
    "limestone_light": _p("ashlar", 0.40, 0.22, 0.012, "#d9d2c3", 0.16),
    "stone_dark": _p("rubble", 0.30, 0.20, 0.022, "#9a958a", 0.28),
    "stone_pelion": _p("slab", 0.40, 0.065, 0.008, "#3a3934", 0.26),
    "stone_karystos": _p("polygonal", 0.45, 0.45, 0.016, "#bab5a9", 0.22),
    "sandstone": _p("ashlar", 0.50, 0.25, 0.010, "#ddd2bb", 0.15),
    "stone_drywall": _p("rubble", 0.32, 0.18, 0.020, "#38342e", 0.26),
    "stone_cladding": _p("slab", 0.35, 0.075, 0.007, "#4a443b", 0.22),
    "stone_poros": _p("ashlar", 0.50, 0.25, 0.012, "#e6dfcd", 0.10),
    # Τούβλο (running bond)
    "brick_exposed": _p("tiles", 0.25, 0.06, 0.010, "#cdc4b4", 0.12, offset=0.5),
    "brick_light": _p("tiles", 0.25, 0.06, 0.010, "#d8d0c2", 0.10, offset=0.5),
    "brick_dark": _p("tiles", 0.25, 0.06, 0.010, "#a49c90", 0.12, offset=0.5),
    "brick_old": _p("tiles", 0.25, 0.055, 0.012, "#c8bda8", 0.20, offset=0.5),
    # Μάρμαρα (slabs with veins)
    "marble_thassos": _p("tiles", 0.60, 0.60, 0.0015, "#dcdad4", 0.02, veins=0.25),
    "marble_dionysos": _p("tiles", 0.60, 0.60, 0.0015, "#cfcdc7", 0.03, veins=0.6),
    "marble_kavala": _p("tiles", 0.60, 0.60, 0.0015, "#d2ccbf", 0.04, veins=0.5),
    "marble_black": _p("tiles", 0.60, 0.60, 0.0015, "#2c2c2e", 0.04, veins=0.5),
    "marble_grey": _p("tiles", 0.60, 1.20, 0.0015, "#7a7b79", 0.04, veins=0.5),
    "marble_beige": _p("tiles", 0.60, 0.60, 0.0015, "#c9b998", 0.05, veins=0.4),
    # Πλακάκια
    "ceramic_light": _p("tiles", 0.33, 0.33, 0.003, "#a39f95", 0.03),
    "terracotta": _p("tiles", 0.30, 0.30, 0.008, "#cbbfad", 0.12),
    "slate_tile": _p("tiles", 0.60, 0.30, 0.004, "#3b4044", 0.12),
    "porcelain_matt_white": _p("tiles", 0.60, 0.60, 0.003, "#a8a49b", 0.02),
    "porcelain_gloss_white": _p("tiles", 0.60, 0.30, 0.003, "#b3afa7", 0.015),
    "tile_wood_look": _p("planks", 1.20, 0.20, 0.002, "#6b533d", 0.10, offset=1 / 3),
    "tile_cement_look": _p("tiles", 1.20, 0.60, 0.003, "#7b7974", 0.05),
    "tile_mosaic_glass": _p("tiles", 0.025, 0.025, 0.002, "#e6e4de", 0.18),
    "tile_bath_white": _p("tiles", 0.15, 0.075, 0.002, "#b0ada6", 0.025, offset=0.5),
    "tile_hydraulic": _p("tiles", 0.20, 0.20, 0.002, "#cdc9c0", 0.08),
    # Θερμοπρόσοψη & επενδύσεις (ανοιχτός αρμός)
    "facade_ceramic_terracotta": _p("tiles", 0.60, 0.30, 0.008, "#2f2a26", 0.08),
    "facade_ceramic_grey": _p("tiles", 0.60, 0.30, 0.008, "#2f2f2e", 0.06),
    "facade_marble": _p("tiles", 0.60, 0.40, 0.005, "#3a3936", 0.04, veins=0.3),
    # Δάπεδα
    "floor_vinyl_oak": _p("planks", 1.22, 0.18, 0.001, "#5c4532", 0.10, offset=1 / 3),
    "floor_laminate_oak": _p("planks", 1.38, 0.19, 0.001, "#5e4733", 0.10, offset=0.4),
    # Περιβάλλων χώρος
    "garden_paver_grey": _p("tiles", 0.40, 0.40, 0.005, "#7c7a75", 0.06),
    "garden_paver_beige": _p("tiles", 0.40, 0.40, 0.005, "#a39578", 0.06, offset=0.5),
    "garden_cobble_granite": _p("tiles", 0.10, 0.10, 0.008, "#5e5d59", 0.16, offset=0.5),
    "garden_cobble_concrete": _p("tiles", 0.20, 0.10, 0.004, "#6e4a3f", 0.10, offset=0.5),
    # Μελαμίνες: decor paper of one board, grain along the length (2,80 m board)
    "melamine_oak_natural": _p("grain", 2.40, 0.16, 0.0, "#8a6743", 0.06),
    "melamine_oak_light": _p("grain", 2.40, 0.16, 0.0, "#ad906b", 0.05),
    "melamine_oak_dark": _p("grain", 2.40, 0.16, 0.0, "#4d3726", 0.06),
    "melamine_walnut": _p("grain", 2.40, 0.20, 0.0, "#4a3022", 0.07),
    "melamine_teak": _p("grain", 2.40, 0.14, 0.0, "#734c2c", 0.06),
    "melamine_birch": _p("grain", 2.40, 0.18, 0.0, "#bea27b", 0.04),
    "melamine_wenge": _p("grain", 2.40, 0.10, 0.0, "#22180f", 0.06),
    "melamine_concrete": _p("speckle", 0.004, 0.004, 0.0, "#a3a19c", 0.04),
    "melamine_stone_grey": _p("speckle", 0.006, 0.006, 0.0, "#8d8a84", 0.25),
    "melamine_marble_white": _p("tiles", 2.80, 2.07, 0.0, "#ebe9e4", 0.0, veins=0.5),
    # Πάγκοι κουζίνας (one slab, no joint): granite/quartz grains, veins, staves
    "worktop_laminate_oak": _p("grain", 2.40, 0.16, 0.0, "#86643f", 0.06),
    "worktop_laminate_stone": _p("speckle", 0.005, 0.005, 0.0, "#8f8c86", 0.30),
    "worktop_quartz_white": _p("speckle", 0.003, 0.003, 0.0, "#f1f0eb", 0.10),
    "worktop_quartz_grey": _p("speckle", 0.003, 0.003, 0.0, "#9d9c98", 0.15),
    "worktop_quartz_veined": _p("tiles", 3.00, 1.40, 0.0, "#efeeea", 0.0, veins=0.45),
    "worktop_granite_black": _p("speckle", 0.004, 0.004, 0.0, "#232325", 0.45),
    "worktop_granite_grey": _p("speckle", 0.006, 0.006, 0.0, "#8a8985", 0.60),
    "worktop_granite_speckled": _p("speckle", 0.007, 0.007, 0.0, "#b9b7b2", 0.85),
    "worktop_sintered_white": _p("tiles", 3.00, 1.40, 0.0, "#f0efeb", 0.0, veins=0.6),
    "worktop_sintered_dark": _p("tiles", 3.00, 1.40, 0.0, "#3a3a3b", 0.0, veins=0.6),
    "worktop_solid_oak": _p("planks", 1.00, 0.04, 0.0005, "#7d5a36", 0.12, offset=0.37),
    "worktop_solid_walnut": _p("planks", 1.00, 0.04, 0.0005, "#3f2a1d", 0.12, offset=0.37),
}
for _material_id, _pattern in _PATTERNS.items():
    MATERIAL_PRESETS[_material_id]["pattern"] = _pattern

# Categories whose every material must show a pattern.
PATTERNED_CATEGORIES = ("Πέτρα", "Πλακάκια", "Τούβλο", "Μάρμαρα")


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


def material_spec(material_id: str | None, doc=None) -> Mapping[str, object] | None:
    """Preset, or the user's own material (``user_…``: the project's copy first)."""
    if not material_id:
        return None
    spec = MATERIAL_PRESETS.get(str(material_id))
    if spec is None:
        from archforge.rendering.user_materials import lookup
        spec = lookup(str(material_id), doc)
    if spec is None:
        return None
    out = dict(spec)
    if "pattern" in out:
        out["pattern"] = dict(out["pattern"])
    return out


def material_name(material_id, doc=None, default: str = "") -> str:
    spec = material_spec(material_id, doc)
    return str(spec["name"]) if spec else (default or str(material_id or ""))


USER_MARK = "★"
USER_CATEGORY = "★ Δικά μου υλικά"


def picker_categories(doc=None):
    """Categories of the materials dialog: the user's own first (when any), then the presets,
    then categories that only user materials use."""
    from archforge.rendering.user_materials import user_materials
    mine = user_materials(doc)
    cats = list(material_categories())
    extra = [str(s["category"]) for s in mine.values() if str(s["category"]) not in cats]
    return ((USER_CATEGORY,) if mine else ()) + tuple(cats) + tuple(dict.fromkeys(extra))


def picker_materials(category: str, doc=None):
    """``[(id, spec)]`` of a dialog category; user materials carry ``spec["user"]``."""
    from archforge.rendering.user_materials import user_materials
    mine = user_materials(doc)
    if category == USER_CATEGORY:
        return tuple(sorted(mine.items(), key=lambda kv: str(kv[1]["name"])))
    presets = materials_in_category(category)
    return presets + tuple((k, v) for k, v in sorted(mine.items(), key=lambda kv: str(kv[1]["name"]))
                           if v.get("category") == category)
