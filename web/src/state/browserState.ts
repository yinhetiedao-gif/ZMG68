/** Ephemeral browser controls only. No PatternDocumentDTO data is stored here. */
export type WorkspaceMode = 'design' | 'manufacture' | 'preview'

export interface BrowserState {
  activeMode: WorkspaceMode
  sidebarOpen: boolean
  inspectorOpen: boolean
  selectionId: string | null
  hoveredId: string | null
  zoom: number
  panX: number
  panY: number
}

export const initialBrowserState: BrowserState = {
  activeMode: 'design',
  sidebarOpen: true,
  inspectorOpen: true,
  selectionId: null,
  hoveredId: null,
  zoom: 1,
  panX: 0,
  panY: 0,
}
