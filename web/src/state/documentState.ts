import type { BoundsMM, FinalGeometry, PatternDocumentDTO } from '../model/types'

export interface DocumentState {
  currentDocument: PatternDocumentDTO | null
  documentRevision: number
  fileName: string | null
  finalGeometry: FinalGeometry[]
  bounds: BoundsMM | null
  evaluateStatus: 'idle' | 'loading' | 'ready' | 'error'
  evaluateError: string | null
  warnings: string[]
}

export const initialDocumentState: DocumentState = {
  currentDocument: null,
  documentRevision: 0,
  fileName: null,
  finalGeometry: [],
  bounds: null,
  evaluateStatus: 'idle',
  evaluateError: null,
  warnings: [],
}
