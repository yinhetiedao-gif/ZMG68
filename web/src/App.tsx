import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react'
import {
  BackendOfflineError, checkBackend, ContractMismatchError, EXPECTED_SCHEMA_VERSION,
} from './api/client'
import { evaluateDocument } from './api/evaluate'
import { importImage } from './api/import'
import { bindImageSource, imageAssetFetcher, type ImageSources } from './api/imageAssets'
import { preparePattern, runPatternAction, type PatternFamily } from './api/pattern'
import { Workspace2D } from './geometry/Workspace2D'
import { DesignPanelControls, defaultDesignDisplay } from './document/DesignPanelControls'
import { designCandidate } from './document/designControls'
import { designSvg, designPng, deliverDesign } from './geometry/designExport'
import { InspectorControls, type EditAction } from './document/InspectorControls'
import { groupFor, validateParameter, type ParameterCatalog } from './document/parameterSchema'
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
import { initialBrowserState, workspaceModeFromLocation, type WorkspaceMode } from './state/browserState'
import { appendPrimitive, createBlankDesign, type PrimitiveType } from './document/nativeDesign'
import { readReferenceLayer, updateReferenceLayer, type ReferenceLayer } from './document/referenceLayer'
import { ReferenceLayerPanel } from './document/ReferenceLayerPanel'
import { useLayoutPreview, useDocumentPreview } from './document/useLayoutPreview'
import { openLinearSize, linearSizeCandidate, linearSizeGroup, linearRegionDefaults, linearSizeOwner,
  sizeFieldTypes, sizeFieldGroup, sizeFieldValues, selectSizeField, changeSizeFieldParameter, resetLinearSizeDraft, type LinearSizeDraft } from './document/linearSize'
import { openRadialSize, radialSizeCandidate, radialSizeGroup, radialSizeDefaults, type RadialSizeDraft } from './document/radialSize'
import { ParameterPanel } from './document/ParameterPanel'
import { ParameterInteraction } from './document/ParameterInteraction'
import { initialDocumentState } from './state/documentState'
import { ManufacturingPanel } from './manufacturing/ManufacturingPanel'
import { useManufacturing } from './manufacturing/useManufacturing'
import { useFabricPreview } from './manufacturing/useFabricPreview'
import { coordinateComputeRequests } from './manufacturing/computeRequests'
import { PreviewPanel } from './manufacturing/PreviewPanel'
import { FabricThreePreview } from './manufacturing/FabricThreePreview'
import { temporaryFabricDimensions } from './manufacturing/fabricTemporaryDimensions'
import { fabricBase, setFabricBaseType, updateFabricBase } from './document/fabricBase'
import { fabricUnitCell, setFabricUnitCellType, updateFabricUnitCell, setFabricPlacementMode } from './document/fabricCell'
import { isOriginalShape, originalPreviewDocument, setOriginalShape } from './document/fabricOriginal'
import { setFabricOutputMode } from './document/fabricBase'
import { setFabricModifierEnabled, setFabricModifierField, updateFabricModifier, setUniformFabricHeight, setDirectionalFabricHeight, setWaveFabricHeight, setCenterFabricHeight } from './document/fabricModifiers'
import { applyFabricPreset, directionalFabricRecipe, waveFabricRecipe, centerFabricRecipe, applyFabricHeightRecipe } from './document/fabricPresets'
import { clearDraft, loadBeforeExampleDraft, loadDraft, saveBeforeExampleDraft, saveDraft,
  type DraftUiState, type LocalDraft, type SourceAssetDraft } from './draft/localDraft'
import { createExampleDocument, exampleIdFromDocument, examples, type BuiltInExample, type ExampleId } from './examples/catalog'
import { confirmUniformRealSize } from './document/realSize'
import { ReleaseDiagnostics } from './ReleaseDiagnostics'

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
]

function pendingLayoutFor(dto: PatternDocumentDTO, draft: LayoutDraft | null): LayoutDraft | null {
  return draft && (draft.changed || draft.family !== currentLayoutFamily(dto)) &&
    draft.sourceRevision === dto.document_revision &&
    (draft.family === 'free' || draft.proposal?.document_id === dto.document_id) ? draft : null
}

