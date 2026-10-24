"""Electrical quantities, explicit specifications and route-cost alternatives."""
from __future__ import annotations
import csv
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView,QComboBox,QFileDialog,QScrollArea,QFrame,QHBoxLayout,QHeaderView,QInputDialog,
                               QDialog,QDialogButtonBox,QFormLayout,QLabel,QLineEdit,QPushButton,QTableWidget,QTableWidgetItem,QTabWidget,QVBoxLayout,QWidget)
from archforge.mep import electrical_takeoff as E


def number(value):
    return '—' if value is None else f'{value:,.2f}'.replace(',',' ').replace('.',',')


def _table(headers):
    table=QTableWidget(0,len(headers));table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True);table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Interactive);table.setColumnWidth(0,360)
    table.setWordWrap(False);table.verticalHeader().hide()
    return table


def _fill(table,rows,tips):
    table.setRowCount(len(rows))
    for i,values in enumerate(rows):
        for j,value in enumerate(values):
            item=QTableWidgetItem(str(value));item.setToolTip(tips[i]);table.setItem(i,j,item)


def _amount(data):
    if data['complete']: return f"Σύνολο καταχωρισμένων ειδών: {number(data['total'])} €"
    return (f"Μερικό τιμολογημένο ποσό: {number(data['known_subtotal'])} € · "
            f"{len(data['missing'])} εκκρεμή είδη · {len(data['geometry_missing'])} ελλείψεις διαδρομών")


