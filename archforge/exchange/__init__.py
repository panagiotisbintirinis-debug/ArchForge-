"""Μεταφραστής του μοντέλου προς άλλα συστήματα (owner 30/10: «ένας μεταφραστής στοιχείων του σχεδίου που να τα
μεταφράζει σε ό,τι σύστημα μας ζητηθεί — IFC, DXF, PDF και άλλα»).

One authoritative Document, read-only; one table (``mapping.py``) says what each ArchForge kind is in every target
system; one small writer per format (``ifc.py``, ``dxf.py``).  A new format is a new writer over the same table.
Nothing here changes the Document.
"""
