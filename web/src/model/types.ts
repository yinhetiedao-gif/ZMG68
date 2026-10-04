export type GeometryType = 'circle' | 'ellipse' | 'rect' | 'path' | 'filled_region'

export interface CanvasDocument {
  width: number
  height: number
  unit: string
  mm_per_unit?: number | null
  origin_x?: number
  origin_y?: number
}

export interface SourceElement {
  id: string
  type: GeometryType
  x: number
  y: number
  width: number
  height: number
  rotation: number
  visible: boolean
  style?: Record<string, unknown>
  path_data?: string
  [key: string]: unknown
}

export interface PatternDocument {
  schema_version: number
  canvas: CanvasDocument
  reference: Record<string, unknown>
  elements: SourceElement[]
  groups: unknown[]
  transforms: Record<string, Record<string, unknown>>
  metadata: Record<string, unknown>
  fields: Record<string, unknown>[]
  modifiers: Record<string, unknown>[]
}

export interface PatternDocumentDTO {
  schema_version: '1.0'
  document_id: string
  document_revision: number
  document: PatternDocument
  assets: { role: string; asset_id: string; media_type: string }[]
}

export interface BoundsMM {
  min_x: number
  min_y: number
  max_x: number
  max_y: number
  width: number
  height: number
  units: 'mm'
}

export interface FinalGeometry {
  id: string
  type: GeometryType
  x: number
  y: number
  width: number
  height: number
  rotation: number
  units: 'mm'
  style?: Record<string, unknown>
  rx?: number
  ry?: number
  path_data?: string
  path_data_coordinate_system?: 'element_local'
  source_transform?: string
  base_x?: number
  base_y?: number
  base_width?: number
  base_height?: number
}

export interface EvaluateResponse {
  schema_version: '1.0'
  document_id: string
  document_revision: number
  geometry: FinalGeometry[]
  bounds_mm: BoundsMM | null
  warnings: string[]
}
