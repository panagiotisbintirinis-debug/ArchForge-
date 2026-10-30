"""The shared table of the translator: an ArchForge kind → its class in IFC and its layer in DXF, plus the storey of
an element.  Change a target here and every writer follows.

IFC classes are IFC4 (ISO 16739-1:2018); DXF layers follow the US National CAD Standard / AIA layer names
(A-WALL, S-COLS …) that every CAD office recognises.
"""
from __future__ import annotations

# kind: (IFC class, IFC PredefinedType or None, DXF layer, Greek name)
KINDS = {
    "wall": ("IfcWall", "STANDARD", "A-WALL", "Τοίχος"),
    "door": ("IfcDoor", "DOOR", "A-DOOR", "Πόρτα"),
    "window": ("IfcWindow", "WINDOW", "A-GLAZ", "Παράθυρο"),
    "opening": ("IfcOpeningElement", "OPENING", "A-DOOR", "Άνοιγμα"),
    "room_floor": ("IfcSlab", "FLOOR", "A-FLOR", "Πλάκα δαπέδου"),
    "floor": ("IfcSlab", "FLOOR", "A-FLOR", "Πλάκα"),
    "room_roof": ("IfcSlab", "ROOF", "A-ROOF", "Πλάκα δώματος"),
    "room_ceiling": ("IfcCovering", "CEILING", "A-CLNG", "Οροφή"),
    "drywall_ceiling": ("IfcCovering", "CEILING", "A-CLNG", "Ψευδοροφή"),
    "room_foundation": ("IfcFooting", "STRIP_FOOTING", "S-FNDN", "Θεμελίωση"),
    "slab_opening": ("IfcOpeningElement", "OPENING", "A-FLOR-OPNG", "Οπή πλάκας"),
    "pitched_roof": ("IfcRoof", "GABLE_ROOF", "A-ROOF", "Στέγη"),
    "ceiling_joists": ("IfcMember", "STUD", "S-FRAM", "Δοκίδες οροφής"),
    "structural_column": ("IfcColumn", "COLUMN", "S-COLS", "Κολόνα"),
    "structural_beam": ("IfcBeam", "BEAM", "S-BEAM", "Δοκός"),
    "footing": ("IfcFooting", "PAD_FOOTING", "S-FNDN", "Πέδιλο"),
    "stair": ("IfcStair", None, "A-FLOR-STRS", "Σκάλα"),
    "ramp": ("IfcRamp", None, "A-FLOR-STRS", "Ράμπα"),
    "railing": ("IfcRailing", "BALUSTRADE", "A-FLOR-HRAL", "Κάγκελο"),
    "cabinet": ("IfcFurniture", None, "A-FURN", "Ντουλάπι"),
    "kitchen_part": ("IfcFurniture", None, "A-FURN", "Κουζίνα"),
    "library_object": ("IfcFurniture", None, "A-FURN", "Αντικείμενο"),
    "plumbing_point": ("IfcSanitaryTerminal", None, "P-FIXT", "Υδραυλικό σημείο"),
    "drainage_point": ("IfcWasteTerminal", None, "P-SANR", "Αποχέτευση"),
    "heating_point": ("IfcSpaceHeater", None, "M-HOTW", "Θέρμανση"),
    "ventilation_point": ("IfcAirTerminal", None, "M-EXHS", "Αερισμός"),
    "electrical_point": ("IfcElectricAppliance", None, "E-POWR", "Ηλεκτρολογικό"),
    "pool": ("IfcBuildingElementProxy", None, "L-SITE-POOL", "Πισίνα"),
    "terrain": ("IfcGeographicElement", "TERRAIN", "C-TOPO", "Έδαφος"),
    "plant": ("IfcGeographicElement", "USERDEFINED", "L-PLNT", "Φυτό"),
    "site_path": ("IfcBuildingElementProxy", None, "L-SITE", "Μονοπάτι"),
    "pergola": ("IfcBuildingElementProxy", None, "A-ROOF-PERG", "Πέργκολα"),
    "dome": ("IfcRoof", "DOME_ROOF", "A-ROOF", "Θόλος"),
    "pod": ("IfcBuildingElementProxy", None, "A-WALL-ORGN", "Pod"),
}
# Electrical points by what they are (mep/electrical.POINT_TYPES).
ELECTRICAL = {
    "panel": ("IfcElectricDistributionBoard", "DISTRIBUTIONBOARD", "E-POWR-PANL"),
    "light": ("IfcLightFixture", "DIRECTIONSOURCE", "E-LITE"), "spot": ("IfcLightFixture", "DIRECTIONSOURCE", "E-LITE"),
    "downlight": ("IfcLightFixture", "DIRECTIONSOURCE", "E-LITE"),
    "wall_washer": ("IfcLightFixture", "DIRECTIONSOURCE", "E-LITE"),
    "led_strip": ("IfcLightFixture", "DIRECTIONSOURCE", "E-LITE"),
    "wall_light": ("IfcLightFixture", "DIRECTIONSOURCE", "E-LITE"),
    "switch": ("IfcSwitchingDevice", "TOGGLESWITCH", "E-POWR-SWCH"),
    "dimmer": ("IfcSwitchingDevice", "DIMMERSWITCH", "E-POWR-SWCH"),
    "socket": ("IfcOutlet", "POWEROUTLET", "E-POWR"), "kitchen_socket": ("IfcOutlet", "POWEROUTLET", "E-POWR"),
    "data_outlet": ("IfcOutlet", "DATAOUTLET", "T-DATA"), "tv_outlet": ("IfcOutlet", "AUDIOVISUALOUTLET", "T-DATA"),
    "network_rack": ("IfcCommunicationsAppliance", "NETWORKBRIDGE", "T-DATA"),
    "wifi_ap": ("IfcCommunicationsAppliance", "NETWORKAPPLIANCE", "T-DATA"),
}
# Not things that are built: never exported as elements.
SKIP = {"camera", "auto_dimensions", "dimension", "section_line", "elevation_line", "underlay", "light_probe",
        "mechanical_joint", "organic_junction", "organic_opening_patch", "structural_support", "structural_load",
        "door", "window", "opening"}            # openings are written with their wall
