import { useCallback, useEffect, useState } from 'react'
import {
  BackendOfflineError,
  checkBackend,
  ContractMismatchError,
  EXPECTED_SCHEMA_VERSION,
} from './api/client'
import { initialBrowserState, type WorkspaceMode } from './state/browserState'

type ConnectionState =
  | { kind: 'checking'; message: string }
  | { kind: 'online'; message: string }
  | { kind: 'offline'; message: string }
  | { kind: 'incompatible'; message: string }

const sourceItems = [
  { label: '图片 Image', mark: '▧' },
  { label: '矢量 SVG', mark: '◇' },
  { label: '基础形状 Shapes', mark: '◯' },
]

const patternItems = [
  { label: '规则矩阵 Grid', mark: '▦' },
  { label: '放射 Radial', mark: '✳' },
  { label: '曲线 Curve', mark: '〰' },
  { label: '自由布局 Free', mark: '⌁' },
]

const modes: { id: WorkspaceMode; label: string; secondary: string }[] = [
  { id: 'design', label: '设计', secondary: 'Design' },
  { id: 'manufacture', label: '制造', secondary: 'Manufacture' },
  { id: 'preview', label: '三维预览', secondary: '3D Preview' },
]

function SideGroup({ title, index, items }: {
  title: string
  index: string
  items: { label: string; mark: string }[]
}) {
  return (
    <section className="side-group" aria-label={title}>
      <div className="group-heading"><span>{index}</span><h2>{title}</h2></div>
      <div className="side-items">
        {items.map((item) => (
          <button className="side-item" key={item.label} type="button" disabled title="即将开放">
            <span className="side-item-mark" aria-hidden="true">{item.mark}</span>
            <span>{item.label}</span>
            <span className="soon-dot" aria-hidden="true" />
          </button>
        ))}
      </div>
    </section>
  )
}

