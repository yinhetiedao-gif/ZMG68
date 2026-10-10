"""Recipe's existing WaveField -> authoritative plan -> candidate -> STL semantics."""
from copy import deepcopy
import math
import numpy as np
import pytest
from ppg.foundation import Canvas, PatternDocument, Reference, RectElement
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.fabric_preview import build_fabric_design
from xiaomang_pattern_lab.fabric_candidate import build_fabric_candidate
from xiaomang_pattern_lab.fabric_fusion import FabricFusionService
from xiaomang_pattern_lab.fabric_stl import export_validated_fabric_stl
from xiaomang_pattern_lab.stl_export import STLExporter
from xiaomang_pattern_lab.mesh_validation import MeshValidator
from xiaomang_pattern_lab.shared_fields import WaveField, LinearField, SizeModifier, RotationModifier, FieldMapping
from xiaomang_pattern_lab.shared_modifiers import SharedModifierStack, PositionModifier


def wave_document(factor=.5, mode='cells_only', wavelength=36, angle=0):
    # Physical non-zero origin, non-square frame; positions independent of UI/camera.
    doc = PatternDocument(Canvas(120, 80, 'svg', factor, 20, 40), Reference('', False), [
        RectElement(f'point-{i}', 30+i%3*40, 50+i//3*20, 4, 4) for i in range(9)])
    doc.fields = [WaveField('owned-wave', wavelength=wavelength, angle=angle).to_dict()]
    doc.metadata['fabric_config'] = {'config_version': 1, 'output_mode': mode,
        'base': {'type': 'solid', 'thickness_mm': .6, 'margin_mm': 1},
        'unit_cell': {'type': 'pyramid', 'width_mm': 4.8, 'depth_mm': 4.8, 'height_mm': 3, 'size_mode': 'follow_pattern'},
        'placement': {'mode': 'pattern_points', 'spacing_x_mm': 5, 'spacing_y_mm': 5},
        'field_modifiers': {'height': {'enabled': True, 'field_id': 'owned-wave', 'min_height_mm': 2, 'max_height_mm': 6}}}
    return doc


@pytest.mark.parametrize('wavelength,angle', [(36, 0), (120, 0), (18, 0), (36, 45)])
@pytest.mark.parametrize('factor', [.5, 2])
def test_wave_world_mm_height_no_source_mutation_and_preview_candidate_parity(wavelength, angle, factor):
    doc = wave_document(factor, wavelength=wavelength, angle=angle)
    snapshot = deepcopy(doc.to_dict())
    dto = PatternDocumentDTO.from_document(doc, 'wave-1b', 1)
    design = build_fabric_design(doc, dto, preview_limit=False)
    candidate = build_fabric_candidate(design.plan, design.config.base, design.design_bounds_mm,
        document_id=dto.document_id, document_revision=1, output_mode=design.config.output_mode)
    assert candidate.base_mesh is None and len(candidate.cell_meshes) == 9
    for element, instance, transform, mesh in zip(doc.elements, design.plan.instances, candidate.instance_transforms, candidate.cell_meshes):
        x, y = element.x*factor, element.y*factor
        phase = 2*math.pi*(x*math.cos(math.radians(angle))+y*math.sin(math.radians(angle)))/wavelength
        height = 2+4*(math.sin(phase)+1)/2
        assert instance.height_mm == pytest.approx(height)
        assert (instance.x_mm, instance.y_mm, instance.z_mm) == (x, y, 0)
        assert transform['height_mm'] == pytest.approx(height)
        assert mesh.bounds[0, 2] == 0 and mesh.bounds[1, 2] == pytest.approx(height)
    assert doc.to_dict() == snapshot


@pytest.mark.parametrize('mode,components', [('cells_only', 9), ('cells_with_base', 1)])
@pytest.mark.parametrize('wavelength,angle', [(36, 0), (18, 45)])
def test_default_and_variant_actual_stl_strict_roundtrip(mode, components, wavelength, angle):
    doc = wave_document(mode=mode, wavelength=wavelength, angle=angle)
    dto = PatternDocumentDTO.from_document(doc, 'wave-export', 4)
    design = build_fabric_design(doc, dto, preview_limit=False)
    candidate = build_fabric_candidate(design.plan, design.config.base, design.design_bounds_mm,
        document_id=dto.document_id, document_revision=4, output_mode=mode)
    final = FabricFusionService().build(candidate)
    payload, report = export_validated_fabric_stl(final)
    mesh = STLExporter.reload_bytes_as_mesh_result(payload)
    validation = MeshValidator().validate(mesh)
    assert validation.is_valid and validation.is_watertight and validation.degenerate_face_count == 0
    assert validation.component_count == components
    assert mesh.mesh.volume > 0 and mesh.mesh.is_winding_consistent
    np.testing.assert_allclose(mesh.mesh.bounds, final.report['bounds_mm'], atol=1e-5, rtol=0)
    assert report['roundtrip_validation']['component_count'] == components


def test_wave_height_retains_2d_size_rotation_and_position_and_scale_once():
    doc = wave_document()
    doc.fields.append(LinearField('user-size', angle=0, start=30, end=110).to_dict())
    doc.modifiers = [SizeModifier('size', 'user-size', FieldMapping(.7, 1.2)).to_dict(),
        RotationModifier('rotate', 'user-size', FieldMapping(-30, 30)).to_dict()]
    stack = SharedModifierStack(source_elements=deepcopy(doc.elements))
    stack.add_modifier('position', PositionModifier(mode='offset', offset_x=2, offset_y=-1).to_dict())
    doc.metadata['xiaomang_pattern_lab.shared_modifiers'] = stack.to_dict()
    baseline = deepcopy(doc)
    baseline.metadata['fabric_config']['field_modifiers'] = {}
    plain = build_fabric_design(baseline, PatternDocumentDTO.from_document(baseline, 'wave', 1))
    waving = build_fabric_design(doc, PatternDocumentDTO.from_document(doc, 'wave', 2))
    for a, b in zip(plain.plan.instances, waving.plan.instances):
        assert (a.x_mm, a.y_mm, a.rotation_deg, a.cell_width_mm, a.cell_depth_mm) == (
            b.x_mm, b.y_mm, b.rotation_deg, b.cell_width_mm, b.cell_depth_mm)
        assert b.cell_width_mm == pytest.approx(4.8*b.scale_x)
        assert b.cell_depth_mm == pytest.approx(4.8*b.scale_y)
    assert len({round(i.height_mm, 4) for i in waving.plan.instances}) > 1
