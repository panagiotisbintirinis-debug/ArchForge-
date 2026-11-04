"""Εγκαταστάσεις › Θέρμανση › «Θερμοκρασίες σχεδιασμού…»: οι τιμές του έργου, όλες αλλάζουν (mep/design_climate.py).

Επάνω η έτοιμη επιλογή με την πηγή της· από κάτω κάθε τιμή σε πεδίο. Αλλάζοντας τη θερμοκρασία χειμώνα με το χέρι η
επιλογή γίνεται «Δική μου τιμή». «Εφαρμογή» = μία αναίρεση. Η ενδεικτική ισχύς θέρμανσης φαίνεται ζωντανά από κάτω.
"""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QVBoxLayout)

from archforge.mep import design_climate as C

TITLE = "Θερμοκρασίες σχεδιασμού"


class DesignClimateDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        doc = window.doc
        self.setWindowTitle(TITLE)
        root = QVBoxLayout(self)
        intro = QLabel("Οι τιμές του έργου για την ενδεικτική ισχύ θέρμανσης. Όλες αλλάζουν· η επιλογή και η πηγή "
                       "γράφονται δίπλα στο αποτέλεσμα. Δεν είναι μελέτη θέρμανσης (EN 12831-1 / ΚΕΝΑΚ).")
        intro.setWordWrap(True)
        root.addWidget(intro)
        form = QFormLayout()
        self.preset = QComboBox(self)
        for key, p in C.PRESETS.items():
            self.preset.addItem(f"{p['label']} · {p['heat_theta_ext_winter']:g} °C".replace(".", ","), key)
        self.preset.addItem(C.CUSTOM_LABEL, C.CUSTOM)
        form.addRow("Περιοχή / επιλογή", self.preset)
        self.source = QLabel(self); self.source.setWordWrap(True)
        form.addRow("Πηγή", self.source)
        values = C.values(doc)
        self.fields = {}
        for key, (_default, unit, label, _src) in C.FIELDS.items():
            box = QDoubleSpinBox(self)
            box.setRange(0.0 if key == "heat_air_changes" else -40.0, 10.0 if key == "heat_air_changes" else 50.0)
            box.setDecimals(1 if unit == "°C" else 2)
            box.setSingleStep(0.5 if unit == "°C" else 0.1)
            box.setSuffix(f" {unit}")
            box.setValue(values[key])
            form.addRow(label, box)
            self.fields[key] = box
        root.addLayout(form)
        self.power = QLabel(self); self.power.setWordWrap(True)
        root.addWidget(self.power)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Close, self)
        buttons.button(QDialogButtonBox.StandardButton.Apply).setText("Εφαρμογή")
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Κλείσιμο")
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._syncing = False
        self.preset.setCurrentIndex(max(0, self.preset.findData(C.preset_of(doc))))
        self.preset.currentIndexChanged.connect(self._preset_changed)
        self.fields["heat_theta_ext_winter"].valueChanged.connect(self._winter_changed)
        self._show_source()

    def _preset_changed(self):
        key = self.preset.currentData()
        if key in C.PRESETS:
            self._syncing = True
            self.fields["heat_theta_ext_winter"].setValue(C.PRESETS[key]["heat_theta_ext_winter"])
            self._syncing = False
        self._show_source()

    def _winter_changed(self, value):
        if self._syncing:
            return
        key = self.preset.currentData()
        if key in C.PRESETS and abs(C.PRESETS[key]["heat_theta_ext_winter"] - value) > 1e-9:
            self.preset.blockSignals(True)
            self.preset.setCurrentIndex(self.preset.findData(C.CUSTOM))
            self.preset.blockSignals(False)
            self._show_source()

    def _show_source(self):
        key = self.preset.currentData()
        self.source.setText(C.PRESETS[key]["source"] if key in C.PRESETS else "δική σας τιμή για το έργο")
        from archforge.mep.heat_load import heat_load
        r = heat_load(self.window.doc)
        self.power.setText(f"Με τις αποθηκευμένες τιμές: ενδεικτική ισχύς ≈ {r['kw']:.1f} kW (ΔT {r['delta_t']:g} K)."
                           .replace(".", ",", 1))

    def changes(self):
        out = {key: box.value() for key, box in self.fields.items()}
        key = self.preset.currentData()
        out["preset"] = key if key in C.PRESETS else C.CUSTOM
        return out

    def apply(self):
        self.window.stack.execute(C.set_command(self.window.doc, self.changes()))
        self._show_source()
        self.window.statusBar().showMessage(f"{TITLE}: εφαρμόστηκαν · Ctrl+Z = αναίρεση", 6000)


def show(window):
    dialog = DesignClimateDialog(window)
    dialog.exec()
    return dialog