PROXY = ("IfcBuildingElementProxy", None, "A-MISC", "Στοιχείο")


def target(entity):
    """(IFC class, PredefinedType, DXF layer, Greek name) of an entity."""
    if entity.kind == "electrical_point":
        ifc, pre, layer = ELECTRICAL.get(str(entity.params.get("point_type")), ("IfcElectricAppliance", None, "E-POWR"))
        return ifc, pre, layer, KINDS["electrical_point"][3]
    return KINDS.get(entity.kind, PROXY)


# Plan primitive roles (core/plan_scene.py) → DXF layer; the first matching prefix wins.
PLAN_LAYERS = (
    ("wall-layer-fill", "A-WALL-PATT"), ("wall", "A-WALL"), ("model", "A-WALL-CNTR"), ("opening-symbol", "A-DOOR"), ("opening", "A-DOOR"),
    ("dimension-label", "A-ANNO-DIMS"), ("dimension", "A-ANNO-DIMS"),
    ("derived-room-label", "A-AREA-IDEN"), ("derived-room", "A-AREA"), ("room-", "A-FLOR"),
    ("structural-column", "S-COLS"), ("structural-beam", "S-BEAM"), ("joist", "S-FRAM"), ("joists-area", "S-FRAM"),
    ("stair", "A-FLOR-STRS"), ("railing", "A-FLOR-HRAL"), ("roof", "A-ROOF"),
    ("cabinet", "A-FURN"), ("worktop", "A-FURN"), ("hob", "A-FURN"), ("sink", "P-FIXT"), ("hood", "A-FURN"),
    ("library", "A-FURN"), ("plant", "L-PLNT"), ("pool", "L-SITE-POOL"), ("terrain", "C-TOPO"),
    ("heat", "M-HOTW"), ("elec", "E-POWR"), ("light", "E-LITE"), ("plumb", "P-FIXT"), ("drain", "P-SANR"),
    ("vent", "M-EXHS"), ("underlay", None), ("floor-underlay", None), ("camera", None), ("lower-storey", None), ("handle", None),
)


# DXF hatch pattern of a wall layer by its material's ``hatch`` key (construction/building_materials.py):
# DESIGN_DEFAULT, names from the standard acad/ISO pattern set that ezdxf ships.
LAYER_PATTERNS = {"plaster": ("AR-SAND", 0.02), "gypsum": ("DOTS", 0.02), "brick": ("ANSI31", 0.02),
                  "stone": ("ANSI33", 0.03), "concrete": ("AR-CONC", 0.005), "masonry": ("ANSI32", 0.02),
                  "insulation_soft": ("INSUL", 0.01), "insulation_rigid": ("ANSI37", 0.02),
                  "wood_cement": ("ANSI38", 0.02)}


def plan_layer(role):
    """DXF layer of a plan primitive role, or None (not part of the drawing: cameras, underlays …)."""
    role = str(role)
    for prefix, layer in PLAN_LAYERS:
        if role.startswith(prefix):
            return layer
    return "A-MISC"


def storeys(doc):
    """[(name, z)] from the lowest up; a project with no storeys has one at 0."""
    out = sorted(((str(n), float(z)) for n, z in doc.levels.items()), key=lambda s: s[1])
    return out or [("Ground", 0.0)]


def storey_of(doc, z, tolerance=0.05):
    """The storey an element starting at height ``z`` belongs to: the highest one at or below it."""
    levels = storeys(doc)
    below = [s for s in levels if s[1] <= float(z) + tolerance]
    return below[-1] if below else levels[0]


def storey_label(name):
    from archforge.output.pdf import level_name
    return level_name(name)
