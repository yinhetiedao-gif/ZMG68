import { useEffect, useId, useRef, useState, type ReactNode } from 'react'

export function InspectorSection({ title, label, activeKey, defaultExpanded = true, children }: {
  title: string; label: string; activeKey?: string | null; defaultExpanded?: boolean; children: ReactNode
}) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  const mounted = useRef(false)
  const contentId = useId()
  useEffect(() => {
    if (mounted.current && activeKey) setExpanded(true)
    mounted.current = true
  }, [activeKey])
  return <section className="inspector-section" aria-label={label}>
    <h3><button type="button" className="section-toggle" aria-expanded={expanded} aria-controls={contentId}
      onClick={() => setExpanded((current) => !current)}>
      <span aria-hidden="true">{expanded ? '▾' : '▸'}</span> {title}
    </button></h3>
    <div id={contentId} hidden={!expanded}>{children}</div>
  </section>
}
