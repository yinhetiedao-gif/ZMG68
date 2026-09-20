"""UI-independent Pattern Lab orchestration over the reusable Core Engine."""
from __future__ import annotations

from copy import copy, deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
import json
from time import perf_counter
from typing import Callable, List, Optional

from ppg.foundation import Canvas, Reference, FoundationPipeline, PatternDocument, SVGNormalizer, load_pattern_document, pattern_document_to_svg, save_pattern_document
from .project_workflow import ProjectFiles

from .interaction import InteractionState
from .faithful_mapping import ConversionMode, FaithfulMappingAdapter
from .parametric import (
    PARAMETRIC_METADATA_KEY,
    GridParametricModel,
    LocalOverride,
    PatternMode,
)
from .parametric_families import AlongCurveParametricModel, FreeParametricModel, ParametricModel, RadialParametricModel
from .element_debug import ElementDebugRecord, ElementDebugSummary, element_debug_record, element_debug_summary
from .evaluation import evaluate_pattern_document, materialize_evaluated_elements, serialize_elements
from .geometry_validation import GeometryValidationReport, GeometryValidator
from .connectivity import ConnectivityAnalyzer, ConnectivityReport
from .manufacturing_geometry import ManufacturingConversionResult, ManufacturingGeometryAdapter
from .manufacturing_backend import ManufacturingBuildResult, ManufacturingBackend, ManufacturingMeshResult, TrimeshBackend
from .mesh_validation import MeshValidationReport, MeshValidator
from .stl_export import STLExportResult, STLExporter
from .placement_assignment import (
    PLACEMENT_METADATA_KEY,
    ImportedElementSlotProvider,
    PlacementAssignmentState,
    RandomSettings,
    ShapePoolEntry,
    ShapePrototypeRegistry,
)
from .shared_modifiers import ModifierScope, SHARED_MODIFIER_METADATA_KEY, SharedModifierStack
from .pattern_analyzer import AnalysisTolerance, GridAnalysisDebug, GridFitResult, MultiFamilyAnalysis, PatternAnalyzer
from .recognition import MultiScaleDotRecognizer
from .presets import (
    ParametricPreset,
    PresetRepository,
    adapt_effect_config,
    bind_reference_image,
    bounds_from_elements,
)


class ViewMode(str, Enum):
    REFERENCE = "reference"
    VECTOR = "vector"
    OVERLAY = "overlay"


@dataclass(frozen=True)
class ConversionLogEntry:
    timestamp: str
    level: str
    message: str


