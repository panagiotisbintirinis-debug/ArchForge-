# ArchForge

ArchForge is an original desktop design application under active development. Its goal is to combine an accessible architectural workflow, freeform 3D modeling, CAD-style precision, Bio-Spectre / organic construction tools, and mechanical extensibility in one XYZ workspace.

## Current status

This repository is a development codebase, not a finished or saleable release. The current production core includes semantic entities, work planes, command-based undo/redo, snapping, transactional draw/move/stretch/rotate interactions, incremental viewport synchronization, orthographic frame generation, floor/room semantics, and migrated Bio-Spectre pod/junction geometry rules.

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

53 automated tests pass in the current development snapshot.
