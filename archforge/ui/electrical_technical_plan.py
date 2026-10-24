"""Read-only electrical technical plan, with the plumbing tab's zoom/pan behaviour."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor,QPainterPath,QPen
from archforge.ui.plan_view import PlanView
from archforge.ui.plumbing_tab import PlumbingTechnicalPlan


class ElectricalTechnicalPlan(PlumbingTechnicalPlan):
    def __init__(self, doc, stack, parent=None):
        super().__init__(doc, stack, parent)
        self.setAcceptDrops(False); self.viewport().setAcceptDrops(False)
        self.setToolTip('Τεχνική κάτοψη ηλεκτρολογικών — wheel: zoom · σύρε: μετακίνηση. '
                        'Σχηματική απόσταση παράλληλων σωληνώσεων· μετρήσεις από τον χάρτη.')

    def redraw(self):
        from archforge.mep.electrical import route_cables_cached
        selected = set(self.doc.selection or ())
        self._selected_circuits = {c['id'] for c in route_cables_cached(self.doc)['circuits']
                                   if selected.intersection(c['points'])}
        from archforge.core.plan_scene import build_plan_frame
        # The report has its own visible electrical network, even when the
        # normal architectural drawing has hidden the electrical layers.
        self._scaled_labels=[]
        self._scene.clear();self._handle_items.clear();self._entity_items.clear()
        self._frame=build_plan_frame(self.doc,layers=False)
        for primitive in self._frame.primitives:self._draw_primitive(primitive)
        self._update_label_visibility()

    def _draw_primitive(self, p):
        if p.role in ('cable','lv-cable'):
            from archforge.mep.electrical import CABLE_COLORS
            meta = dict(p.meta)
            selected = bool(set(meta.get('circuit','').split(',')) & self._selected_circuits)
            group = meta.get('group',meta.get('system',''))
            pen = QPen(QColor(CABLE_COLORS.get(group,'#e07a00')))
            pen.setWidthF(4.5 if selected else 2.0);pen.setCosmetic(True)
            if p.role=='lv-cable':pen.setStyle(Qt.PenStyle.DashDotLine)
            path = QPainterPath(QPointF(*p.points[0]))
            for point in p.points[1:]:path.lineTo(QPointF(*point))
            item = self._scene.addPath(path,pen);item.setZValue(30 if selected else 20)
            item.setData(0,meta.get('conduit_piece',''));item.setData(1,selected)
            if p.role=='cable':
                item.setToolTip(f"{meta['conduit']} · Φ{meta['diameter_mm']} · {meta['circuit']} — σχηματική απόσταση σειρών")
            else:item.setToolTip(f"Ασθενή: {meta.get('system','')} — χωριστή επάνω σειρά")
            return item
        electrical = p.role in ('cable','elec-box','electrical-label','electrical-point','lv-cable','lv-box','lv-label')
        e = self.doc.entities.get(p.entity_id)
        architecture = p.role.startswith('wall') or (e is not None and e.kind in ('wall','door','window','opening'))
        if electrical or architecture:
            item = PlanView._draw_primitive(self,p)
            return item

    def _draw_handle(self, handle):
        pass

    def _draw_hud(self, hud):
        pass

    def keyPressEvent(self, event):
        # This report view cannot mutate the model through Delete/placement shortcuts.
        event.ignore()
