import pytest
from archforge.core.model import Document, Entity
from archforge.organic.materials import BIOSPECTRE_MATERIALS, BIOSPECTRE_CONSTRUCTIONS, register_biospectre_presets
from archforge.organic.bubble_cluster import create_bio_spectre_cluster, add_upper_dome, compute_cluster_reorganization
from archforge.organic.spectre import NEUROARCHITECTURE_AQUA_PROPERTIES

def test_biospectre_materials_specs():
    assert 'hempcrete_sprayed' in BIOSPECTRE_MATERIALS
    assert BIOSPECTRE_MATERIALS['hempcrete_sprayed']['embodied_carbon_kg_co2_m3'] < 0
    assert 'spectre_polycarbonate_aqua' in BIOSPECTRE_MATERIALS
    assert BIOSPECTRE_MATERIALS['spectre_polycarbonate_aqua']['thickness_mm'] == 18.0
    assert NEUROARCHITECTURE_AQUA_PROPERTIES['emission_peak_wavelength_nm'] == 490.0

def test_register_biospectre_presets():
    doc = Document()
    register_biospectre_presets(doc)
    assert 'bio_spectre_hybrid_shell' in doc.constructions
    assert 'bio_spectre_cistern_foundation' in doc.constructions
    assert 'hempcrete_sprayed' in doc.materials

def test_bio_spectre_cluster_creation():
    doc = Document()
    result = create_bio_spectre_cluster(doc, center_x=0.0, center_y=0.0, include_upper_dome=True)
    assert result['total_pods_created'] == 5
    pods = [e for e in doc.entities.values() if e.kind == 'pod']
    assert len(pods) == 5
    
    # Check that reorganization identified junctions
    reorg = result['reorganization']
    assert len(reorg['horizontal_junctions']) >= 3
    assert len(reorg['vertical_stack_junctions']) >= 1

def test_add_upper_dome_fluid_reorganization():
    doc = Document()
    # Create 2 base pods that touch
    p1 = Entity(kind='pod', name="Pod A", params={'cx': 0.0, 'cy': 0.0, 'floor_level': 0.0, 'diameter_x': 6.0, 'diameter_y': 6.0, 'height': 3.5, 'shell_thickness': 0.02, 'rotation': 0.0})
    p2 = Entity(kind='pod', name="Pod B", params={'cx': 4.5, 'cy': 0.0, 'floor_level': 0.0, 'diameter_x': 6.0, 'diameter_y': 6.0, 'height': 3.5, 'shell_thickness': 0.02, 'rotation': 0.0})
    doc.add(p1)
    doc.add(p2)
    
    upper_id = add_upper_dome(doc, cx=2.25, cy=0.0, diameter=4.5, height=3.0)
    assert upper_id in doc.entities
    upper = doc.entities[upper_id]
    # Check resting elevation is placed above ground
    assert upper.params['floor_level'] > 2.0
