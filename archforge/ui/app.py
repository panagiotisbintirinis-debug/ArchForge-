from PySide6.QtWidgets import QApplication
from .main_window import MainWindow
from .material_browser import install_material_browser

# Keep the proven ArchForge window authoritative and replace only the material
# browsing surface on this feature branch.
install_material_browser(MainWindow)


def main():
    app=QApplication.instance() or QApplication([])
    app.setApplicationName('ArchForge')
    w=MainWindow();w.show();return app.exec()

if __name__=='__main__':raise SystemExit(main())
