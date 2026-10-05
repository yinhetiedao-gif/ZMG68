import { useCallback, useEffect, useRef, useState, type ChangeEvent } from 'react'
import {
  BackendOfflineError, checkBackend, ContractMismatchError, EXPECTED_SCHEMA_VERSION,
} from './api/client'
import { evaluateDocument } from './api/evaluate'
import { importImage } from './api/import'
import { bindImageSource, imageAssetFetcher, type ImageSources } from './api/imageAssets'
import { analyzePattern, preparePattern, runPatternAction, type PatternAnalysis, type PatternFamily } from './api/pattern'
import { Workspace2D } from './geometry/Workspace2D'
import { InspectorControls, type EditAction } from './document/InspectorControls'
import type { ParameterCatalog } from './document/parameterSchema'
import { currentLayoutFamily, editLayoutDraft, initialLayoutDraft, layoutCommitDocument, type LayoutDraft } from './document/layoutDraft'
import {
  addField, addModifier, bindScalarModifierField, removeField, removeModifier, restoreSnapshot, setFieldEnabled,
  updateElement, updateField, updateGrid, updateLayout, updateReplacement,
  updateScalarModifier, updateStackModifier,
} from './document/editor'
import type { FinalGeometry, PatternDocumentDTO } from './model/types'
import {
  directSourceElement, millimetresPerUnit, moveSourceElement,
  prepareProject, withMillimetreMapping,
} from './model/project'
import { initialBrowserState, type WorkspaceMode } from './state/browserState'
import { initialDocumentState } from './state/documentState'
import { ManufacturingPanel } from './manufacturing/ManufacturingPanel'
import { useManufacturing } from './manufacturing/useManufacturing'
import { useFabricPreview } from './manufacturing/useFabricPreview'
import { PreviewPanel } from './manufacturing/PreviewPanel'
import { setFabricBaseType, updateFabricBase } from './document/fabricBase'
import { setFabricUnitCellType, updateFabricUnitCell, setFabricPlacementMode } from './document/fabricCell'
import { setFabricModifierEnabled, setFabricModifierField, updateFabricModifier } from './document/fabricModifiers'
import { applyFabricPreset } from './document/fabricPresets'
import { clearDraft, loadBeforeExampleDraft, loadDraft, saveBeforeExampleDraft, saveDraft,
  type DraftUiState, type LocalDraft, type SourceAssetDraft } from './draft/localDraft'
import { createExampleDocument, exampleIdFromDocument, examples, type BuiltInExample, type ExampleId } from './examples/catalog'
import { confirmUniformRealSize } from './document/realSize'

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
  { id: 'design', label: '① 设计', secondary: 'Design' },
  { id: 'manufacture', label: '② 检查制造', secondary: 'Manufacture' },
  { id: 'preview', label: '③ 预览与导出', secondary: '3D Preview' },
]

function pendingLayoutFor(dto: PatternDocumentDTO, draft: LayoutDraft | null): LayoutDraft | null {
  return draft && (draft.changed || draft.family !== currentLayoutFamily(dto)) &&
    draft.sourceRevision === dto.document_revision &&
    (draft.family === 'free' || draft.proposal?.document_id === dto.document_id) ? draft : null
}

function ExampleCard({ example, onOpen, disabled }: { example: BuiltInExample; onOpen: (id: ExampleId) => void; disabled: boolean }) {
  const capabilityLabel = { editable: '可编辑', standard_stl: '支持标准二维 STL', preview_only: '仅预览' }
  return <button className="example-card" type="button" disabled={disabled} onClick={() => onOpen(example.id)}
    aria-label={`打开示例：${example.title}`}>
    <span className={`example-thumbnail ${example.thumbnail}`} aria-hidden="true">
      {Array.from({ length: 9 }, (_, index) => <i key={index} />)}
    </span>
    <span className="example-copy"><strong>{example.title}</strong><small>{example.description}</small>
      <span className="example-capabilities">{example.capabilities.map((capability) =>
        <em key={capability}>{capabilityLabel[capability]}</em>)}</span>
      <span className="example-open">打开示例 →</span></span>
  </button>
}