@dataclass
class PatternLabSession:
    """All actual editing routes through PatternDocument, never a Canvas item."""

    pipeline: FoundationPipeline
    workspace: Path
    faithful_mapping: Optional[FaithfulMappingAdapter] = None
    document: Optional[PatternDocument] = None
    selected_id: Optional[str] = None
    selected_ids: List[str] = field(default_factory=list)
    view_mode: ViewMode = ViewMode.OVERLAY
    show_reference: bool = True
    logs: List[ConversionLogEntry] = field(default_factory=list)
    editable_svg_path: Optional[Path] = None
    _undo_stack: List[dict] = field(default_factory=list, init=False, repr=False)
    _redo_stack: List[dict] = field(default_factory=list, init=False, repr=False)
    _transaction_before: Optional[dict] = field(default=None, init=False, repr=False)
    _transaction_label: Optional[str] = field(default=None, init=False, repr=False)
    pattern_mode: PatternMode = field(default=PatternMode.FREE, init=False)
    conversion_mode: ConversionMode = field(default=ConversionMode.PARAMETRIC, init=False)
    grid_model: Optional[GridParametricModel] = field(default=None, init=False)
    # ``grid_model`` stays available to V1/V3 callers.  All product editing
    # routes use this generic active model so Grid is one family, not the
    # parameterisation system itself.
    parametric_model: ParametricModel | None = field(default=None, init=False)
    dot_recognizer: MultiScaleDotRecognizer = field(default_factory=MultiScaleDotRecognizer, init=False, repr=False)
    pattern_analyzer: PatternAnalyzer = field(default_factory=PatternAnalyzer, init=False, repr=False)
    svg_serialize_count: int = field(default=0, init=False)
    document_commit_count: int = field(default=0, init=False)
    undo_record_count: int = field(default=0, init=False)
    app_data_dir: Optional[Path] = field(default=None, repr=False)
    current_project_path: Optional[Path] = field(default=None, init=False)
    revision: int = field(default=0, init=False)
    saved_revision: Optional[int] = field(default=None, init=False)
    _revision_serial: int = field(default=0, init=False, repr=False)
    _undo_revisions: list[int] = field(default_factory=list, init=False, repr=False)
    _redo_revisions: list[int] = field(default_factory=list, init=False, repr=False)
    _recovered_revision: Optional[int] = field(default=None, init=False, repr=False)
    on_project_change: Optional[Callable[[], None]] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self.workspace = Path(self.workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.project_files = ProjectFiles(self.workspace, self.app_data_dir)
        if self.document is not None:
            self._hydrate_parametric_state()

    def log(self, message: str, level: str = "INFO") -> None:
        stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        self.logs.append(ConversionLogEntry(stamp, level, message))

    @property
    def current_project_name(self) -> str:
        if self.current_project_path is None:
            return "未命名"
        return self.current_project_path.name.removesuffix(".pattern.json").removesuffix(".json")

    @property
    def is_dirty(self) -> bool:
        return self.document is not None and self.revision != self.saved_revision

    @property
    def missing_reference(self) -> bool:
        path = self.document.reference.source_path if self.document else ""
        return bool(path) and not Path(path).is_file()

    def _project_changed(self) -> None:
        if self.on_project_change:
            try:
                self.on_project_change()
            except Exception as error:
                # A title/timer problem must never invalidate a successful save.
                self.log("项目状态已更新，但界面通知失败：%s" % error, "WARNING")

    def _reset_project_history(self, path: Path | None, *, saved: bool) -> None:
        self.current_project_path = path
        self._revision_serial += 1
        self.revision = self._revision_serial
        self.saved_revision = self.revision if saved else None
        self._recovered_revision = None
        self._undo_stack.clear(); self._redo_stack.clear()
        self._undo_revisions.clear(); self._redo_revisions.clear()
        self._transaction_before = None; self._transaction_label = None
        self.selected_id = None; self.selected_ids.clear()
        self._discard_own_recovery()
        self._project_changed()

    def _discard_own_recovery(self) -> None:
        try:
            self.project_files.discard_recovery()
        except OSError as error:
            self.log("无法清理恢复副本：%s" % error, "WARNING")

    def new_document(self) -> PatternDocument:
        self.document = PatternDocument(Canvas(300, 300, unit="mm", mm_per_unit=1), Reference(""), [])
        self._hydrate_parametric_state()
        self.editable_svg_path = self.workspace / "editable.svg"
        self._reset_project_history(None, saved=False)
        self.log("新建未命名项目")
        return self.document

    def _remember_project(self, path: Path) -> None:
        try:
            self.project_files.remember(path)
        except OSError as error:
            self.log("项目操作成功，但最近项目列表未写入：%s" % error, "WARNING")

    def autosave_recovery(self) -> Path | None:
        if not self.is_dirty or self.transaction_active or self._recovered_revision == self.revision:
            return None
        target = self.project_files.write_recovery(self.require_document(), self.current_project_path, self.revision)
        self._recovered_revision = self.revision
        return target

    def restore_recovery(self, path: Path) -> PatternDocument:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        document = self.project_files.validate_recovery(payload)
        candidate = self._prepare_loaded_document(document)
        original = payload.get("project_path")
        self._adopt_loaded_document(candidate, Path(original).resolve() if original else None, saved=False)
        # Preserve the recovered data before retiring its prior crash copy.
        self.autosave_recovery()
        self.project_files.discard_recovery(Path(path))
        self.log("已恢复项目；请保存以写入正式工程。")
        return self.require_document()

    def import_image(self, image_path: str, conversion_mode: ConversionMode | str = ConversionMode.FAITHFUL) -> PatternDocument:
        source = Path(image_path).resolve()
        requested_mode = ConversionMode(conversion_mode)
        # A session owns one active import at a time.  Keep its working path
        # intentionally short: nested Chinese project folders plus a repeated
        # filename otherwise exceed Windows' legacy 260-character file limit
        # during `preprocessed/<name>-binary.png` generation.
        output_dir = self.workspace / "import"
        output_dir.mkdir(parents=True, exist_ok=True)
        svg_path = output_dir / "vectorized.svg"
        self.log("导入：%s" % source.name)
        if requested_mode is ConversionMode.FAITHFUL:
            adapter = self.faithful_mapping or FaithfulMappingAdapter(
                self.pipeline.image_processor, self.pipeline.vectorizer, SVGNormalizer(),
            )
            result = adapter.map_raster(str(source), str(svg_path))
        else:
            result = self.pipeline.import_raster(str(source), str(svg_path))
        self.document = result.document
        recognition = self.dot_recognizer.enrich_document(
            self.document,
            result.preprocess.image_path,
            # Faithful Mapping keeps its closed material regions.  The same
            # recognizer only annotates those regions as dots so later Pattern
            # Analysis can inspect PatternDocument.elements without an image.
            materialize_missing=requested_mode is ConversionMode.PARAMETRIC,
        )
        self.document.reference.visible = False
        self.pattern_mode = PatternMode.FREE
        self.conversion_mode = requested_mode
        self.grid_model = None
        self.parametric_model = None
        self.selected_id = None; self.selected_ids.clear()
        self.editable_svg_path = svg_path
        self._undo_stack.clear(); self._redo_stack.clear(); self._transaction_before = None; self._transaction_label = None
        self.log("预处理：%s" % result.preprocess.engine)
        label = "保真映射" if requested_mode is ConversionMode.FAITHFUL else "参数化识别"
        self.log("%s：%s；检测到 %d 个独立 Element。" % (label, result.vectorization.engine, len(self.document.elements)))
        self.log(
            "多尺度圆点识别：%d 个；Path 恢复 %d；保真区域标注 %d；补充小圆 %d。" % (
                recognition.detected_count, recognition.converted_path_count,
                recognition.annotated_region_count, recognition.materialized_count,
            )
        )
        self.export_svg(str(svg_path), record=False)
        self._reset_project_history(None, saved=False)
        return self.document

    def require_document(self) -> PatternDocument:
        if self.document is None:
            raise RuntimeError("请先导入图片或打开 PatternDocument。")
        return self.document

    @property
    def has_parametric_model(self) -> bool:
        return self.pattern_mode is not PatternMode.FREE and self.parametric_model is not None

    def select(self, element_id: Optional[str], additive: bool = False) -> Optional[str]:
        document = self.require_document()
        if element_id is not None:
            document.element(element_id)
        if additive and element_id is not None:
            if element_id in self.selected_ids:
                self.selected_ids.remove(element_id)
            else:
                self.selected_ids.append(element_id)
            self.selected_id = self.selected_ids[-1] if self.selected_ids else None
        else:
            self.selected_id = element_id
            self.selected_ids = [element_id] if element_id is not None else []
        # Hover and pointer work must not fill the Conversion Log.  Selection
        # is still reflected in Inspector and the Canvas immediately.
        return self.selected_id

    def select_many(self, element_ids: List[str], *, additive: bool = False) -> Optional[str]:
        """Select real, currently editable Elements by their stable IDs.

        Selection is deliberately session-only: rectangle selection and
        Ctrl+A must not create document Undo records or a second selection
        model.  ``additive`` appends unseen IDs for Shift + rectangle select;
        Shift + click keeps its existing toggle behaviour in :meth:`select`.
        """
        document = self.require_document()
        identifiers = list(dict.fromkeys(element_ids))
        for identifier in identifiers:
            document.element(identifier)
        if additive:
            self.selected_ids = list(dict.fromkeys([*self.selected_ids, *identifiers]))
        else:
            self.selected_ids = identifiers
        self.selected_id = identifiers[-1] if identifiers else None
        if additive and self.selected_ids:
            self.selected_id = identifiers[-1] if identifiers else self.selected_ids[-1]
        return self.selected_id

    def clear_selection(self) -> None:
        """Clear transient selection without changing PatternDocument."""

        self.selected_id = None
        self.selected_ids.clear()

    def select_all(self) -> Optional[str]:
        """Select visible final Elements only; helpers and Mask controls stay out."""

        return self.select_many([
            element.id for element in self.require_document().elements if element.visible
        ])

    def select_rectangle(
        self, left: float, top: float, right: float, bottom: float, *, additive: bool = False,
    ) -> Optional[str]:
        """Select visible Element centres in a world-coordinate rectangle."""

        x0, x1 = sorted((float(left), float(right)))
        y0, y1 = sorted((float(top), float(bottom)))
        identifiers = [
            element.id
            for element in self.require_document().elements
            if element.visible and x0 <= element.x <= x1 and y0 <= element.y <= y1
        ]
        return self.select_many(identifiers, additive=additive)

    def select_at(self, x: float, y: float) -> Optional[str]:
        selected = self.hit_test(x, y)
        return self.select(selected)

    def hit_test(self, x: float, y: float) -> Optional[str]:
        document = self.require_document()
        candidates = []
        for element in reversed(document.elements):
            if not element.visible:
                continue
            if abs(x - element.x) <= element.width / 2 and abs(y - element.y) <= element.height / 2:
                candidates.append(element)
        return min(candidates, key=lambda item: (item.x - x) ** 2 + (item.y - y) ** 2).id if candidates else None

    @property
    def transaction_active(self) -> bool:
        return self._transaction_before is not None

    def begin_transaction(self, label: str) -> None:
        """Snapshot once at pointer-down; motion events never create commands."""
        document = self.require_document()
        if self.transaction_active:
            raise RuntimeError("已有进行中的编辑事务。")
        self._persist_parametric_state()
        self._transaction_before = document.to_dict()
        self._transaction_label = str(label)

    def commit_transaction(self) -> bool:
        document = self.require_document()
        if not self.transaction_active:
            return False
        started = perf_counter()
        before = self._transaction_before
        label = self._transaction_label or "编辑"
        self._transaction_before = None; self._transaction_label = None
        self._persist_parametric_state()
        after = document.to_dict()
        if before == after:
            return False
        self._undo_stack.append(before)
        self._undo_revisions.append(self.revision)
        self._redo_revisions.clear()
        self._revision_serial += 1
        self.revision = self._revision_serial
        self.undo_record_count += 1
        self._redo_stack.clear()
        self.log("%s已提交（1 条 Undo Transaction）" % label)
        try:
            self._after_edit()
        finally:
            self.document_commit_count += 1
            self._last_commit_seconds = perf_counter() - started
            self._project_changed()
        return True

    def cancel_transaction(self) -> None:
        if not self.transaction_active:
            return
        self.document = PatternDocument.from_dict(self._transaction_before)
        self._transaction_before = None; self._transaction_label = None
        self._hydrate_parametric_state()
        self._after_edit()
        self.log("已取消当前编辑事务")

    def _mutate(self, label: str, action) -> None:
        automatic = not self.transaction_active
        if automatic:
            self.begin_transaction(label)
        try:
            action()
        except Exception:
            # Never leave a half-applied automatic edit transaction behind;
            # pointer/Inspector failures must restore the prior document.
            if automatic:
                self.cancel_transaction()
            raise
        if automatic:
            self.commit_transaction()

    def set_element_position(self, element_id: str, x: float, y: float) -> None:
        document = self.require_document()
        element = document.element(element_id)
        if self.has_parametric_model:
            self._mutate("移动", lambda: self._set_grid_element_geometry(element_id, x=float(x), y=float(y)))
        elif self.active_placement_state() is not None:
            self._mutate("移动", lambda: self._set_placement_slot_geometry(element_id, x=float(x), y=float(y)))
        else:
            self._mutate("移动", lambda: document.move_element(element_id, float(x) - element.x, float(y) - element.y))

    def set_element_size(self, element_id: str, width: float, height: float) -> None:
        document = self.require_document()
        if self.has_parametric_model:
            self._mutate("缩放", lambda: self._set_grid_element_geometry(element_id, width=float(width), height=float(height)))
        elif self.active_placement_state() is not None:
            self._mutate("缩放", lambda: self._set_placement_slot_geometry(
                element_id, width=float(width), height=float(height),
            ))
        else:
            self._mutate("缩放", lambda: document.resize_element(element_id, float(width), float(height)))

    def commit_interaction(
        self, interaction: InteractionState, *, element_ids: Optional[List[str]] = None,
    ) -> bool:
        """Commit a transient Canvas preview once, on pointer-up only.

        No pointer-motion callback invokes this method.  The active transaction
        was snapshotted at pointer-down, so this contributes one Undo command.
        """

        document = self.require_document()
        if not self.transaction_active:
            raise RuntimeError("Canvas 交互缺少事务起点。")
        identifiers = list(dict.fromkeys(element_ids or [interaction.element_id]))
        if len(identifiers) > 1 and interaction.kind == "move":
            # The Canvas only previews a transient delta.  Apply it to all
            # selected real Elements once on pointer-up, then commit one Undo.
            self.move_selected(
                interaction.current_x - interaction.start_x,
                interaction.current_y - interaction.start_y,
            )
            return self.commit_transaction()
        if self.has_parametric_model:
            base = self.parametric_model.base_element(interaction.element_id)
            if base is None:
                raise KeyError("规则矩阵中找不到 Element：%s" % interaction.element_id)
            override = self.parametric_model.local_overrides.get(interaction.element_id, LocalOverride())
            override.offset_x = interaction.current_x - base.x
            override.offset_y = interaction.current_y - base.y
            override.scale_x = max(0.01, interaction.current_width / max(base.width, 0.01))
            override.scale_y = max(0.01, interaction.current_height / max(base.height, 0.01))
            override.rotation_offset = interaction.current_rotation - base.rotation
            self.parametric_model.local_overrides[interaction.element_id] = override
            self._rebuild_parametric_document()
        elif self.active_placement_state() is not None:
            self._set_placement_slot_geometry(
                interaction.element_id,
                x=interaction.current_x,
                y=interaction.current_y,
                width=interaction.current_width,
                height=interaction.current_height,
                rotation=interaction.current_rotation,
            )
        else:
            element = document.element(interaction.element_id)
            document.move_element(interaction.element_id, interaction.current_x - element.x, interaction.current_y - element.y)
            document.resize_element(interaction.element_id, interaction.current_width, interaction.current_height)
            document.rotate_element(interaction.element_id, interaction.current_rotation)
        return self.commit_transaction()

    def analyze_pattern(self) -> Optional[GridFitResult]:
        """Try a Grid fit from PatternDocument elements only.

        It intentionally has no access to an import path, a fixture name or a
        preset id.  A low score leaves the document in Free Element Mode.
        """

        return self.pattern_analyzer.analyze(self.require_document().elements)

    def analyze_families(self) -> MultiFamilyAnalysis:
        """Run all structural candidates and always return a free fallback."""
        return self.pattern_analyzer.analyze_families(self.require_document().elements)

    @property
    def grid_analysis_debug(self) -> GridAnalysisDebug:
        """Last Matrix V2 diagnostic, including a useful failure reason."""

        return self.pattern_analyzer.last_debug

    def set_grid_analysis_tolerance(self, tolerance: AnalysisTolerance | str) -> None:
        """Change only the spatial-fit policy; document geometry is untouched."""

        self.pattern_analyzer.set_tolerance(tolerance)

    def infer_grid(self) -> Optional[GridFitResult]:
        """Compatibility name for the UI's existing grid conversion action."""

        return self.analyze_pattern()

    def debug_summary(self) -> ElementDebugSummary:
        return element_debug_summary(self.require_document())

    def debug_element(self, element_id: Optional[str] = None) -> Optional[ElementDebugRecord]:
        selected = element_id or self.selected_id
        return element_debug_record(self.require_document().element(selected)) if selected else None

    def active_placement_state(self) -> PlacementAssignmentState | None:
        raw = self.require_document().metadata.get(PLACEMENT_METADATA_KEY)
        if not isinstance(raw, dict) or not bool(raw.get("enabled", False)):
            return None
        return PlacementAssignmentState.from_dict(raw)

    def _replacement_source(self) -> list:
        """Return canonical pre-replacement geometry, never Canvas output."""

        state = PlacementAssignmentState.from_document(self.require_document())
        if state.source_elements:
            return state.source_snapshot()
        if self.parametric_model is not None:
            return self.parametric_model.generate()
        shared = SharedModifierStack.from_document(self.require_document())
        if shared is not None and shared.source_elements:
            return shared.source_snapshot()
        return deepcopy(self.require_document().elements)

    def _placement_state_for_edit(self) -> PlacementAssignmentState:
        document = self.require_document()
        state = PlacementAssignmentState.from_document(document)
        source = self._replacement_source()
        if not state.source_elements:
            state.set_source_elements(source)
        if not state.slots:
            state.slots = ImportedElementSlotProvider.from_elements(source)
        if not state.prototypes.ids():
            state.prototypes = ShapePrototypeRegistry.with_builtins()
        state.enabled = True
        return state

    def replace_selected_shape(self, prototype_id: str) -> None:
        """Replace selected slots while preserving their source geometry."""

        identifiers = list(self.selected_ids or ([self.selected_id] if self.selected_id else []))
        if not identifiers:
            raise RuntimeError("请先选择至少一个 Element 进行形状替换。")

        def action() -> None:
            state = self._placement_state_for_edit()
            if prototype_id not in state.prototypes.ids():
                raise ValueError("不支持的替换形状：%s" % prototype_id)
            slot_ids = {slot.slot_id for slot in state.slots} | {slot.source_element_id for slot in state.slots}
            missing = [identifier for identifier in identifiers if identifier not in slot_ids]
            if missing:
                raise KeyError("找不到形状替换 Slot：%s" % ", ".join(missing))
            for element_id in identifiers:
                state.replacement_map.set(element_id, prototype_id)
            state.attach(self.require_document())
            materialize_evaluated_elements(self.require_document())

        self._mutate("替换形状", action)
        self.log("替换形状 %d 个 Element → %s" % (len(identifiers), prototype_id))

    def restore_selected_shape(self) -> None:
        """Remove one replacement mapping; no raster/vector re-analysis."""

        identifiers = list(self.selected_ids or ([self.selected_id] if self.selected_id else []))
        if not identifiers:
            raise RuntimeError("请先选择至少一个 Element 恢复原形。")

        def action() -> None:
            state = self.active_placement_state()
            if state is None:
                return
            for element_id in identifiers:
                state.replacement_map.remove(element_id)
            state.attach(self.require_document())
            materialize_evaluated_elements(self.require_document())

        self._mutate("恢复原始形状", action)
        self.log("恢复原始形状：%d 个 Element" % len(identifiers))

    def replacement_for(self, element_id: str) -> str | None:
        state = self.active_placement_state()
        return state.replacement_map.values.get(str(element_id)) if state is not None else None

    def shape_pool_state(self) -> PlacementAssignmentState:
        """Read Gate M state without mutating an old PatternDocument.

        This is deliberately a read facade.  Merely opening the Shape Pool UI
        must not attach metadata or change an old document's visual output.
        """

        return PlacementAssignmentState.from_document(self.require_document())

    def update_shape_pool(
        self,
        entries: list[ShapePoolEntry],
        *,
        enabled: bool | None = None,
        seed: int | None = None,
        scope: ModifierScope | dict[str, object] | None = None,
        label: str = "更新形状池",
    ) -> None:
        """Persist a Shape Pool as one non-destructive Undo transaction."""

        clean_entries = [
            ShapePoolEntry(
                prototype_id=str(entry.prototype_id),
                weight=max(0.0, float(entry.weight)),
                enabled=bool(entry.enabled),
            )
            for entry in entries
        ]

        def action() -> None:
            state = self._placement_state_for_edit()
            unknown = [entry.prototype_id for entry in clean_entries if entry.prototype_id not in state.prototypes.ids()]
            if unknown:
                raise ValueError("形状池包含未注册 Shape：%s" % ", ".join(unknown))
            state.shape_pool = clean_entries
            if enabled is not None:
                state.shape_pool_enabled = bool(enabled)
            if seed is not None:
                state.shape_random_seed = max(0, int(seed))
            if scope is not None:
                state.shape_pool_scope = (
                    scope if isinstance(scope, ModifierScope) else ModifierScope.from_dict(scope)
                )
            state.attach(self.require_document())
            materialize_evaluated_elements(self.require_document())
            if state.shape_pool_enabled and not state.has_active_pool_candidates():
                self.log("形状池没有有效权重，已回退为原始形状。", "INFO")

        self._mutate(label, action)

    def set_shape_pool_enabled(self, enabled: bool) -> None:
        state = self.shape_pool_state()
        self.update_shape_pool(
            state.shape_pool,
            enabled=bool(enabled),
            seed=state.shape_random_seed,
            label="启用形状池" if enabled else "停用形状池",
        )

    def set_shape_random_seed(self, seed: int) -> None:
        state = self.shape_pool_state()
        self.update_shape_pool(
            state.shape_pool,
            enabled=state.shape_pool_enabled,
            seed=max(0, int(seed)),
            label="修改形状随机种子",
        )

    def set_shape_pool_scope(self, scope: ModifierScope | dict[str, object]) -> None:
        """Commit one shared Scope update without changing pool/seed values."""

        state = self.shape_pool_state()
        self.update_shape_pool(
            state.shape_pool,
            enabled=state.shape_pool_enabled,
            seed=state.shape_random_seed,
            scope=scope,
            label="更新形状池作用范围",
        )

    def randomize_shape_seed(self) -> int:
        """Generate and commit a fresh seed; assignment remains derived."""

        import secrets

        new_seed = secrets.randbelow(2_147_483_647) + 1
        state = self.shape_pool_state()
        self.update_shape_pool(
            state.shape_pool,
            enabled=state.shape_pool_enabled,
            seed=new_seed,
            scope=state.shape_pool_scope,
            label="形状池换一种",
        )
        return new_seed

    def reset_shape_pool(self) -> None:
        """Reset Gate M state only; manual replacements and source persist."""

        def action() -> None:
            state = self._placement_state_for_edit()
            state.reset_shape_pool()
            state.attach(self.require_document())
            materialize_evaluated_elements(self.require_document())

        self._mutate("恢复形状池默认值", action)

    # Gate N: transforms and occupancy share the existing Placement layer;
    # they intentionally do not create a second RandomDocument or Generator.
    def random_transform_state(self) -> RandomSettings:
        return self.shape_pool_state().random

    def update_random_transforms(
        self, settings: RandomSettings, *, label: str = "更新随机与密度"
    ) -> None:
        """Persist one complete deterministic transform update as one Undo."""

        normalized = RandomSettings.from_dict(settings.to_dict())

        def action() -> None:
            state = self._placement_state_for_edit()
            state.random = normalized
            state.attach(self.require_document())
            materialize_evaluated_elements(self.require_document())

        self._mutate(label, action)

    def set_random_transform_scope(self, scope: ModifierScope | dict[str, object]) -> None:
        settings = self.random_transform_state()
        settings.scope = scope if isinstance(scope, ModifierScope) else ModifierScope.from_dict(scope)
        self.update_random_transforms(settings, label="更新随机作用范围")

    def randomize_transform_seed(self) -> int:
        """Commit a new Gate N seed without changing Shape Pool assignment."""

        import secrets

        settings = self.random_transform_state()
        settings.seed = secrets.randbelow(2_147_483_647) + 1
        self.update_random_transforms(settings, label="随机与密度换一个")
        return settings.seed

    # Gate O: a preset is an effect recipe.  It deliberately lives alongside
    # the workspace rather than in a PatternDocument, so source geometry and a
    # project file remain separate from a reusable configuration.
    @property
    def preset_repository(self) -> PresetRepository:
        return PresetRepository(self.workspace / "presets")

    def list_parametric_presets(self) -> list[ParametricPreset]:
        return self.preset_repository.list()

    def _preset_source_elements(self) -> list:
        """Return target geometry before effects, never the Canvas output."""

        return self._replacement_source()

    def save_parametric_preset(self, name: str) -> ParametricPreset:
        """Persist a versioned effect-only preset without creating an Undo item."""

        document = self.require_document()
        shared = SharedModifierStack.from_document(document)
        placement = PlacementAssignmentState.from_document(document)
        source = self._preset_source_elements()
        placement_raw = placement.to_dict()
        preset = ParametricPreset(
            name=str(name).strip() or "未命名预设",
            fields=deepcopy(document.fields),
            modifiers=deepcopy(document.modifiers),
            shared_modifier_stack=shared.to_dict() if shared else {},
            shape_pool={
                "shape_prototypes": deepcopy(placement_raw.get("shape_prototypes") or {}),
                "shape_pool": deepcopy(placement_raw.get("shape_pool") or []),
                "shape_pool_enabled": bool(placement.shape_pool_enabled),
                "shape_random_seed": int(placement.shape_random_seed),
                "shape_pool_scope": placement.shape_pool_scope.to_dict(),
                "enabled": bool(placement.enabled),
            },
            assignment_settings=deepcopy(placement.assignment.to_dict()),
            random_settings=deepcopy(placement.random.to_dict()),
            source_bounds=bounds_from_elements(source),
            metadata={"created_by": "xiaomang_pattern_lab", "preset_kind": "parametric_effects"},
        )
        self.preset_repository.save(preset)
        self.log("保存参数预设：%s" % preset.name)
        return preset

    def rename_parametric_preset(self, preset_id: str, name: str) -> ParametricPreset:
        preset = self.preset_repository.get(preset_id)
        preset.name = str(name).strip() or preset.name
        self.preset_repository.save(preset)
        self.log("重命名参数预设：%s" % preset.name)
        return preset

    def duplicate_parametric_preset(self, preset_id: str, name: str | None = None) -> ParametricPreset:
        preset = self.preset_repository.get(preset_id)
        duplicate = preset.copy_named(name or (preset.name + " 副本"))
        self.preset_repository.save(duplicate)
        self.log("复制参数预设：%s" % duplicate.name)
        return duplicate

    def delete_parametric_preset(self, preset_id: str) -> None:
        preset = self.preset_repository.get(preset_id)
        self.preset_repository.delete(preset_id)
        self.log("删除参数预设：%s" % preset.name)

    def apply_parametric_preset(self, preset_id: str) -> None:
        """Replace effect configuration in exactly one non-destructive Undo.

        Source elements, current structural model, slots, manual replacements,
        local overrides, selection and viewport data are deliberately retained.
        The input recipe is coordinate-adapted from its saved source bounds to
        the target document's current source geometry before it is attached.
        """

        preset = self.preset_repository.get(preset_id)

        def action() -> None:
            document = self.require_document()
            target_source = self._preset_source_elements()
            target_bounds = bounds_from_elements(target_source)
            current_stack = SharedModifierStack.from_document(document)
            current_placement = PlacementAssignmentState.from_document(document)

            stack_payload = bind_reference_image(
                adapt_effect_config(
                    preset.shared_modifier_stack, preset.source_bounds, target_bounds,
                ),
                document.reference.source_path,
            )
            fields = bind_reference_image(
                adapt_effect_config(preset.fields, preset.source_bounds, target_bounds),
                document.reference.source_path,
            )
            graph_modifiers = bind_reference_image(
                adapt_effect_config(preset.modifiers, preset.source_bounds, target_bounds),
                document.reference.source_path,
            )

            if stack_payload:
                # Unknown future stack layers are skipped rather than making a
                # whole saved preset unopenable in an older Pattern Lab.
                valid_layers = []
                for layer in stack_payload.get("modifiers", []):
                    if isinstance(layer, dict) and str(layer.get("type")) in {"size", "rotation", "position"}:
                        valid_layers.append(layer)
                    elif isinstance(layer, dict):
                        self.log("预设跳过当前版本不支持的效果层：%s" % layer.get("type"), "WARNING")
                stack_payload["modifiers"] = valid_layers
                stack = SharedModifierStack.from_dict(stack_payload)
                stack.enabled = True
                stack.source_kind = current_stack.source_kind if current_stack else "imported_elements"
                stack.source_elements = serialize_elements(target_source)
                # A local user edit is geometry-specific and must not be
                # replaced by a different document's preset.
                stack.local_overrides = deepcopy(current_stack.local_overrides) if current_stack else {}
                stack.attach(document, source_kind=stack.source_kind)
                # Explicit layers intentionally own the graph.  A legacy graph
                # is restored only if the preset did not contain an explicit
                # Modifier Stack layer.
                if not stack.modifiers:
                    document.fields = deepcopy(fields)
                    document.modifiers = deepcopy(graph_modifiers)
            else:
                document.metadata.pop(SHARED_MODIFIER_METADATA_KEY, None)
                document.fields = deepcopy(fields)
                document.modifiers = deepcopy(graph_modifiers)

            pool_payload = adapt_effect_config(preset.shape_pool, preset.source_bounds, target_bounds)
            random_payload = adapt_effect_config(preset.random_settings, preset.source_bounds, target_bounds)
            needs_placement = bool(pool_payload.get("enabled", False) or pool_payload.get("shape_pool_enabled", False)
                                   or random_payload.get("enabled", False) or current_placement.replacement_map.values)
            if needs_placement:
                state = current_placement
                if not state.source_elements:
                    state.set_source_elements(target_source)
                if not state.slots:
                    state.slots = ImportedElementSlotProvider.from_elements(target_source)
                raw_prototypes = pool_payload.get("shape_prototypes")
                if isinstance(raw_prototypes, dict) and raw_prototypes:
                    try:
                        state.prototypes = ShapePrototypeRegistry.from_dict(raw_prototypes)
                    except (TypeError, ValueError):
                        self.log("预设中的自定义形状无法读取，已保留当前形状库。", "WARNING")
                if not state.prototypes.ids():
                    state.prototypes = ShapePrototypeRegistry.with_builtins()
                state.shape_pool = [
                    ShapePoolEntry.from_dict(item) for item in pool_payload.get("shape_pool", [])
                    if isinstance(item, (dict, str))
                ] or state.shape_pool
                state.shape_pool_enabled = bool(pool_payload.get("shape_pool_enabled", False))
                state.shape_random_seed = max(0, int(pool_payload.get("shape_random_seed", 1)))
                state.shape_pool_scope = ModifierScope.from_dict(pool_payload.get("shape_pool_scope"))
                state.assignment = state.assignment.from_dict(preset.assignment_settings)
                state.random = RandomSettings.from_dict(random_payload)
                state.enabled = True
                state.attach(document)
            else:
                # The recipe turns automatic shape/random effects off, while
                # preserving manual replacement mappings as local edits.
                if current_placement.replacement_map.values:
                    current_placement.shape_pool_enabled = False
                    current_placement.random = RandomSettings()
                    current_placement.enabled = True
                    current_placement.attach(document)
                else:
                    document.metadata.pop(PLACEMENT_METADATA_KEY, None)

            materialize_evaluated_elements(document)

        self._mutate("应用参数预设", action)
        self.log("应用参数预设：%s（已按当前图案尺寸适配）" % preset.name)

    def _set_placement_slot_geometry(
        self, element_id: str, *, x: float | None = None, y: float | None = None,
        width: float | None = None, height: float | None = None,
        rotation: float | None = None, rebuild: bool = True,
    ) -> None:
        state = self.active_placement_state()
        if state is None:
            raise RuntimeError("当前没有启用形状替换。")
        found = False
        updated = []
        for slot in state.slots:
            if slot.slot_id == element_id or slot.source_element_id == element_id:
                slot = replace(
                    slot,
                    center_x=slot.center_x if x is None else float(x),
                    center_y=slot.center_y if y is None else float(y),
                    width=slot.width if width is None else max(0.01, float(width)),
                    height=slot.height if height is None else max(0.01, float(height)),
                    rotation=slot.rotation if rotation is None else float(rotation),
                )
                found = True
            updated.append(slot)
        if not found:
            raise KeyError("形状替换中找不到 Element：%s" % element_id)
        state.slots = updated
        state.attach(self.require_document())
        if rebuild:
            materialize_evaluated_elements(self.require_document())

    def activate_grid(self, model: GridParametricModel) -> None:
        self.activate_parametric(PatternMode.GRID, model, "转换为规则矩阵")

    def activate_parametric(self, mode: PatternMode | str, model, label: str | None = None) -> None:
        mode = PatternMode(mode)
        if mode is PatternMode.FREE:
            raise ValueError("自由元素不需要 ParametricModel。")
        def action() -> None:
            # Preserve a read-only source snapshot for audit / future re-fit.
            # It is never a Canvas-owned second geometry state.
            source_elements = serialize_elements(self.require_document().elements)
            self.pattern_mode = mode
            self.parametric_model = GridParametricModel.from_dict(model.to_dict()) if mode is PatternMode.GRID else model.__class__.from_dict(model.to_dict())
            self.grid_model = self.parametric_model if mode is PatternMode.GRID else None
            self._persist_parametric_state(source_elements=source_elements)
            self._rebuild_parametric_document()
        self._mutate(label or "转换为参数化结构", action)
        self.selected_id = None; self.selected_ids.clear()

    def activate_radial(self, model: RadialParametricModel) -> None:
        self.activate_parametric(PatternMode.RADIAL, model, "转换为放射参数化")

    def activate_along_curve(self, model: AlongCurveParametricModel) -> None:
        self.activate_parametric(PatternMode.ALONG_CURVE, model, "转换为沿曲线参数化")

    def activate_free_parametric(self, model: FreeParametricModel | None = None) -> None:
        self.activate_parametric(PatternMode.FREE_PARAMETRIC, model or FreeParametricModel.from_elements(self.require_document().elements), "进入自由参数化")

    @property
    def has_shared_modifiers(self) -> bool:
        return SharedModifierStack.from_document(self.require_document()) is not None

    def activate_shared_modifiers(self, stack: SharedModifierStack | None = None,
                                  *, source_kind: str = "imported_elements") -> None:
        """Enable the common effect layer without requiring Grid recognition.

        The imported/source snapshot is kept in metadata, so applying a new
        field never compounds on the previous evaluated result.  If a Grid or
        another ParametricModel is active, that model remains the structural
        source and the shared stack is applied after it.
        """

        def action() -> None:
            document = self.require_document()
            current = SharedModifierStack.from_document(document)
            target = stack or current or SharedModifierStack()
            if not target.source_elements:
                target.source_kind = current.source_kind if current else str(source_kind)
                target.source_elements = (
                    deepcopy(current.source_elements) if current and current.source_elements
                    else serialize_elements(document.elements)
                )
            target.enabled = True
            target.attach(document, source_kind=target.source_kind)
            materialize_evaluated_elements(document)

        self._mutate("启用共享参数化效果", action)

    def update_shared_modifiers(self, stack: SharedModifierStack) -> None:
        """Commit one shared modifier stack while preserving its source snapshot."""

        document = self.require_document()
        previous = SharedModifierStack.from_document(document)
        if not stack.source_elements and previous and previous.source_elements:
            stack.source_elements = deepcopy(previous.source_elements)
            stack.source_kind = previous.source_kind
        elif not stack.source_elements:
            # The existing UI uses update even for FIRST activation. Capture
            # the source before materialisation, just as activate does;
            # otherwise repeated Apply/Save/Load compounds the size effect.
            stack.source_elements = serialize_elements(document.elements)

        def action() -> None:
            stack.enabled = True
            stack.attach(document, source_kind=stack.source_kind)
            materialize_evaluated_elements(document)

        self._mutate("更新共享参数化效果", action)

    def deactivate_shared_modifiers(self) -> None:
        """Remove the shared layer and restore its non-destructive source when available."""

        def action() -> None:
            document = self.require_document()
            stack = SharedModifierStack.from_document(document)
            if stack and stack.source_elements:
                document.elements = stack.source_snapshot()
                document._sync_transforms()
            document.metadata.pop(SHARED_MODIFIER_METADATA_KEY, None)
            document.fields = []
            document.modifiers = []

        self._mutate("停用共享参数化效果", action)

    def _stack_for_edit(self) -> SharedModifierStack:
        """Return an explicit Gate-H stack without changing source geometry."""
        document = self.require_document()
        current = SharedModifierStack.from_document(document)
        if current is not None and current.modifiers:
            return current
        source = (deepcopy(current.source_elements) if current and current.source_elements
                  else serialize_elements(document.elements))
        stack = SharedModifierStack(
            source_kind=current.source_kind if current else "imported_elements",
            source_elements=source,
        )
        # Migrate the two legacy compatibility controls only when they carry a
        # visible effect.  This keeps old documents byte-compatible until a
        # user explicitly edits the new stack.
        if current is not None:
            size = current.size_field
            if size.mode.value != "constant" or abs(size.min_scale - 1.0) > 1e-9 or abs(size.max_scale - 1.0) > 1e-9:
                stack.add_modifier("size", size.to_dict(), modifier_id="legacy-size")
            rotation = current.rotation_field
            if rotation.mode.value != "constant" or abs(rotation.angle) > 1e-9:
                stack.add_modifier("rotation", rotation.to_dict(), modifier_id="legacy-rotation")
        return stack

    def add_modifier_layer(self, modifier_type: str, parameters: dict[str, object], *, modifier_id: str | None = None) -> str:
        """Add one ordered Size/Rotation/Position layer as one Undo command."""
        result: list[str] = []

        def action() -> None:
            stack = self._stack_for_edit()
            result.append(stack.add_modifier(modifier_type, parameters, modifier_id=modifier_id))
            stack.attach(self.require_document(), source_kind=stack.source_kind)
            materialize_evaluated_elements(self.require_document())

        self._mutate("添加效果层", action)
        return result[0]

    def preview_modifier_parameters(self, index: int, parameters: dict[str, object]):
        """Evaluate temporary layer parameters without mutating PatternDocument.

        Slider motion uses this read-only route.  The real document, Undo stack
        and source snapshot are touched only by ``update_modifier_parameters``
        when the interaction is committed.
        """

        candidate = PatternDocument.from_dict(self.require_document().to_dict())
        stack = SharedModifierStack.from_document(candidate)
        if stack is None:
            raise RuntimeError("当前文档没有可编辑的效果堆栈。")
        target = stack.modifiers[stack._check_index(index)]
        target["parameters"] = deepcopy(dict(parameters))
        stack.attach(candidate, source_kind=stack.source_kind)
        return evaluate_pattern_document(candidate)

    def update_modifier_parameters(self, index: int, parameters: dict[str, object], *, label: str = "更新效果层") -> None:
        """Commit one layer's parameters as exactly one Undo transaction."""

        def update(stack: SharedModifierStack) -> None:
            target = stack.modifiers[stack._check_index(index)]
            target["parameters"] = deepcopy(dict(parameters))

        self._edit_modifier_stack(label, update)

    def preview_modifier_scope(self, index: int, scope: ModifierScope | dict[str, object]):
        """Evaluate one temporary Scope without mutating document or Undo state."""

        candidate = PatternDocument.from_dict(self.require_document().to_dict())
        stack = SharedModifierStack.from_document(candidate)
        if stack is None:
            raise RuntimeError("当前文档没有可编辑的效果堆栈。")
        stack.set_modifier_scope(index, scope)
        stack.attach(candidate, source_kind=stack.source_kind)
        return evaluate_pattern_document(candidate)

    def update_modifier_scope(self, index: int,
                              scope: ModifierScope | dict[str, object], *,
                              label: str = "更新效果作用范围") -> None:
        """Commit one layer Scope as exactly one Undo transaction."""

        self._edit_modifier_stack(label, lambda stack: stack.set_modifier_scope(index, scope))

    def _edit_modifier_stack(self, label: str, operation) -> None:
        def action() -> None:
            stack = self._stack_for_edit()
            operation(stack)
            stack.attach(self.require_document(), source_kind=stack.source_kind)
            materialize_evaluated_elements(self.require_document())
        self._mutate(label, action)

    def set_modifier_enabled(self, index: int, enabled: bool) -> None:
        self._edit_modifier_stack("切换效果层", lambda stack: stack.set_enabled(index, enabled))

    def delete_modifier_layer(self, index: int) -> None:
        self._edit_modifier_stack("删除效果层", lambda stack: stack.delete_modifier(index))

    def duplicate_modifier_layer(self, index: int) -> str:
        result: list[str] = []
        self._edit_modifier_stack("复制效果层", lambda stack: result.append(stack.duplicate_modifier(index)))
        return result[0]

    def move_modifier_layer(self, index: int, delta: int) -> int:
        result: list[int] = []
        self._edit_modifier_stack("调整效果层顺序", lambda stack: result.append(stack.move_modifier(index, delta)))
        return result[0]

    def reset_modifier_layer(self, index: int) -> None:
        self._edit_modifier_stack("重置效果层", lambda stack: stack.reset_modifier(index))

    def deactivate_grid(self) -> None:
        """Compatibility name for the explicit non-destructive bake action."""

        self.bake_to_free_elements()

    def bake_to_free_elements(self) -> None:
        """Evaluate once, then make the evaluated geometry independent again."""

        def action() -> None:
            # Final Elements are calculated exactly once from the model before
            # the compact parametric metadata is intentionally removed.
            self._rebuild_parametric_document()
            self.pattern_mode = PatternMode.FREE
            self.grid_model = None
            self.parametric_model = None
            self.require_document().metadata.pop(PARAMETRIC_METADATA_KEY, None)
        self._mutate("烘焙为自由元素", action)

    def preview_grid(self, model: GridParametricModel):
        """Return temporary generated Elements without mutating the document."""

        return model.generate()

    def update_grid(self, model: GridParametricModel) -> None:
        if self.pattern_mode is not PatternMode.GRID:
            raise RuntimeError("请先转换为规则矩阵。")
        def action() -> None:
            self.grid_model = GridParametricModel.from_dict(model.to_dict())
            self.parametric_model = self.grid_model
            self._rebuild_parametric_document()
        self._mutate("更新规则矩阵", action)

    def set_grid_mask(self, mask) -> None:
        """Apply the V1 mask as a normal modifier transaction."""

        if not self.has_parametric_model:
            raise RuntimeError("请先转换为规则矩阵。")

        def action() -> None:
            self.parametric_model.mask = mask
            self._rebuild_parametric_document()

        self._mutate("更新矩阵掩膜", action)

    def move_selected(self, dx: float, dy: float) -> None:
        document = self.require_document()
        if not self.selected_id:
            raise RuntimeError("请先选择一个 Element。")
        if self.has_parametric_model:
            selected_ids = list(self.selected_ids or [self.selected_id])
            def action() -> None:
                for identifier in selected_ids:
                    selected = document.element(identifier)
                    self._set_grid_element_geometry(identifier, x=selected.x + float(dx), y=selected.y + float(dy), rebuild=False)
                self._rebuild_parametric_document()
            self._mutate("移动", action)
        elif self.active_placement_state() is not None:
            selected_ids = list(self.selected_ids or [self.selected_id])
            def action() -> None:
                for identifier in selected_ids:
                    selected = document.element(identifier)
                    self._set_placement_slot_geometry(
                        identifier, x=selected.x + float(dx), y=selected.y + float(dy), rebuild=False,
                    )
                materialize_evaluated_elements(document)
            self._mutate("移动", action)
        else:
            selected_ids = list(self.selected_ids or [self.selected_id])
            self._mutate("移动", lambda: [document.move_element(identifier, float(dx), float(dy)) for identifier in selected_ids])
        if not self.transaction_active:
            self.log("移动 %s：Δx=%g，Δy=%g" % (self.selected_id, dx, dy))

    def resize_selected(self, width: float, height: Optional[float] = None) -> None:
        document = self.require_document()
        if not self.selected_id:
            raise RuntimeError("请先选择一个 Element。")
        def action() -> None:
            if self.has_parametric_model:
                selected_ids = list(self.selected_ids or [self.selected_id])
                primary = document.element(self.selected_id)
                target_width = float(width)
                target_height = float(height if height is not None else width)
                # Multi-selection keeps each local size relationship while the
                # primary Inspector value defines one relative scale action.
                scale_x = target_width / max(primary.width, 0.01)
                scale_y = target_height / max(primary.height, 0.01)
                for identifier in selected_ids:
                    current = document.element(identifier)
                    self._set_grid_element_geometry(identifier, width=current.width * scale_x, height=current.height * scale_y, rebuild=False)
                self._rebuild_parametric_document()
            elif self.active_placement_state() is not None:
                selected_ids = list(self.selected_ids or [self.selected_id])
                primary = document.element(self.selected_id)
                target_width = float(width)
                target_height = float(height if height is not None else width)
                scale_x = target_width / max(primary.width, 0.01)
                scale_y = target_height / max(primary.height, 0.01)
                for identifier in selected_ids:
                    current = document.element(identifier)
                    self._set_placement_slot_geometry(
                        identifier,
                        width=current.width * scale_x,
                        height=current.height * scale_y,
                        rebuild=False,
                    )
                materialize_evaluated_elements(document)
            else:
                selected_ids = list(self.selected_ids or [self.selected_id])
                primary = document.element(self.selected_id)
                target_width = float(width)
                target_height = float(height if height is not None else width)
                scale_x = target_width / max(primary.width, 0.01)
                scale_y = target_height / max(primary.height, 0.01)
                for identifier in selected_ids:
                    current = document.element(identifier)
                    document.resize_element(
                        identifier,
                        current.width * scale_x,
                        current.height * scale_y,
                    )
        self._mutate("缩放", action)
        resized = document.element(self.selected_id)
        if not self.transaction_active:
            self.log("修改尺寸 %s：%g × %g" % (resized.id, resized.width, resized.height))

    def scale_selected(self, scale_x: float, scale_y: Optional[float] = None) -> None:
        """Scale the selected set around each Element's own centre.

        The primary Element remains the Inspector reference.  Applying the
        same relative factor preserves differing source sizes and uses the
        existing resize/local-override path instead of introducing a second
        transform engine.
        """

        if not self.selected_id:
            raise RuntimeError("请先选择至少一个 Element。")
        factor_x = max(0.01, float(scale_x))
        factor_y = max(0.01, float(scale_y if scale_y is not None else scale_x))
        primary = self.require_document().element(self.selected_id)
        self.resize_selected(primary.width * factor_x, primary.height * factor_y)

    def rotate_selected_by(self, angle: float) -> None:
        """Rotate every selected Element by one shared angle in degrees."""

        if not self.selected_id:
            raise RuntimeError("请先选择至少一个 Element。")
        primary = self.require_document().element(self.selected_id)
        self.rotate_selected(primary.rotation + float(angle))

    def hide_selected(self) -> None:
        """Hide selected Elements without deleting source geometry."""

        document = self.require_document()
        identifiers = list(self.selected_ids or ([self.selected_id] if self.selected_id else []))
        if not identifiers:
            raise RuntimeError("请先选择至少一个 Element。")

        def action() -> None:
            if self.has_parametric_model:
                for identifier in identifiers:
                    override = self.parametric_model.local_overrides.get(identifier, LocalOverride())
                    override.visible = False
                    self.parametric_model.local_overrides[identifier] = override
                self._rebuild_parametric_document()
            elif self.active_placement_state() is not None:
                state = self.active_placement_state()
                state.slots = [
                    replace(slot, visible=False)
                    if slot.slot_id in identifiers or slot.source_element_id in identifiers else slot
                    for slot in state.slots
                ]
                state.attach(document)
                materialize_evaluated_elements(document)
            else:
                for identifier in identifiers:
                    document.element(identifier).visible = False
                document._sync_transforms()

        self._mutate("隐藏选中", action)
        self.clear_selection()
        self.log("隐藏 %d 个 Element" % len(identifiers))

    def show_all_elements(self) -> None:
        """Remove Gate L visibility edits while retaining every Element record."""

        document = self.require_document()

        def action() -> None:
            if self.has_parametric_model:
                for override in self.parametric_model.local_overrides.values():
                    if override.visible is False:
                        override.visible = None
                self._rebuild_parametric_document()
            elif self.active_placement_state() is not None:
                state = self.active_placement_state()
                state.slots = [replace(slot, visible=True) for slot in state.slots]
                state.attach(document)
                materialize_evaluated_elements(document)
            else:
                for element in document.elements:
                    element.visible = True
                document._sync_transforms()

        self._mutate("显示全部", action)
        self.log("显示全部 Element")

    def delete_selected(self) -> None:
        document = self.require_document()
        if not self.selected_id:
            raise RuntimeError("请先选择一个 Element。")
        deleted_ids = list(self.selected_ids or [self.selected_id])
        deleted = []
        def action() -> None:
            nonlocal deleted
            if self.has_parametric_model:
                for identifier in deleted_ids:
                    deleted.append(document.element(identifier))
                    override = self.parametric_model.local_overrides.get(identifier, LocalOverride())
                    override.visible = False
                    self.parametric_model.local_overrides[identifier] = override
                self._rebuild_parametric_document()
            else:
                deleted.extend(document.delete_element(identifier) for identifier in deleted_ids)
        self._mutate("删除", action)
        self.selected_id = None; self.selected_ids.clear()
        if not self.transaction_active:
            self.log("删除 Element：%s" % ", ".join(item.id for item in deleted))

    def duplicate_selected(self, dx: float = 8.0, dy: float = 8.0) -> str:
        document = self.require_document()
        if not self.selected_id:
            raise RuntimeError("请先选择一个 Element。")
        if self.has_parametric_model and self.pattern_mode is not PatternMode.FREE_PARAMETRIC:
            # A duplicate is not a local override and would disappear on the
            # next base-grid rebuild.  Refuse explicitly rather than creating
            # misleading, non-persistent geometry in this first model.
            raise RuntimeError("结构参数化模式暂不支持复制；请先烘焙为自由元素后复制。")
        source_ids = list(self.selected_ids or [self.selected_id])
        duplicates = []
        def action() -> None:
            if self.pattern_mode is PatternMode.FREE_PARAMETRIC:
                # Free parametric mode owns an imported base-element list, so
                # a duplicate belongs in that list rather than in a transient
                # materialised Canvas collection.
                from copy import deepcopy
                from uuid import uuid4
                for identifier in source_ids:
                    source = document.element(identifier)
                    clone = deepcopy(source)
                    clone.id = "free:%s" % uuid4().hex
                    clone.x += float(dx); clone.y += float(dy)
                    self.parametric_model.base_elements.append(serialize_elements([clone])[0])
                    duplicates.append(clone)
                self._rebuild_parametric_document()
            else:
                duplicates.extend(document.duplicate_element(identifier, dx=dx, dy=dy) for identifier in source_ids)
        self._mutate("复制", action)
        self.selected_ids = [item.id for item in duplicates]
        self.selected_id = self.selected_ids[-1]
        if not self.transaction_active:
            self.log("复制 Element：%s" % ", ".join(self.selected_ids))
        return self.selected_id

    def rotate_selected(self, rotation: float) -> None:
        if not self.selected_id:
            raise RuntimeError("请先选择一个 Element。")
        document = self.require_document()
        if self.has_parametric_model:
            selected_ids = list(self.selected_ids or [self.selected_id])
            primary = document.element(self.selected_id)
            delta = float(rotation) - primary.rotation
            def action() -> None:
                for identifier in selected_ids:
                    current = document.element(identifier)
                    self._set_grid_element_geometry(identifier, rotation=current.rotation + delta, rebuild=False)
                self._rebuild_parametric_document()
            self._mutate("旋转", action)
        elif self.active_placement_state() is not None:
            selected_ids = list(self.selected_ids or [self.selected_id])
            primary = document.element(self.selected_id)
            delta = float(rotation) - primary.rotation
            def action() -> None:
                for identifier in selected_ids:
                    current = document.element(identifier)
                    self._set_placement_slot_geometry(
                        identifier, rotation=current.rotation + delta, rebuild=False,
                    )
                materialize_evaluated_elements(document)
            self._mutate("旋转", action)
        else:
            selected_ids = list(self.selected_ids or [self.selected_id])
            primary = document.element(self.selected_id)
            delta = float(rotation) - primary.rotation
            self._mutate(
                "旋转",
                lambda: [
                    document.rotate_element(identifier, document.element(identifier).rotation + delta)
                    for identifier in selected_ids
                ],
            )

    def union_selected(self) -> str:
        if self.has_parametric_model:
            raise RuntimeError("规则矩阵模式暂不支持布尔运算；请先切换到自由元素模式。")
        identifiers = list(self.selected_ids or ([self.selected_id] if self.selected_id else []))
        if len(identifiers) < 2:
            raise RuntimeError("请至少选择两个实心区域。")
        self._mutate("布尔并集", lambda: self._assign_boolean_result("union", identifiers))
        return self.selected_id or ""

    def difference_selected(self) -> str:
        if self.has_parametric_model:
            raise RuntimeError("规则矩阵模式暂不支持布尔运算；请先切换到自由元素模式。")
        if not self.selected_id or len(self.selected_ids) < 2:
            raise RuntimeError("先选择主区域，再按 Shift 选择至少一个要减去的区域。")
        self._mutate("布尔差集", lambda: self._assign_boolean_result("difference", list(self.selected_ids)))
        return self.selected_id or ""

    def _assign_boolean_result(self, operation: str, identifiers: List[str]) -> None:
        document = self.require_document()
        if operation == "union":
            result = document.boolean_union(identifiers)
        else:
            result = document.boolean_difference(self.selected_id or identifiers[-1], [identifier for identifier in identifiers if identifier != self.selected_id])
        self.selected_id = result.id
        self.selected_ids = [result.id]

    def undo(self) -> bool:
        document = self.require_document()
        if self.transaction_active:
            self.commit_transaction()
        if not self._undo_stack:
            self.log("没有可撤销的操作", "INFO")
            return False
        self._redo_stack.append(document.to_dict())
        self._redo_revisions.append(self.revision)
        self.revision = self._undo_revisions.pop()
        self.document = PatternDocument.from_dict(self._undo_stack.pop())
        self._hydrate_parametric_state()
        self.selected_ids = [identifier for identifier in self.selected_ids if any(item.id == identifier for item in self.document.elements)]
        if self.selected_id and self.selected_id not in self.selected_ids:
            self.selected_id = self.selected_ids[-1] if self.selected_ids else None
        self._after_edit(); self.log("Undo：已恢复上一步编辑")
        self._project_changed()
        return True

    def redo(self) -> bool:
        document = self.require_document()
        if self.transaction_active:
            self.commit_transaction()
        if not self._redo_stack:
            self.log("没有可重做的操作", "INFO")
            return False
        self._undo_stack.append(document.to_dict())
        self._undo_revisions.append(self.revision)
        self.revision = self._redo_revisions.pop()
        self.document = PatternDocument.from_dict(self._redo_stack.pop())
        self._hydrate_parametric_state()
        self.selected_ids = [identifier for identifier in self.selected_ids if any(item.id == identifier for item in self.document.elements)]
        if self.selected_id and self.selected_id not in self.selected_ids:
            self.selected_id = self.selected_ids[-1] if self.selected_ids else None
        self._after_edit(); self.log("Redo：已恢复下一步编辑")
        self._project_changed()
        return True

    def export_svg(self, output_path: Optional[str] = None, record: bool = True) -> Path:
        document = self.require_document()
        target = Path(output_path or self.editable_svg_path or (self.workspace / "editable.svg")).resolve()
        target = pattern_document_to_svg(document, str(target))
        self.svg_serialize_count += 1
        self.editable_svg_path = target
        if record:
            self.log("导出 SVG：%s" % target.name)
        return target

    def save_document(self, output_path: Optional[str] = None) -> Path:
        document = self.require_document()
        if self.transaction_active:
            self.commit_transaction()
        self._persist_parametric_state()
        target = Path(output_path or self.current_project_path or (self.workspace / "pattern.pattern.json")).resolve()
        target = save_pattern_document(document, str(target))
        self.current_project_path = target
        self.saved_revision = self.revision
        self._recovered_revision = None
        self._discard_own_recovery()
        self._remember_project(target)
        self._project_changed()
        self.log("保存 PatternDocument：%s" % target.name)
        return target

    def load_document(self, path: str) -> PatternDocument:
        target = Path(path).resolve()
        candidate = self._prepare_loaded_document(load_pattern_document(str(target)))
        self._adopt_loaded_document(candidate, target, saved=True)
        self._remember_project(target)
        self.log("重新加载 PatternDocument：%s" % Path(path).name)
        return self.require_document()

    def _prepare_loaded_document(self, document: PatternDocument) -> "PatternLabSession":
        # A temporary view of the same Session API validates/rebuilds a detached
        # document. No disk writes, history clearing or live replacement occur.
        candidate = copy(self)
        candidate.document = document
        candidate.logs = []
        candidate.on_project_change = None
        candidate._hydrate_parametric_state()
        if candidate.has_parametric_model:
            candidate._rebuild_parametric_document()
        elif (SharedModifierStack.from_document(document) is not None
              or candidate.active_placement_state() is not None):
            materialize_evaluated_elements(document)
        else:
            # Also validate bare Gate-R graphs without a compatibility stack.
            evaluate_pattern_document(document)
        document.validate()
        return candidate

    def _adopt_loaded_document(self, candidate: "PatternLabSession", path: Path | None, *, saved: bool) -> None:
        self.document = candidate.document
        self.pattern_mode, self.grid_model = candidate.pattern_mode, candidate.grid_model
        self.parametric_model = candidate.parametric_model
        self.editable_svg_path = self.workspace / "editable.svg"
        self._reset_project_history(path, saved=saved)
        if self.missing_reference:
            self.log("参考图片未找到；矢量元素保留，可通过文件菜单重新定位。", "WARNING")

    def relink_reference(self, path: str) -> None:
        target = Path(path).resolve()
        from PIL import Image
        with Image.open(target) as image:
            image.verify()

        def action():
            document = self.require_document()
            old = document.reference.source_path
            document.reference.source_path = str(target)

            def bind(value):
                if isinstance(value, dict):
                    for key, item in value.items():
                        if key == "source_elements":
                            continue
                        if key == "image_path" and item in (old, ""):
                            value[key] = str(target)
                        else:
                            bind(item)
                elif isinstance(value, list):
                    for item in value:
                        bind(item)
            bind(document.fields)
            bind(document.metadata)
            self._hydrate_parametric_state()
            if self.has_parametric_model or SharedModifierStack.from_document(document) is not None:
                self._rebuild_parametric_document()
        self._mutate("重新定位参考图片", action)

    def _after_edit(self) -> None:
        self._persist_parametric_state()
        self.export_svg(record=False)

    def _rebuild_parametric_document(self) -> None:
        """Evaluate active family → Modifiers → Overrides into Elements."""

        if self.parametric_model is None:
            if self.document is not None and (
                SharedModifierStack.from_document(self.document) is not None
                or self.active_placement_state() is not None
            ):
                materialize_evaluated_elements(self.document)
            return
        document = self.require_document()
        self._persist_parametric_state()
        materialize_evaluated_elements(document)

    # Kept only for Matrix V1/V3 integrations that call the old private name.
    def _rebuild_grid_document(self) -> None:
        self._rebuild_parametric_document()

    def evaluate_elements(self):
        """Expose the single Evaluate pipeline for non-UI callers and tests."""

        return evaluate_pattern_document(self.require_document())

    def validate_final_geometry(self, *, epsilon: float = 1e-6) -> GeometryValidationReport:
        """Read-only Gate T validation of transient final manufacturing geometry.

        This intentionally neither bakes evaluated elements nor starts an Undo
        transaction, so analysis cannot dirty a project or change its canvas.
        """

        return GeometryValidator(epsilon=epsilon).validate_document(self.require_document())

    def analyze_connectivity(self, *, epsilon: float = 1e-6) -> ConnectivityReport:
        """Read final 2D components without dirtying or changing the project."""

        return ConnectivityAnalyzer(epsilon=epsilon).analyze_document(self.require_document())

    def adapt_manufacturing_geometry(self, *, curve_tolerance_mm: float = 0.05) -> ManufacturingConversionResult:
        """Create transient, mm-native manufacturing 2D geometry without editing."""

        return ManufacturingGeometryAdapter(curve_tolerance_mm=curve_tolerance_mm).adapt_document(self.require_document())

    def build_manufacturing_mesh(
        self, *, height_mm: float = 2.0, backend: ManufacturingBackend | None = None,
    ) -> ManufacturingBuildResult:
        """Explicit Gate V build: U.5 result first, then a derived mesh only."""

        conversion = self.adapt_manufacturing_geometry()
        mesh_result = (backend or TrimeshBackend()).extrude(conversion.geometry, height_mm)
        return ManufacturingBuildResult(conversion=conversion, mesh_result=mesh_result)

    def validate_manufacturing_mesh(
        self, mesh_result: ManufacturingMeshResult, *, validator: MeshValidator | None = None,
    ) -> MeshValidationReport:
        """Gate W reads an already-derived Mesh only; it never re-evaluates this session."""

        return (validator or MeshValidator()).validate(mesh_result)

    def export_validated_stl(
        self, mesh_result: ManufacturingMeshResult, output_path: str | Path, *, overwrite: bool = False,
        exporter: STLExporter | None = None,
    ) -> STLExportResult:
        """Gate X uses the supplied Gate V Mesh only; it never rebuilds the document."""

        return (exporter or STLExporter()).export(mesh_result, output_path, overwrite=overwrite)

    def _set_grid_element_geometry(
        self,
        element_id: str,
        *,
        x: Optional[float] = None,
        y: Optional[float] = None,
        width: Optional[float] = None,
        height: Optional[float] = None,
        rotation: Optional[float] = None,
        rebuild: bool = True,
    ) -> None:
        """Translate a direct Inspector edit into a persistent LocalOverride."""

        if self.parametric_model is None:
            raise RuntimeError("当前没有参数化模型。")
        current = self.require_document().element(element_id)
        base = self.parametric_model.base_element(element_id)
        if base is None:
            raise KeyError("参数化模型中找不到 Element：%s" % element_id)
        target_x = current.x if x is None else float(x)
        target_y = current.y if y is None else float(y)
        target_width = current.width if width is None else max(0.01, float(width))
        target_height = current.height if height is None else max(0.01, float(height))
        target_rotation = current.rotation if rotation is None else float(rotation)
        override = self.parametric_model.local_overrides.get(element_id, LocalOverride())
        override.offset_x = target_x - base.x
        override.offset_y = target_y - base.y
        override.scale_x = target_width / max(base.width, 0.01)
        override.scale_y = target_height / max(base.height, 0.01)
        override.rotation_offset = target_rotation - base.rotation
        self.parametric_model.local_overrides[element_id] = override
        if rebuild:
            self._rebuild_parametric_document()

    def _persist_parametric_state(self, *, source_elements: Optional[list[dict]] = None) -> None:
        if self.document is None:
            return
        if self.has_parametric_model:
            previous = self.document.metadata.get(PARAMETRIC_METADATA_KEY)
            if source_elements is None and isinstance(previous, dict):
                source_elements = previous.get("source_elements")
            self.document.metadata[PARAMETRIC_METADATA_KEY] = {
                "mode": self.pattern_mode.value,
                "family": self.pattern_mode.value,
                # Preserve the old key only for persisted Grid documents.
                "grid": self.grid_model.to_dict() if self.pattern_mode is PatternMode.GRID and self.grid_model is not None else None,
                "model": self.parametric_model.to_dict(),
                # Source geometry is retained for audit / future re-analysis;
                # there is no separate persisted ``final_elements`` cache.
                "source_elements": source_elements or [],
            }
        else:
            self.document.metadata.pop(PARAMETRIC_METADATA_KEY, None)

    def _hydrate_parametric_state(self) -> None:
        if self.document is None:
            self.pattern_mode = PatternMode.FREE
            self.grid_model = None
            self.parametric_model = None
            return
        payload = self.document.metadata.get(PARAMETRIC_METADATA_KEY)
        if not isinstance(payload, dict):
            self.pattern_mode = PatternMode.FREE
            self.grid_model = None
            self.parametric_model = None
            return
        try: self.pattern_mode = PatternMode(payload.get("mode", PatternMode.FREE.value))
        except ValueError: self.pattern_mode = PatternMode.FREE
        if self.pattern_mode is PatternMode.GRID:
            self.grid_model = GridParametricModel.from_dict(payload.get("grid") or payload.get("model"))
            self.parametric_model = self.grid_model
        elif self.pattern_mode in (PatternMode.RADIAL, PatternMode.ALONG_CURVE, PatternMode.FREE_PARAMETRIC):
            from .parametric_families import parametric_model_from_payload
            self.grid_model = None
            family = {PatternMode.RADIAL: "radial", PatternMode.ALONG_CURVE: "along_curve", PatternMode.FREE_PARAMETRIC: "free"}[self.pattern_mode]
            self.parametric_model = parametric_model_from_payload(family, payload.get("model") or {})
            if self.parametric_model is None: self.pattern_mode = PatternMode.FREE
        else:
            self.grid_model = None; self.parametric_model = None
