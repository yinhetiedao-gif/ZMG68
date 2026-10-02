import { describe, expect, it } from 'vitest'
import type { PatternDocumentDTO } from '../model/types'
import type { ParameterCatalog, ParameterDefinition } from './parameterSchema'
import { applyFabricPreset, fabricPresets } from './fabricPresets'
import { fabricDesignWarnings, fabricPreviewSummary } from './fabricDesignSummary'
import type { FabricDesignPreview } from '../api/fabricPreview'
import { restoreSnapshot } from './editor'

const number = (id: string, value: number): ParameterDefinition => ({ id, label: id,
  type: 'number', default: value, value, min: id === 'margin_mm' || id === 'threshold' ? 0 : -360,
  max: id === 'threshold' ? 1 : 10000, step: .1, unit: '', options: [] })
const group = (values: Record<string, number>) => ({ label: 'test', parameters:
  Object.entries(values).map(([key, value]) => number(key, value)) })
const catalog = { schema_version: '1.0', units: 'mm', definitions: {
  layout: {}, modifier: {}, field: {
    wave: group({ angle: 0, wavelength: 50, phase: 0, amplitude: 1, offset: 0 }),
    linear: group({ angle: 0, start: 0, end: 100 }),
    noise: group({ scale: 50, strength: 1, seed: 1, offset_x: 0, offset_y: 0, octaves: 3, contrast: 1 }),
  },
  fabric_base: { solid: group({ thickness_mm: .6, margin_mm: 0 }),
    grid: group({ thickness_mm: .6, spacing_x_mm: 5, spacing_y_mm: 5, line_width_mm: 1, margin_mm: 0 }) },
  fabric_cell: Object.fromEntries(['cylinder', 'cone', 'pyramid', 'double_tower', 'fin'].map((type) =>
    [type, group({ width_mm: 2, depth_mm: 2, height_mm: 3 })])),
  fabric_placement: { regular: group({ spacing_x_mm: 5, spacing_y_mm: 5 }) },
  fabric_modifier: { height: group({ min_height_mm: 1, max_height_mm: 5 }),
    scale: group({ min_scale: .5, max_scale: 1.5 }), density: group({ threshold: .5 }),
    orientation: group({ min_angle_deg: -45, max_angle_deg: 45 }) },
} } as ParameterCatalog
const dto = { schema_version: '1.0', document_id: 'fabric-preset', document_revision: 8, assets: [],
  document: { schema_version: 1, canvas: { width: 50, height: 40, unit: 'mm' }, reference: {},
    elements: [{ id: 'element-1', type: 'rect', x: 4, y: 5, width: 2, height: 2,
      rotation: 0, visible: true }], groups: [], transforms: {}, fields: [], modifiers: [], metadata: {} },
} as PatternDocumentDTO

describe('F3.5 Fabric presets', () => {
  it.each(fabricPresets)('$label applies deterministically in one revision without editing source', (preset) => {
    const first = applyFabricPreset(dto, preset.id, catalog)
    const second = applyFabricPreset(dto, preset.id, catalog)
    expect(first).toEqual(second)
    expect(first.document_revision).toBe(dto.document_revision + 1)
    expect(first.document.elements).toBe(dto.document.elements)
    expect(dto.document.metadata).toEqual({})
    expect(first.document.metadata.fabric_config).toMatchObject({ base: preset.base,
      placement: preset.placement, unit_cell: preset.cell })
    const modifiers = (first.document.metadata.fabric_config as Record<string, unknown>).field_modifiers as Record<string, { field_id: string }>
    expect(Object.values(modifiers).every((modifier) => first.document.fields.some((field) => field.id === modifier.field_id))).toBe(true)
    const undone = restoreSnapshot(dto, first.document_revision)
    expect(undone.document).toEqual(dto.document)
    expect(undone.document_revision).toBe(dto.document_revision + 2)
  })

  it('reuses an active field and replaces only Fabric design configuration', () => {
    const initial = applyFabricPreset(dto, 'soft-texture', catalog)
    const next = applyFabricPreset(initial, 'wave-textile', catalog)
    expect(next.document_revision).toBe(initial.document_revision + 1)
    expect(next.document.fields.length).toBe(1)
    expect(next.document.fields[0].id).toBe(initial.document.fields[0].id)
    expect(next.document.elements).toBe(initial.document.elements)
  })

  it('reports summary and nonblocking design risks without mutating geometry', () => {
    const preset = applyFabricPreset(dto, 'wave-textile', catalog)
    const summary = fabricPreviewSummary(preset, null)
    expect(summary).toMatchObject({ cell: 'fin', height: '1–6 mm', placement: 'Area Fill', preview: '待更新' })
    expect(fabricDesignWarnings(preset)).toEqual([])
    const risky = { ...preset, document: { ...preset.document, metadata: { fabric_config: {
      ...(preset.document.metadata.fabric_config as Record<string, unknown>),
      base: { type: 'solid', thickness_mm: .1, margin_mm: 0 },
      placement: { mode: 'area_fill', spacing_x_mm: .7, spacing_y_mm: 5 },
      field_modifiers: { height: { enabled: true, max_height_mm: 9 },
        scale: { enabled: true, min_scale: .2 }, density: { enabled: true, threshold: .9 } },
    } } } } as PatternDocumentDTO
    expect(fabricDesignWarnings(risky)).toHaveLength(4)
    expect(risky.document.elements).toBe(dto.document.elements)
    const measured = fabricPreviewSummary(preset, { active_count: 2, preview_simplified: false,
      instances: [
        { enabled: true, height_mm: 2, scale: 1, scale_x: .5, scale_y: 1 },
        { enabled: true, height_mm: 4, scale: 2, scale_x: 1, scale_y: 1 },
      ] } as FabricDesignPreview)
    expect(measured).toMatchObject({ instances: 2, height: '2–4 mm', scale: '0.5–2', preview: 'Full' })
  })
})
