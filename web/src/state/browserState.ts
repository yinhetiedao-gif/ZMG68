import { initialView, type ViewTransform } from '../geometry/view'

/** Ephemeral browser controls only. No PatternDocumentDTO data is stored here. */
export type WorkspaceMode = 'design' | 'manufacture' | 'preview'

export interface BrowserState {
  activeMode: WorkspaceMode
  sidebarOpen: boolean
  inspectorOpen: boolean
  selectedElementIds: string[]
  hoveredId: string | null
  viewTransform: ViewTransform
}

export const initialBrowserState: BrowserState = {
  activeMode: 'design',
  sidebarOpen: true,
  inspectorOpen: true,
  selectedElementIds: [],
  hoveredId: null,
  viewTransform: initialView,
}
