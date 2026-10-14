from PySide6.QtWidgets import QApplication
from .main_window import MainWindow
from .material_library import install_material_library

# The visual Material Library is a UI layer over the existing authoritative
# material_id / surface_materials system.  The previous dialog remains
# available from the library as the advanced/supplier-code editor.
install_material_library(MainWindow)


def main():
    app=QApplication.instance() or QApplication([])
    app.setApplicationName('ArchForge')
    w=MainWindow();w.show();return app.exec()

if __name__=='__main__':raise SystemExit(main())
