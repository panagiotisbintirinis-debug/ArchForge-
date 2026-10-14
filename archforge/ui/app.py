from PySide6.QtWidgets import QApplication
from .main_window import MainWindow
from .material_library import install_material_library
from .material_object_integration import install_material_object_integration

# The visual Material Library is a UI layer over the existing authoritative
# material_id / surface_materials system.  The previous dialog remains
# available from the library as the advanced/supplier-code editor.
install_material_library(MainWindow)
# Library objects/cabinets expose their real semantic parts to that browser and
# use a compact lazy-loaded entry point instead of the old always-visible palette.
install_material_object_integration()


def main():
    app=QApplication.instance() or QApplication([])
    app.setApplicationName('ArchForge')
    w=MainWindow();w.show();return app.exec()

if __name__=='__main__':raise SystemExit(main())
