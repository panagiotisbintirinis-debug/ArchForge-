from PySide6.QtWidgets import QApplication
from .main_window import MainWindow
from .pbr_viewport import PBRViewport
from .material_library import install_material_library
from .material_object_integration import install_material_object_integration
from .library_instance_integration import install_library_instance_model
from .rendering_quality_upgrade import install_rendering_quality_upgrade
from .plumbing_display import install_plumbing_display
from .plumbing_tab import install_on_class as install_plumbing_tab
from .plumbing_system_control import install_on_class as install_plumbing_system_control
from .plumbing_technical_safety import install_safe_connectivity_overlay
from .mep_3d_visibility import install as install_mep_3d_visibility
from .plumbing_manifold_3d import install as install_plumbing_manifold_3d
from .plumbing_manifold_2d import install as install_plumbing_manifold_2d
from .plumbing_connection_details import install as install_plumbing_connection_details
from .plumbing_component_drag import install as install_plumbing_component_drag
from .plumbing_economy_tab import install as install_plumbing_economy_tab

# Upgrade only the visual PBR presentation. Geometry/model ownership remains
# untouched; the embedded Three.js viewport receives the improved look before
# any MainWindow/PBR viewport instance is created.
install_rendering_quality_upgrade()
# The visual Material Library is a UI layer over the existing authoritative
# material_id / surface_materials system.
install_material_library(MainWindow)
install_material_object_integration()
install_library_instance_model(MainWindow)
# Extend the one existing LibraryCarry path with plumbing components.  A dropped
# fitting is an authoritative plumbing_accessory and must snap to a valid host.
install_plumbing_component_drag()
# The Layers workspace is authoritative for 3D MEP visibility. Prevent the
# legacy PBR hidden-layer set from silently overriding the H/M environment.
install_mep_3d_visibility(PBRViewport)
# Add a separate, identifiable manifold/cabinet presentation object to PBR.
install_plumbing_manifold_3d()
# Plumbing plan presentation is intentionally pipe-only; technical details live
# in a separate central report tab.
install_plumbing_display(MainWindow)
# Extend the report classes before MainWindow instances create the plumbing tab.
install_plumbing_connection_details()
install_plumbing_economy_tab()
install_plumbing_manifold_2d()
install_plumbing_tab(MainWindow)
# Remove the scene-bounds regression from connectivity markers before any
# technical-plan instance is created, then add the visible live system selector.
install_safe_connectivity_overlay()
install_plumbing_system_control(MainWindow)


def main():
    app=QApplication.instance() or QApplication([])
    app.setApplicationName('ArchForge')
    w=MainWindow();w.show();return app.exec()

if __name__=='__main__':raise SystemExit(main())