export function App() {
  const [connection, setConnection] = useState<ConnectionState>({ kind: 'checking', message: '正在连接后端…' })
  const [parameterCatalog, setParameterCatalog] = useState<ParameterCatalog | null>(null)
  const [retry, setRetry] = useState(0)
  const [browser, setBrowser] = useState(initialBrowserState)
  const [project, setProject] = useState(initialDocumentState)
  const imageSourcesRef = useRef<ImageSources>({})
  const [assetFetch] = useState(() => imageAssetFetcher(() => imageSourcesRef.current))
  const manufacturing = useManufacturing(project.currentDocument, assetFetch)
  const fabricPreview = useFabricPreview(project.currentDocument, assetFetch)
  const [projectError, setProjectError] = useState<string | null>(null)
  const [exampleChooserOpen, setExampleChooserOpen] = useState(false)
  const [draftNotice, setDraftNotice] = useState<string | null>(null)
  const [restoreNotice, setRestoreNotice] = useState<string | null>(null)
  const [draftSaveStatus, setDraftSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [activeExampleSession, setActiveExampleSession] = useState(false)
  const [restorableDraft, setRestorableDraft] = useState<LocalDraft | null>(null)
  const [preExampleDraft, setPreExampleDraft] = useState<LocalDraft | null>(null)
  const sourceAssetRef = useRef<SourceAssetDraft | null>(null)
  const draftTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const draftWrites = useRef<Promise<unknown>>(Promise.resolve())
  const draftSaveSequence = useRef(0)
  const [mapping, setMapping] = useState<{ dto: PatternDocumentDTO; fileName: string; warnings: string[] } | null>(null)
  const [mappingValue, setMappingValue] = useState('')
  const [pendingPreview, setPendingPreview] = useState<{ id: string; dx: number; dy: number } | null>(null)
  const [fitToken, setFitToken] = useState(0)
  const historyRef = useRef<{ past: PatternDocumentDTO[]; future: PatternDocumentDTO[] }>({ past: [], future: [] })
  const [historyCount, setHistoryCount] = useState({ past: 0, future: 0 })
  const inputRef = useRef<HTMLInputElement>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)
  const svgInputRef = useRef<HTMLInputElement>(null)
  const fieldImageInputRef = useRef<HTMLInputElement>(null)
  const fieldImageTarget = useRef('')
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
  const [selectedFieldId, setSelectedFieldId] = useState('')
  const [layoutDraft, setLayoutDraft] = useState<LayoutDraft | null>(null)
  const [preparingLayout, setPreparingLayout] = useState(false)
  const layoutSequence = useRef(0)
  const activeDocumentRef = useRef<PatternDocumentDTO | null>(null)
  const lastValidDocumentRef = useRef<PatternDocumentDTO | null>(null)
  const pendingControls = useRef(new Set<string>())
  const [parameterPending, setParameterPending] = useState(false)
  const [parameterSyncVersion, setParameterSyncVersion] = useState(0)
  const [canvasEditing, setCanvasEditing] = useState(false)
  const onParameterPending = useCallback((id: string, pending: boolean) => {
    if (pending) pendingControls.current.add(id)
    else pendingControls.current.delete(id)
    setParameterPending(pendingControls.current.size > 0)
  }, [])

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
    if (draftTimer.current) clearTimeout(draftTimer.current)
  }, [])
  useEffect(() => {
    let active = true
    void loadDraft().then((draft) => {
      if (active && !activeDocumentRef.current) setRestorableDraft(draft)
    }).catch((error: unknown) => {
      if (active) setDraftNotice(error instanceof Error ? error.message : '无法读取本地草稿。')
    })
    return () => { active = false }
  }, [])
  useEffect(() => {
    let active = true
    void loadBeforeExampleDraft().then((draft) => { if (active) setPreExampleDraft(draft) })
      .catch((error: unknown) => { if (active) setDraftNotice(error instanceof Error ? error.message : '无法读取示例前的作品。') })
    return () => { active = false }
  }, [])

  const persistDraft = useCallback((dto: PatternDocumentDTO, fileName: string | null,
    sourceAsset: SourceAssetDraft | null, uiState: DraftUiState): Promise<LocalDraft> => {
    const sequence = ++draftSaveSequence.current
    setDraftSaveStatus('saving')
    const metadata = { ...uiState, image_sources: imageSourcesRef.current }
    const next = draftWrites.current.catch(() => undefined).then(() => saveDraft(dto, fileName, sourceAsset, metadata))
    draftWrites.current = next
    return next.then((saved) => {
      if (sequence === draftSaveSequence.current) setDraftSaveStatus('saved')
      return saved
    }, (error: unknown) => {
      if (sequence === draftSaveSequence.current) setDraftSaveStatus('error')
      throw error
    })
  }, [])

  useEffect(() => {
    if (draftTimer.current) clearTimeout(draftTimer.current)
    const dto = project.currentDocument
    if (!dto || project.evaluateStatus !== 'ready' || lastValidDocumentRef.current !== dto) return
    const fileName = project.fileName
    const sourceAsset = sourceAssetRef.current
    const uiState: DraftUiState = { pending_layout: pendingLayoutFor(dto, layoutDraft),
      example_session_active: activeExampleSession }
    setDraftSaveStatus('saving')
    draftTimer.current = setTimeout(() => {
      draftTimer.current = null
      void persistDraft(dto, fileName, sourceAsset, uiState).then(() => setDraftNotice(null))
        .catch((error: unknown) => setDraftNotice(error instanceof Error ? error.message : '本地草稿保存失败。'))
    }, 450)
    return () => { if (draftTimer.current) clearTimeout(draftTimer.current) }
  }, [project.currentDocument, project.evaluateStatus, project.fileName, layoutDraft,
    activeExampleSession, persistDraft])

  useEffect(() => {
    if (draftSaveStatus !== 'saving' && draftSaveStatus !== 'error') return
    const guard = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', guard)
    return () => window.removeEventListener('beforeunload', guard)
  }, [draftSaveStatus])

  const saveBeforeReplacement = async () => {
    if (draftTimer.current) clearTimeout(draftTimer.current)
    draftTimer.current = null
    const dto = project.currentDocument
    if (!dto) return
    if (project.evaluateStatus !== 'ready' || lastValidDocumentRef.current !== dto)
      throw new Error('当前设计仍在计算或修改未完成，已取消切换。')
    try {
      await persistDraft(dto, project.fileName, sourceAssetRef.current, {
        pending_layout: pendingLayoutFor(dto, layoutDraft), example_session_active: activeExampleSession,
      })
    } catch (error) {
      throw new Error(`当前作品保存失败，已取消切换：${error instanceof Error ? error.message : '本地草稿无法写入。'}`)
    }
  }

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
    void evaluateDocument(dto, controller.signal, assetFetch).then((result) => {
      if (sequence !== evaluateSequence.current) return
      lastValidDocumentRef.current = dto
      setProject((current) => ({
        ...current, finalGeometry: result.geometry, bounds: result.bounds_mm,
        evaluateStatus: 'ready', evaluateError: null,
        warnings: [...new Set([...current.warnings, ...result.warnings])],
      }))
      setPendingPreview(null)
      setBrowser((current) => {
        const remaining = current.selectedElementIds.filter((id) => result.geometry.some((item) => item.id === id))
        return remaining.length === current.selectedElementIds.length ? current : { ...current, selectedElementIds: remaining }
      })
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
  }, [invalidatePatternAnalysis, requestPatternAnalysis, assetFetch])

  const acceptProject = (dto: PatternDocumentDTO, fileName: string, warnings: string[], options: {
    pendingLayout?: LayoutDraft | null; exampleSessionActive?: boolean; restored?: boolean
  } = {}) => {
    const pending = pendingLayoutFor(dto, options.pendingLayout ?? null)
    setRestorableDraft(null)
    lastValidDocumentRef.current = null
    setProjectError(null)
    ++layoutSequence.current
    setSelectedFamily(pending?.family ?? currentLayoutFamily(dto))
    setSelectedFieldId('')
    setLayoutDraft(pending ?? initialLayoutDraft(dto))
    setPreparingLayout(false)
    setMapping(null)
    setActiveExampleSession(options.exampleSessionActive ?? false)
    if (!options.exampleSessionActive) setPreExampleDraft(null)
    setDraftSaveStatus(options.restored ? 'saved' : 'saving')
    setRestoreNotice(options.restored ? pending
      ? '已恢复上次编辑及未应用的布局参数。刷新后撤销历史不会保留。'
      : '已恢复上次编辑。刷新后撤销历史不会保留。' : null)
    publishHistory({ past: [], future: [] })
    setBrowser((current) => ({ ...current, selectedElementIds: [], activeMode: 'design' }))
    runEvaluate(dto, { fileName, warnings, fitOnSuccess: true, analyzeDelayMs: 0 })
  }
  const openExample = async (id: ExampleId) => {
    if (importing || !connected) return
    try {
      if (project.currentDocument && (project.evaluateStatus !== 'ready' ||
          lastValidDocumentRef.current !== project.currentDocument)) throw new Error('当前设计仍在计算，请完成后再打开示例。')
      await saveBeforeReplacement()
      const previous = !activeExampleSession && project.currentDocument && !exampleIdFromDocument(project.currentDocument)
        ? { dto: project.currentDocument, fileName: project.fileName, asset: sourceAssetRef.current,
          pending: pendingLayoutFor(project.currentDocument, layoutDraft) }
        : !activeExampleSession && !project.currentDocument && restorableDraft
          ? { dto: restorableDraft.dto, fileName: restorableDraft.file_name, asset: restorableDraft.source_asset,
            pending: restorableDraft.pending_layout ?? null }
          : null
      if (previous) setPreExampleDraft(await saveBeforeExampleDraft(previous.dto, previous.fileName, previous.asset,
        { pending_layout: previous.pending, example_session_active: false,
          image_sources: project.currentDocument ? imageSourcesRef.current : restorableDraft?.image_sources }))
      const identifier = globalThis.crypto?.randomUUID?.() ?? `example-${Date.now()}-${Math.random().toString(16).slice(2)}`
      const dto = createExampleDocument(id, identifier)
      const example = examples.find((item) => item.id === id)!
      sourceAssetRef.current = null
      imageSourcesRef.current = {}
      setExampleChooserOpen(false)
      acceptProject(dto, example.title, [], { exampleSessionActive: activeExampleSession || Boolean(previous) })
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : '无法保存当前草稿，示例未打开。')
    }
  }
  const onFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    try {
      await saveBeforeReplacement()
      const identifier = globalThis.crypto?.randomUUID?.() ?? `web-${Date.now()}-${Math.random().toString(16).slice(2)}`
      const prepared = prepareProject(await file.text(), identifier)
      if (prepared.needsMillimetreMapping) {
        setMapping({ dto: prepared.dto, fileName: file.name, warnings: prepared.warnings })
        setMappingValue('')
        setProjectError(null)
      } else {
        sourceAssetRef.current = null
        acceptProject(prepared.dto, file.name, prepared.warnings)
      }
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : '无法读取项目。')
    }
  }
  const openImage = async (file: File) => {
    if (importing) return
    setImporting(true)
    setProjectError(null)
    try {
      await saveBeforeReplacement()
      const dto = await importImage(file)
      imageSourcesRef.current = {}
      sourceAssetRef.current = { blob: file, filename: file.name, media_type: file.type }
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
  const confirmMapping = async () => {
    if (!mapping) return
    try {
      await saveBeforeReplacement()
      sourceAssetRef.current = null
      acceptProject(withMillimetreMapping(mapping.dto, Number(mappingValue)), mapping.fileName, mapping.warnings)
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : '毫米映射无效。')
    }
  }
  const selectedId = browser.selectedElementIds[0] ?? null
  const selected = project.finalGeometry.find((item) => item.id === selectedId) ?? null
  const canEditDocument = project.evaluateStatus === 'ready' || (project.evaluateStatus === 'error'
    && lastValidDocumentRef.current?.document_id === project.currentDocument?.document_id)
  const sourceCanDrag = (item: FinalGeometry) => {
    const dto = project.currentDocument
    const source = dto && directSourceElement(dto, item.id, item.x, item.y)
    return canEditDocument && Boolean(source && source.type === item.type)
  }
  const commitDocument = (next: PatternDocumentDTO, before: PatternDocumentDTO, warnings?: string[]) => {
    if (next === before || project.evaluateStatus === 'idle') return
    const previousHistory = historyRef.current
    const previousSaveStatus = draftSaveStatus
    setDraftSaveStatus('saving')
    publishHistory({ past: [...previousHistory.past, before], future: [] })
    setProjectError(null)
    ++layoutSequence.current
    setSelectedFamily(currentLayoutFamily(next))
    setLayoutDraft(initialLayoutDraft(next))
    setPreparingLayout(false)
    runEvaluate(next, { rollback: before, warnings, onFailure: () => {
      publishHistory(previousHistory)
      setDraftSaveStatus(previousSaveStatus)
      setSelectedFamily(currentLayoutFamily(before))
      setLayoutDraft(initialLayoutDraft(before))
    }, analyzeDelayMs: 400 })
  }
  const resetExample = () => {
    const before = project.currentDocument
    const id = exampleIdFromDocument(before)
    if (!before || !id || !canEditDocument) return
    try {
      const original = createExampleDocument(id, before.document_id)
      commitDocument(restoreSnapshot(original, before.document_revision), before)
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : '无法恢复示例初始状态。')
    }
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
    if (!dto || !layoutDraft || applyingPatternRef.current || !canEditDocument) return
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
    if (!dto || !canEditDocument) return
    try {
      let next: PatternDocumentDTO
      if (action.kind === 'field_add') {
        const added = addField(dto, action.fieldType, parameterCatalog)
        next = added.dto
        const source = sourceAssetRef.current
        if (['image', 'distance'].includes(action.fieldType) && source && ['image/png', 'image/jpeg'].includes(source.media_type)) {
          const token = `image-${crypto.randomUUID()}`
          imageSourcesRef.current = { ...imageSourcesRef.current, [token]: source }
          next = bindImageSource(next, added.id, token, source.media_type, false)
        }
        setSelectedFieldId(added.id)
      } else if (action.kind === 'image_source') {
        fieldImageTarget.current = action.id
        fieldImageInputRef.current?.click()
        return
      } else if (action.kind === 'modifier_add') next = addModifier(dto, action.modifierType, parameterCatalog)
      else if (action.kind === 'modifier_remove') next = removeModifier(dto, action.lane, action.id)
      else if (action.kind === 'field_remove') {
        next = removeField(dto, action.id)
        setSelectedFieldId('')
      } else if (action.kind === 'field_enabled') next = setFieldEnabled(dto, action.id, action.enabled)
      else if (action.kind === 'field_binding') next = bindScalarModifierField(dto, action.id, action.fieldId)
      else if (action.kind === 'grid') next = updateGrid(dto, action.key, action.value, parameterCatalog)
      else if (action.kind === 'layout') next = updateLayout(dto, action.key, action.value, parameterCatalog)
      else if (action.kind === 'element' && typeof action.value === 'number') {
        const final = project.finalGeometry.find((item) => item.id === action.id)
        if (!final || !sourceCanDrag(final)) throw new Error('该元素没有可靠的源映射，不能直接编辑。')
        next = updateElement(dto, action.id, action.key, action.value)
      } else if (action.kind === 'field') {
        next = updateField(dto, action.id, action.key, action.value, parameterCatalog)
      } else if (action.kind === 'scalar' && (typeof action.value === 'number' || typeof action.value === 'boolean')) {
        next = updateScalarModifier(dto, action.id, action.key, action.value, parameterCatalog)
      } else if (action.kind === 'stack' &&
        (typeof action.value === 'number' || typeof action.value === 'boolean' || typeof action.value === 'string')) {
        next = updateStackModifier(dto, action.id, action.key, action.value, parameterCatalog)
      } else if (action.kind === 'shape' && typeof action.value === 'string') {
        next = updateReplacement(dto, action.id, action.value)
      } else throw new Error('不支持的编辑操作。')
      commitDocument(next, dto)
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : '参数修改失败。')
      setParameterSyncVersion((version) => version + 1)
    }
  }
  const undo = () => {
    const dto = project.currentDocument
    const history = historyRef.current
    if (!dto || !canEditDocument || !history.past.length) return
    setProjectError(null)
    const before = history.past[history.past.length - 1]
    const previousSaveStatus = draftSaveStatus
    setDraftSaveStatus('saving')
    publishHistory({ past: history.past.slice(0, -1), future: [...history.future, dto] })
    const restored = restoreSnapshot(before, dto.document_revision)
    ++layoutSequence.current
    setSelectedFamily(currentLayoutFamily(restored))
    setLayoutDraft(initialLayoutDraft(restored))
    runEvaluate(restored, {
      rollback: dto, onFailure: () => { publishHistory(history); setDraftSaveStatus(previousSaveStatus) },
    })
  }
  const redo = () => {
    const dto = project.currentDocument
    const history = historyRef.current
    if (!dto || !canEditDocument || !history.future.length) return
    setProjectError(null)
    const after = history.future[history.future.length - 1]
    const previousSaveStatus = draftSaveStatus
    setDraftSaveStatus('saving')
    publishHistory({ past: [...history.past, dto], future: history.future.slice(0, -1) })
    const restored = restoreSnapshot(after, dto.document_revision)
    ++layoutSequence.current
    setSelectedFamily(currentLayoutFamily(restored))
    setLayoutDraft(initialLayoutDraft(restored))
    runEvaluate(restored, {
      rollback: dto, onFailure: () => { publishHistory(history); setDraftSaveStatus(previousSaveStatus) },
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
  const interactionStatus = project.evaluateStatus === 'loading' ? 'Evaluating · 正在计算'
    : parameterPending || canvasEditing || (project.currentDocument && pendingLayoutFor(project.currentDocument, layoutDraft))
      ? 'Editing · 待提交'
      : project.evaluateError || projectError ? 'Error · 修改未完成，可重试或撤销'
        : 'Ready · 就绪'

  const restoreLocalDraft = () => {
    if (!restorableDraft) return
    sourceAssetRef.current = restorableDraft.source_asset
    imageSourcesRef.current = restorableDraft.image_sources ?? {}
    acceptProject(restorableDraft.dto, restorableDraft.file_name ?? '上次编辑', [], {
      pendingLayout: restorableDraft.pending_layout,
      exampleSessionActive: restorableDraft.example_session_active,
      restored: true,
    })
  }
  const restorePreExampleDraft = async () => {
    if (!preExampleDraft) return
    try {
      await saveBeforeReplacement()
      sourceAssetRef.current = preExampleDraft.source_asset
      imageSourcesRef.current = preExampleDraft.image_sources ?? {}
      acceptProject(preExampleDraft.dto, preExampleDraft.file_name ?? '示例前的作品', [], {
        pendingLayout: preExampleDraft.pending_layout, restored: true,
      })
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : '无法恢复示例前的作品。')
    }
  }
  const startFresh = async () => {
    try {
      await clearDraft()
      setRestorableDraft(null)
      setPreExampleDraft(null)
      setDraftNotice(null)
    } catch (error) {
      setDraftNotice(error instanceof Error ? error.message : '无法清除本地草稿。')
    }
  }

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey) || event.altKey || event.isComposing || event.repeat) return
      const target = event.target
      if (target instanceof HTMLElement && target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"])')) return
      const key = event.key.toLowerCase()
      if (key !== 'z' && key !== 'y') return
      event.preventDefault()
      if (key === 'y' || event.shiftKey) redo()
      else undo()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  })

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand-lockup">
        <div className="brand-symbol" aria-hidden="true"><span /><span /><span /><span /></div>
        <div className="brand-copy"><strong>Xiaomang Pattern Lab</strong><span>小芒图案实验室</span></div>
        <span className="alpha-tag">WEB ALPHA</span>
        {import.meta.env.MODE === 'staging' && <span className="alpha-tag">TEST / STAGING</span>}
      </div>
      <div className="project-name" aria-label="当前项目">
        <span>项目</span><strong>{project.fileName ?? 'Untitled'}</strong>
        {project.currentDocument ? <>
          <span className="project-unsaved" aria-live="polite">
            {draftSaveStatus === 'saved' ? '已保存' : draftSaveStatus === 'error' ? '保存失败' : '正在保存…'}
          </span>
          {pendingLayoutFor(project.currentDocument, layoutDraft) && <span className="project-pending">有未应用修改</span>}
        </> : <span className="project-unsaved">未创建</span>}
      </div>
      <div className="top-status">
        <div className={`backend-badge ${connection.kind}`} role="status" aria-live="polite">
          <span className="status-light" aria-hidden="true" />
          {connected ? '已连接' : connection.kind === 'checking' ? '正在连接' : connection.kind === 'offline' ? '连接中断' : '连接不兼容'}
        </div>
      </div>
    </header>

    <div className="work-area">
      <aside className="sidebar" aria-label="左侧工具栏">
        <div className="sidebar-intro"><span className="eyebrow">WORKSPACE / 工作台</span><p>导入图片，设计可直接编辑的二维图案。</p></div>
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
        {project.currentDocument && <section className="side-group" aria-label="内置示例">
          <div className="group-heading"><span>EX</span><h2>内置示例</h2></div>
          <button className="side-item" type="button" aria-expanded={exampleChooserOpen}
            onClick={() => setExampleChooserOpen((open) => !open)}><span className="side-item-mark">◉</span>试用示例</button>
          {exampleChooserOpen && <div className="sidebar-examples">{examples.map((example) => <ExampleCard
            key={example.id} example={example} onOpen={(id) => void openExample(id)} disabled={!connected || importing} />)}</div>}
        </section>}
        <section className="side-group" aria-label="图案结构">
          <div className="group-heading"><span>02</span><h2>图案结构</h2></div>
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
          {selectedFamily && <p className="pattern-analysis-status">已选：{patternItems.find((item) => item.id === selectedFamily)?.label}。在右侧调整并应用。</p>}
        </section>
        <div className="sidebar-footnote"><span className="footnote-icon">i</span><p>也可将 PNG、JPG 或 SVG 拖入画布。</p></div>
      </aside>

      <main className="workspace" aria-label="中央工作区">
        {restorableDraft && !project.currentDocument && <div className="draft-restore" role="region" aria-label="恢复上次编辑">
          <span>发现上次编辑：{restorableDraft.file_name ?? '未命名设计'} · {new Date(restorableDraft.saved_at).toLocaleString()}</span>
          <button type="button" onClick={restoreLocalDraft}>恢复上次编辑</button>
          <button type="button" onClick={() => void startFresh()}>新建项目</button>
        </div>}
        {draftNotice && <div className="draft-notice" role="alert">{draftNotice}</div>}
        {restoreNotice && <div className="draft-restore-notice" role="status">{restoreNotice}</div>}
        <div className="workspace-toolbar">
          <div className="breadcrumb"><span>工作区</span><span className="crumb-divider">/</span><strong>{modeName}</strong></div>
          <div className="workspace-scale">{project.currentDocument ? `CANVAS · ${project.finalGeometry.length} ELEMENTS · mm` : 'CANVAS · 暂无文档'}</div>
          <div className="history-actions"><button type="button" onClick={undo} title="Ctrl+Z" disabled={!historyCount.past || !canEditDocument}>撤销</button>
            <button type="button" onClick={redo} title="Ctrl+Y / Ctrl+Shift+Z" disabled={!historyCount.future || !canEditDocument}>重做</button>
            {exampleIdFromDocument(project.currentDocument) && <span className="example-session-label">正在试用示例：{project.fileName}</span>}
            {exampleIdFromDocument(project.currentDocument) && <button type="button" onClick={resetExample}
              disabled={!canEditDocument}>恢复示例初始状态</button>}
            {activeExampleSession && exampleIdFromDocument(project.currentDocument) && preExampleDraft && <button type="button"
              onClick={() => void restorePreExampleDraft()} disabled={!canEditDocument}>← 返回之前作品</button>}</div>
        </div>
        <div className="canvas-stage" onDragOver={(event) => event.preventDefault()} onDrop={onDrop}>
          {browser.activeMode === 'design' && project.currentDocument && project.evaluateStatus !== 'idle' ? (
            <Workspace2D geometry={project.finalGeometry} bounds={project.bounds} mmPerUnit={scale}
              view={browser.viewTransform}
              onViewChange={(viewTransform) => setBrowser((current) => ({ ...current, viewTransform }))}
              selectedId={selectedId}
              onSelect={(id) => setBrowser((current) => ({ ...current, selectedElementIds: id ? [id] : [] }))}
              canDrag={sourceCanDrag} onDragCommit={commitDrag} pendingPreview={pendingPreview} fitToken={fitToken}
              onEditingChange={setCanvasEditing} />
          ) : browser.activeMode === 'design' ? (
            <section className="empty-state" aria-label="空白设计工作区">
              <div className="orbit-art" aria-hidden="true"><div className="orbit-ring ring-one" /><div className="orbit-ring ring-two" /><div className="orbit-ring ring-three" /><span className="orbit-core" /><i className="orbit-dot dot-one" /><i className="orbit-dot dot-two" /><i className="orbit-dot dot-three" /></div>
              <span className="empty-kicker">A NEW CANVAS AWAITS</span>
              <h1>导入图片开始设计</h1>
              <p>导入自己的图案，或打开可编辑示例体验参数化设计。</p>
              <div className="empty-actions"><button type="button" className="primary-action ui-primary" disabled={!connected || importing}
                onClick={() => imageInputRef.current?.click()}>导入自己的图案</button>
              </div>
              <div className="empty-examples">{examples.map((example) => <ExampleCard
                key={example.id} example={example} onOpen={(id) => void openExample(id)} disabled={!connected || importing} />)}</div>
            </section>
          ) : browser.activeMode === 'manufacture' ? (
            <ManufacturingPanel heightText={manufacturing.heightText} onHeightChange={manufacturing.setHeightText}
              projectWarnings={project.warnings}
              document={project.currentDocument} designBounds={project.bounds} parameterCatalog={parameterCatalog}
              canEditSize={canEditDocument && project.evaluateStatus === 'ready'}
              onConfirmRealSize={(width, height) => {
                const dto = project.currentDocument
                if (!dto || !project.bounds || !canEditDocument) return
                try {
                  commitDocument(confirmUniformRealSize(dto, project.bounds, width, height), dto,
                    project.warnings.filter((warning) => !warning.includes('制造前必须确认真实尺寸')))
                } catch (error) {
                  setProjectError(error instanceof Error ? error.message : '真实尺寸无效。')
                }
              }}
              onFabricType={(type) => {
                const dto = project.currentDocument
                if (!dto || !canEditDocument) return
                try { commitDocument(setFabricBaseType(dto, type, parameterCatalog), dto) }
                catch (error) { setProjectError(error instanceof Error ? error.message : 'Fabric Base 配置无效。') }
              }}
              onFabricParameter={(key, value) => {
                const dto = project.currentDocument
                if (!dto || !canEditDocument) return
                try { commitDocument(updateFabricBase(dto, key, value, parameterCatalog), dto) }
                catch (error) { setProjectError(error instanceof Error ? error.message : 'Fabric Base 参数无效。') }
              }}
              onUnitCellType={(type) => {
                const dto = project.currentDocument
                if (!dto || !canEditDocument) return
                try { commitDocument(setFabricUnitCellType(dto, type, parameterCatalog), dto) }
                catch (error) { setProjectError(error instanceof Error ? error.message : 'Unit Cell 配置无效。') }
              }}
              onUnitCellParameter={(section, key, value) => {
                const dto = project.currentDocument
                if (!dto || !canEditDocument) return
                try { commitDocument(updateFabricUnitCell(dto, section, key, value, parameterCatalog), dto) }
                catch (error) { setProjectError(error instanceof Error ? error.message : 'Unit Cell 参数无效。') }
              }}
              onPlacementMode={(mode) => {
                const dto = project.currentDocument
                if (!dto || !canEditDocument) return
                try { commitDocument(setFabricPlacementMode(dto, mode), dto) }
                catch (error) { setProjectError(error instanceof Error ? error.message : 'Fabric 布点方式无效。') }
              }}
              onFabricModifierEnabled={(type, enabled) => {
                const dto = project.currentDocument
                if (!dto || !canEditDocument) return
                try { commitDocument(setFabricModifierEnabled(dto, type, enabled, parameterCatalog), dto) }
                catch (error) { setProjectError(error instanceof Error ? error.message : 'Fabric Modifier 配置无效。') }
              }}
              onFabricModifierField={(type, fieldId) => {
                const dto = project.currentDocument
                if (!dto || !canEditDocument) return
                try { commitDocument(setFabricModifierField(dto, type, fieldId), dto) }
                catch (error) { setProjectError(error instanceof Error ? error.message : 'Fabric 参数场绑定无效。') }
              }}
              onFabricModifierParameter={(type, key, value) => {
                const dto = project.currentDocument
                if (!dto || !canEditDocument) return
                try { commitDocument(updateFabricModifier(dto, type, key, value, parameterCatalog), dto) }
                catch (error) { setProjectError(error instanceof Error ? error.message : 'Fabric Modifier 参数无效。') }
              }}
              onFabricPreset={(presetId) => {
                const dto = project.currentDocument
                if (!dto || !canEditDocument) return
                try { commitDocument(applyFabricPreset(dto, presetId, parameterCatalog), dto) }
                catch (error) { setProjectError(error instanceof Error ? error.message : 'Fabric 预设无效。') }
              }}
              fabricPreviewStatus={fabricPreview.status} fabricPreviewResult={fabricPreview.result}
              fabricPreviewError={fabricPreview.error} onUpdateFabricPreview={() => void fabricPreview.update()}
              candidateFetcher={assetFetch}
              validHeight={manufacturing.validHeight} canBuild={connected && project.evaluateStatus === 'ready'
                && Boolean(project.currentDocument) && manufacturing.validHeight}
              onBuild={() => void manufacturing.build()} status={manufacturing.status}
              result={manufacturing.result} error={manufacturing.error} projectName={project.fileName}
              isCurrentResult={manufacturing.isCurrentResult}
              onBackDesign={() => setBrowser((current) => ({ ...current, activeMode: 'design' }))}
              onPreview={() => setBrowser((current) => ({ ...current, activeMode: 'preview' }))} />
          ) : <PreviewPanel result={manufacturing.result} status={manufacturing.status}
            projectName={project.fileName} isCurrentResult={manufacturing.isCurrentResult}
            document={project.currentDocument} fabricPreview={fabricPreview.result}
            onGoManufacture={() => setBrowser((current) => ({ ...current, activeMode: 'manufacture' }))} />}
          {project.evaluateStatus === 'loading' && <div className="viewer-notice" role="status">Python 正在计算最终二维几何…</div>}
          {importing && <div className="viewer-notice" role="status">Python 正在转换图片为可编辑元素…</div>}
          {project.evaluateError && <div className="viewer-error" role="alert">{project.evaluateError}</div>}
          {projectError && <div className="viewer-error" role="alert">{projectError}</div>}
          {browser.activeMode === 'design' && project.warnings.length > 0 &&
            <div className="viewer-warning" role="note">{project.warnings.join(' ')}</div>}
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
              data-step-state={browser.activeMode === mode.id ? 'current' : mode.id === 'design' && project.currentDocument
                || mode.id === 'manufacture' && manufacturing.result && manufacturing.isCurrentResult(manufacturing.result.manufacturing_result_id)
                || mode.id === 'preview' && (fabricPreview.result || manufacturing.result && manufacturing.isCurrentResult(manufacturing.result.manufacturing_result_id))
                ? 'complete' : 'not-ready'}
              aria-label={`${mode.id === 'manufacture' ? '制造' : mode.id === 'preview' ? '三维预览' : '设计'} ${mode.secondary}`}
              aria-current={browser.activeMode === mode.id ? 'page' : undefined}
              onClick={() => setBrowser((current) => ({ ...current, activeMode: mode.id }))}>
              <span>{mode.label}</span><small>{mode.secondary}</small>
            </button>)}
          <span className="mode-bar-spacer" /><span className="interaction-status" role="status" aria-label="编辑状态">{interactionStatus}</span>
        </nav>
      </main>

      <aside className="inspector" aria-label="右侧检查器">
        <div className="inspector-title"><div><span className="eyebrow">PROPERTIES</span><h2>检查器</h2></div><span className="inspector-dots" aria-hidden="true">•••</span></div>
        {!project.currentDocument && <div className="inspector-empty"><span className="inspect-glyph" aria-hidden="true">⌗</span><strong>未选择对象</strong><p>No selection</p><small>点击元素可查看其世界毫米信息。</small></div>}
        {project.currentDocument && <div style={{ display: browser.activeMode === 'design' ? undefined : 'none' }}><InspectorControls key={project.currentDocument.document_id}
          syncToken={`${project.documentRevision}:${project.evaluateStatus}:${parameterSyncVersion}`} onPending={onParameterPending}
          dto={project.currentDocument} selected={selected} parameterCatalog={parameterCatalog}
          selectedFieldId={selectedFieldId} onSelectField={setSelectedFieldId}
          imageSourceNames={Object.fromEntries(project.currentDocument.assets.map((asset) =>
            [asset.role.slice(6), imageSourcesRef.current[asset.asset_id]?.filename ?? '源图片待恢复']))}
          layoutSelection={selectedFamily} layoutDraft={layoutDraft} layoutBusy={preparingLayout}
          onApplyLayout={() => void applyLayout()} onCancelLayout={cancelLayout}
          layoutActionsDisabled={!connected || !hasEditableGeometry || applyingPattern}
          gradientExample={exampleIdFromDocument(project.currentDocument) === 'gradient-grid'}
          onLayoutDraftEdit={(key, value) => {
            try { setLayoutDraft((draft) => draft ? editLayoutDraft(draft, key, value, parameterCatalog) : draft) }
            catch (error) {
              setProjectError(error instanceof Error ? error.message : '布局参数无效。')
              setParameterSyncVersion((version) => version + 1)
            }
          }}
          onEdit={editParameter} disabled={!canEditDocument} /></div>}
        {project.currentDocument && browser.activeMode !== 'design' &&
          <p className="inspector-readonly">设计参数位于「① 设计」。当前步骤专注制造结果与导出。</p>}
        <div className={`connection-card ${connection.kind}`}>
          <div className="connection-card-head"><span>连接状态</span><span className="connection-state-text">{connected ? '已连接' : connection.kind === 'checking' ? '检查中' : connection.kind === 'offline' ? '离线' : '协议不兼容'}</span></div>
          {!connected && <p>{connection.message}</p>}
          {!connected && connection.kind !== 'checking' && <button type="button" onClick={reconnect}>重新检测连接</button>}
          {connected && project.evaluateStatus === 'error' && project.currentDocument &&
            <button type="button" onClick={() => runEvaluate(project.currentDocument!)}>重试二维求值</button>}
          <details className="diagnostic-details"><summary>诊断详情</summary>
            <p>Python Engine · Contract <strong>v{EXPECTED_SCHEMA_VERSION}</strong> · mm</p>
            {!connected && <p>待验证</p>}
            {project.currentDocument && <p>文档修订：{project.documentRevision}<span className="visually-hidden">revision {project.documentRevision}</span></p>}
            <p>{connection.message}</p>
          </details>
        </div>
      </aside>
    </div>
    {/* Test fixture loader only; absent from development/production UI and accessibility tree. */}
    {import.meta.env.MODE === 'test' && <input ref={inputRef} type="file" accept=".json,application/json" className="visually-hidden"
      aria-label="选择 PatternDocument 项目文件" onChange={(event) => void onFile(event)} />}
    <input ref={imageInputRef} type="file" accept=".png,.jpg,.jpeg,image/png,image/jpeg" className="visually-hidden"
      aria-label="选择 PNG 或 JPG 图片" onChange={onImageFile} />
    <input ref={svgInputRef} type="file" accept=".svg,image/svg+xml" className="visually-hidden"
      aria-label="选择 SVG 图片" onChange={onImageFile} />
    <input ref={fieldImageInputRef} type="file" accept=".png,.jpg,.jpeg,image/png,image/jpeg"
      className="visually-hidden" aria-label="选择图片场源文件" onChange={(event) => {
        const file = event.target.files?.[0]
        event.target.value = ''
        const dto = project.currentDocument
        if (!file || !dto || !canEditDocument) return
        try {
          const mediaType = /\.png$/i.test(file.name) ? 'image/png' : /\.jpe?g$/i.test(file.name) ? 'image/jpeg' : ''
          if (!mediaType || !file.size || file.size > 8 * 1024 * 1024) throw new Error('请选择 8 MiB 内的 PNG/JPG 图片。')
          const token = `image-${crypto.randomUUID()}`
          const next = bindImageSource(dto, fieldImageTarget.current, token, mediaType)
          imageSourcesRef.current = { ...imageSourcesRef.current,
            [token]: { blob: file, filename: file.name, media_type: mediaType } }
          commitDocument(next, dto)
        } catch (error) { setProjectError(error instanceof Error ? error.message : '图片场源文件无法载入。') }
      }} />
  </div>
}
