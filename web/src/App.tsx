import { useCallback, useEffect, useRef, useState, type ChangeEvent } from 'react'
import {
  BackendOfflineError, checkBackend, ContractMismatchError, EXPECTED_SCHEMA_VERSION,
} from './api/client'
import { evaluateDocument } from './api/evaluate'
import { importImage } from './api/import'
import { analyzePattern, preparePattern, runPatternAction, type PatternAnalysis, type PatternFamily } from './api/pattern'
import { Workspace2D } from './geometry/Workspace2D'
import { InspectorControls, type EditAction } from './document/InspectorControls'
import type { ParameterCatalog } from './document/parameterSchema'
import { currentLayoutFamily, editLayoutDraft, initialLayoutDraft, layoutCommitDocument, type LayoutDraft } from './document/layoutDraft'
import {
  restoreSnapshot, updateElement, updateField, updateGrid, updateLayout, updateReplacement,
  updateScalarModifier, updateStackModifier,
} from './document/editor'
import type { FinalGeometry, PatternDocumentDTO } from './model/types'
import {
  directSourceElement, millimetresPerUnit, moveSourceElement,
  prepareProject, withMillimetreMapping,
} from './model/project'
import { initialBrowserState, type WorkspaceMode } from './state/browserState'
import { initialDocumentState } from './state/documentState'

type ConnectionState =
  | { kind: 'checking'; message: string }
  | { kind: 'online'; message: string }
  | { kind: 'offline'; message: string }
  | { kind: 'incompatible'; message: string }

const patternItems = [
  { id: 'grid', label: '规则矩阵 Grid', mark: '▦' },
  { id: 'radial', label: '放射 Radial', mark: '✳' },
  { id: 'along_curve', label: '曲线 Curve', mark: '〰' },
  { id: 'free', label: '自由布局 Free', mark: '⌁' },
] satisfies { id: PatternFamily; label: string; mark: string }[]
const modes: { id: WorkspaceMode; label: string; secondary: string }[] = [
  { id: 'design', label: '设计', secondary: 'Design' },
  { id: 'manufacture', label: '制造', secondary: 'Manufacture' },
  { id: 'preview', label: '三维预览', secondary: '3D Preview' },
]

