import type { ReactNode } from 'react'

export type PanelIconName = 'layout' | 'radial' | 'curve' | 'free' | 'presets' | 'fields' | 'controls' | 'size' | 'assets' | 'vector' | 'shape' | 'height' | 'output' | 'manufacture' | 'chevron'

// Shared presentation only: these icons carry no document or selection state.
const paths: Record<PanelIconName, ReactNode> = {
  layout: <><rect x="3" y="3" width="6" height="6" rx="1" /><rect x="15" y="3" width="6" height="6" rx="1" /><rect x="3" y="15" width="6" height="6" rx="1" /><rect x="15" y="15" width="6" height="6" rx="1" /></>,
  radial: <><circle cx="12" cy="12" r="3" /><circle cx="12" cy="12" r="9" /><path d="M12 3v3m9 6h-3m-6 9v-3m-9-6h3" /></>,
  curve: <><path d="M4 18C4 5 20 19 20 6" /><circle cx="4" cy="18" r="2" /><circle cx="20" cy="6" r="2" /></>,
  free: <><circle cx="5" cy="6" r="2" /><rect x="15" y="4" width="5" height="5" rx="1" /><path d="m10 13 4 7H6Z" /></>,
  presets: <><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 3v18M3 9h18M15 9v12M9 15h12" /></>,
  fields: <><path d="m3 8 9-5 9 5-9 5ZM3 12l9 5 9-5M3 16l9 5 9-5" /></>,
  controls: <><path d="M3 6h6m4 0h8M3 12h11m4 0h3M3 18h3m4 0h11" /><circle cx="11" cy="6" r="2" /><circle cx="16" cy="12" r="2" /><circle cx="8" cy="18" r="2" /></>,
  size: <><rect x="3" y="13" width="6" height="6" rx="1" /><rect x="13" y="5" width="8" height="8" rx="1" /><path d="m6 9 4-4m-4 0h4v4" /></>,
  assets: <><rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="8" cy="9" r="1.5" /><path d="m3 17 5-5 4 4 4-7 5 8" /></>,
  vector: <><path d="m12 3 9 9-9 9-9-9Z" /><path d="M12 7v10M7 12h10" /></>,
  shape: <><path d="m12 3 9 5v8l-9 5-9-5V8Zm-9 5 9 5 9-5M12 13v8" /></>,
  height: <><path d="M4 20V10h4v10m4 0V4h4v16m4 0V8M2 20h20" /></>,
  output: <><path d="m3 16 9-5 9 5-9 5ZM3 11l9-5 9 5M3 6l9-3 9 3" /></>,
  manufacture: <><path d="M8 3h8v5H8Zm-4 8h16v9H4ZM8 15h8M8 18h5" /><path d="M8 8v3m8-3v3" /></>,
  chevron: <path d="m9 5 7 7-7 7" />,
}

export function PanelIcon({ name, className = '' }: { name: PanelIconName; className?: string }) {
  return <svg className={`panel-icon ${className}`} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    {paths[name]}
  </svg>
}
