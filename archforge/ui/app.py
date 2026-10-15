from PySide6.QtWidgets import QApplication
from .main_window import MainWindow
from .material_library import install_material_library
from .material_object_integration import install_material_object_integration
from .library_instance_integration import install_library_instance_model
from .rendering_quality_upgrade import install_rendering_quality_upgrade
from .plumbing_display import install_plumbing_display
from .plumbing_tab import install_on_class as install_plumbing_tab

# Upgrade only the visual PBR presentation. Geometry/model ownership remains
# untouched; the embedded Three.js viewport receives the improved look before
# any MainWindow/PBR viewport instance is created.
install_rendering_quality_upgrade()
# The visual Material Library is a UI layer over the existing authoritative
# material_id / surface_materials system.
install_material_library(MainWindow)
install_material_object_integration()
install_library_instance_model(MainWindow)
# Plumbing plan presentation is intentionally pipe-only; technical details live
# in a separate central report tab.
install_plumbing_display(MainWindow)
install_plumbing_tab(MainWindow)


def main():
    app=QApplication.instance() or QApplication([])
    app.setApplicationName('ArchForge')
    w=MainWindow();w.show();return app.exec()

if __name__=='__main__':raise SystemExit(main())
