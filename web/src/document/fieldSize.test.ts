import { describe, expect, it } from 'vitest'
import data from '../test/sizeFieldCatalog.json'
import { createExampleDocument } from '../examples/catalog'
import { phase1aBounds } from '../test/phase1aFixture'
import { type ParameterCatalog } from './parameterSchema'
import { openLinearSize, linearSizeCandidate, linearSizeOwner, selectSizeField, sizeFieldGroup, sizeFieldTypes,
  changeSizeFieldParameter, sizeFieldValues } from './linearSize'
const catalog = data as ParameterCatalog
const source = () => { const dto = createExampleDocument('basic-grid', 'fields'); dto.document.canvas.mm_per_unit = .5; return dto }

describe('one field-driven size draft, Python catalog and legacy ownership', () => {
  it('uses actual scalar catalog, real type defaults and separate dimensional conversion', () => {
    expect(sizeFieldTypes(catalog).map(([id]) => id)).toEqual(Object.keys(catalog.definitions.field))
    let draft = selectSizeField(openLinearSize(source(), phase1aBounds), 'wave', catalog)
    expect(draft.fieldParameters).toEqual({ angle: 0, wavelength: 50, phase: 0, amplitude: 1, offset: 0, invert: false })
    expect(sizeFieldValues(draft, catalog).field_wavelength).toBe(25)
    draft = changeSizeFieldParameter(draft, catalog, 'field_wavelength', 17)
    expect(linearSizeOwner(linearSizeCandidate(draft, catalog))!.field.parameters).toHaveProperty('wavelength', 34)
    draft = selectSizeField(draft, 'stripe', catalog)
    expect(draft.fieldParameters).toHaveProperty('period', 50)
    expect(draft.fieldParameters).not.toHaveProperty('wavelength')
    expect(sizeFieldGroup(catalog, draft)!.parameters.every(p => p.id.startsWith('field_'))).toBe(true)
  })
  it('keeps one Size ID and effect order across Linear → Wave → Stripe → Linear and reopen', () => {
    let dto = source(), id: unknown
    for (const type of ['linear', 'wave', 'stripe', 'linear', 'wave']) {
      const before = JSON.stringify(dto)
      const draft = selectSizeField(openLinearSize(dto, phase1aBounds), type, catalog)
      Object.assign(draft.values, { min_output: .7, max_output: 1.1, strength: .8 })
      const candidate = linearSizeCandidate(draft, catalog)
      expect(JSON.stringify(dto)).toBe(before); expect(candidate.document_revision).toBe(dto.document_revision)
      expect(candidate.document.modifiers).toHaveLength(1)
      expect(candidate.document.elements).toBe(dto.document.elements); expect(candidate.document.transforms).toBe(dto.document.transforms)
      const owner = linearSizeOwner(candidate)!
      if (id) expect(owner.modifier.id).toBe(id)
      id = owner.modifier.id; expect(owner.field.type).toBe(type)
      dto = JSON.parse(JSON.stringify(candidate))
    }
    expect(dto.document.fields).toHaveLength(3)
    expect(openLinearSize(dto, phase1aBounds).fieldType).toBe('wave')
    expect(openLinearSize(dto, phase1aBounds).values.min_output).toBe(.7)
  })
  it('binds an unchanged existing Wave, but parameter edits isolate it and leave user/Fabric bindings unchanged', () => {
    const dto = source(), field = { id: 'user-wave', type: 'wave', enabled: true,
      parameters: { angle: 30, wavelength: 30, phase: .2, amplitude: 1, offset: 0, invert: false } }
    dto.document.fields.push(field)
    dto.document.modifiers.push({ id: 'user-rotation', type: 'rotation', field_id: field.id, mapping: { min_output: -5, max_output: 5 } })
    dto.document.metadata.fabric_config = { field_modifiers: { height: { enabled: true, field_id: field.id } } }
    let draft = selectSizeField(openLinearSize(dto, phase1aBounds), 'wave', catalog, field.id)
    expect(linearSizeOwner(linearSizeCandidate(draft, catalog))!.field.id).toBe(field.id)
    draft = changeSizeFieldParameter(draft, catalog, 'field_phase', 1)
    const copied = linearSizeCandidate(draft, catalog), owner = linearSizeOwner(copied)!
    expect(owner.field.id).not.toBe(field.id); expect(copied.document.fields[0]).toEqual(field)
    expect(copied.document.modifiers[0]).toEqual(dto.document.modifiers[0])
    expect(copied.document.metadata.fabric_config).toBe(dto.document.metadata.fabric_config)
    expect(copied.document.modifiers).toHaveLength(2)
    // Once the managed copy itself gains another consumer, copy-on-write again.
    copied.document.fields.push({ id: 'composite', type: 'composite', parameters: { input_a_field_id: owner.field.id } })
    const reopened = openLinearSize(copied, phase1aBounds)
    const isolated = linearSizeCandidate(changeSizeFieldParameter(reopened, catalog, 'field_phase', 2), catalog)
    expect(linearSizeOwner(isolated)!.field.id).not.toBe(owner.field.id)
    expect(isolated.document.fields.find(f => f.id === owner.field.id)).toEqual(owner.field)
  })
  it('saves an edited existing Linear projection domain, not refitting it after refresh', () => {
    const dto = source(); dto.document.fields.push({ id: 'custom-axis', type: 'linear', enabled: true, parameters: { angle: 22, start: -500, end: 600 } })
    const draft = changeSizeFieldParameter(selectSizeField(openLinearSize(dto, phase1aBounds), 'linear', catalog, 'custom-axis'), catalog, 'field_angle', 45)
    const copied = linearSizeCandidate(draft, catalog), reopened = openLinearSize(JSON.parse(JSON.stringify(copied)), phase1aBounds)
    expect(reopened.explicitLinear).toBe(true)
    expect(linearSizeOwner(linearSizeCandidate(reopened, catalog))!.field.parameters).toEqual({ angle: 45, start: -500, end: 600 })
    const wave = linearSizeCandidate(selectSizeField(reopened, 'wave', catalog), catalog)
    const back = selectSizeField(openLinearSize(wave, phase1aBounds), 'linear', catalog)
    expect(back.explicitLinear).toBe(true)
    expect(linearSizeOwner(linearSizeCandidate(back, catalog))!.field.parameters).toEqual({ angle: 45, start: -500, end: 600 })
  })
  it('switching field types keeps the real local rectangle, including legacy fitted linear direction', () => {
    let draft = openLinearSize(source(), phase1aBounds)
    Object.assign(draft.values, { scope_mode: 'local', angle: 47 })
    const before = linearSizeOwner(linearSizeCandidate(draft, catalog))!.modifier.region
    draft = selectSizeField(draft, 'wave', catalog)
    expect(linearSizeOwner(linearSizeCandidate(draft, catalog))!.modifier.region).toEqual(before)
    draft = selectSizeField(draft, 'linear', catalog)
    expect(linearSizeOwner(linearSizeCandidate(draft, catalog))!.modifier.region).toEqual(before)
  })
  it.each(['wave', 'stripe', 'checker', 'noise', 'ring', 'spiral', 'constant'])('keeps local %s range on the consumer only, persisted in native coordinates', type => {
    const draft = selectSizeField(openLinearSize(source(), phase1aBounds), type, catalog)
    Object.assign(draft.values, { scope_mode: 'local', center_x: 40, center_y: 50, length: 20, width: 10, scope_angle: 35, feather: 1 })
    const dto = linearSizeCandidate(draft, catalog), owner = linearSizeOwner(dto)!
    expect(owner.modifier.region).toEqual({ center_x: 80, center_y: 100, length: 40, width: 20, angle: 35, feather: 2 })
    expect(owner.field.parameters).not.toHaveProperty('region')
    const reopened = openLinearSize(JSON.parse(JSON.stringify(dto)), phase1aBounds)
    expect(reopened.values.scope_angle).toBe(35)
    expect(linearSizeOwner(linearSizeCandidate(reopened, catalog))!.modifier.region).toEqual(owner.modifier.region)
  })
  it.each(['image', 'distance'])('%s requires an explicit real asset and preserves sample bounds and mm distance semantics', type => {
    const draft = selectSizeField(openLinearSize(source(), phase1aBounds), type, catalog)
    expect(() => linearSizeCandidate(draft, catalog)).toThrow('有效的 PNG/JPG')
    draft.imageAsset = { role: '', asset_id: 'explicit-token', media_type: 'image/png' }
    const dto = linearSizeCandidate(draft, catalog), field = linearSizeOwner(dto)!.field
    expect(field.parameters).toHaveProperty('sample_bounds', [0, 0, 60, 60])
    expect(dto.assets[0]).toEqual({ ...draft.imageAsset, role: `field:${field.id}` })
    expect(dto.document.reference).toEqual(draft.source.document.reference)
    if (type === 'distance') expect(sizeFieldValues(draft, catalog).field_max_distance_mm).toBe(10)
  })
})