export function App() {
  const [connection, setConnection] = useState<ConnectionState>({ kind: 'checking', message: '正在连接后端…' })
  const [activeMode, setActiveMode] = useState<WorkspaceMode>(initialBrowserState.activeMode)
  const [retry, setRetry] = useState(0)

  const reconnect = useCallback(() => setRetry((value) => value + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    let current = true
    setConnection({ kind: 'checking', message: '正在连接后端…' })
    checkBackend(fetch, controller.signal).then(() => {
      if (current) setConnection({ kind: 'online', message: 'Backend Online' })
    }).catch((error: unknown) => {
      if (!current) return
      if (error instanceof ContractMismatchError) {
        setConnection({ kind: 'incompatible', message: error.message })
      } else if (error instanceof BackendOfflineError) {
        setConnection({ kind: 'offline', message: error.message })
      } else {
        setConnection({ kind: 'offline', message: '后端连接失败。' })
      }
    })
    return () => { current = false; controller.abort() }
  }, [retry])

  const connected = connection.kind === 'online'
  const modeName = modes.find((mode) => mode.id === activeMode)?.label ?? '设计'

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-symbol" aria-hidden="true"><span /><span /><span /><span /></div>
          <div className="brand-copy">
            <strong>Xiaomang Pattern Lab</strong>
            <span>小芒图案实验室</span>
          </div>
          <span className="alpha-tag">WEB ALPHA</span>
        </div>
        <div className="project-name" aria-label="当前项目"><span>项目</span><strong>Untitled</strong><span className="project-unsaved">未创建</span></div>
        <div className="top-status">
          <div className={`backend-badge ${connection.kind}`} role="status" aria-live="polite">
            <span className="status-light" aria-hidden="true" />
            {connected ? 'Backend Online' : connection.kind === 'checking' ? '正在连接' : connection.kind === 'offline' ? 'Backend Offline' : 'Contract Error'}
          </div>
          <div className={`contract-badge ${connected ? 'verified' : ''}`}>
            <span>CONTRACT</span><strong>{connected ? `v${EXPECTED_SCHEMA_VERSION}` : '待验证'}</strong>
          </div>
        </div>
      </header>

      <div className="work-area">
        <aside className="sidebar" aria-label="左侧工具栏">
          <div className="sidebar-intro"><span className="eyebrow">WORKSPACE / 工作台</span><p>从灵感到结构，逐步形成可编辑图案。</p></div>
          <SideGroup title="素材来源" index="01" items={sourceItems} />
          <SideGroup title="图案结构" index="02" items={patternItems} />
          <div className="sidebar-footnote"><span className="footnote-icon">i</span><p>导入与绘制将在后续版本开放。此工作区目前仅验证 Web 与 Python 后端连接。</p></div>
        </aside>

        <main className="workspace" aria-label="中央工作区">
          <div className="workspace-toolbar">
            <div className="breadcrumb"><span>工作区</span><span className="crumb-divider">/</span><strong>{modeName}</strong></div>
            <div className="workspace-scale">CANVAS · 暂无文档</div>
          </div>
          <div className="canvas-stage">
            {activeMode === 'design' ? (
              <section className="empty-state" aria-label="空白设计工作区">
                <div className="orbit-art" aria-hidden="true"><div className="orbit-ring ring-one" /><div className="orbit-ring ring-two" /><div className="orbit-ring ring-three" /><span className="orbit-core" /><i className="orbit-dot dot-one" /><i className="orbit-dot dot-two" /><i className="orbit-dot dot-three" /></div>
                <span className="empty-kicker">A NEW CANVAS AWAITS</span>
                <h1>拖入图片或打开项目</h1>
                <p>这里将成为你的二维设计画布。导入与编辑功能即将开放。</p>
                <button type="button" disabled className="primary-disabled">打开项目 · 即将开放</button>
                <span className="empty-hint">WM4 · Web 工作区基础版</span>
              </section>
            ) : (
              <section className="empty-state future-state" aria-label={`${modeName}即将开放`}>
                <div className="future-mark" aria-hidden="true">{activeMode === 'manufacture' ? '▤' : '◇'}</div>
                <span className="empty-kicker">NEXT WORKSPACE</span>
                <h1>{modeName} · 即将开放</h1>
                <p>当前仅提供模式导航；没有启动制造、生成模型或展示三维预览。</p>
              </section>
            )}
          </div>
          <nav className="mode-bar" aria-label="工作模式">
            <div className="mode-label">模式</div>
            {modes.map((mode) => (
              <button key={mode.id} type="button" className={`mode-button ${activeMode === mode.id ? 'selected' : ''}`}
                aria-label={`${mode.label} ${mode.secondary}`}
                aria-current={activeMode === mode.id ? 'page' : undefined}
                onClick={() => setActiveMode(mode.id)}>
                <span>{mode.label}</span><small>{mode.secondary}</small>
                {mode.id !== 'design' && <em>COMING SOON</em>}
              </button>
            ))}
            <span className="mode-bar-spacer" />
            <span className="mode-version">WM4 / SHELL</span>
          </nav>
        </main>

        <aside className="inspector" aria-label="右侧检查器">
          <div className="inspector-title"><div><span className="eyebrow">PROPERTIES</span><h2>检查器</h2></div><span className="inspector-dots" aria-hidden="true">•••</span></div>
          <div className="inspector-empty"><span className="inspect-glyph" aria-hidden="true">⌗</span><strong>未选择对象</strong><p>No selection</p><small>选择一个元素后，参数将显示在这里。</small></div>
          <div className={`connection-card ${connection.kind}`}>
            <div className="connection-card-head"><span>连接状态</span><span className="connection-state-text">{connected ? '已连接' : connection.kind === 'checking' ? '检查中' : connection.kind === 'offline' ? '离线' : '协议不兼容'}</span></div>
            <p>{connected ? 'Python Engine 已就绪，合同 v1.0 · mm 验证通过。' : connection.message}</p>
            {!connected && connection.kind !== 'checking' && <button type="button" onClick={reconnect}>重新检测连接</button>}
          </div>
        </aside>
      </div>
    </div>
  )
}