function retainPendingFabricLayout(draft: LayoutDraft, next: PatternDocumentDTO): LayoutDraft {
  const metadata = draft.proposal?.document.metadata
  return { ...draft, sourceRevision: next.document_revision, proposal: draft.proposal ? {
    ...draft.proposal, document_revision: next.document_revision,
    document: { ...draft.proposal.document, fields: next.document.fields, metadata: { ...metadata,
      fabric_config: next.document.metadata.fabric_config,
      web_fabric_height_effect: next.document.metadata.web_fabric_height_effect,
      web_fabric_recipe: next.document.metadata.web_fabric_recipe,
    } },
  } : null }
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
  const [parameterLoad, setParameterLoad] = useState<{ status: 'loading' | 'ready' | 'error'; error?: string }>({ status: 'loading' })
  const [fabricStlTestExportEnabled, setFabricStlTestExportEnabled] = useState<boolean | undefined>()
  const [releaseHealth, setReleaseHealth] = useState<import('./api/client').HealthResponse | null>(null)
  const [retry, setRetry] = useState(0)
  const [browser, setBrowser] = useState(() => ({ ...initialBrowserState, activeMode: workspaceModeFromLocation() }))
  const [designContext, publishDesignContext] = useState<'layout' | 'element' | 'effects' | 'reference' | 'linear' | null>(null)
  const [linearDraft, setLinearDraft] = useState<LinearSizeDraft | RadialSizeDraft | null>(null)
  const [designDisplay, setDesignDisplay] = useState(defaultDesignDisplay)
  const designDisplayRef = useRef(designDisplay); designDisplayRef.current = designDisplay
  const [designExportBusy, setDesignExportBusy] = useState(false)
  const setDesignContext = (context: typeof designContext) => {
    if (linearDraft && sizeFormPending && context !== 'linear' && context !== designContext &&
        !window.confirm('尺寸变化尚未应用。离开此编辑会丢弃待应用配置，正式作品保持不变。继续？')) return false
    publishDesignContext(context)
    return true
  }
  const [linearSync, setLinearSync] = useState(0)
  const [referenceLayer, setReferenceLayer] = useState<ReferenceLayer | null>(null)
  const referenceLayerRef = useRef<ReferenceLayer | null>(null); referenceLayerRef.current = referenceLayer
  const [referenceDraft, setReferenceDraft] = useState<ReferenceLayer | null>(null)
  const [referenceUrl, setReferenceUrl] = useState('')
  const referenceInputRef = useRef<HTMLInputElement>(null)
  const referenceReadSequence = useRef(0)
  useEffect(() => {
    if (!referenceLayer) { setReferenceUrl(''); return }
    const url = URL.createObjectURL(referenceLayer.blob)
    setReferenceUrl(url)
    return () => URL.revokeObjectURL(url)
  }, [referenceLayer?.blob])
  const [project, setProject] = useState(initialDocumentState)
  const imageSourcesRef = useRef<ImageSources>({})
  const [computeBusy, setComputeBusy] = useState(false)
  const [computeRequests] = useState(() => coordinateComputeRequests(
    imageAssetFetcher(() => imageSourcesRef.current), setComputeBusy))
  const assetFetch = computeRequests.fetcher
  const manufacturing = useManufacturing(project.currentDocument, assetFetch, computeRequests.isBusy)
  const [recipeSaving, setRecipeSaving] = useState(false)
  const recipeSavingRef = useRef(false)
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
  const [elementDraft, setElementDraft] = useState<Record<string, number>>({})
  useEffect(() => setElementDraft({}), [project.documentRevision, browser.selectedElementIds[0]])
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
  const [applyingPattern, setApplyingPattern] = useState(false)
  const applyingPatternRef = useRef(false)
  const [selectedFamily, setSelectedFamily] = useState<PatternFamily | null>(null)
  const [selectedFieldId, setSelectedFieldId] = useState('')
  const [layoutDraft, setLayoutDraft] = useState<LayoutDraft | null>(null)
  const [layoutPreviewSeed, setLayoutPreviewSeed] = useState<{ key: string; result: import('./model/types').EvaluateResponse } | null>(null)
  const [preparingLayout, setPreparingLayout] = useState(false)
  const layoutSequence = useRef(0)
  const activeDocumentRef = useRef<PatternDocumentDTO | null>(null)
  const lastValidDocumentRef = useRef<PatternDocumentDTO | null>(null)
  const pendingControls = useRef(new Set<string>())
  const [parameterPending, setParameterPending] = useState(false)
  const [cellDraft, setCellDraft] = useState<Record<string, number>>({})
  const [manufacturingActionHost, setManufacturingActionHost] = useState<HTMLDivElement | null>(null)
  const [parameterSyncVersion, setParameterSyncVersion] = useState(0)
  const [canvasEditing, setCanvasEditing] = useState(false)
  const onParameterPending = useCallback((id: string, pending: boolean) => {
    if (pending) pendingControls.current.add(id)
    else pendingControls.current.delete(id)
    setParameterPending(pendingControls.current.size > 0)
  }, [])
  const onUnitCellDraft = useCallback((key: string, value: import('./document/parameterSchema').ParameterValue | null) => {
    setCellDraft(previous => {
      if (typeof value === 'number' && previous[key] === value || value === null && !(key in previous)) return previous
      const next = { ...previous }
      if (typeof value === 'number') next[key] = value
      else delete next[key]
      return next
    })
  }, [])
  useEffect(() => setCellDraft({}), [project.currentDocument?.document_id])
  const fabricPreviewInput = useMemo(() => originalPreviewDocument(project.currentDocument, parameterCatalog, Number(manufacturing.heightText)),
    [project.currentDocument, parameterCatalog, manufacturing.heightText])
  const noOriginalGeometry = isOriginalShape(project.currentDocument) && !project.finalGeometry.length
  const hasPreviewShape = isOriginalShape(project.currentDocument) && !noOriginalGeometry || Boolean(fabricUnitCell(project.currentDocument))
  const fabricPreview = useFabricPreview(fabricPreviewInput, assetFetch, computeRequests.isBusy, {
    automatic: browser.activeMode !== 'design' && connection.kind === 'online' && hasPreviewShape,
    blocked: parameterPending || recipeSaving || project.evaluateStatus !== 'ready', computeBusy,
  })
  const fabricDisplayPlan = useMemo(() => hasPreviewShape ? temporaryFabricDimensions(fabricPreview.displayResult,
    fabricPreview.displayDocument, project.currentDocument, cellDraft) : null,
    [fabricPreview.displayResult, fabricPreview.displayDocument, project.currentDocument, cellDraft, hasPreviewShape])
  const linearActive = designContext === 'linear' && browser.activeMode === 'design' && Boolean(linearDraft)
  const linearCurrent = Boolean(linearDraft && linearDraft.sourceKey === JSON.stringify(project.currentDocument))
  const sizeGroup = linearDraft?.kind === 'radial' ? radialSizeGroup(parameterCatalog, linearDraft.source, linearDraft.bounds) : linearSizeGroup(parameterCatalog, linearDraft ?? undefined)
  const scalarSizeGroup = linearDraft?.kind === 'linear' ? sizeFieldGroup(parameterCatalog, linearDraft) : null
  const sizeDriverGroup = scalarSizeGroup?.parameters.length === 0
    ? { ...scalarSizeGroup, parameters: sizeGroup?.parameters.filter(p => p.id === 'angle') ?? [] } : scalarSizeGroup
  const updateSizeDraftValue = (key: string, value: import('./document/parameterSchema').ParameterValue) => {
    if (typeof value === 'number') setLinearDraft(current => !current ? null : current.kind === 'radial'
      ? { ...current, values: { ...current.values, [key]: value } } : { ...current, values: { ...current.values, [key]: value } })
  }
  const linearProposal = useMemo(() => {
    if (!linearActive || !linearCurrent || !linearDraft) return { dto: null, error: null }
    try {
      if (linearDraft.kind === 'linear' && ['image', 'distance'].includes(linearDraft.fieldType ?? '') &&
          !imageSourcesRef.current[linearDraft.imageAsset?.asset_id ?? '']?.blob.size)
        throw new Error('此尺寸效果缺少有效源图片，请选择 PNG/JPG 或已恢复源资产的参数场。参考底图不会自动参与。')
      return { dto: linearDraft.kind === 'radial' ? radialSizeCandidate(linearDraft, parameterCatalog) : linearSizeCandidate(linearDraft, parameterCatalog), error: null }
    }
    catch (error) { return { dto: null, error: error instanceof Error ? error.message : '渐变参数无效。' } }
  }, [linearActive, linearCurrent, linearDraft, parameterCatalog])
  const stagedLinear = useDocumentPreview(linearProposal.dto, assetFetch, null,
    linearActive && linearCurrent ? linearDraft!.sourceKey : '')
  const sizeProposalKey = useRef(''); sizeProposalKey.current = JSON.stringify(linearProposal.dto)
  const sizeFormPending = useMemo(() => {
    if (!linearDraft) return false
    if (linearDraft.kind !== 'linear' || !linearDraft.controlsOnly || !linearCurrent) return true
    try { return JSON.stringify(designCandidate(linearDraft.source, parameterCatalog, linearDraft.designValues, linearDraft.gridValues, linearDraft.artboard)) !== linearDraft.sourceKey }
    catch { return true }
  }, [linearDraft, linearCurrent, parameterCatalog])
  useEffect(() => {
    if (browser.activeMode !== 'design' && linearDraft?.kind === 'linear' && linearDraft.controlsOnly && !sizeFormPending) {
      setLinearDraft(null); publishDesignContext(null)
    }
  }, [browser.activeMode, linearDraft, sizeFormPending])
  useEffect(() => {
    // A workspace switch is not an explicit cancellation of a size-effect draft.
    if (designContext !== 'linear') setLinearDraft(null)
  }, [designContext])
  const geometryInputsPending = sizeFormPending || parameterPending || canvasEditing || Boolean(project.currentDocument && pendingLayoutFor(project.currentDocument, layoutDraft))
  const inputsReady = useRef(false)
  const inputSnapshot = useRef(project.currentDocument); inputSnapshot.current = project.currentDocument
  inputsReady.current = !geometryInputsPending && project.evaluateStatus === 'ready'
  const canUseInputs = useCallback(() => inputsReady.current && pendingControls.current.size === 0
    && activeDocumentRef.current === inputSnapshot.current, [])
  const safeCurrentResult = useCallback((id: string) => canUseInputs() && manufacturing.isCurrentResult(id), [manufacturing.isCurrentResult, canUseInputs])
  const stagedLayout = useLayoutPreview(layoutDraft, browser.activeMode === 'design' && !preparingLayout && !parameterPending
    && Boolean(project.currentDocument && pendingLayoutFor(project.currentDocument, layoutDraft)), assetFetch, layoutPreviewSeed)

  const reconnect = useCallback(() => setRetry((value) => value + 1), [])
  const publishHistory = (next: { past: PatternDocumentDTO[]; future: PatternDocumentDTO[] }) => {
    historyRef.current = next
    setHistoryCount({ past: next.past.length, future: next.future.length })
  }
  useEffect(() => {
    const controller = new AbortController()
    let current = true
    setConnection({ kind: 'checking', message: '正在连接后端…' })
    setParameterCatalog(null)
    setParameterLoad({ status: 'loading' })
    setFabricStlTestExportEnabled(undefined)
    setReleaseHealth(null)
    checkBackend(fetch, controller.signal).then(({ health, contract }) => {
      if (current) {
        setReleaseHealth(health)
        setFabricStlTestExportEnabled(contract.fabric_stl_test_export_enabled)
        setParameterCatalog(contract.parameter_definitions?.schema_version === '1.0' &&
          contract.parameter_definitions.units === 'mm' ? contract.parameter_definitions : null)
        setParameterLoad(contract.parameter_definitions?.schema_version === '1.0' && contract.parameter_definitions.units === 'mm'
          && contract.parameter_definitions.definitions
          ? { status: 'ready' } : { status: 'error', error: '参数定义响应缺失或版本／单位不匹配，请重试加载参数。' })
        setConnection({ kind: 'online', message: 'Backend Online' })
      }
    }).catch((error: unknown) => {
      if (!current) return
      setParameterLoad({ status: 'error', error: error instanceof Error ? error.message : '参数定义请求失败。' })
      if (error instanceof ContractMismatchError) setConnection({ kind: 'incompatible', message: error.message })
      else if (error instanceof BackendOfflineError) setConnection({ kind: 'offline', message: error.message })
      else setConnection({ kind: 'offline', message: '后端连接失败。' })
    })
    return () => { current = false; controller.abort() }
  }, [retry])
  useEffect(() => () => evaluateController.current?.abort(), [])
  useEffect(() => () => {
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
    const metadata = { reference_layer: referenceLayerRef.current, ...uiState, image_sources: imageSourcesRef.current, design_display: designDisplayRef.current }
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
    activeExampleSession, persistDraft, referenceLayer, designDisplay])

  useEffect(() => {
    if (draftSaveStatus !== 'saving' && draftSaveStatus !== 'error') return
    const guard = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', guard)
    return () => window.removeEventListener('beforeunload', guard)
  }, [draftSaveStatus])

  const saveBeforeReplacement = async () => {
    if (linearDraft && sizeFormPending && !window.confirm('尺寸变化尚未应用，未应用内容不会保存。切换作品将丢弃它；当前正式作品会先保存。继续？'))
      throw new Error('已取消切换，待应用尺寸配置和当前作品均保留。')
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

  const runEvaluate = useCallback((dto: PatternDocumentDTO, options: {
    fileName?: string; warnings?: string[]; fitOnSuccess?: boolean
    rollback?: PatternDocumentDTO
    onFailure?: () => void
  } = {}) => {
    evaluateController.current?.abort()
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
    })
  }, [assetFetch])

  const acceptProject = (dto: PatternDocumentDTO, fileName: string, warnings: string[], options: {
    pendingLayout?: LayoutDraft | null; exampleSessionActive?: boolean; restored?: boolean; referenceLayer?: ReferenceLayer | null
  } = {}) => {
    const pending = pendingLayoutFor(dto, options.pendingLayout ?? null)
    setRestorableDraft(null)
    lastValidDocumentRef.current = null
    setProjectError(null)
    ++layoutSequence.current
    setSelectedFamily(pending?.family ?? currentLayoutFamily(dto))
    setSelectedFieldId('')
    setLinearDraft(null)
    publishDesignContext(exampleIdFromDocument(dto) === 'gradient-grid' ? 'effects' : exampleIdFromDocument(dto) ? 'layout' : null)
    setReferenceLayer(options.referenceLayer ?? null)
    referenceLayerRef.current = options.referenceLayer ?? null
    setReferenceDraft(null)
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
    setBrowser((current) => ({ ...current, selectedElementIds: [], activeMode: options.restored ? workspaceModeFromLocation() : 'design' }))
    runEvaluate(dto, { fileName, warnings, fitOnSuccess: true })
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
          reference_layer: project.currentDocument ? referenceLayer : restorableDraft?.reference_layer,
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
  const canEditDocument = !recipeSaving && (project.evaluateStatus === 'ready' || (project.evaluateStatus === 'error'
    && lastValidDocumentRef.current?.document_id === project.currentDocument?.document_id))
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
    } })
  }

  const applyFabricRecipe = async (presetId: string) => {
    const dto = project.currentDocument
    if (!dto || !canEditDocument || recipeSavingRef.current) return
    if (linearDraft) {
      setProjectError('二维尺寸效果尚未应用，请返回设计先应用或取消，再应用 Fabric 配方。')
      return
    }
    recipeSavingRef.current = true; setRecipeSaving(true)
    try {
      await saveBeforeReplacement()
      if (activeDocumentRef.current !== dto) throw new Error('保护作品期间设计已变化，请重新应用配方。')
      const pending = pendingLayoutFor(dto, layoutDraft)
      const next = [directionalFabricRecipe.id, waveFabricRecipe.id, centerFabricRecipe.id].some(id => id === presetId)
        ? applyFabricHeightRecipe(dto, parameterCatalog, project.bounds,
          presetId === waveFabricRecipe.id ? 'wave' : presetId === centerFabricRecipe.id ? 'center' : 'directional', Number(manufacturing.heightText))
        : applyFabricPreset(dto, presetId, parameterCatalog)
      commitDocument(next, dto)
      // A Fabric edit must not Apply or lose a separate unconfirmed Layout form.
      if (pending) setLayoutDraft(retainPendingFabricLayout(pending, next))
    } catch (error) { setProjectError(error instanceof Error ? error.message : 'Fabric 配方应用失败。') }
    finally { recipeSavingRef.current = false; setRecipeSaving(false) }
  }
  const editFabricHeight = (mode: 'uniform' | 'directional' | 'wave' | 'center', key?: string, value?: import('./document/parameterSchema').ParameterValue) => {
    const dto = project.currentDocument
    if (!dto || !canEditDocument) return
    try {
      const pending = pendingLayoutFor(dto, layoutDraft)
      const working = isOriginalShape(dto) && !fabricBase(dto) ? setOriginalShape(dto, parameterCatalog, { height_mm: Number(manufacturing.heightText) }) : dto
      const updated = mode === 'uniform' ? setUniformFabricHeight(working, parameterCatalog)
        : mode === 'wave' ? setWaveFabricHeight(working, parameterCatalog, key && value !== undefined ? { [key]: value } : {})
        : mode === 'center' ? setCenterFabricHeight(working, parameterCatalog, project.bounds,
          key && typeof value === 'number' ? { [key]: value } : {})
        : setDirectionalFabricHeight(working, parameterCatalog, project.bounds,
          key && typeof value === 'number' ? { [key]: value } : {})
      const next = updated === dto ? dto : { ...updated, document_revision: dto.document_revision + 1 }
      commitDocument(next, dto)
      if (pending) setLayoutDraft(retainPendingFabricLayout(pending, next))
    } catch (error) {
      setProjectError(error instanceof Error ? error.message : '高度设置失败。')
      setParameterSyncVersion(version => version + 1)
    }
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
    if (!setDesignContext('layout')) return
    const sequence = ++layoutSequence.current
    setSelectedFamily(family)
    setBrowser(current => ({ ...current, activeMode: 'design' }))
    setLayoutPreviewSeed(null)
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
      if (sequence === layoutSequence.current && activeDocumentRef.current === dto) {
        setLayoutDraft({ family, sourceRevision: dto.document_revision, proposal: result.proposed_document, changed: false })
        if (result.preview) setLayoutPreviewSeed({ key: JSON.stringify(result.proposed_document), result: result.preview })
      }
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
  const selectLinearSize = (kind: 'linear' | 'radial' = 'linear', controlsOnly = false) => {
    const dto = project.currentDocument
    if (!dto || !canEditDocument || !project.bounds || !linearSizeGroup(parameterCatalog)) return
    if (pendingLayoutFor(dto, layoutDraft) || preparingLayout || parameterPending) {
      setProjectError('请先应用或取消未完成的布局/参数修改，再打开尺寸渐变。'); return
    }
    if (linearDraft && !window.confirm('已有未应用尺寸配置。打开另一个尺寸入口将丢弃它，正式作品不变。继续？')) return
    setLinearDraft(kind === 'radial' ? openRadialSize(dto, project.bounds) : { ...openLinearSize(dto, project.bounds), controlsOnly }); setLinearSync(value => value + 1)
    setDesignContext('linear'); setBrowser(current => ({ ...current, activeMode: 'design' })); setProjectError(null)
  }
  const applyLinearSize = async () => {
    const dto = project.currentDocument
    if (!dto || !linearDraft || !canEditDocument || canvasEditing || parameterPending || !stagedLinear.result || !linearProposal.dto ||
      linearDraft.sourceKey !== JSON.stringify(dto) || activeDocumentRef.current !== dto || pendingLayoutFor(dto, layoutDraft) || recipeSavingRef.current) return
    const proposal = linearProposal.dto, key = JSON.stringify(proposal)
    if (linearDraft.kind === 'linear' && linearDraft.controlsOnly && key === JSON.stringify(dto)) {
      setLinearDraft(null); publishDesignContext('effects'); return
    }
    recipeSavingRef.current = true; setRecipeSaving(true)
    try {
      await persistDraft(dto, project.fileName, sourceAssetRef.current, { pending_layout: null, example_session_active: activeExampleSession })
      if (activeDocumentRef.current !== dto || sizeProposalKey.current !== key) throw new Error('保存期间输入已变化，请重新确认最新预览。')
      commitDocument({ ...proposal, document_revision: dto.document_revision + 1 }, dto)
      setLinearDraft(null); publishDesignContext('effects')
    } catch (error) { setProjectError(`未应用配置，正式作品已保留：${error instanceof Error ? error.message : '当前作品保存失败。'}`) }
    finally { recipeSavingRef.current = false; setRecipeSaving(false) }
  }
  const exportDesign = async (type: 'svg' | 'png') => {
    const dto = project.currentDocument
    if (!dto || geometryInputsPending || project.evaluateStatus !== 'ready' || lastValidDocumentRef.current !== dto || designExportBusy) return
    setDesignExportBusy(true)
    try {
      const svg = designSvg(dto, { schema_version: '1.0', document_id: dto.document_id, document_revision: dto.document_revision,
        geometry: project.finalGeometry, bounds_mm: project.bounds, warnings: [] })
      const blob = type === 'svg' ? new Blob([svg], { type: 'image/svg+xml' })
        : await designPng(svg, designDisplay.pngWidth, dto.document.canvas.height / dto.document.canvas.width)
      if (activeDocumentRef.current !== dto) throw new Error('设计在导出期间已变化，请重新导出。')
      deliverDesign(blob, `xiaomang-pattern.${type}`)
    } catch (error) { setProjectError(error instanceof Error ? error.message : '设计导出失败。') }
    finally { setDesignExportBusy(false) }
  }
  const addPrimitive = (type: PrimitiveType) => {
    if (!connected || importing || parameterPending) return
    const before = project.currentDocument
    if (before && (!canEditDocument || pendingLayoutFor(before, layoutDraft))) {
      setProjectError('请先应用或取消未完成的布局/参数修改，再添加图形。'); return
    }
    if (!before && restorableDraft) { setDraftNotice('请先恢复上次作品，或点击“新建项目”确认后再添加图形。'); return }
    try {
      const next = appendPrimitive(before ?? createBlankDesign(crypto.randomUUID()), type)
      if (before) commitDocument(next.dto, before)
      else {
        acceptProject(next.dto, '原生二维设计', [])
        publishHistory({ past: [createBlankDesign(next.dto.document_id)], future: [] })
      }
      setBrowser(current => ({ ...current, selectedElementIds: [next.id], activeMode: 'design' }))
      setDesignContext('element')
    } catch (error) { setProjectError(error instanceof Error ? error.message : '无法添加图形。') }
  }
  const onReferenceFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; event.target.value = ''
    if (!file || !connected || importing || parameterPending) return
    const dto = project.currentDocument
    const sequence = ++referenceReadSequence.current
    if (!dto && restorableDraft) { setDraftNotice('请先恢复上次作品，或点击“新建项目”确认后再添加底图。'); return }
    if (dto && !canEditDocument) return
    try {
      const target = dto ?? createBlankDesign(crypto.randomUUID())
      const layer = await readReferenceLayer(file, target)
      if (sequence !== referenceReadSequence.current || activeDocumentRef.current !== dto) return
      if (!dto) acceptProject(target, '原生二维设计', [])
      setReferenceLayer(layer); setReferenceDraft(null); setDesignContext('reference')
      setBrowser(current => ({ ...current, activeMode: 'design', selectedElementIds: [] }))
    } catch (error) { setProjectError(error instanceof Error ? error.message : '参考底图载入失败。') }
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
    if (pendingLayoutFor(dto, layoutDraft)) {
      setProjectError('请先应用或取消布局修改，再编辑图形或效果。')
      setParameterSyncVersion(version => version + 1)
      return
    }
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
    : linearActive || parameterPending || canvasEditing || (project.currentDocument && pendingLayoutFor(project.currentDocument, layoutDraft))
      ? 'Editing · 待提交'
      : project.evaluateError || projectError ? 'Error · 修改未完成，可重试或撤销'
        : 'Ready · 就绪'

  const restoreLocalDraft = () => {
    if (!restorableDraft) return
    sourceAssetRef.current = restorableDraft.source_asset
    setDesignDisplay(restorableDraft.design_display ?? defaultDesignDisplay)
    imageSourcesRef.current = restorableDraft.image_sources ?? {}
    acceptProject(restorableDraft.dto, restorableDraft.file_name ?? '上次编辑', [], {
      pendingLayout: restorableDraft.pending_layout,
      exampleSessionActive: restorableDraft.example_session_active,
      restored: true,
      referenceLayer: restorableDraft.reference_layer,
    })
  }
  const restorePreExampleDraft = async () => {
    if (!preExampleDraft) return
    try {
      await saveBeforeReplacement()
      sourceAssetRef.current = preExampleDraft.source_asset
      setDesignDisplay(preExampleDraft.design_display ?? defaultDesignDisplay)
      imageSourcesRef.current = preExampleDraft.image_sources ?? {}
      acceptProject(preExampleDraft.dto, preExampleDraft.file_name ?? '示例前的作品', [], {
        pendingLayout: preExampleDraft.pending_layout, restored: true, referenceLayer: preExampleDraft.reference_layer,
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
        <a className="pattern-library-link" href="/patterns/" target="_blank" rel="noopener noreferrer">小芒图案库 ↗</a>
        <div className={`backend-badge ${connection.kind}`} role="status" aria-live="polite">
          <span className="status-light" aria-hidden="true" />
          {connected ? '已连接' : connection.kind === 'checking' ? '正在连接' : connection.kind === 'offline' ? '连接中断' : '连接不兼容'}
        </div>
      </div>
    </header>

    <div className={`work-area ${browser.activeMode !== 'design' ? 'manufacture-layout' : ''}`}>
      <aside className="sidebar" aria-label="左侧工具栏">
        <div className="sidebar-intro"><span className="eyebrow">WORKSPACE / 工作台</span><p>导入图片，设计可直接编辑的二维图案。</p></div>
        <section className="side-group" aria-label="素材来源">
          <div className="group-heading"><span>01</span><h2>素材来源</h2></div>
          <div className="side-items">
            <button className="side-item" type="button" disabled={importing || !connected}
              onClick={() => imageInputRef.current?.click()}><span className="side-item-mark">▧</span>导入 PNG / JPG</button>
            <button className="side-item" type="button" disabled={importing || !connected}
              onClick={() => svgInputRef.current?.click()}><span className="side-item-mark">◇</span>导入 SVG</button>
          </div>
        </section>
        {project.currentDocument && <section className="side-group" aria-label="内置示例">
          <div className="group-heading"><span>EX</span><h2>内置示例</h2></div>
          <button className="side-item" type="button" aria-expanded={exampleChooserOpen}
            onClick={() => setExampleChooserOpen((open) => !open)}><span className="side-item-mark">◉</span>试用示例</button>
          {exampleChooserOpen && <div className="sidebar-examples">{examples.map((example) => <ExampleCard
            key={example.id} example={example} onOpen={(id) => void openExample(id)} disabled={!connected || importing} />)}</div>}
        </section>}
        <section className="side-group" aria-label="图案逻辑">
          <div className="group-heading"><span>02</span><h2>图案逻辑</h2></div>
          <p className="pattern-analysis-status">当前结构：{patternItems.find((item) => item.id === committedFamily)?.label}</p>
          <div className="side-items">{patternItems.map((item) => {
            const available = Boolean(project.currentDocument && connected && !applyingPattern
              && (item.id === 'free' || hasEditableGeometry))
            return <button className={`side-item ${selectedFamily === item.id ? 'selected' : ''}`} key={item.id}
              type="button" disabled={!available} aria-pressed={selectedFamily === item.id}
              title={available ? '仅选择候选结构，不改变元素位置。' : '请先导入有效的二维图案。'}
              onClick={() => void selectLayout(item.id)}>
              <span className="side-item-mark" aria-hidden="true">{item.mark}</span>
              <span>{item.label}</span>
              {!available && <span className="soon-dot" aria-hidden="true" />}
            </button>
          })}</div>
          {selectedFamily && <p className="pattern-analysis-status">已选：{patternItems.find((item) => item.id === selectedFamily)?.label}。在右侧调整并应用。</p>}
        </section>
        <section className="side-group" aria-label="基础图形">
          <div className="group-heading"><span>03</span><h2>基础图形</h2></div>
          <div className="side-items">{([['circle', '圆形'], ['ellipse', '椭圆'], ['rect', '矩形']] as const).map(([type, label]) =>
            <button className="side-item" key={type} type="button" disabled={!connected || importing || parameterPending}
              onClick={() => addPrimitive(type)}>＋ 添加{label}</button>)}</div>
          <small>添加一个独立图形，不替换当前图案。</small>
        </section>
        <section className="side-group" aria-label="参考底图">
          <div className="group-heading"><span>04</span><h2>添加底图</h2></div>
          <button className="side-item" type="button" disabled={!connected || importing || parameterPending}
            onClick={() => referenceInputRef.current?.click()}>{referenceLayer ? '更换参考底图' : '添加参考底图'}</button>
          {referenceLayer && <button className="side-item" type="button" onClick={() => setDesignContext('reference')}>底图属性</button>}
          <small>仅二维参考，不生成图案，不进入 STL。</small>
        </section>
        <section className="side-group" aria-label="参数场与效果">
          <button className="side-item" type="button" disabled={!project.currentDocument}
            onClick={() => { setDesignContext('effects'); setBrowser(current => ({ ...current, activeMode: 'design' })) }}>参数场与效果</button>
          <span className="eyebrow">尺寸变化效果</span>
          <button type="button" className="side-item" disabled={!canEditDocument || !project.bounds || !groupFor(parameterCatalog, 'design', 'shape')}
            onClick={() => selectLinearSize('linear', true)}>图案控制 · 排列/形状/随机/画板</button>
          <button type="button" className={`side-item ${linearActive && linearDraft?.kind === 'linear' ? 'selected' : ''}`}
            disabled={!canEditDocument || !project.bounds || !linearSizeGroup(parameterCatalog)}
            title="尺寸变化：线性、波浪、条纹及其他参数场共用此入口" onClick={() => selectLinearSize()}>尺寸变化</button>
          <small className="inspector-readonly">支持切换波浪、条纹、棋盘、噪声、图片等驱动。</small>
          <button type="button" className={`side-item ${linearActive && linearDraft?.kind === 'radial' ? 'selected' : ''}`}
            disabled={!canEditDocument || !project.bounds || !project.currentDocument || !radialSizeGroup(parameterCatalog, project.currentDocument)}
            onClick={() => selectLinearSize('radial')}>径向尺寸渐变</button>
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
            <Workspace2D geometry={(linearActive && linearCurrent ? stagedLinear.displayResult?.geometry ?? project.finalGeometry : stagedLayout.result?.geometry ?? project.finalGeometry).map(item => designContext === 'element' && item.id === selectedId && sourceCanDrag(item)
              ? { ...item, ...elementDraft } : item)} bounds={(linearActive && linearCurrent ? stagedLinear.displayResult?.bounds_mm : null) ?? stagedLayout.result?.bounds_mm ?? project.bounds ?? (referenceLayer ? {
                min_x: referenceLayer.x_mm - referenceLayer.width_mm / 2, min_y: referenceLayer.y_mm - referenceLayer.height_mm / 2,
                max_x: referenceLayer.x_mm + referenceLayer.width_mm / 2, max_y: referenceLayer.y_mm + referenceLayer.height_mm / 2,
                width: referenceLayer.width_mm, height: referenceLayer.height_mm, units: 'mm',
              } : null)} mmPerUnit={scale}
              referenceLayer={referenceLayer && referenceUrl ? { ...(referenceDraft ?? referenceLayer), url: referenceUrl } : null}
              onSelectReference={() => { setDesignContext('reference'); setBrowser(current => ({ ...current, selectedElementIds: [] })) }}
              view={browser.viewTransform}
              onViewChange={(viewTransform) => setBrowser((current) => ({ ...current, viewTransform }))}
              selectedId={selectedId}
              onSelect={(id) => { if (linearActive && !id) return; setBrowser((current) => ({ ...current, selectedElementIds: id ? [id] : [] })); setDesignContext(id ? 'element' : null) }}
              artboard={project.currentDocument ? { x: (project.currentDocument.document.canvas.origin_x ?? 0) * (millimetresPerUnit(project.currentDocument.document) ?? 1), y: (project.currentDocument.document.canvas.origin_y ?? 0) * (millimetresPerUnit(project.currentDocument.document) ?? 1),
                width: (linearDraft?.kind === 'linear' && linearDraft.artboard ? linearDraft.artboard.width : project.currentDocument.document.canvas.width * (millimetresPerUnit(project.currentDocument.document) ?? 1)),
                height: (linearDraft?.kind === 'linear' && linearDraft.artboard ? linearDraft.artboard.height : project.currentDocument.document.canvas.height * (millimetresPerUnit(project.currentDocument.document) ?? 1)), grid: designDisplay.grid } : undefined}
              influenceAreas={linearActive && linearCurrent && canEditDocument && linearDraft?.kind === 'linear' && linearDraft.values.scope_mode === 'areas' ? linearDraft.influenceAreas : undefined}
              selectedArea={linearDraft?.kind === 'linear' ? linearDraft.selectedArea : undefined}
              onAreaChange={(id, parameters) => setLinearDraft(draft => draft?.kind === 'linear' ? { ...draft, selectedArea: id,
                influenceAreas: draft.influenceAreas?.map(a => a.id === id ? { ...a, parameters: { ...a.parameters, ...parameters } } : a) } : draft)}
              gradientControl={linearActive && linearCurrent && canEditDocument && linearDraft && !(linearDraft.kind === 'linear' && (linearDraft.controlsOnly || linearDraft.values.scope_mode === 'areas')) ? linearDraft.kind === 'radial' ? linearDraft
                : (!linearDraft.fieldType || linearDraft.fieldType === 'linear') && !linearDraft.existingFieldId && !linearDraft.explicitLinear ? linearDraft
                : linearDraft.values.scope_mode === 'local' ? { ...linearDraft, kind: 'region', values: { ...linearDraft.values, angle: linearDraft.values.scope_angle ?? 0 } } : null : null}
              onGradientChange={values => {
                if (!linearCurrent || !canEditDocument || !sizeGroup) return
                const changes = linearDraft?.kind === 'linear' && (linearDraft.fieldType && linearDraft.fieldType !== 'linear' || linearDraft.existingFieldId || linearDraft.explicitLinear) && 'angle' in values
                  ? { ...values, scope_angle: values.angle } : values
                if (changes !== values) delete (changes as Record<string, number>).angle
                const valid = Object.entries(changes).every(([key, value]) => {
                  const definition = sizeGroup.parameters.find(item => item.id === key)
                  return definition && validateParameter(definition, value)
                })
                if (valid) setLinearDraft(current => !current ? null : current.kind === 'radial'
                  ? { ...current, values: { ...current.values, ...changes } } : { ...current, values: { ...current.values, ...changes } })
              }}
              canDrag={item => !linearActive && !pendingLayoutFor(project.currentDocument!, layoutDraft) && sourceCanDrag(item)} onDragCommit={commitDrag} pendingPreview={pendingPreview} fitToken={fitToken}
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
          ) : fabricBase(project.currentDocument) || isOriginalShape(project.currentDocument) ? null : <PreviewPanel hideExport result={manufacturing.result} status={manufacturing.status}
            projectName={project.fileName} isCurrentResult={safeCurrentResult}
            document={project.currentDocument} fabricPreview={fabricPreview.result}
            fabricStlTestExportEnabled={fabricStlTestExportEnabled}
            onGoManufacture={() => setBrowser((current) => ({ ...current, activeMode: 'manufacture' }))} />}
          {(fabricBase(project.currentDocument) || isOriginalShape(project.currentDocument)) && <section className="fabric-live-stage" hidden={browser.activeMode === 'design'} aria-label="中央 Fabric 设计预览">
            <header className="fabric-live-heading"><strong>3D 设计预览</strong><small>设计预览不代表最终制造已通过</small>
              <span role="status">{noOriginalGeometry ? '请先导入图案或在设计中添加图形' : !hasPreviewShape ? '旧作品未选择形状，请在右侧启用保留原图或选择造型' : parameterPending ? Object.keys(cellDraft).length && fabricDisplayPlan !== fabricPreview.displayResult
                ? '临时显示 · 松手提交后校准' : '有未提交参数 · 松手后自动更新'
                : fabricPreview.status === 'building' ? '正在更新 · 保留上次有效画面' : fabricPreview.status === 'stale' ? '设计已变化 · 等待更新' : fabricPreview.error ?? ''}</span></header>
            {fabricDisplayPlan ? <FabricThreePreview key={project.currentDocument?.document_id} plan={fabricDisplayPlan}
              stale={fabricPreview.status !== 'ready'} />
              : <div className="preview-empty"><p>{noOriginalGeometry ? '当前没有可挤出的原图。请导入图案或在设计中添加图形。' : !hasPreviewShape ? '在右侧选择单元类型，即可查看设计预览。' : fabricPreview.error ?? '正在准备原图或单元设计预览，请稍候。'}</p></div>}
          </section>}
          {project.evaluateStatus === 'loading' && <div className="viewer-notice" role="status">Python 正在计算最终二维几何…</div>}
          {linearActive && <div className="viewer-notice" role="status">未应用的尺寸渐变预览 · {!linearCurrent ? '正式设计已变化，请重新打开效果' :
            linearProposal.error ?? stagedLinear.error ?? (stagedLinear.pending ? '正在计算最新输入 · 保留上次有效画面' : '点击右侧应用，或取消恢复')}</div>}
          {browser.activeMode === 'design' && project.currentDocument && pendingLayoutFor(project.currentDocument, layoutDraft) &&
            <div className="viewer-notice" role="status">未应用的布局预览 · {stagedLayout.pending ? '正在计算最新输入' : stagedLayout.error ?? '点击右侧应用，或取消恢复'} </div>}
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
                ? 'complete' : 'not-ready'}
              aria-label={`${mode.id === 'manufacture' ? '制造' : '设计'} ${mode.secondary}`}
              aria-current={browser.activeMode === mode.id ? 'page' : undefined}
              onClick={() => setBrowser((current) => ({ ...current, activeMode: mode.id }))}>
              <span>{mode.label}</span><small>{mode.secondary}</small>
            </button>)}
          <span className="mode-bar-spacer" /><span className="interaction-status" role="status" aria-label="编辑状态">{interactionStatus}</span>
        </nav>
      </main>

      <aside className={`inspector ${browser.activeMode !== 'design' ? 'manufacture-inspector' : ''}`} aria-label="右侧检查器">
        <div className="inspector-title"><div><span className="eyebrow">PROPERTIES</span><h2>检查器</h2></div><span className="inspector-dots" aria-hidden="true">•••</span></div>
        <div className="inspector-content">
        {!project.currentDocument && <div className="inspector-empty"><span className="inspect-glyph" aria-hidden="true">⌗</span><strong>未选择对象</strong><p>No selection</p><small>点击元素可查看其世界毫米信息。</small></div>}
        {project.currentDocument && <div style={{ display: browser.activeMode === 'design' ? undefined : 'none' }}><InspectorControls key={project.currentDocument.document_id}
          selectionCount={browser.selectedElementIds.length}
          context={designContext === 'reference' || designContext === 'linear' || !designContext ? 'none' : designContext}
          onElementDraft={(key, value) => setElementDraft(current => {
            const next = { ...current }; if (typeof value === 'number') next[key] = value; else delete next[key]; return next
          })}
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
          onEdit={editParameter} disabled={!canEditDocument} />
          {!designContext && <p className="inspector-readonly">在左侧选择图案逻辑、参数场或底图，或点击画布中的图形以编辑。</p>}
          {linearActive && linearDraft && sizeGroup && <section aria-label={linearDraft.kind === 'radial' ? '径向尺寸渐变参数' : '尺寸变化参数'}>
            <h3>{linearDraft.kind === 'radial' ? '径向尺寸渐变' : linearDraft.controlsOnly ? '完整图案控制' : '参数场驱动的尺寸变化'}</h3>
            <p className="layout-pending" role="status">{sizeFormPending ? '有未应用修改' : '公共参数未改变 · 显示设置无需应用到几何'}</p>
            {linearDraft.kind === 'linear' && <ParameterInteraction.Provider value={{ syncToken: String(linearSync), onPending: onParameterPending }}>
              <fieldset disabled={!linearCurrent || !canEditDocument} style={{ border: 0, padding: 0, minWidth: 0 }}>
                <DesignPanelControls draft={linearDraft} catalog={parameterCatalog} onChange={setLinearDraft} display={designDisplay} onDisplay={setDesignDisplay} />
              </fieldset>
            </ParameterInteraction.Provider>}
            {linearDraft.kind === 'linear' && !linearDraft.controlsOnly && <>
              <div className="field-picker"><label htmlFor="size-field-source">驱动来源</label>
                <select id="size-field-source" disabled={!linearCurrent || !canEditDocument || parameterPending}
                  value={linearDraft.existingFieldId ? 'existing' : 'owned'} onChange={event => {
                    if (event.target.value === 'owned') setLinearDraft(selectSizeField(linearDraft, linearDraft.fieldType ?? 'linear', parameterCatalog))
                    else { const field = project.currentDocument?.document.fields.find(f => f.enabled !== false && sizeFieldTypes(parameterCatalog).some(([id]) => f.type === id))
                      if (field) setLinearDraft(selectSizeField(linearDraft, String(field.type), parameterCatalog, String(field.id)))
                      else setProjectError('没有可绑定的已启用参数场。请先在高级面板创建，或使用本效果专用场。') }
                    setLinearSync(v => v + 1)
                  }}><option value="owned">快捷：本效果专用场</option><option value="existing">高级：绑定已有场</option></select>
              </div>
              <div className="field-picker"><label htmlFor="size-field-type">变化方式</label>
                <select id="size-field-type" disabled={!linearCurrent || !canEditDocument || parameterPending}
                  value={linearDraft.fieldType ?? 'linear'} onChange={event => {
                    setLinearDraft(selectSizeField(linearDraft, event.target.value, parameterCatalog)); setLinearSync(v => v + 1)
                  }}>{sizeFieldTypes(parameterCatalog).map(([id, group]) => <option key={id} value={id}>{group.label}</option>)}</select>
              </div>
              {linearDraft.existingFieldId && <div className="field-picker"><label htmlFor="size-existing-field">已有场</label>
                <select id="size-existing-field" value={linearDraft.existingFieldId} disabled={!linearCurrent || !canEditDocument || parameterPending}
                  onChange={event => { const field = project.currentDocument!.document.fields.find(f => f.id === event.target.value)!
                    setLinearDraft(selectSizeField(linearDraft, String(field.type), parameterCatalog, String(field.id))); setLinearSync(v => v + 1) }}>
                  {project.currentDocument.document.fields.filter(f => f.enabled !== false && sizeFieldTypes(parameterCatalog).some(([id]) => f.type === id))
                    .map(f => <option key={String(f.id)} value={String(f.id)}>{groupFor(parameterCatalog, 'field', String(f.type))?.label} · {String(f.id)}</option>)}
                </select><small>绑定未改动的已有场；修改下方场参数时只编辑本效果副本，不改变原共享场。</small></div>}
              {['image', 'distance'].includes(linearDraft.fieldType ?? '') && <div>
                <p className="inspector-readonly">源图片：{imageSourcesRef.current[linearDraft.imageAsset?.asset_id ?? '']?.filename ?? '未选择或尚未恢复'}。图片采样范围使用文档世界坐标；参考底图不会自动参与。</p>
                <button type="button" disabled={!linearCurrent || !canEditDocument} onClick={() => {
                  fieldImageTarget.current = '__size_draft'; fieldImageInputRef.current?.click()
                }}>选择尺寸效果源图片</button>
              </div>}
              {sizeDriverGroup && sizeDriverGroup.parameters.length > 0 && <ParameterInteraction.Provider value={{ syncToken: String(linearSync), onPending: onParameterPending }}>
                <fieldset disabled={!linearCurrent || !canEditDocument} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
                  <h4>场参数 · {sizeDriverGroup.label}</h4>
                  <ParameterPanel group={sizeDriverGroup} values={{ ...linearDraft.values, ...sizeFieldValues(linearDraft, parameterCatalog) }} onCommit={(key, value) => {
                    if (key === 'angle') { updateSizeDraftValue(key, value); return }
                    try { setLinearDraft(current => current?.kind === 'linear' ? changeSizeFieldParameter(current, parameterCatalog, key, value) : current) }
                    catch (error) { setProjectError(error instanceof Error ? error.message : '场参数无效。') }
                  }} />
                </fieldset>
              </ParameterInteraction.Provider>}
            </>}
            <p className="inspector-readonly">{linearDraft.kind === 'radial'
              ? '作用于全部有效图案元素，保留原中心与布局。按到中心的直线距离变化；半径处及范围外保持外围比例。线性及其他尺寸效果仍按原顺序叠加。'
              : linearDraft.controlsOnly ? '公共参数只控制二维结构源，之后沿用现有场与效果顺序；不会创建尺寸场或改变制造输出模式。'
              : linearDraft.values.scope_mode === 'areas' ? '只在启用影响区内施加本层尺寸变化；重叠取最大权重，外部保留之前效果。'
              : linearDraft.values.scope_mode === 'local' ? '只按进入本效果时的元素中心判断矩形范围；区域外完整保留之前效果。过渡只混合本层尺寸变化，不切割轮廓，不移动中心。'
              : !linearDraft.fieldType || linearDraft.fieldType === 'linear' ? `作用于全部有效图案元素，保留原中心与布局。${linearDraft.values.invert ? '已反转：方向起点为最大比例，终点为最小比例' : '方向起点为最小比例，终点为最大比例'}；范围外保持端点值。`
              : '参数场输出 0–1 标量，再映射为尺寸比例。只改变各元素大小，保留中心、旋转与原布局；实际变化取决于各元素中心的采样值。'}</p>
            <p className="inspector-readonly">图案参考范围：X {linearDraft.bounds.min_x.toFixed(2)}–{linearDraft.bounds.max_x.toFixed(2)} mm，Y {linearDraft.bounds.min_y.toFixed(2)}–{linearDraft.bounds.max_y.toFixed(2)} mm。{linearDraft.kind === 'linear' && linearDraft.values.scope_mode === 'local' ? '局部区域由下方中心、方向、长度和宽度独立确定。' : ''}</p>
            {project.currentDocument.document.modifiers.some(item => item.type === 'size' && item.enabled !== false && item.id !== linearSizeOwner(project.currentDocument!)?.modifier.id) &&
              <p className="inspector-readonly">其他尺寸效果仍按现有顺序叠加；本效果不会关闭它们。</p>}
            {! (linearDraft.kind === 'linear' && linearDraft.controlsOnly) && <ParameterInteraction.Provider value={{ syncToken: String(linearSync), onPending: onParameterPending }}>
              <fieldset disabled={!linearCurrent || !canEditDocument} style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}>
                {linearDraft.kind === 'radial' ? <ParameterPanel group={sizeGroup} values={{ ...linearDraft.values }} onCommit={updateSizeDraftValue} /> : <>
                  <h4>尺寸映射</h4>
                  <small>作用强度即本尺寸层的逻辑强度；0保留之前尺寸，1应用完整映射。不会改变共享场或其他消费者。</small>
                  <label><input type="checkbox" checked={linearDraft.values.invert ?? false} onChange={e => setLinearDraft({ ...linearDraft, values: { ...linearDraft.values, invert: e.target.checked } })} />反转渐变（仅本层）</label>
                  <ParameterPanel group={{ ...sizeGroup, parameters: sizeGroup.parameters.filter(p => ['min_output', 'max_output', 'strength'].includes(p.id)) }}
                    values={{ ...linearDraft.values }} onCommit={updateSizeDraftValue} />
                  <h4>作用范围</h4>
                  <div className="field-picker"><label htmlFor="linear-scope-mode">作用范围</label><select id="linear-scope-mode" value={linearDraft.values.scope_mode ?? 'global'}
                    onChange={event => {
                      const mode = event.target.value as 'global' | 'local' | 'areas'
                      setLinearDraft(current => current?.kind === 'linear' ? { ...current, values: { ...linearRegionDefaults(current.bounds), ...current.values, scope_mode: mode } } : current)
                    }}><option value="global">全图</option><option value="local">局部区域</option><option value="areas">多影响区（最多3个）</option></select></div>
                  {linearDraft.values.scope_mode === 'areas' && <DesignPanelControls areaOnly draft={linearDraft} catalog={parameterCatalog} onChange={setLinearDraft} display={designDisplay} onDisplay={setDesignDisplay} />}
                  <ParameterPanel group={{ ...sizeGroup, parameters: sizeGroup.parameters.filter(p => !['angle', 'min_output', 'max_output', 'strength'].includes(p.id)) }}
                    values={{ ...linearDraft.values }} onCommit={updateSizeDraftValue} />
                </>}
              </fieldset>
            </ParameterInteraction.Provider>}
            <p className="inspector-readonly">画布控制点拖动中限频自动预览；数值控件松手或确认后自动预览。控制点松手仍未应用，点击应用才提交。未应用输入不会保存；刷新或切换上下文将丢弃它们。</p>
            <div className="layout-inspector-actions">
              <button type="button" onClick={() => { setLinearDraft(current => current ? current.kind === 'radial'
                ? { ...current, values: radialSizeDefaults(current.bounds) } : resetLinearSizeDraft(current, parameterCatalog) : null); setLinearSync(value => value + 1) }}>恢复默认</button>
              <button type="button" onClick={() => { setLinearDraft(null); publishDesignContext('effects') }}>取消效果</button>
              <button type="button" className="ui-primary" disabled={!canEditDocument || !linearCurrent || canvasEditing || parameterPending || !stagedLinear.result || !linearProposal.dto}
                onClick={applyLinearSize}>应用效果</button>
            </div>
          </section>}
          <section aria-label="当前设计导出">
            <h3>导出当前设计</h3>
            <p className="inspector-readonly">{geometryInputsPending ? '请先应用或取消待确认配置，再导出当前设计。' : '按画板边界导出已应用结果；不含底图、网格及辅助标记。'}</p>
            <div className="layout-inspector-actions">
            <button type="button" className="ui-secondary" disabled={geometryInputsPending || project.evaluateStatus !== 'ready' || designExportBusy || !project.finalGeometry.length} onClick={() => void exportDesign('svg')}>下载设计SVG</button>
            <button type="button" className="ui-secondary" disabled={geometryInputsPending || project.evaluateStatus !== 'ready' || designExportBusy || !project.finalGeometry.length} onClick={() => void exportDesign('png')}>下载透明PNG</button>
            </div>
          </section>
          {designContext === 'reference' && referenceLayer && <ReferenceLayerPanel layer={referenceLayer}
            onCommit={(key, value) => {
              try { setReferenceLayer(updateReferenceLayer(referenceLayer, key, value)); setReferenceDraft(null) }
              catch (error) { setProjectError(error instanceof Error ? error.message : '底图参数无效。') }
            }} onDraft={(key, value) => {
              try { setReferenceDraft(value === null ? null : updateReferenceLayer(referenceLayer, key, value)) }
              catch { setReferenceDraft(null) }
            }} onRemove={() => { setReferenceLayer(null); setReferenceDraft(null); setDesignContext(null) }} />}
        </div>}
        <div className="manufacturing-inspector-form" hidden={browser.activeMode === 'design'}>
            {sizeFormPending && <p className="layout-pending" role="status">二维尺寸效果尚未应用。当前3D仅显示已应用设计；请返回设计应用或取消后再制造／下载。</p>}
            <ManufacturingPanel heightText={manufacturing.heightText} onHeightChange={manufacturing.setHeightText}
              projectWarnings={project.warnings}
              document={project.currentDocument} designBounds={project.bounds} parameterCatalog={parameterCatalog}
              parameterLoad={parameterLoad} onRetryParameters={reconnect}
              actionHost={manufacturingActionHost} parametersDisabled={!canEditDocument} onUnitCellDraft={onUnitCellDraft} canUseInputs={canUseInputs}
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
              onOutputMode={(mode) => {
                const dto = project.currentDocument
                if (!dto || !canEditDocument) return
                try { const working = !fabricBase(dto) && isOriginalShape(dto) ? setOriginalShape(dto, parameterCatalog, { height_mm: Number(manufacturing.heightText) }) : dto
                  commitDocument({ ...setFabricOutputMode(working, mode), document_revision: dto.document_revision + 1 }, dto) }
                catch (error) { setProjectError(error instanceof Error ? error.message : '输出方式无效。') }
              }}
              onUnitCellType={(type) => {
                const dto = project.currentDocument
                if (!dto || !canEditDocument) return
                if (type !== 'none' && parameterLoad.status !== 'ready') {
                  setProjectError(parameterLoad.status === 'loading' ? '正在加载单元参数，请稍候。' : parameterLoad.error ?? '单元参数加载失败，请重试。')
                  return
                }
                try {
                  if (type === 'original') commitDocument(setOriginalShape(dto, parameterCatalog,
                    dto.document.metadata.fabric_config ? {} : { height_mm: Number(manufacturing.heightText) }), dto)
                  else {
                    const working = fabricBase(dto) ? dto : setOriginalShape(dto, parameterCatalog, { height_mm: Number(manufacturing.heightText) })
                    commitDocument({ ...setFabricUnitCellType(working, type, parameterCatalog), document_revision: dto.document_revision + 1 }, dto)
                  }
                }
                catch (error) { setProjectError(`切换 ${type} 失败：${error instanceof Error ? error.message : 'Unit Cell 配置无效。'} 当前仍为 ${fabricUnitCell(dto)?.type ?? '无单元'}。`) }
              }}
              onOriginalShapeParameter={(key, value) => {
                const dto = project.currentDocument
                if (!dto || !canEditDocument) return
                try { const pending = pendingLayoutFor(dto, layoutDraft)
                  const next = setOriginalShape(dto, parameterCatalog, {
                    ...((dto.document.metadata.fabric_config as any)?.original_shape ? {} : { height_mm: Number(manufacturing.heightText) }),
                    [key]: value,
                  })
                  commitDocument(next, dto)
                  if (pending) setLayoutDraft(retainPendingFabricLayout(pending, next))
                } catch (error) { setProjectError(error instanceof Error ? error.message : '原图参数无效。'); setParameterSyncVersion(v => v + 1) }
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
                try {
                  const working = isOriginalShape(dto) && !fabricBase(dto)
                    ? setOriginalShape(dto, parameterCatalog, { height_mm: Number(manufacturing.heightText) }) : dto
                  const next = setFabricModifierEnabled(working, type, enabled, parameterCatalog)
                  commitDocument(next === dto ? dto : { ...next, document_revision: dto.document_revision + 1 }, dto)
                }
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
              onFabricPreset={presetId => void applyFabricRecipe(presetId)} recipeSaving={recipeSaving}
              onHeightEffect={mode => editFabricHeight(mode)}
              onDirectionalHeightParameter={(key, value) => editFabricHeight('directional', key, value)}
              onWaveHeightParameter={(key, value) => editFabricHeight('wave', key, value)}
              onCenterHeightParameter={(key, value) => editFabricHeight('center', key, value)}
              heightSyncToken={`${project.documentRevision}:${project.evaluateStatus}:${parameterSyncVersion}`}
              onHeightPending={onParameterPending}
              computeBusy={computeBusy} isComputeBusy={computeRequests.isBusy}
              fabricPreviewStatus={fabricPreview.status} fabricPreviewResult={fabricPreview.result}
              fabricPreviewError={fabricPreview.error} onUpdateFabricPreview={() => { if (canUseInputs()) void fabricPreview.update() }}
              candidateFetcher={assetFetch}
              fabricStlTestExportEnabled={fabricStlTestExportEnabled}
              validHeight={manufacturing.validHeight} canBuild={connected && project.evaluateStatus === 'ready'
                && Boolean(project.currentDocument) && manufacturing.validHeight && !geometryInputsPending}
              onBuild={() => { if (canUseInputs()) void manufacturing.build() }} status={manufacturing.status}
              result={manufacturing.result} error={manufacturing.error} projectName={project.fileName}
              isCurrentResult={safeCurrentResult}
              onBackDesign={() => setBrowser((current) => ({ ...current, activeMode: 'design' }))}
              onPreview={() => setBrowser((current) => ({ ...current, activeMode: 'manufacture' }))} />
        </div>
        <div className={`connection-card ${connection.kind}`}>
          <div className="connection-card-head"><span>连接状态</span><span className="connection-state-text">{connected ? '已连接' : connection.kind === 'checking' ? '检查中' : connection.kind === 'offline' ? '离线' : '协议不兼容'}</span></div>
          {!connected && <p>{connection.message}</p>}
          {!connected && connection.kind !== 'checking' && <button type="button" onClick={reconnect}>重新检测连接</button>}
          {connected && project.evaluateStatus === 'error' && project.currentDocument &&
            <button type="button" onClick={() => runEvaluate(project.currentDocument!)}>重试二维求值</button>}
          <details className="diagnostic-details"><summary>诊断详情</summary>
            <p>Python Engine · Contract <strong>v{EXPECTED_SCHEMA_VERSION}</strong> · mm</p>
            <ReleaseDiagnostics health={releaseHealth} />
            {!connected && <p>待验证</p>}
            {project.currentDocument && <p>文档修订：{project.documentRevision}<span className="visually-hidden">revision {project.documentRevision}</span></p>}
            <p>{connection.message}</p>
          </details>
        </div>
        </div>
        <div className="manufacturing-action-dock" hidden={browser.activeMode === 'design'} ref={setManufacturingActionHost} />
      </aside>
    </div>
    {/* Test fixture loader only; absent from development/production UI and accessibility tree. */}
    {import.meta.env.MODE === 'test' && <input ref={inputRef} type="file" accept=".json,application/json" className="visually-hidden"
      aria-label="选择 PatternDocument 项目文件" onChange={(event) => void onFile(event)} />}
    <input ref={imageInputRef} type="file" accept=".png,.jpg,.jpeg,image/png,image/jpeg" className="visually-hidden"
      aria-label="选择 PNG 或 JPG 图片" onChange={onImageFile} />
    <input ref={svgInputRef} type="file" accept=".svg,image/svg+xml" className="visually-hidden"
      aria-label="选择 SVG 图片" onChange={onImageFile} />
    <input ref={referenceInputRef} type="file" accept=".png,.jpg,.jpeg,image/png,image/jpeg" className="visually-hidden"
      aria-label="选择二维参考底图" onChange={event => void onReferenceFile(event)} />
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
          if (fieldImageTarget.current === '__size_draft') {
            imageSourcesRef.current = { ...imageSourcesRef.current, [token]: { blob: file, filename: file.name, media_type: mediaType } }
            setLinearDraft(current => current?.kind === 'linear' && ['image', 'distance'].includes(current.fieldType ?? '')
              ? { ...current, imageAsset: { role: '', asset_id: token, media_type: mediaType } } : current)
            return
          }
          const next = bindImageSource(dto, fieldImageTarget.current, token, mediaType)
          imageSourcesRef.current = { ...imageSourcesRef.current,
            [token]: { blob: file, filename: file.name, media_type: mediaType } }
          commitDocument(next, dto)
        } catch (error) { setProjectError(error instanceof Error ? error.message : '图片场源文件无法载入。') }
      }} />
  </div>
}
