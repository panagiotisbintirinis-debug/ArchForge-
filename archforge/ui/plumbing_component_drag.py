"""Visual drag/drop plumbing components through the existing LibraryCarry path."""
from __future__ import annotations


def install() -> None:
    from archforge.ui import library_drag
    from archforge.ui.library_drag import LibraryCarry
    from archforge.core.commands import AddEntity
    from archforge.core.model import Entity
    from archforge.mep.plumbing_components import (
        accessory_params, component_actions, component_label, snap_target,
    )

    if getattr(LibraryCarry, "_archforge_plumbing_components_installed", False):
        return

    original_droppable = library_drag.droppable
    library_drag.droppable = lambda action: bool(action) and (
        action[0] == "plumbing_component" or original_droppable(action)
    )

    original_init = LibraryCarry.__init__
    original_name = LibraryCarry.name.fget
    original_ghost = LibraryCarry._ghost
    original_label = LibraryCarry.label
    original_commit = LibraryCarry._commit

    def init(self, window, action):
        original_init(self, window, action)
        self._plumbing_target = None

    def name(self):
        if self.kind == "plumbing_component":
            return component_label(self.action[1])
        return original_name(self)

    def ghost(self, x, y):
        if self.kind != "plumbing_component":
            return original_ghost(self, x, y)
        target = snap_target(self.doc, str(self.action[1]), float(x), float(y))
        self._plumbing_target = target
        if target is None:
            self.message = "άφησέ το πάνω σε έγκυρο υδραυλικό σημείο / σωλήνα / συλλέκτη"
            return {"cross": (float(x), float(y)), "ok": False}
        self.message = ""
        return {
            "cross": (float(target["x"]), float(target["y"])),
            "ok": True,
            "snapped": str(target["host_kind"]),
        }

    def label(self):
        if self.kind != "plumbing_component":
            return original_label(self)
        if self.message:
            return f"{self.name}: {self.message}"
        host = str((self._plumbing_target or {}).get("host_kind", ""))
        where = {"point": "σημείο σύνδεσης", "pipe": "σωλήνα", "manifold": "συλλέκτη"}.get(host, host)
        return f"{self.name} → {where} — άφησε για τοποθέτηση · Esc ακύρωση"

    def commit(self, x, y, target):
        if self.kind != "plumbing_component":
            return original_commit(self, x, y, target)
        snapped = snap_target(self.doc, str(self.action[1]), float(x), float(y))
        if snapped is None:
            raise ValueError("δεν υπάρχει έγκυρο σημείο σύνδεσης κοντά")
        params = accessory_params(str(self.action[1]), snapped)
        entity = Entity("plumbing_accessory", params, name=self.name)
        self.window.stack.execute(AddEntity(entity))
        return entity.id

    LibraryCarry.__init__ = init
    LibraryCarry.name = property(name)
    LibraryCarry._ghost = ghost
    LibraryCarry.label = label
    LibraryCarry._commit = commit
    LibraryCarry._archforge_plumbing_components_installed = True

    # Add a first-class «Εξαρτήματα» subgroup under Η/Μ → Υδραυλικά without
    # replacing the existing point tools or imported asset library.
    from archforge.ui.main_window import MainWindow
    original_outline = MainWindow._library_outline

    def outline(self):
        themes = original_outline(self)
        rows = component_actions()
        if not rows:
            return themes
        out = []
        inserted = False
        for theme, subs in themes:
            if theme == "Η/Μ":
                new_subs = []
                for sub, items in subs:
                    if sub == "Υδραυλικά":
                        new_subs.append((sub, items))
                        new_subs.append(("Υδραυλικά — Εξαρτήματα", rows))
                        inserted = True
                    else:
                        new_subs.append((sub, items))
                out.append((theme, new_subs))
            else:
                out.append((theme, subs))
        if not inserted:
            out.append(("Η/Μ", [("Υδραυλικά — Εξαρτήματα", rows)]))
        return out

    MainWindow._library_outline = outline
