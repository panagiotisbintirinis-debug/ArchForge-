from PySide6.QtWidgets import QApplication
from .main_window import MainWindow
from .material_library import install_material_library
from .material_object_integration import install_material_object_integration
from .library_instance_integration import install_library_instance_model
from .rendering_quality_upgrade import install_rendering_quality_upgrade
from .lighting_system import install_lighting_system

# Upgrade only the visual PBR presentation.  Geometry/model ownership remains
# untouched; the embedded Three.js viewport receives the improved look before
# any MainWindow/PBR viewport instance is created.
install_rendering_quality_upgrade()
# Architectural lighting shares the same PBR scene: day/afternoon/night plus
# project Point/Spot/Strip lights.  Light entities remain ordinary project
# entities, preserving CommandStack/save-load ownership.
install_lighting_system()
# The visual Material Library is a UI layer over the existing authoritative
# material_id / surface_materials system.  The previous dialog remains
# available from the library as the advanced/supplier-code editor.
install_material_library(MainWindow)
# Library objects/cabinets expose their real semantic parts to that browser and
# use a compact lazy-loaded entry point instead of the old always-visible palette.
install_material_object_integration()
# Catalogue assets are immutable definitions.  Every placement is a fresh
# project instance that owns size/material/sculpt overrides and reset defaults.
install_library_instance_model(MainWindow)


def main():
    app=QApplication.instance() or QApplication([])
    app.setApplicationName('ArchForge')
    w=MainWindow();w.show();return app.exec()

if __name__=='__main__':raise SystemExit(main())