export function App() {
  const [connection, setConnection] = useState<ConnectionState>({ kind: 'checking', message: '正在连接后端…' })
  const [parameterCatalog, setParameterCatalog] = useState<ParameterCatalog | null>(null)
  const [retry, setRetry] = useState(0)
  const [browser, setBrowser] = useState(initialBrowserState)
  const [project, setProject] = useState(initialDocumentState)
  const [projectError, setProjectError] = useState<string | null>(null)
  const [mapping, setMapping] = useState<{ dto: PatternDocumentDTO; fileName: string; warnings: string[] } | null>(null)
  const [mappingValue, setMappingValue] = useState('')
  const [pendingPreview, setPendingPreview] = useState<{ id: string; dx: number; dy: number } | null>(null)
  const [fitToken, setFitToken] = useState(0)
  const historyRef = useRef<{ past: PatternDocumentDTO[]; future: PatternDocumentDTO[] }>({ past: [], future: [] })
  const [historyCount, setHistoryCount] = useState({ past: 0, future: 0 })
  const inputRef = useRef<HTMLInputElement>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)
  const svgInputRef = useRef<HTMLInputElement>(null)
  const [importing, setImporting] = useState(false)
  const evaluateController = useRef<AbortController | null>(null)
  const evaluateSequence = useRef(0)
  const analyzeController = useRef<AbortController | null>(null)
  const analyzeSequence = useRef(0)
  const analyzeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [patternAnalysis, setPatternAnalysis] = useState<PatternAnalysis | null>(null)
  const [analysisStatus, setAnalysisStatus] = useState<'idle' | 'stale' | 'loading' | 'ready' | 'error'>('idle')
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [applyingPattern, setApplyingPattern] = useState(false)
  const applyingPatternRef = useRef(false)
  const [selectedFamily, setSelectedFamily] = useState<PatternFamily | null>(null)
  const [layoutDraft, setLayoutDraft] = useState<LayoutDraft | null>(null)
  const [preparingLayout, setPreparingLayout] = useState(false)
  const layoutSequence = useRef(0)
  const activeDocumentRef = useRef<PatternDocumentDTO | null>(null)

  const reconnect = useCallback(() => setRetry((value) => value + 1), [])
  const publishHistory = (next: { past: PatternDocumentDTO[]; future: PatternDocumentDTO[] }) => {
    historyRef.current = next
    setHistoryCount({ past: next.past.length, future: next.future.length })
  }
  useEffect(() => {
    const controller = new AbortController()
    let current = true
    setConnection({ kind: 'checking', message: '正在连接后端…' })
    checkBackend(fetch, controller.signal).then(({ contract }) => {
      if (current) {
        setParameterCatalog(contract.parameter_definitions?.schema_version === '1.0' &&
          contract.parameter_definitions.units === 'mm' ? contract.parameter_definitions : null)
        setConnection({ kind: 'online', message: 'Backend Online' })
      }
    }).catch((error: unknown) => {
      if (!current) return
      if (error instanceof ContractMismatchError) setConnection({ kind: 'incompatible', message: error.message })
      else if (error instanceof BackendOfflineError) setConnection({ kind: 'offline', message: error.message })
      else setConnection({ kind: 'offline', message: '后端连接失败。' })
    })
    return () => { current = false; controller.abort() }
  }, [retry])
  useEffect(() => () => evaluateController.current?.abort(), [])
  useEffect(() => () => {
    analyzeController.current?.abort()
    if (analyzeTimer.current) clearTimeout(analyzeTimer.current)
  }, [])

  const invalidatePatternAnalysis = useCallback(() => {
    if (analyzeTimer.current) clearTimeout(analyzeTimer.current)
    analyzeTimer.current = null
    analyzeController.current?.abort()
    ++analyzeSequence.current
    setAnalysisStatus('stale')
    setAnalysisError(null)
  }, [])

  const requestPatternAnalysis = useCallback((dto: PatternDocumentDTO, delayMs = 0) => {
    invalidatePatternAnalysis()
    const sequence = analyzeSequence.current
    const start = () => {
      if (sequence !== analyzeSequence.current) return
      analyzeTimer.current = null
      const controller = new AbortController()
      analyzeController.current = controller
      setAnalysisStatus('loading')
      void analyzePattern(dto, controller.signal).then((result) => {
        if (sequence !== analyzeSequence.current) return
        setPatternAnalysis(result)
        setAnalysisStatus('ready')
      }).catch((error: unknown) => {
        if (controller.signal.aborted || sequence !== analyzeSequence.current) return
        setAnalysisStatus('error')
        setAnalysisError(error instanceof Error ? error.message : '图案分析失败。')
      })
    }
    if (delayMs > 0) analyzeTimer.current = setTimeout(start, delayMs)
    else start()
  }, [invalidatePatternAnalysis])

  const runEvaluate = useCallback((dto: PatternDocumentDTO, options: {
    fileName?: string; warnings?: string[]; fitOnSuccess?: boolean
    rollback?: PatternDocumentDTO
    onFailure?: () => void
    analyzeDelayMs?: number
  } = {}) => {
    evaluateController.current?.abort()
    invalidatePatternAnalysis()
    activeDocumentRef.current = dto
    const controller = new AbortController()
    evaluateController.current = controller
    const sequence = ++evaluateSequence.current
    setProject((current) => ({
      ...current, currentDocument: dto, documentRevision: dto.document_revision,
      fileName: options.fileName ?? current.fileName,
      warnings: options.warnings ?? current.warnings,
      evaluateStatus: 'loading', evaluateError: null,
      ...(options.fitOnSuccess ? { finalGeometry: [], bounds: null } : {}),
    }))
    void evaluateDocument(dto, controller.signal).then((result) => {
      if (sequence !== evaluateSequence.current) return
      setProject((current) => ({
        ...current, finalGeometry: result.geometry, bounds: result.bounds_mm,
        evaluateStatus: 'ready', evaluateError: null,
        warnings: [...new Set([...current.warnings, ...result.warnings])],
      }))
      setPendingPreview(null)
      if (options.fitOnSuccess) setFitToken((value) => value + 1)
      requestPatternAnalysis(dto, options.analyzeDelayMs ?? 400)
    }).catch((error: unknown) => {
      if (controller.signal.aborted || sequence !== evaluateSequence.current) return
      options.onFailure?.()
      activeDocumentRef.current = options.rollback ?? dto
      setProject((current) => ({
        ...current,
        currentDocument: options.rollback ?? current.currentDocument,
        documentRevision: options.rollback?.document_revision ?? current.documentRevision,
        evaluateStatus: 'error',
        evaluateError: error instanceof Error ? error.message : '二维求值失败。',
      }))
      setPendingPreview(null)
      if (options.rollback) requestPatternAnalysis(options.rollback, 400)
    })
  }, [invalidatePatternAnalysis, requestPatternAnalysis])

  const acceptProject = (dto: PatternDocumentDTO, fileName: string, warnings: string[]) => {
    setProjectError(null)
    ++layoutSequence.current
    setSelectedFamily(currentLayoutFamily(dto))
    setLayoutDraft(initialLayoutDraft(dto))
    setPreparingLayout(false)
    setMapping(null)
    publishHistory({ past: [], future: [] })
    setBrowser((current) => ({ ...current, selectedElementIds: [], activeMode: 'design' }))
    runEvaluate(dto, { fileName, warnings, fitOnSuccess: true, analyzeDelayMs: 0 })
  }
  const onFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    try {
      const identifier = globalThis.crypto?.randomUUID?.() ?? `web-${Date.now()}-${Math.random().toString(16).slice(2)}`
      const prepared = prepareProject(await file.text(), identifier)
      if (prepared.needsMillimetreMapping) {
        setMapping({ dto: prepared.dto, fileName: file.name, warnings: prepared.warnings })
        setMappingValue('')
        setProjectError(null)
      } else acceptProject(prepared.dto, file.name, prepared.warnings)
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : '无法读取项目。')
    }
  }
  const openImage = async (file: File) => {
    if (importing) return
    setImporting(true)
    setProjectError(null)
    try {
      const dto = await importImage(file)
      acceptProject(dto, file.name, dto.document.metadata.web_import_scale_unconfirmed
        ? ['导入图案暂按 1 原始单位 = 1 mm 显示；制造前必须确认真实尺寸。'] : [])
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : '导入图片失败。')
    } finally {
      setImporting(false)
    }
  }
  const onImageFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (file) void openImage(file)
  }
  const onDrop = (event: React.DragEvent<HTMLElement>) => {
    event.preventDefault()
    const file = event.dataTransfer.files[0]
    if (file) void openImage(file)
  }
  const confirmMapping = () => {
    if (!mapping) return
    try {
      acceptProject(withMillimetreMapping(mapping.dto, Number(mappingValue)), mapping.fileName, mapping.warnings)
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : '毫米映射无效。')
    }
  }
  const selectedId = browser.selectedElementIds[0] ?? null
  const selected = project.finalGeometry.find((item) => item.id === selectedId) ?? null
  const sourceCanDrag = (item: FinalGeometry) => {
    const dto = project.currentDocument
    const source = dto && directSourceElement(dto, item.id, item.x, item.y)
    return project.evaluateStatus === 'ready' && Boolean(source && source.type === item.type)
  }
  const commitDocument = (next: PatternDocumentDTO, before: PatternDocumentDTO) => {
    if (next === before || project.evaluateStatus === 'idle') return
    const previousHistory = historyRef.current
    publishHistory({ past: [...previousHistory.past, before], future: [] })
    setProjectError(null)
    ++layoutSequence.current
    setSelectedFamily(currentLayoutFamily(next))
    setLayoutDraft(initialLayoutDraft(next))
    setPreparingLayout(false)
    runEvaluate(next, { rollback: before, onFailure: () => {
      publishHistory(previousHistory)
      setSelectedFamily(currentLayoutFamily(before))
      setLayoutDraft(initialLayoutDraft(before))
    }, analyzeDelayMs: 400 })
  }
  const selectLayout = async (family: PatternFamily) => {
    const dto = project.currentDocument
    if (!dto || !connected || !hasEditableGeometry) return
    const sequence = ++layoutSequence.current
    setSelectedFamily(family)
    setProjectError(null)
    if (family === 'free') {
      setLayoutDraft({ family, sourceRevision: dto.document_revision, proposal: null, changed: false })
      setPreparingLayout(false)
      return
    }
    if (currentLayoutFamily(dto) === family) {
      setLayoutDraft(initialLayoutDraft(dto))
      setPreparingLayout(false)
      return
    }
    setLayoutDraft(null)
    setPreparingLayout(true)
    try {
      // An empty parameter set asks the existing Python engine for editable layout defaults.
      const result = await preparePattern(dto, family, {})
      if (sequence === layoutSequence.current && activeDocumentRef.current === dto)
        setLayoutDraft({ family, sourceRevision: dto.document_revision, proposal: result.proposed_document, changed: false })
    } catch (error) {
      if (sequence === layoutSequence.current) setProjectError(error instanceof Error ? error.message : '布局提案准备失败。')
    } finally {
      if (sequence === layoutSequence.current) setPreparingLayout(false)
    }
  }
  const applyLayout = async () => {
    const dto = project.currentDocument
    if (!dto || !layoutDraft || applyingPatternRef.current || project.evaluateStatus !== 'ready') return
    applyingPatternRef.current = true
    setApplyingPattern(true)
    try {
      if (layoutDraft.family === 'free') {
        if (currentLayoutFamily(dto) !== 'free') {
          const result = await runPatternAction(dto, 'bake')
          if (activeDocumentRef.current === dto) commitDocument(result, dto)
        }
      } else {
        const next = layoutCommitDocument(layoutDraft, dto)
        if (next) commitDocument(next, dto)
      }
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : '应用布局失败。')
    } finally {
      applyingPatternRef.current = false
      setApplyingPattern(false)
    }
  }
  const cancelLayout = () => {
    const dto = project.currentDocument
    if (!dto) return
    ++layoutSequence.current
    setSelectedFamily(currentLayoutFamily(dto))
    setLayoutDraft(initialLayoutDraft(dto))
    setPreparingLayout(false)
    setProjectError(null)
  }
  const commitDrag = (id: string, dx: number, dy: number) => {
    const dto = project.currentDocument
    const final = project.finalGeometry.find((item) => item.id === id)
    if (!dto || !final || !sourceCanDrag(final)) return
    try {
      const next = moveSourceElement(dto, id, dx, dy)
      setPendingPreview({ id, dx, dy })
      commitDocument(next, dto)
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : '无法拖动该元素。')
    }
  }
  const editParameter = (action: EditAction) => {
    const dto = project.currentDocument
    if (!dto || project.evaluateStatus !== 'ready') return
    try {
      let next: PatternDocumentDTO
      if (action.kind === 'grid') next = updateGrid(dto, action.key, action.value, parameterCatalog)
      else if (action.kind === 'layout') next = updateLayout(dto, action.key, action.value, parameterCatalog)
      else if (action.kind === 'element' && typeof action.value === 'number') {
        const final = project.finalGeometry.find((item) => item.id === action.id)
        if (!final || !sourceCanDrag(final)) throw new Error('该元素没有可靠的源映射，不能直接编辑。')
        next = updateElement(dto, action.id, action.key, action.value)
      } else if (action.kind === 'field') {
        next = updateField(dto, action.id, action.key, action.value, parameterCatalog)
      } else if (action.kind === 'scalar' && (typeof action.value === 'number' || typeof action.value === 'boolean')) {
        next = updateScalarModifier(dto, action.id, action.key, action.value, parameterCatalog)
      } else if (action.kind === 'stack' && (typeof action.value === 'number' || typeof action.value === 'boolean')) {
        next = updateStackModifier(dto, action.id, action.key, action.value)
      } else if (action.kind === 'shape' && typeof action.value === 'string') {
        next = updateReplacement(dto, action.id, action.value)
      } else throw new Error('不支持的编辑操作。')
      commitDocument(next, dto)
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : '参数修改失败。')
    }
  }
  const undo = () => {
    const dto = project.currentDocument
    const history = historyRef.current
    if (!dto || project.evaluateStatus !== 'ready' || !history.past.length) return
    const before = history.past[history.past.length - 1]
    publishHistory({ past: history.past.slice(0, -1), future: [...history.future, dto] })
    const restored = restoreSnapshot(before, dto.document_revision)
    ++layoutSequence.current
    setSelectedFamily(currentLayoutFamily(restored))
    setLayoutDraft(initialLayoutDraft(restored))
    runEvaluate(restored, {
      rollback: dto, onFailure: () => publishHistory(history),
    })
  }
  const redo = () => {
    const dto = project.currentDocument
    const history = historyRef.current
    if (!dto || project.evaluateStatus !== 'ready' || !history.future.length) return
    const after = history.future[history.future.length - 1]
    publishHistory({ past: [...history.past, dto], future: history.future.slice(0, -1) })
    const restored = restoreSnapshot(after, dto.document_revision)
    ++layoutSequence.current
    setSelectedFamily(currentLayoutFamily(restored))
    setLayoutDraft(initialLayoutDraft(restored))
    runEvaluate(restored, {
      rollback: dto, onFailure: () => publishHistory(history),
    })
  }

  const connected = connection.kind === 'online'
  const hasEditableGeometry = Boolean(project.currentDocument?.document.elements.some((element) =>
    element.visible && Number.isFinite(element.x) && Number.isFinite(element.y)
      && Number.isFinite(element.width) && Number.isFinite(element.height)
      && element.width > 0 && element.height > 0) && project.finalGeometry.length > 0)
  const modeName = modes.find((mode) => mode.id === browser.activeMode)?.label ?? '设计'
  const scale = project.currentDocument ? millimetresPerUnit(project.currentDocument.document) ?? 1 : 1
  const committedFamily = project.currentDocument ? currentLayoutFamily(project.currentDocument) : 'free'

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand-lockup">
        <div className="brand-symbol" aria-hidden="true"><span /><span /><span /><span /></div>
        <div className="brand-copy"><strong>Xiaomang Pattern Lab</strong><span>小芒图案实验室</span></div>
        <span className="alpha-tag">WEB ALPHA</span>
      </div>
      <div className="project-name" aria-label="当前项目">
        <span>项目</span><strong>{project.fileName ?? 'Untitled'}</strong>
        <span className="project-unsaved">{project.currentDocument ? `revision ${project.documentRevision}` : '未创建'}</span>
      </div>
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
        <div className="sidebar-intro"><span className="eyebrow">WORKSPACE / 工作台</span><p>打开项目，查看并移动可直接编辑的二维元素。</p></div>
        <button className="open-project-side" type="button" onClick={() => inputRef.current?.click()}>打开本地项目</button>
        <section className="side-group" aria-label="素材来源">
          <div className="group-heading"><span>01</span><h2>素材来源</h2></div>
          <div className="side-items">
            <button className="side-item" type="button" disabled={importing || !connected}
              onClick={() => imageInputRef.current?.click()}><span className="side-item-mark">▧</span>导入 PNG / JPG</button>
            <button className="side-item" type="button" disabled={importing || !connected}
              onClick={() => svgInputRef.current?.click()}><span className="side-item-mark">◇</span>导入 SVG</button>
            <button className="side-item" type="button" disabled title="即将开放"><span className="side-item-mark">◯</span>基础形状 Shapes</button>
          </div>
        </section>
        <section className="side-group" aria-label="图案结构">
          <div className="group-heading"><span>02</span><h2>图案结构</h2></div>
          <p className="pattern-analysis-status">自动识别仅提供推荐；布局由你选择。</p>
          <p className="pattern-analysis-status">当前结构：{patternItems.find((item) => item.id === committedFamily)?.label}</p>
          <div className="side-items">{patternItems.map((item) => {
            const available = Boolean(project.currentDocument && connected && !applyingPattern
              && (item.id === 'free' || hasEditableGeometry))
            const recommended = analysisStatus === 'ready'
              && patternAnalysis?.document_id === project.currentDocument?.document_id
              && patternAnalysis?.document_revision === project.documentRevision
              && patternAnalysis?.recommended_family === item.id
            return <button className={`side-item ${selectedFamily === item.id ? 'selected' : ''}`} key={item.id}
              type="button" disabled={!available} aria-pressed={selectedFamily === item.id}
              title={available ? '仅选择候选结构，不改变元素位置。' : '请先导入有效的二维图案。'}
              onClick={() => void selectLayout(item.id)}>
              <span className="side-item-mark" aria-hidden="true">{item.mark}</span>
              <span>{item.label}</span>{recommended && <small>推荐 {Math.round((patternAnalysis?.confidence ?? 0) * 100)}%</small>}
              {!available && <span className="soon-dot" aria-hidden="true" />}
            </button>
          })}</div>
          <p className="pattern-analysis-status" role="status">
            {analysisStatus === 'loading' ? '正在分析图案；结构仍可尝试使用。'
              : analysisStatus === 'stale' ? '图案已修改，推荐结果待更新；结构仍可使用。'
                : analysisStatus === 'ready' && patternAnalysis?.analysis_status === 'matched'
                  ? `推荐：${patternItems.find((item) => item.id === patternAnalysis?.recommended_family)?.label}（${Math.round((patternAnalysis?.confidence ?? 0) * 100)}%）`
                  : analysisStatus === 'ready' ? '暂无可靠推荐；可手动尝试图案结构。'
                    : analysisStatus === 'error' ? `分析失败：${analysisError}；结构仍可尝试使用。`
                      : '导入图案后自动分析结构。'}
          </p>
          {analysisStatus === 'ready' && patternAnalysis?.recommended_family &&
            <button type="button" disabled={!hasEditableGeometry} onClick={() => void selectLayout(patternAnalysis.recommended_family!)}>
              使用推荐
            </button>}
          {selectedFamily && <p className="pattern-analysis-status">已选布局：{patternItems.find((item) => item.id === selectedFamily)?.label}；应用前画布和项目不变。</p>}
          <div className="pattern-actions">
            <button type="button" disabled={!connected || !hasEditableGeometry || preparingLayout || applyingPattern
              || !layoutDraft || (selectedFamily === committedFamily && !layoutDraft.changed)}
              onClick={() => void applyLayout()}>应用布局</button>
            <button type="button" disabled={!project.currentDocument || preparingLayout || applyingPattern}
              onClick={cancelLayout}>取消布局</button>
          </div>
        </section>
        <div className="sidebar-footnote"><span className="footnote-icon">i</span><p>拖入 PNG/JPG/SVG 可由 Python 转换为独立元素；制造尚未开放。</p></div>
      </aside>

      <main className="workspace" aria-label="中央工作区">
        <div className="workspace-toolbar">
          <div className="breadcrumb"><span>工作区</span><span className="crumb-divider">/</span><strong>{modeName}</strong></div>
          <div className="workspace-scale">{project.currentDocument ? `CANVAS · ${project.finalGeometry.length} ELEMENTS · mm` : 'CANVAS · 暂无文档'}</div>
          <div className="history-actions"><button type="button" onClick={undo} disabled={!historyCount.past || project.evaluateStatus !== 'ready'}>撤销</button>
            <button type="button" onClick={redo} disabled={!historyCount.future || project.evaluateStatus !== 'ready'}>重做</button></div>
        </div>
        <div className="canvas-stage" onDragOver={(event) => event.preventDefault()} onDrop={onDrop}>
          {browser.activeMode === 'design' && project.currentDocument && project.evaluateStatus !== 'idle' ? (
            <Workspace2D geometry={project.finalGeometry} bounds={project.bounds} mmPerUnit={scale}
              view={browser.viewTransform}
              onViewChange={(viewTransform) => setBrowser((current) => ({ ...current, viewTransform }))}
              selectedId={selectedId}
              onSelect={(id) => setBrowser((current) => ({ ...current, selectedElementIds: id ? [id] : [] }))}
              canDrag={sourceCanDrag} onDragCommit={commitDrag} pendingPreview={pendingPreview} fitToken={fitToken} />
          ) : browser.activeMode === 'design' ? (
            <section className="empty-state" aria-label="空白设计工作区">
              <div className="orbit-art" aria-hidden="true"><div className="orbit-ring ring-one" /><div className="orbit-ring ring-two" /><div className="orbit-ring ring-three" /><span className="orbit-core" /><i className="orbit-dot dot-one" /><i className="orbit-dot dot-two" /><i className="orbit-dot dot-three" /></div>
              <span className="empty-kicker">A NEW CANVAS AWAITS</span>
              <h1>打开项目查看二维图案</h1>
              <p>读取本地 PatternDocument JSON，并由 Python 计算最终几何。</p>
              <button type="button" className="primary-action" onClick={() => inputRef.current?.click()}>打开项目</button>
              <span className="empty-hint">WM6 · Parametric Controls MVP</span>
            </section>
          ) : (
            <section className="empty-state future-state" aria-label={`${modeName}即将开放`}>
              <div className="future-mark" aria-hidden="true">{browser.activeMode === 'manufacture' ? '▤' : '◇'}</div>
              <span className="empty-kicker">NEXT WORKSPACE</span><h1>{modeName} · 即将开放</h1>
              <p>当前仅提供模式导航；没有启动制造、生成模型或展示三维预览。</p>
            </section>
          )}
          {project.evaluateStatus === 'loading' && <div className="viewer-notice" role="status">Python 正在计算最终二维几何…</div>}
          {importing && <div className="viewer-notice" role="status">Python 正在转换图片为可编辑元素…</div>}
          {project.evaluateError && <div className="viewer-error" role="alert">{project.evaluateError}</div>}
          {projectError && <div className="viewer-error" role="alert">{projectError}</div>}
          {project.warnings.length > 0 && <div className="viewer-warning" role="note">{project.warnings.join(' ')}</div>}
          {mapping && <div className="mapping-overlay" role="dialog" aria-label="设置毫米映射">
            <div className="mapping-card">
              <h2>项目缺少毫米映射</h2>
              <p>旧项目使用 SVG 单位。请提供真实比例；软件不会猜测打印尺寸。</p>
              <label>1 SVG 单位对应多少 mm
                <input type="number" min="0.000001" step="any" value={mappingValue}
                  onChange={(event) => setMappingValue(event.target.value)} />
              </label>
              <div><button type="button" onClick={() => setMapping(null)}>取消</button>
                <button type="button" onClick={confirmMapping}>按此比例打开</button></div>
            </div>
          </div>}
        </div>
        <nav className="mode-bar" aria-label="工作模式">
          <div className="mode-label">模式</div>
          {modes.map((mode) =>
            <button key={mode.id} type="button" className={`mode-button ${browser.activeMode === mode.id ? 'selected' : ''}`}
              aria-label={`${mode.label} ${mode.secondary}`}
              aria-current={browser.activeMode === mode.id ? 'page' : undefined}
              onClick={() => setBrowser((current) => ({ ...current, activeMode: mode.id }))}>
              <span>{mode.label}</span><small>{mode.secondary}</small>
              {mode.id !== 'design' && <em>COMING SOON</em>}
            </button>)}
          <span className="mode-bar-spacer" /><span className="mode-version">WM6 / 2D</span>
        </nav>
      </main>

      <aside className="inspector" aria-label="右侧检查器">
        <div className="inspector-title"><div><span className="eyebrow">PROPERTIES</span><h2>检查器</h2></div><span className="inspector-dots" aria-hidden="true">•••</span></div>
        {selected ? <div className="inspector-selection">
          <strong>已选元素</strong>
          <dl><dt>ID</dt><dd>{selected.id}</dd><dt>类型</dt><dd>{selected.type}</dd>
            <dt>中心</dt><dd>{selected.x.toFixed(2)}, {selected.y.toFixed(2)} mm</dd>
            <dt>范围</dt><dd>{selected.width.toFixed(2)} × {selected.height.toFixed(2)} mm</dd></dl>
          <p>{sourceCanDrag(selected) ? '可直接拖动；释放鼠标后提交一次。' : '派生或参数化元素不可直接拖动；可编辑其文档规则。'}</p>
        </div> : <div className="inspector-empty"><span className="inspect-glyph" aria-hidden="true">⌗</span><strong>未选择对象</strong><p>No selection</p><small>点击元素可查看其世界毫米信息。</small></div>}
        {project.currentDocument && <InspectorControls key={`${project.currentDocument.document_id}:${project.documentRevision}:${project.evaluateStatus}`}
          dto={project.currentDocument} selected={selected} parameterCatalog={parameterCatalog}
          layoutSelection={selectedFamily} layoutDraft={layoutDraft} layoutBusy={preparingLayout}
          onLayoutDraftEdit={(key, value) => {
            try { setLayoutDraft((draft) => draft ? editLayoutDraft(draft, key, value, parameterCatalog) : draft) }
            catch (error) { setProjectError(error instanceof Error ? error.message : '布局参数无效。') }
          }}
          onEdit={editParameter} disabled={project.evaluateStatus !== 'ready'} />}
        <div className={`connection-card ${connection.kind}`}>
          <div className="connection-card-head"><span>连接状态</span><span className="connection-state-text">{connected ? '已连接' : connection.kind === 'checking' ? '检查中' : connection.kind === 'offline' ? '离线' : '协议不兼容'}</span></div>
          <p>{connected ? 'Python Engine 已就绪，合同 v1.0 · mm 验证通过。' : connection.message}</p>
          {!connected && connection.kind !== 'checking' && <button type="button" onClick={reconnect}>重新检测连接</button>}
          {connected && project.evaluateStatus === 'error' && project.currentDocument &&
            <button type="button" onClick={() => runEvaluate(project.currentDocument!)}>重试二维求值</button>}
        </div>
      </aside>
    </div>
    <input ref={inputRef} type="file" accept=".json,application/json" className="visually-hidden"
      aria-label="选择 PatternDocument 项目文件" onChange={(event) => void onFile(event)} />
    <input ref={imageInputRef} type="file" accept=".png,.jpg,.jpeg,image/png,image/jpeg" className="visually-hidden"
      aria-label="选择 PNG 或 JPG 图片" onChange={onImageFile} />
    <input ref={svgInputRef} type="file" accept=".svg,image/svg+xml" className="visually-hidden"
      aria-label="选择 SVG 图片" onChange={onImageFile} />
  </div>
}
