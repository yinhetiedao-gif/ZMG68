import { useEffect, useId, useState, type ReactNode } from 'react'

export function InspectorSection({ title, label, activeKey, children }: {
  title: string; label: string; activeKey?: string | null; children: ReactNode
}) {
  const [expanded, setExpanded] = useState(true)
  const contentId = useId()
  useEffect(() => { if (activeKey) setExpanded(true) }, [activeKey])
  return <section className="inspector-section" aria-label={label}>
    <h3><button type="button" className="section-toggle" aria-expanded={expanded} aria-controls={contentId}
      onClick={() => setExpanded((current) => !current)}>
      <span aria-hidden="true">{expanded ? '▾' : '▸'}</span> {title}
    </button></h3>
    <div id={contentId} hidden={!expanded}>{children}</div>
  </section>
}
