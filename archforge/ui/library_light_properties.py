"""Controls of a luminous library instance: one object, ordinary undoable edits."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QSlider, QLabel

KEYS = {'light_level', 'light_enabled', 'light_shadows', 'light_kelvin'}


def add_rows(window, entity):
    if not entity.params.get('light_sources'):
        return
    p, eid = entity.params, entity.id
    for key, label, fallback in [('light_enabled','Αναμμένο',1), ('light_shadows','Σκιές φωτιστικού',1)]:
        box = QCheckBox(); box.setChecked(bool(p.get(key,fallback)))
        box.toggled.connect(lambda on,k=key: window._set_entity_choice(eid,k,float(on)))
        window.form.addRow(label,box)
    slider=QSlider(Qt.Orientation.Horizontal);slider.setRange(0,100)
    slider.setValue(round(100*float(p.get('light_level',1))))
    text=QLabel(f'{slider.value()} %')
    slider.valueChanged.connect(lambda v:text.setText(f'{v} %'))
    slider.sliderReleased.connect(lambda:window._set_entity_choice(eid,'light_level',slider.value()/100))
    window.form.addRow('Φωτεινότητα',slider);window.form.addRow('',text)
    color=QComboBox();color.addItem('Χρώμα από το μοντέλο',0.0)
    for value in sorted({2700.,3000.,4000.,6500.} | ({float(p['light_kelvin'])} if p.get('light_kelvin') else set())):
        color.addItem(f'{value:g} K',value)
    color.setCurrentIndex(max(0,color.findData(float(p.get('light_kelvin',0)))))
    color.activated.connect(lambda _:window._set_entity_choice(eid,'light_kelvin',color.currentData()))
    window.form.addRow('Χρώμα φωτός',color)
