"""Existing radius-zero Ring semantics; preview/candidate/STL share final heights."""
from copy import deepcopy
import math
import numpy as np
import pytest
from ppg.foundation import Canvas, PatternDocument, Reference, RectElement, FilledRegionElement
from xiaomang_pattern_lab.shared_fields import RingField, LinearField, FieldContext, FieldMapping, SizeModifier, RotationModifier
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.fabric_preview import build_fabric_design
from xiaomang_pattern_lab.fabric_candidate import build_fabric_candidate
from xiaomang_pattern_lab.fabric_fusion import FabricFusionService
from xiaomang_pattern_lab.fabric_stl import export_validated_fabric_stl
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.mesh_validation import MeshValidator


def fixture(source, mode):
    doc = PatternDocument(Canvas(120, 80, 'svg', .5, 20, 40), Reference('', False), [
        RectElement(f'cell-{i}', 30+i%3*20, 50+i//3*20, 6, 4, rotation=i*5) for i in range(9)])
    doc.fields = [RingField('height', center_x=25, center_y=35, radius=0, ring_width=40).to_dict(),
                  LinearField('user', angle=0, start=30, end=70).to_dict()]
    doc.modifiers = [SizeModifier('size', 'user', FieldMapping(.7, 1)).to_dict(),
                     RotationModifier('rotation', 'user', FieldMapping(-10, 10)).to_dict()]
    doc.metadata['fabric_config'] = {'config_version': 1, 'shape_source': source, 'output_mode': mode,
        'base': {'type': 'solid', 'thickness_mm': .6, 'margin_mm': 1},
        'unit_cell': {'type': 'fin', 'width_mm': 2, 'depth_mm': 1, 'height_mm': 3, 'size_mode': 'follow_pattern'},
        'original_shape': {'size_scale': 1.2, 'height_mm': 2},
        'placement': {'mode': 'pattern_points', 'spacing_x_mm': 5, 'spacing_y_mm': 5},
        'field_modifiers': {'height': {'enabled': True, 'field_id': 'height', 'min_height_mm': 2, 'max_height_mm': 6}}}
    return doc


def build(doc):
    dto = PatternDocumentDTO.from_document(doc, 'center-recipe', 8)
    design = build_fabric_design(doc, dto, preview_limit=False)
    candidate = build_fabric_candidate(design.plan, design.config.base, design.design_bounds_mm,
        document_id=dto.document_id, document_revision=8, output_mode=design.config.output_mode)
    return design, candidate


def test_ring_center_peak_numerical_semantics_and_world_units():
    field = RingField('peak', center_x=25, center_y=40, radius=0, ring_width=40)
    points = [(25, 40), (35, 40), (45, 40), (50, 40), (25, 50)]
    elements = [RectElement(str(i), x, y, 1, 1) for i, (x, y) in enumerate(points)]
    assert [field.evaluate(element, FieldContext.from_elements(elements)) for element in elements] == pytest.approx([1, .5, 0, 0, .5])


@pytest.mark.parametrize('source', ['original', 'unit_cell'])
@pytest.mark.parametrize('mode', ['cells_only', 'cells_with_base'])
def test_final_xy_size_rotation_and_each_height_candidate_and_stl(source, mode):
    doc = fixture(source, mode); before = deepcopy(doc.to_dict())
    baseline = deepcopy(doc); baseline.metadata['fabric_config']['field_modifiers']['height']['enabled'] = False
    previous, _ = build(baseline)
    design, candidate = build(doc)
    for item, old, mesh in zip(design.plan.instances, previous.plan.instances, candidate.cell_meshes):
        assert (item.x_mm, item.y_mm, item.rotation_deg, item.cell_width_mm, item.cell_depth_mm) == pytest.approx(
            (old.x_mm, old.y_mm, old.rotation_deg, old.cell_width_mm, old.cell_depth_mm))
        expected = 2 + 4 * max(0, 1 - math.hypot(item.x_mm-25, item.y_mm-35)/20)
        assert item.height_mm == pytest.approx(expected)
        assert mesh.bounds[0, 2] == pytest.approx(0 if mode == 'cells_only' else .6)
        assert mesh.bounds[1, 2] == pytest.approx(item.z_mm + expected)
    final = FabricFusionService().build(candidate)
    payload, _ = export_validated_fabric_stl(final)
    reloaded = STLExporter.reload_bytes_as_mesh_result(payload)
    report = MeshValidator().validate(reloaded)
    assert report.is_valid and report.is_watertight and report.degenerate_face_count == 0
    assert report.component_count == (9 if mode == 'cells_only' else 1)
    assert reloaded.mesh.volume > 0 and reloaded.mesh.is_winding_consistent
    np.testing.assert_allclose(reloaded.mesh.bounds, final.report['bounds_mm'], atol=1e-5)
    assert doc.to_dict() == before


def test_original_hole_remains_real_and_height_is_sampled_at_its_anchor():
    doc = fixture('original', 'cells_only'); doc.modifiers = []
    doc.elements = [FilledRegionElement('hole', 50, 70, 12, 12, rotation=20,
        style={'fill': 'black', 'fill-rule': 'evenodd'}, path_data='M0 0H12V12H0Z M3 3H9V9H3Z',
        base_x=0, base_y=0, base_width=12, base_height=12)]
    design, candidate = build(doc)
    assert design.plan.instances[0].height_mm == 6
    assert candidate.cell_meshes[0].euler_number == 0
    data, _ = export_validated_fabric_stl(FabricFusionService().build(candidate))
    mesh = STLExporter.reload_bytes_as_mesh_result(data)
    assert mesh.mesh.euler_number == 0 and MeshValidator().validate(mesh).is_valid
    assert mesh.mesh.volume == pytest.approx((144-36)*.25*1.2**2*6, rel=1e-5)


@pytest.mark.parametrize('cx,cy,radius', [(25, 35, 30), (25, 35, 6), (17, 29, 18)])
def test_broad_narrow_offcenter_support_preserves_all_instances(cx, cy, radius):
    doc = fixture('original', 'cells_only')
    doc.fields[0] = RingField('height', center_x=cx, center_y=cy, radius=0, ring_width=radius*2).to_dict()
    design, _ = build(doc)
    assert len(design.plan.instances) == 9
    for item in design.plan.instances:
        expected = 2+4*max(0, 1-math.hypot(item.x_mm-cx, item.y_mm-cy)/radius)
        assert item.height_mm == pytest.approx(expected)
