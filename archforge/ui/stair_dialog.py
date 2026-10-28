"""«Σκάλα» — one window for a placed stair (owner 14/10: «κάνε ένα παρόμοιο μενού»).

Sections on the left (Γενικά · Κατασκευή · Κάγκελο · Υλικά), the fields in the middle and a live
drawing on the right (plan symbol over a section of the flights).  «Εντάξει» applies everything as
one undo through the shared commands (UpdateEntity + the stair's railings); nothing changes before.
Sizes are shown in cm with the precision a builder uses, not four decimals.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QPolygonF
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                               QHBoxLayout, QLabel, QListWidget, QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

from archforge.architecture import stair_options as SO
from archforge.architecture.railings import STAIR_HEIGHT, STAIR_RAILING_CHOICES, TYPES as RAILING_TYPES
from archforge.architecture.stairs import candidate_from_params

LAYOUTS = {'straight': 'Ευθεία', 'l': 'Γ (L)', 'u': 'Π (U)', 'spiral': 'Σπιράλ'}
SECTIONS = ('Γενικά', 'Κατασκευή', 'Κάγκελο', 'Υλικά')


def blondel(riser, tread):
    """2·ρίχτι + πάτημα (m): comfortable 0.60–0.65 (κανόνας Blondel — πρακτική, προς έλεγχο)."""
    return 2 * riser + tread


class StairPreview(QWidget):
    """Plan symbol over a section of the flights, for the params being edited."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.params = None
        self.sides = ()
        self.setMinimumSize(300, 420)

    def set_params(self, params, sides=()):
        self.params = dict(params)
        self.sides = tuple(sides)
        self.update()

    def paintEvent(self, _event):
        if not self.params:
            return
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillRect(self.rect(), QColor('white'))
        w, h = self.width(), self.height()
        try:
            c = candidate_from_params(self.params)
        except Exception as exc:                      # Α3: the reason in the preview, not a blank picture
            p.setPen(QColor(170, 40, 40))
            p.drawText(QRectF(12, 12, w - 24, h - 24), int(Qt.AlignmentFlag.AlignCenter) | int(Qt.TextFlag.TextWordWrap),
                       f'Η σκάλα δεν σχεδιάζεται με αυτές τις τιμές:\n{exc}')
            return
        self._plan(p, c, QRectF(12, 24, w - 24, h * 0.45 - 30))
        self._section(p, c, QRectF(12, h * 0.45 + 24, w - 24, h * 0.55 - 36))
        p.setPen(QColor(90, 100, 115))
        p.drawText(QPointF(12, 16), 'Κάτοψη')
        p.drawText(QPointF(12, h * 0.45 + 16), 'Τομή (ξεδιπλωμένη κατά τη γραμμή βάδισης)')
        p.end()

    def _plan(self, p, c, box):
        from archforge.architecture.stairs import stair_footprint, stair_plan_symbol
        lines, _labels = stair_plan_symbol(c, 'lower')
        fp = stair_footprint(c)
        xs = [q[0] for q in fp]; ys = [q[1] for q in fp]
        s = min(box.width() / max(1e-6, max(xs) - min(xs)), box.height() / max(1e-6, max(ys) - min(ys))) * 0.9
        ox = box.center().x() - (min(xs) + max(xs)) / 2 * s
        oy = box.center().y() + (min(ys) + max(ys)) / 2 * s

        def at(q):
            return QPointF(ox + q[0] * s, oy - q[1] * s)
        for style, pts in lines:
            pen = QPen(QColor(40, 45, 55)); pen.setWidthF(1.0)
            if style in ('hidden', 'walk-hidden'):
                pen.setStyle(Qt.PenStyle.DashLine)
            if style in ('walk', 'walk-hidden', 'arrow'):
                pen.setColor(QColor(30, 100, 200))
            p.setPen(pen)
            for a, b in zip(pts, pts[1:]):
                p.drawLine(at(a), at(b))
        from archforge.architecture.railings import stair_railing_lines
        pen = QPen(QColor(200, 90, 20)); pen.setWidthF(2.0); p.setPen(pen)
        for side in self.sides:
            try:
                lines = stair_railing_lines(self.params, side)
            except ValueError:
                continue
            for line in lines:
                for a, b in zip(line, line[1:]):
                    p.drawLine(at(a), at(b))

    def _section(self, p, c, box):
        """Steps unfolded along the walking line, drawn the way the chosen structure is built."""
        q = self.params
        kind = SO.structure(q)
        n, t, r = c.tread_count, c.tread_depth, c.riser_height
        landing = c.landing_depth if c.layout in ('l', 'u') else 0.0
        first = max(1, n // 2) if landing else n
        run = n * t + landing
        rise = c.upper_z - c.lower_z
        s = min(box.width() / max(run, 1e-6), box.height() / max(rise + 0.3, 1e-6)) * 0.92
        x0, z0 = box.left() + 4, box.bottom() - 4

        def at(x, z):
            return QPointF(x0 + x * s, z0 - z * s)
        ink = QPen(QColor(40, 45, 55)); ink.setWidthF(1.0)
        p.setPen(QPen(QColor(150, 150, 150), 1)); p.drawLine(at(-0.2, 0), at(run + 0.2, 0))
        wood = QBrush(QColor(196, 150, 100)); stone = QBrush(QColor(225, 222, 214)); conc = QBrush(QColor(200, 200, 200))
        steel = QBrush(QColor(60, 64, 70))
        tread_brush = stone if kind in ('solid', 'slab') else wood

        def step_x(i):
            return i * t + (landing if i >= first else 0.0)
        p.setPen(ink)
        for i in range(n):
            x, top = step_x(i), (i + 1) * r
            if kind == 'solid':
                p.setBrush(conc); p.drawRect(QRectF(at(x, top), at(x + t, 0)).normalized())
            elif kind == 'slab':
                p.setBrush(stone); p.drawRect(QRectF(at(x, top), at(x + t, top - r)).normalized())
            else:
                th = {'timber': SO.TREAD_TIMBER, 'steel': SO.TREAD_STEEL}.get(kind, SO.TREAD_CANTILEVER)
                p.setBrush(tread_brush); p.drawRect(QRectF(at(x, top), at(x + t + 0.03, top - th)).normalized())
        if landing:
            lz = first * r; lx = step_x(first - 1) + t
            p.setBrush(conc if kind in ('solid', 'slab') else tread_brush)
            p.drawRect(QRectF(at(lx, lz), at(lx + landing, 0 if kind == 'solid' else lz - 0.12)).normalized())
        if kind == 'slab':
            pitch = r / t
            band = SO.SLAB * math.sqrt(1 + pitch * pitch)
            for a, b, k0 in ((0.0, first * t, 0), (first * t + landing, run, first)):
                if b - a < 1e-6:
                    continue
                base = k0 * r
                poly = QPolygonF([at(a, base), at(b, base + (b - a) * pitch), at(b, max(base, base + (b - a) * pitch - band)),
                                  at(a, max(0.0, base - band) if k0 == 0 else base - band)])
                p.setBrush(conc); p.drawPolygon(poly)
        elif kind in ('timber', 'steel') and q.get('stringers', 'sides') != 'none':
            pitch = r / t
            p.setBrush(wood if kind == 'timber' else steel)
            for a, b, k0 in ((0.0, first * t, 0), (first * t + landing, run, first)):
                if b - a < 1e-6:
                    continue
                base = k0 * r; depth = SO.STRINGER_DEPTH[kind]
                top_a, top_b = base + r + 0.02, base + (b - a) * pitch + 0.02
                p.drawPolygon(QPolygonF([at(a, top_a), at(b, top_b), at(b, max(base, top_b - depth)), at(a, max(base, top_a - depth))]))
        elif kind == 'cantilever':
            pen = QPen(QColor(120, 120, 120)); pen.setStyle(Qt.PenStyle.DashLine); p.setPen(pen)
            p.drawText(at(0.1, rise * 0.85), 'τοίχος πίσω από τα σκαλιά')
        if kind in ('timber', 'steel'):
            p.setPen(ink); p.setBrush(tread_brush)
            th = SO.TREAD_TIMBER if kind == 'timber' else SO.TREAD_STEEL
            for i in range(n):                         # treads over the stringers
                x, top = step_x(i), (i + 1) * r
                p.drawRect(QRectF(at(x, top), at(x + t + 0.03, top - max(th, 0.035))).normalized())
        if self.sides:
            pen = QPen(QColor(200, 90, 20)); pen.setWidthF(2.0); p.setPen(pen)
            hr = float(q.get('railing_height', STAIR_HEIGHT))
            pts = [(step_x(0), r + hr), (step_x(first - 1) + t, first * r + hr)]
            if landing:
                pts += [(step_x(first) - 0.0, first * r + hr), (step_x(n - 1) + t, n * r + hr)]
            for a, b in zip(pts, pts[1:]):
                p.drawLine(at(*a), at(*b))
        # The landing level up there.
        pen = QPen(QColor(30, 100, 200)); pen.setStyle(Qt.PenStyle.DashLine); p.setPen(pen)
        p.drawLine(at(run - 0.6, rise), at(run + 0.2, rise))


class StairDialog(QDialog):
    def __init__(self, window, eid):
        super().__init__(window)
        self.window, self.eid = window, eid
        self.doc = window.doc
        stair = self.doc.get(eid)
        self.original = dict(stair.params)
        self.params = dict(stair.params)
        self.choice = SO.railing_choice(self.doc, eid)
        kids = [self.doc.get(c) for c in self.doc.children.get(eid, ()) if c in self.doc.entities
                and self.doc.get(c).kind == 'railing' and 'stair_side' in self.doc.get(c).params]
        self.railing_type = kids[0].params.get('railing_type', 'balusters') if kids else 'balusters'
        self.setWindowTitle('Σκάλα')
        self.resize(900, 560)
        root = QVBoxLayout(self)
        body = QHBoxLayout(); root.addLayout(body)
        self.sections = QListWidget(); self.sections.addItems(SECTIONS); self.sections.setFixedWidth(150)
        self.pages = QStackedWidget()
        self.preview = StairPreview()
        body.addWidget(self.sections); body.addWidget(self.pages, 1); body.addWidget(self.preview)
        self.sections.currentRowChanged.connect(self.pages.setCurrentIndex)
        for build in (self._general, self._structure, self._railing, self._materials):
            page = QWidget(); form = QFormLayout(page); build(form); self.pages.addWidget(page)
        self.sections.setCurrentRow(0)
        self.warning = QLabel(); self.warning.setWordWrap(True); root.addWidget(self.warning)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Εντάξει')
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText('Άκυρο')
        buttons.accepted.connect(self.apply); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._refresh()

    # --- pages -------------------------------------------------------------------------------
    def _general(self, form):
        p = self.params
        self.info = QLabel(); self.info.setWordWrap(True)
        form.addRow('Τύπος', QLabel(LAYOUTS.get(p['layout'], p['layout']) + '  (άλλος τύπος: σχεδίασέ τη ξανά · Tab)'))
        form.addRow('Ύψος ορόφου', QLabel(f"{(p['upper_z'] - p['lower_z']) * 100:.1f} cm".replace('.', ',')))
        self.risers = QSpinBox(); self.risers.setRange(3, 40); self.risers.setValue(int(p['riser_count']))
        self.risers.setToolTip('Πόσα ρίχτια: το ύψος του ρίχτη προκύπτει (ύψος ορόφου ÷ ρίχτια)')
        self.risers.valueChanged.connect(self._set_risers)
        form.addRow('Ρίχτια', self.risers)
        self.tread = QDoubleSpinBox(); self.tread.setDecimals(1); self.tread.setRange(20.0, 40.0); self.tread.setSuffix(' cm')
        self.tread.setValue(p['tread_depth'] * 100); self.tread.valueChanged.connect(lambda v: self._set('tread_depth', v / 100))
        form.addRow('Πάτημα', self.tread)
        self.width = QDoubleSpinBox(); self.width.setDecimals(0); self.width.setRange(60, 250); self.width.setSuffix(' cm')
        self.width.setValue(p['width'] * 100); self.width.valueChanged.connect(lambda v: self._set('width', v / 100))
        form.addRow('Πλάτος', self.width)
        numbers = QCheckBox('Αρίθμηση σκαλοπατιών στην κάτοψη'); numbers.setChecked(bool(p.get('plan_numbers', 0)))
        numbers.toggled.connect(lambda on: self._set('plan_numbers', 1 if on else 0))
        form.addRow(numbers)
        form.addRow(self.info)

    def _structure(self, form):
        p = self.params
        self.kind = QComboBox()
        for key, label in SO.STRUCTURES.items():
            self.kind.addItem(label, key)
        self.kind.setCurrentIndex(self.kind.findData(SO.structure(p)))
        self.kind.currentIndexChanged.connect(lambda _i: self._set('structure', self.kind.currentData()))
        form.addRow('Κατασκευή', self.kind)
        self.stringers = QComboBox()
        for key, label in SO.STRINGERS.items():
            self.stringers.addItem(label, key)
        self.stringers.setCurrentIndex(max(0, self.stringers.findData(p.get('stringers', 'sides'))))
        self.stringers.currentIndexChanged.connect(lambda _i: self._set('stringers', self.stringers.currentData()))
        form.addRow('Λουκέτα', self.stringers)
        self.wall_side = QComboBox()
        for key, label in (('', 'Αυτόματα (όπου είναι ο τοίχος)'), ('left', 'Αριστερά (ανεβαίνοντας)'), ('right', 'Δεξιά (ανεβαίνοντας)')):
            self.wall_side.addItem(label, key)
        self.wall_side.setCurrentIndex(max(0, self.wall_side.findData(p.get('cantilever_side', ''))))
        self.wall_side.currentIndexChanged.connect(lambda _i: self._set('cantilever_side', self.wall_side.currentData() or None))
        form.addRow('Τοίχος των πρόβολων', self.wall_side)
        if p.get('layout') == 'spiral':
            form.addRow(QLabel('Σπιράλ: η κατασκευή σχεδιάζεται ακόμη γεμάτη.'))
        self.under = QLabel(); self.under.setWordWrap(True); form.addRow(self.under)
        self.cabinets = QCheckBox('Ντουλάπια από κάτω (γεμίζουν το κενό, ακολουθούν την κλίση)')
        self.cabinets.setChecked(SO.has_under_stair_cabinets(self.doc, self.eid))
        self.cabinets.toggled.connect(lambda _on: self._refresh())
        form.addRow(self.cabinets)

    def _railing(self, form):
        self.left = QCheckBox('Αριστερά'); self.right = QCheckBox('Δεξιά')
        self.on_wall = QCheckBox('Και στην πλευρά που ακουμπά σε τοίχο')
        c = self.choice
        self.left.setChecked(c in ('left', 'both', 'auto')); self.right.setChecked(c in ('right', 'both', 'auto'))
        self.on_wall.setChecked(c != 'auto')
        for box in (self.left, self.right, self.on_wall):
            box.toggled.connect(lambda _on: self._railing_changed())
        row = QHBoxLayout(); row.addWidget(self.left); row.addWidget(self.right); row.addStretch(1)
        holder = QWidget(); holder.setLayout(row)
        form.addRow('Κάγκελο', holder)
        form.addRow('', self.on_wall)
        self.rtype = QComboBox()
        for key, spec in RAILING_TYPES.items():
            self.rtype.addItem(spec['label'], key)
        self.rtype.setCurrentIndex(max(0, self.rtype.findData(self.railing_type)))
        self.rtype.currentIndexChanged.connect(lambda _i: setattr(self, 'railing_type', self.rtype.currentData()))
        form.addRow('Τύπος', self.rtype)
        self.rheight = QDoubleSpinBox(); self.rheight.setDecimals(0); self.rheight.setRange(80, 120); self.rheight.setSuffix(' cm')
        self.rheight.setValue(float(self.params.get('railing_height', STAIR_HEIGHT)) * 100)
        self.rheight.valueChanged.connect(lambda v: self._set('railing_height', v / 100))
        form.addRow('Ύψος κουπαστής', self.rheight)
        form.addRow(QLabel('Πάνω από τη μύτη του σκαλιού · ακολουθεί τη σκάλα όταν μετακινείται ή αλλάζει.'))

    def _materials(self, form):
        from archforge.rendering.materials import MATERIAL_PRESETS
        self.material_form = form
        self.material_presets = MATERIAL_PRESETS
        self._fill_materials()

    def _fill_materials(self):
        from archforge.geometry.mesh import _stair_mesh
        form = self.material_form
        while form.rowCount():
            form.removeRow(0)
        try:
            roles = sorted(set(_stair_mesh(self.params, self.doc).triangle_surfaces))
        except Exception as exc:                      # Α3: said in the form, not an empty editor
            form.addRow(QLabel(f'Οι επιφάνειες της σκάλας δεν υπολογίστηκαν ({exc}) — τα υλικά ανά τμήμα δεν '
                               'είναι διαθέσιμα με αυτές τις τιμές.'))
            roles = []
        chosen = dict(self.params.get('surface_materials') or {})
        for role in roles:
            if role not in SO.ROLE_NAMES or role == 'bottom' and SO.structure(self.params) != 'solid':
                continue
            combo = QComboBox()
            default = SO.DEFAULT_MATERIALS[SO.structure(self.params)].get(role)
            name = self.material_presets.get(default, {}).get('name', default or '—')
            combo.addItem(f'Προεπιλογή: {name}', '')
            for mid, spec in self.material_presets.items():
                combo.addItem(spec['name'], mid)
            combo.setCurrentIndex(max(0, combo.findData(chosen.get(role, ''))))
            combo.currentIndexChanged.connect(lambda _i, r=role, w=combo: self._set_material(r, w.currentData()))
            form.addRow(SO.ROLE_NAMES[role], combo)

    # --- edits ---------------------------------------------------------------------------------
    def _set(self, key, value):
        if value is None:
            self.params.pop(key, None)
        else:
            self.params[key] = value
        if key == 'structure':
            self._fill_materials()
        self._refresh()

    def _set_risers(self, n):
        height = self.params['upper_z'] - self.params['lower_z']
        self.params['riser_count'] = int(n)
        self.params['riser_height'] = height / int(n)
        self._refresh()

    def _set_material(self, role, mid):
        mats = dict(self.params.get('surface_materials') or {})
        if mid:
            mats[role] = mid
        else:
            mats.pop(role, None)
        self._set('surface_materials', mats or None)

    def _railing_changed(self):
        left, right = self.left.isChecked(), self.right.isChecked()
        if left and right:
            self.choice = 'both' if self.on_wall.isChecked() else 'auto'
        else:
            self.choice = 'left' if left else ('right' if right else 'none')
        self._refresh()

    def _refresh(self):
        from archforge.architecture.stairs import stair_wall_conflicts
        p = self.params
        r, t = p['riser_height'], p['tread_depth']
        c = candidate_from_params(p)
        slope = math.degrees(math.atan2(r, t))
        b = blondel(r, t)
        ok = 0.60 <= b <= 0.65
        self.info.setText(
            f"Ρίχτι {r * 100:.1f} cm · κλίση {slope:.0f}° · μήκος ανάπτυξης {(c.tread_count * t):.2f} m\n"
            f"2·ρίχτι + πάτημα = {b * 100:.0f} cm {'✓ άνετη (60–65)' if ok else '⚠ εκτός 60–65 cm'} — πρακτική, προς έλεγχο".replace('.', ','))
        kind = SO.structure(p)
        self.cabinets.setEnabled(kind != 'solid' or self.cabinets.isChecked())
        self.stringers.setEnabled(kind in ('timber', 'steel'))
        self.wall_side.setEnabled(kind == 'cantilever')
        if kind == 'cantilever':
            side = SO.cantilever_side(self.doc, p)
            self.under.setText(f"Πατήματα {SO.TREAD_CANTILEVER * 100:.0f} cm πακτωμένα {SO.EMBED * 100:.0f} cm στον τοίχο "
                               f"({'αριστερά' if side == 'left' else 'δεξιά'}) — ο τοίχος πρέπει να τα φέρει (προς στατικό έλεγχο). "
                               'Κενό από κάτω: ναι.')
        else:
            self.under.setText('Κενό από κάτω: ' + ('όχι (γεμάτη ως το δάπεδο)' if kind == 'solid' else
                                                    'ναι — μπορούν να μπουν ντουλάπια / αποθήκη'))
        problems = []
        if stair_wall_conflicts(self.doc, c):
            problems.append('⚠ Με αυτές τις διαστάσεις η σκάλα περνά από τοίχο.')
        if kind == 'cantilever' and not SO.cantilever_has_wall(self.doc, p):
            problems.append('⚠ Πρόβολα σκαλοπάτια χωρίς τοίχο δίπλα τους δεν στέκουν: βάλε τη σκάλα κολλητά σε τοίχο '
                            '(ή διάλεξε πλευρά) ή άλλη κατασκευή.')
        self.warning.setText('\n'.join(problems))
        self.warning.setStyleSheet('color: #c62828; font-weight: 600;' if problems else '')
        self.preview.set_params(p, {'none': (), 'left': ('left',), 'right': ('right',)}.get(self.choice, ('left', 'right')))

    def changes(self):
        out = {k: v for k, v in self.params.items() if self.original.get(k) != v}
        for k in self.original:
            if k not in self.params:
                out[k] = None
        return {k: v for k, v in out.items() if v is not None}, [k for k, v in out.items() if v is None]

    def command(self):
        from archforge.core.commands import CompositeCommand, UpdateEntity
        changes, removed = self.changes()
        if removed:                                   # «Προεπιλογή» again: drop the stored choice
            for k in removed:
                changes[k] = {} if k == 'surface_materials' else ''
        railing_moved = (self.choice != SO.railing_choice(self.doc, self.eid) or self.railing_type is not None
                         and self.choice != 'none')
        main = (SO.railing_command(self.doc, self.eid, self.choice, self.railing_type, changes) if railing_moved
                else (UpdateEntity(self.eid, changes) if changes else None))
        had = SO.has_under_stair_cabinets(self.doc, self.eid)
        want = self.cabinets.isChecked()
        if want and SO.structure(self.params) == 'solid':
            raise ValueError('γεμάτη σκάλα: δεν έχει κενό από κάτω για ντουλάπια')
        extra = None
        if want and (changes or not had):
            extra = SO.UnderStairCabinets(self.eid)          # computed on the stair as changed above
        elif had and not want:
            from archforge.core.commands import DeleteEntities
            extra = DeleteEntities([cid for cid in self.doc.children.get(self.eid, ()) if cid in self.doc.entities
                                    and self.doc.get(cid).kind == 'cabinet' and self.doc.get(cid).params.get('under_stair')])
        commands = [c for c in (main, extra) if c is not None]
        return CompositeCommand(commands, 'Σκάλα') if commands else None

    def apply(self):
        try:
            command = self.command()
            if command is not None:
                self.window.stack.execute(command)
        except (ValueError, KeyError) as exc:
            self.warning.setText(f'Δεν εφαρμόστηκε: {exc}')
            return
        self.window._redraw_views(all_views=True)
        self.window.refresh_inspector()
        self.window.statusBar().showMessage('Σκάλα: οι αλλαγές εφαρμόστηκαν · Ctrl+Z = αναίρεση όλων μαζί', 6000)
        self.accept()


def open_stair_dialog(window, eid):
    if eid not in window.doc.entities or window.doc.get(eid).kind != 'stair':
        return None
    dialog = StairDialog(window, eid)
    window._stair_dialog = dialog
    dialog.open()
    return dialog
