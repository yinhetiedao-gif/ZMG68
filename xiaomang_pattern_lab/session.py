"""UI-independent Pattern Lab orchestration over the reusable Core Engine."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from time import perf_counter
from typing import List, Optional

from ppg.foundation import FoundationPipeline, PatternDocument, SVGNormalizer, load_pattern_document, pattern_document_to_svg, save_pattern_document

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
from .shared_modifiers import SHARED_MODIFIER_METADATA_KEY, SharedModifierStack
from .pattern_analyzer import AnalysisTolerance, GridAnalysisDebug, GridFitResult, MultiFamilyAnalysis, PatternAnalyzer
from .recognition import MultiScaleDotRecognizer


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

    def __post_init__(self) -> None:
        self.workspace = Path(self.workspace).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        if self.document is not None:
            self._hydrate_parametric_state()

    def log(self, message: str, level: str = "INFO") -> None:
        stamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        self.logs.append(ConversionLogEntry(stamp, level, message))

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

    def select_many(self, element_ids: List[str]) -> Optional[str]:
        document = self.require_document()
        identifiers = list(dict.fromkeys(element_ids))
        for identifier in identifiers:
            document.element(identifier)
        self.selected_ids = identifiers
        self.selected_id = identifiers[-1] if identifiers else None
        return self.selected_id

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
        self.undo_record_count += 1
        self._redo_stack.clear()
        self.log("%s已提交（1 条 Undo Transaction）" % label)
        self._after_edit()
        self.document_commit_count += 1
        self._last_commit_seconds = perf_counter() - started
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
        else:
            self._mutate("移动", lambda: document.move_element(element_id, float(x) - element.x, float(y) - element.y))

    def set_element_size(self, element_id: str, width: float, height: float) -> None:
        document = self.require_document()
        if self.has_parametric_model:
            self._mutate("缩放", lambda: self._set_grid_element_geometry(element_id, width=float(width), height=float(height)))
        else:
            self._mutate("缩放", lambda: document.resize_element(element_id, float(width), float(height)))

    def commit_interaction(self, interaction: InteractionState) -> bool:
        """Commit a transient Canvas preview once, on pointer-up only.

        No pointer-motion callback invokes this method.  The active transaction
        was snapshotted at pointer-down, so this contributes one Undo command.
        """

        document = self.require_document()
        if not self.transaction_active:
            raise RuntimeError("Canvas 交互缺少事务起点。")
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
        """Add one ordered Size/Rotation layer as a single Undo command."""
        result: list[str] = []

        def action() -> None:
            stack = self._stack_for_edit()
            result.append(stack.add_modifier(modifier_type, parameters, modifier_id=modifier_id))
            stack.attach(self.require_document(), source_kind=stack.source_kind)
            materialize_evaluated_elements(self.require_document())

        self._mutate("添加效果层", action)
        return result[0]

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
            else:
                document.resize_element(self.selected_id, width, height)
        self._mutate("缩放", action)
        resized = document.element(self.selected_id)
        if not self.transaction_active:
            self.log("修改尺寸 %s：%g × %g" % (resized.id, resized.width, resized.height))

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
        else:
            selected_ids = list(self.selected_ids or [self.selected_id])
            self._mutate("旋转", lambda: [document.rotate_element(identifier, float(rotation)) for identifier in selected_ids])

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
        self.document = PatternDocument.from_dict(self._undo_stack.pop())
        self._hydrate_parametric_state()
        self.selected_ids = [identifier for identifier in self.selected_ids if any(item.id == identifier for item in self.document.elements)]
        if self.selected_id and self.selected_id not in self.selected_ids:
            self.selected_id = self.selected_ids[-1] if self.selected_ids else None
        self._after_edit(); self.log("Undo：已恢复上一步编辑")
        return True

    def redo(self) -> bool:
        document = self.require_document()
        if self.transaction_active:
            self.commit_transaction()
        if not self._redo_stack:
            self.log("没有可重做的操作", "INFO")
            return False
        self._undo_stack.append(document.to_dict())
        self.document = PatternDocument.from_dict(self._redo_stack.pop())
        self._hydrate_parametric_state()
        self.selected_ids = [identifier for identifier in self.selected_ids if any(item.id == identifier for item in self.document.elements)]
        if self.selected_id and self.selected_id not in self.selected_ids:
            self.selected_id = self.selected_ids[-1] if self.selected_ids else None
        self._after_edit(); self.log("Redo：已恢复下一步编辑")
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
        target = Path(output_path or (self.workspace / "pattern.pattern.json")).resolve()
        target = save_pattern_document(document, str(target))
        self.log("保存 PatternDocument：%s" % target.name)
        return target

    def load_document(self, path: str) -> PatternDocument:
        self.document = load_pattern_document(path)
        self._hydrate_parametric_state()
        if self.has_parametric_model:
            # Do not trust a stale materialized Element list from disk.  The
            # model, modifiers and overrides are the authoritative state.
            self._rebuild_parametric_document()
        elif SharedModifierStack.from_document(self.document) is not None:
            materialize_evaluated_elements(self.document)
        self.selected_id = None; self.selected_ids.clear()
        self.editable_svg_path = self.workspace / (Path(path).stem + ".svg")
        self.export_svg(str(self.editable_svg_path), record=False)
        self._undo_stack.clear(); self._redo_stack.clear(); self._transaction_before = None; self._transaction_label = None
        self.log("重新加载 PatternDocument：%s" % Path(path).name)
        return self.document

    def _after_edit(self) -> None:
        self._persist_parametric_state()
        self.export_svg(record=False)

    def _rebuild_parametric_document(self) -> None:
        """Evaluate active family → Modifiers → Overrides into Elements."""

        if self.parametric_model is None:
            if self.document is not None and SharedModifierStack.from_document(self.document) is not None:
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