class ElectricalTakeoffPage(QScrollArea):
    def __init__(self,board):
        super().__init__();self.board=board;self.window=board.window
        self.preview_doc=self.window.doc;self.comparison=None;self._compared=False
        self.setObjectName('electricalTakeoffPage');self.setWidgetResizable(True);self.setFrameShape(QFrame.Shape.NoFrame)
        content=QWidget();self.setWidget(content);root=QVBoxLayout(content);root.setContentsMargins(0,4,0,0)
        bar=QHBoxLayout();bar.addWidget(QLabel('Διέλευση:'))
        self.mode=QComboBox();self.mode.setObjectName('electricalPassagePreview');self.mode.addItem('Τρέχον έργο','')
        for key,label in E.MODES.items():self.mode.addItem('Προεπισκόπηση: '+label,key)
        bar.addWidget(self.mode);self.apply=QPushButton('Εφαρμογή')
        self.apply.setToolTip('Αλλάζει όλα τα ηλεκτρολογικά σημεία προορισμού, ισχυρά και ασθενή. Ένα Undo τα επαναφέρει.')
        bar.addWidget(self.apply)
        fit=QPushButton('Όλο σχέδιο');fit.clicked.connect(board.technical_plan.fit_content);bar.addWidget(fit);bar.addStretch(1)
        extra=QPushButton('Πρόσθετο είδος…');extra.clicked.connect(lambda:self._edit_extra());bar.addWidget(extra)
        remove=QPushButton('Διαγραφή');remove.setToolTip('Διαγραφή επιλεγμένου πρόσθετου είδους, με Undo');remove.clicked.connect(self._remove_extra);bar.addWidget(remove)
        export=QPushButton('CSV…');export.clicked.connect(self.export_csv);bar.addWidget(export);root.addLayout(bar)
        self.notice=QLabel();self.notice.setWordWrap(True);root.addWidget(self.notice)
        self.summary=QLabel();self.summary.setWordWrap(True);self.summary.setStyleSheet('font-weight:600');root.addWidget(self.summary)
        self.tabs=QTabWidget();root.addWidget(self.tabs,1)
        self.table=_table(['Είδος / προδιαγραφή','Ποσότητα','Μον.','Υλικό €/μον.','Εργασία €/μον.','Υλικά €','Εργασία €','Ποσό €','Εκκρεμότητες'])
        self.table.setObjectName('electricalQuantityPrices');self.tabs.addTab(self.table,'Ποσότητες & τιμές')
        boxpage=QWidget();boxlayout=QVBoxLayout(boxpage);boxbar=QHBoxLayout();self.box_kind=QComboBox()
        for kind,label in E.BOX_LABELS.items():self.box_kind.addItem(label,kind)
        self.box_default=QLineEdit();self.box_default.setPlaceholderText('Μέγεθος / μοντέλο από μελέτη ή προσφορά')
        setdefault=QPushButton('Ορισμός ανά χρήση');setdefault.clicked.connect(self._box_default)
        boxbar.addWidget(self.box_kind);boxbar.addWidget(self.box_default,1);boxbar.addWidget(setdefault);boxlayout.addLayout(boxbar)
        self.box_table=_table(['Θέση / χρήση','x · y · z (m)','Γραμμές','Μέγεθος / μοντέλο'])
        self.box_table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch)
        boxlayout.addWidget(self.box_table);self.tabs.addTab(boxpage,'Κουτιά ανά μέγεθος')
        comparepage=QWidget();layout=QVBoxLayout(comparepage);materials=QHBoxLayout();self.profiles={}
        from archforge.mep.conduit_fill import CONDUIT_PROFILES
        for mode in ('floor','ceiling'):
            materials.addWidget(QLabel(E.MODES[mode]+':'));combo=QComboBox();combo.addItem('Σειρά έργου','')
            for key,spec in CONDUIT_PROFILES.items():
                if key!='geonflex':combo.addItem(spec['name'],key)
            materials.addWidget(combo,1);self.profiles[mode]=combo;combo.currentIndexChanged.connect(self.refresh)
        layout.addLayout(materials)
        compare=QPushButton('Υπολογισμός σύγκρισης δαπέδου / οροφής');compare.clicked.connect(self.calculate_comparison);layout.addWidget(compare)
        self.compare_summary=QLabel('Υπολόγισε τα δύο εναλλακτικά σχέδια και τις ποσότητές τους.');self.compare_summary.setWordWrap(True)
        layout.addWidget(self.compare_summary)
        self.compare_table=_table(['Είδος','Μον.','Υλικό €/μον.','Εργασία €/μον.','Δάπεδο ποσ.','Δάπεδο €','Οροφή ποσ.','Οροφή €'])
        layout.addWidget(self.compare_table);self.tabs.addTab(comparepage,'Σύγκριση διελεύσεων')
        helptext=QLabel('Διπλό κλικ σε τιμή, ποσότητα από μελέτη ή προδιαγραφή: εισαγωγή. '
                       'Κενό = δεν ορίστηκε · 0 = ρητή μηδενική τιμή. Ποσά προ ΦΠΑ. '
                       'Κουτιά μηχανισμών, στηρίγματα και λοιπά εξαρτήματα: «Πρόσθετο είδος» από μελέτη / προσφορά. '
                       'Καταλληλότητα υλικών, θύρες κουτιών, καμπύλες και πρόσβαση: προς έλεγχο ηλεκτρολόγου.')
        helptext.setWordWrap(True);root.addWidget(helptext)
        self.mode.currentIndexChanged.connect(self.refresh);self.apply.clicked.connect(self._apply)
        self.table.cellDoubleClicked.connect(self._edit_cell);self.box_kind.currentIndexChanged.connect(self._show_default)
        self.box_table.cellDoubleClicked.connect(self._edit_box);self.compare_table.cellDoubleClicked.connect(self._edit_comparison_price)

    def refresh(self,*_args):
        from archforge.core.commands import CommandStack
        from archforge.mep.project_pricebook import effective_prices
        mode=self.mode.currentData()
        try:
            profile=self.profiles[mode].currentData() if mode in self.profiles else None
            self.preview_doc=E.routing_preview(self.window.doc,mode,profile) if mode else self.window.doc
            self.result=E.takeoff(self.preview_doc)
        except ValueError as exc:
            self.mode.blockSignals(True);self.mode.setCurrentIndex(0);self.mode.blockSignals(False)
            self.preview_doc=self.window.doc;mode='';self.result=E.takeoff(self.preview_doc);self.notice.setText(str(exc))
        else:
            self.notice.setText(('ΠΡΟΕΠΙΣΚΟΠΗΣΗ '+E.MODES[mode]+': η διέλευση δεν εφαρμόστηκε. Σχέδιο και ποσότητες αφορούν αυτή την εναλλακτική. Οι τιμές / προδιαγραφές αποθηκεύονται στο έργο.'
                                 if mode else 'Τρέχον έργο: ποσότητες όλων των ορόφων · σχέδιο τρέχοντος ορόφου.'))
        self.apply.setEnabled(bool(mode))
        stack=self.window.stack if self.preview_doc is self.window.doc else CommandStack(self.preview_doc)
        if self.board.pages.currentWidget() is self:self.board.technical_plan.rebind(self.preview_doc,stack)
        else:self.board.technical_plan.rebind(self.window.doc,self.window.stack)
        self.summary.setText(_amount(self.result)+f" · Υλικά {number(self.result['material'])} € · Εργασία {number(self.result['labour'])} € (γνωστά ποσά)")
        self.summary.setToolTip('\n'.join(x['description']+': '+', '.join(x['reasons']) for x in self.result['missing'])+'\n'+'\n'.join(self.result['geometry_missing']))
        self.raw=self.result['raw_rows'];self.row_data=self.result['rows'];prices=effective_prices(self.window.doc)
        missing={x['code']:', '.join(x['reasons']) for x in self.result['missing']};rows=[];tips=[]
        for x in self.row_data:
            p=prices.get(x['code']);rows.append([x['description'],number(x['quantity']),x['unit'],
                number(p.material_unit_price if p else None),number(p.labour_unit_price if p else None),
                number(x['material']),number(x['labour']),number(x['amount']),missing.get(x['code'],'')])
            tips.append(f"{x['code']}\n{x['why']}\n{x['status']} · {x['source']}\nΤιμή: {x.get('price_source') or 'δεν ορίστηκε'}")
        _fill(self.table,rows,tips);self.boxes=E.box_inventory(self.preview_doc)
        _fill(self.box_table,[[f"{i+1}. {E.BOX_LABELS[b['kind']]}",' · '.join(number(v) for v in b['point']),
                              ', '.join(b['circuits']),b['spec'] or '— εισάγετε μέγεθος / μοντέλο'] for i,b in enumerate(self.boxes)],
              [b['key']+'\n'+b['spec_source'] for b in self.boxes])
        self._show_default()
        if self._compared:self.calculate_comparison()

    def _commit(self,function):
        try:
            function()
            if not self.board.isVisible():self.board.refresh()
        except ValueError as exc:self.notice.setText(str(exc))

    def _apply(self):
        mode=self.mode.currentData()
        if mode:
            profile=self.profiles[mode].currentData() if mode in self.profiles else None
            self._commit(lambda:E.apply_routing(self.window.doc,self.window.stack,mode,profile))

    def _panel_map(self,field,key,value):
        from archforge.core.commands import UpdateEntity
        p=E.panel(self.window.doc)
        if p is None:raise ValueError('Βάλτε ηλεκτρικό πίνακα για να αποθηκευτεί η προδιαγραφή στο έργο.')
        data=dict(p.params.get(field,{}))
        if value is None or value=='':data.pop(key,None)
        else:data[key]=value
        if data!=p.params.get(field,{}):self.window.stack.execute(UpdateEntity(p.id,{field:data}))

    def _show_default(self,*_args):
        p=E.panel(self.window.doc)
        self.box_default.setText(p.params.get('electrical_box_defaults',{}).get(self.box_kind.currentData(),'') if p else '')

    def _box_default(self):
        kind=self.box_kind.currentData();text=self.box_default.text().strip()
        self._commit(lambda:self._panel_map('electrical_box_defaults',kind,text))

    def _ask(self,title,prompt,value):
        text,ok=QInputDialog.getText(self,title,prompt,QLineEdit.EchoMode.Normal,value)
        return text.strip() if ok else None

    def _price_dialog(self,code,column):
        from archforge.mep.project_pricebook import effective_prices
        p=effective_prices(self.window.doc).get(code);component='material' if column==3 else 'labour'
        value=getattr(p,component+'_unit_price') if p else None
        text=self._ask('Τιμή υλικού' if component=='material' else 'Τιμή εργασίας',
                       code+'\n€/μονάδα, προ ΦΠΑ · κενό για διαγραφή, 0 αν περιλαμβάνεται.',
                       '' if value is None else str(value).replace('.',','))
        if text is None:return
        def commit():
            value=None if not text else float(text.replace(' ','').replace(',','.'))
            E.edit_price(self.window.doc,self.window.stack,code,component,value)
        self._commit(commit)

    def _edit_cell(self,row,column):
        item=self.row_data[row];meta=self.raw[row][3];code=meta.get('base_code',meta['code'])
        if column in (3,4):return self._price_dialog(item['code'],column)
        if meta.get('extra_id') and column in (0,1):return self._edit_extra(meta['extra_id'])
        if column==1 and meta.get('quantity_input'):
            text=self._ask('Ποσότητα από μελέτη',item['description']+'\nΚενό = εκκρεμεί.', '' if item['quantity'] is None else str(item['quantity']))
            if text is not None:self._commit(lambda:self._panel_map('electrical_quantity_inputs',code,None if not text else float(text.replace(',','.'))))
        elif column==0 and code.startswith('electrical.box.'):self.tabs.setCurrentIndex(1)
        elif column==0 and meta.get('requires_spec'):
            p=E.panel(self.window.doc);old=p.params.get('electrical_item_specs',{}).get(code,'') if p else ''
            text=self._ask('Προδιαγραφή από τη μελέτη',item['description']+'\nΤύπος / μέγεθος / μοντέλο από μελέτη ή προσφορά.',old)
            if text is not None:self._commit(lambda:self._panel_map('electrical_item_specs',code,text))

    def _edit_box(self,row,column):
        if column!=3:return
        b=self.boxes[row];text=self._ask('Κουτί στη συγκεκριμένη θέση',E.BOX_LABELS[b['kind']]+' · '+b['key']+
                                      '\nΜέγεθος / μοντέλο. Κενό = χωρίς προδιαγραφή στη θέση αυτή.',b['spec'])
        if text is not None:
            from archforge.core.commands import UpdateEntity
            p=E.panel(self.window.doc)
            if p is None:return self.notice.setText('Βάλτε πρώτα ηλεκτρικό πίνακα.')
            values=dict(p.params.get('electrical_box_specs',{}));values[b['key']]=text
            self._commit(lambda:self.window.stack.execute(UpdateEntity(p.id,{'electrical_box_specs':values})))

    def calculate_comparison(self):
        from archforge.mep.project_pricebook import effective_prices
        try:comparison=E.compare_routing(self.window.doc,{k:c.currentData() for k,c in self.profiles.items()})
        except ValueError as exc:
            self.compare_summary.setText(str(exc));self.compare_table.setRowCount(0);self.comparison=None;return
        self._compared=True;self.comparison=comparison;a,b=comparison['floor'],comparison['ceiling']
        text='Δάπεδο: '+_amount(a)+'\nΟροφή: '+_amount(b)
        if a['complete'] and b['complete']:text+=f"\nΔιαφορά οροφής − δαπέδου: {number(b['total']-a['total'])} € (καταχωρισμένα είδη, προ ΦΠΑ)."
        else:text+='\nΣύγκριση συνολικού κόστους μετά τη συμπλήρωση ποσοτήτων, προδιαγραφών και τιμών.'
        self.compare_summary.setText(text);maps={mode:{x['code']:x for x in data['rows']} for mode,data in comparison.items()}
        self.compare_codes=sorted(set(maps['floor'])|set(maps['ceiling']));prices=effective_prices(self.window.doc);rows=[];tips=[]
        for code in self.compare_codes:
            x=maps['floor'].get(code) or maps['ceiling'][code];p=prices.get(code)
            values=[x['description'],x['unit'],number(p.material_unit_price if p else None),number(p.labour_unit_price if p else None)]
            for mode in ('floor','ceiling'):
                entry=maps[mode].get(code);values += [number(entry['quantity']) if entry else '0',number(entry['amount']) if entry else '0,00']
            rows.append(values);tips.append(code+'\n'+x['why'])
        _fill(self.compare_table,rows,tips)

    def _edit_comparison_price(self,row,column):
        if column in (2,3):self._price_dialog(self.compare_codes[row],column+1)

    def export_csv(self,path=None):
        if not isinstance(path,str):path,_=QFileDialog.getSaveFileName(self,'Επιμέτρηση ηλεκτρολογικών','ilektrologika_posotites.csv','CSV (*.csv)')
        if not path:return
        with open(path,'w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.writer(stream,delimiter=';');writer.writerow(['Ποσά προ ΦΠΑ · μοντέλο προς έλεγχο ηλεκτρολόγου'])
            datasets=[('Τρέχον έργο' if not self.mode.currentData() else 'Προεπισκόπηση '+E.MODES[self.mode.currentData()],self.result)]
            if self.comparison:datasets += [(E.MODES[m],d) for m,d in self.comparison.items()]
            for label,data in datasets:
                writer.writerow([label,_amount(data)]);writer.writerow(['Κωδικός','Είδος','Μονάδα','Ποσότητα','Υλικά €','Εργασία €','Ποσό €','Πλήρης τιμή'])
                for x in data['rows']:writer.writerow([x['code'],x['description'],x['unit'],number(x['quantity']),number(x['material']),number(x['labour']),number(x['amount']),'ναι' if x['complete'] else 'όχι'])
                for x in data['missing']:writer.writerow(['ΕΚΚΡΕΜΕΙ',x['description'],', '.join(x['reasons'])])
                for warning in data['geometry_missing']:writer.writerow(['ΕΛΛΕΙΨΗ ΔΙΑΔΡΟΜΗΣ',warning])
        return path

    def _edit_extra(self,identity=None):
        from uuid import uuid4
        from archforge.core.commands import UpdateEntity
        p=E.panel(self.window.doc)
        if p is None:return self.notice.setText('Βάλτε πρώτα ηλεκτρικό πίνακα.')
        values=list(p.params.get('electrical_extra_items',[]));old=next((x for x in values if x['id']==identity),{})
        dialog=QDialog(self);dialog.setWindowTitle('Πρόσθετο υλικό / εργασία από μελέτη ή προσφορά')
        form=QFormLayout(dialog);desc=QLineEdit(old.get('description',''));unit=QLineEdit(old.get('unit',''))
        quantity=QLineEdit('' if old.get('quantity') is None else str(old['quantity']));mode=QComboBox()
        mode.addItem('Σε όλες τις διελεύσεις','all')
        for key,label in E.MODES.items():mode.addItem('Μόνο συνολική διέλευση: '+label,key)
        mode.setCurrentIndex(max(0,mode.findData(old.get('mode','all'))))
        form.addRow('Είδος / μέγεθος / μοντέλο',desc);form.addRow('Μονάδα μέτρησης',unit);form.addRow('Ποσότητα (κενό = εκκρεμεί)',quantity);form.addRow('Εναλλακτική',mode)
        note=QLabel('Τα στοιχεία εισάγονται από εσένα. Οι τιμές υλικού και εργασίας συμπληρώνονται μετά, στον πίνακα.');note.setWordWrap(True);form.addRow(note)
        error=QLabel();error.setWordWrap(True);form.addRow(error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);form.addRow(buttons)
        buttons.rejected.connect(dialog.reject)
        def validate():
            try:
                raw=quantity.text().strip();qty=None if not raw else float(raw.replace(',','.'))
                item={'id':identity or uuid4().hex,'description':desc.text().strip(),'unit':unit.text().strip(),'quantity':qty,'mode':mode.currentData()}
                # Validate before closing the dialog; command execution happens after exec returns.
                from archforge.core.model import validate_params
                changes={'electrical_extra_items':[x for x in values if x['id']!=identity]+[item]}
                validate_params('electrical_point',changes)
                dialog.changes=changes;dialog.accept()
            except ValueError as exc:error.setText(str(exc))
        buttons.accepted.connect(validate)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            self._commit(lambda:self.window.stack.execute(UpdateEntity(p.id,dialog.changes)))

    def _remove_extra(self):
        from archforge.core.commands import UpdateEntity
        row=self.table.currentRow()
        if row<0:return
        identity=self.raw[row][3].get('extra_id');p=E.panel(self.window.doc)
        if not identity or p is None:return self.notice.setText('Επίλεξε ένα πρόσθετο είδος. Οι ποσότητες του μοντέλου αλλάζουν από το σχέδιο.')
        values=[x for x in p.params.get('electrical_extra_items',[]) if x['id']!=identity]
        self._commit(lambda:self.window.stack.execute(UpdateEntity(p.id,{'electrical_extra_items':values})))
