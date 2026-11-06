# ArchForge

ArchForge is an original desktop design application under active development. Its goal is to combine an accessible architectural workflow, freeform 3D modeling, CAD-style precision, Bio-Spectre / organic construction tools, and mechanical extensibility in one XYZ workspace.

## Current status

This repository is a development codebase, not a finished or saleable release. One authoritative model drives the
plan, 3D, sections, schedules and every export. What is in it today (each with tests):

* **Architecture (BIM):** parametric walls with layered build-ups, doors / windows hosted in walls (typology, glazing,
  shutters, screens, thermal data), slabs, rooms, roofs, stairs, railings, storeys, renovation phases, library objects.
* **2D / CAD:** plans per storey, sections, elevations, dimensions (manual and automatic), free 2D drafting (lines,
  polylines, rectangles, polygons, circles, arcs, text, fills), layers, snapping, typed lengths and angles,
  drawing sheets A4–A0 with title block.
* **Exchange:** IFC4 export and import, DXF export, DXF import (as underlay or as editable drawing), PDF.
* **Structure:** 3D frame solver, EN 1998-1 seismic action with the Greek annex, RC / steel member design, foundations.
* **MEP:** electrical, low voltage / KNX, plumbing, drainage, heating, ventilation, lighting — routed networks and
  take-offs.
* **Energy:** U-values from layers, ΤΟΤΕΕ 20701-2/2021 window tables and U limits, thermal bridges, 3D-conduction
  thermal image of façades, window design solver, sun hours and shading per window and month.
* **Coordination:** live schedules (openings, envelope, rooms, circuits, clashes), clash detection between
  architecture, structure and MEP.
* **Site and organic:** terrain, retaining walls, pools, plants; Bio-Spectre pods and sculpting.

What is missing is listed honestly in `docs/ArchForge_Dynatotites_2026-11.md` (Greek).

## Development rules

A feature is not considered implemented merely because a toolbar button or primitive exists. It must be editable, undoable, persistent across save/reload, validated, interoperable with relevant systems, and covered by tests.

## Run tests

```bash
python -m pytest -q
```

## Launch on Windows

Install the dependencies from `requirements.txt`, then run `START_ARCHFORGE.cmd` or:

```bash
python -m archforge.ui.app
```

## Current test baseline

About 2,500 automated tests pass on Linux (06/11/2026). Run them headless with
`QT_QPA_PLATFORM=offscreen QTWEBENGINE_DISABLE_SANDBOX=1 python -m pytest -q`.
