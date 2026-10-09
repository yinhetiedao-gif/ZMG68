"""Web candidate regression for the existing ordered radial size path, not a new field."""
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from ppg.foundation import Canvas, CircleElement, EllipseElement, RectElement, PatternDocument, Reference
from xiaomang_pattern_lab.contracts import PatternDocumentDTO
from xiaomang_pattern_lab.shared_modifiers import SHARED_MODIFIER_METADATA_KEY
from xiaomang_pattern_lab.web import create_app


@pytest.mark.parametrize('element_type', [CircleElement, EllipseElement, RectElement])
@pytest.mark.parametrize('unit,factor', [('mm', 1), ('px', .5)])
def test_radial_candidate_retains_centers_and_composes_with_existing_scalar_size(element_type, unit, factor):
    elements = [element_type(f'point-{i}', x, 80, 8, 8 if element_type is CircleElement else 6, rotation=9)
                for i, x in enumerate([40, 80, 140])]
    doc = PatternDocument(Canvas(160, 100, unit, factor, 20, 40), Reference(''), elements)
    doc.fields = [{'id': 'user-field', 'type': 'constant', 'parameters': {'value': .5}}]
    doc.modifiers = [{'id': 'user-size', 'type': 'size', 'field_id': 'user-field',
                      'mapping': {'min_output': .8, 'max_output': 1, 'strength': 1}}]
    doc.metadata[SHARED_MODIFIER_METADATA_KEY] = {'version': 1, 'enabled': True,
        'source_kind': 'imported_elements', 'source_elements': deepcopy(doc.to_dict()['elements']),
        'modifiers': [{'id': 'owned-radial', 'type': 'size', 'enabled': True, 'scope': {'mode': 'all'},
            'parameters': {'mode': 'radial', 'center_x': 80, 'center_y': 80, 'radius': 40,
                           'min_scale': 1.2, 'max_scale': .6, 'strength': 1}}]}
    dto = PatternDocumentDTO.from_document(doc, 'radial-candidate', 7).to_dict()
    before = deepcopy(dto)
    with TestClient(create_app()) as client:
        response = client.post('/api/v1/evaluate', json={'schema_version': '1.0',
            'document_id': dto['document_id'], 'document': dto, 'document_revision': 7})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['document_revision'] == 7 and dto == before
    assert len(result['geometry']) == len(elements)
    for source, geometry, radial_ratio in zip(elements, result['geometry'], [.6, 1.2, .6]):
        assert (geometry['x'], geometry['y']) == (source.x * factor, source.y * factor)
        assert geometry['rotation'] == source.rotation
        assert geometry['width'] == pytest.approx(source.width * .9 * radial_ratio * factor)
        assert geometry['height'] == pytest.approx(source.height * .9 * radial_ratio * factor)
