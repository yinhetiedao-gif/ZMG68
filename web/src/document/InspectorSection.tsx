import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { PanelIcon, type PanelIconName } from '../ui/PanelIcon'

export function InspectorSection({ title, label, icon, activeKey, defaultExpanded = true, hidden = false, expanded: controlledExpanded, onExpandedChange, children }: {
  title: string; label: string; activeKey?: string | null; defaultExpanded?: boolean; hidden?: boolean; children: ReactNode
  icon?: PanelIconName
  expanded?: boolean; onExpandedChange?: (expanded: boolean) => void
}) {
  const [localExpanded, setLocalExpanded] = useState(defaultExpanded)
  const expanded = controlledExpanded ?? localExpanded
  const setExpanded = (next: boolean) => {
    if (onExpandedChange) onExpandedChange(next)
    else setLocalExpanded(next)
  }
  const mounted = useRef(false)
  const contentId = useId()
  useEffect(() => {
    if (mounted.current && activeKey) setExpanded(true)
    mounted.current = true
  }, [activeKey])
  return <section className={`inspector-section${icon ? ' parameter-card' : ''}`} aria-label={label} hidden={hidden}>
    <h3><button type="button" className="section-toggle" aria-expanded={expanded} aria-controls={contentId}
      onClick={() => setExpanded(!expanded)}>
      {icon && <PanelIcon name={icon} />}
      <span className="section-title">{title}</span>
      <PanelIcon name="chevron" className="disclosure-chevron" />
    </button></h3>
    <div id={contentId} hidden={!expanded}>{children}</div>
  </section>
}
