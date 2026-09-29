// Browser-only proposal: Python creates geometry; React edits declared parameters.
import type { PatternDocumentDTO } from '../model/types'
import type { PatternFamily } from '../api/pattern'
import type { ParameterCatalog } from './parameterSchema'
import { updateGrid, updateLayout } from './editor'
import { asRecord, layoutModel } from './selectors'

export interface LayoutDraft {
  family: PatternFamily
  sourceRevision: number
  proposal: PatternDocumentDTO | null
  changed: boolean
}

export function currentLayoutFamily(dto: PatternDocumentDTO): PatternFamily {
  const state = asRecord(dto.document.metadata['xiaomang_pattern_lab.parametric'])
  const mode = String(state?.mode ?? layoutModel(dto)?.mode ?? '')
  return mode === 'grid' || mode === 'radial' || mode === 'along_curve' ? mode : 'free'
}

export function initialLayoutDraft(dto: PatternDocumentDTO): LayoutDraft {
  const family = currentLayoutFamily(dto)
  return { family, sourceRevision: dto.document_revision,
    proposal: family === 'free' ? null : dto, changed: false }
}

export function editLayoutDraft(draft: LayoutDraft, key: string, value: number | boolean,
  catalog: ParameterCatalog | null): LayoutDraft {
  if (!draft.proposal) throw new Error('布局提案尚未准备完成。')
  const proposal = draft.family === 'grid' && typeof value === 'number'
    ? updateGrid(draft.proposal, key, value, catalog)
    : updateLayout(draft.proposal, key, value, catalog)
  return { ...draft, proposal, changed: draft.changed || proposal !== draft.proposal }
}

export function layoutCommitDocument(draft: LayoutDraft, source: PatternDocumentDTO): PatternDocumentDTO | null {
  if (draft.sourceRevision !== source.document_revision) throw new Error('布局提案已过期，请重新选择布局。')
  if (!draft.proposal || (!draft.changed && draft.proposal === source)) return null
  return { ...draft.proposal, document_revision: source.document_revision + 1 }
}
