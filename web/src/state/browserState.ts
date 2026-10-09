import { initialView, type ViewTransform } from '../geometry/view'

/** Ephemeral browser controls only. No PatternDocumentDTO data is stored here. */
export type WorkspaceMode = 'design' | 'manufacture'

/** Old links/ephemeral sessions pointed at the removed third workspace. */
export function normalizeWorkspaceMode(value: unknown): WorkspaceMode {
  return value === 'manufacture' || value === 'preview' ? 'manufacture' : 'design'
}

export function workspaceModeFromLocation(): WorkspaceMode {
  if (typeof location === 'undefined') return 'design'
  return normalizeWorkspaceMode(new URLSearchParams(location.search).get('mode') ?? location.hash.replace(/^#/, ''))
}

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
