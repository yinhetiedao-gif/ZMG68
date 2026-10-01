# Fabric System V1 — F0 Architecture Blueprint

状态：**设计提案，未实现**。基线为 `2c00b7fd36c38ce4c7f64b94ed262ec7eb2ccd55`，由 `web-v0.1-alpha` 标签和 `backup/web-v0.1-alpha-physical-validated` 分支保护。Web Alpha 已由用户报告完成真实打印；F0 不改变它的任何运行行为。本文中的类型、接口和流程（除明确写作“现有”的部分外）均为后续 Gate 的契约草案，不代表当前产品能力。

## 1. 架构与不可变边界

```text
现有、唯一持久设计事实：PatternDocument
  ├─ Canvas / Reference / source Elements / Groups / Transforms / Metadata
  ├─ Layout: Free / Grid / Radial / Curve
  ├─ Fields + 现有 2D Modifier Stack + Local Overrides
  └─ FabricConfig?（未来可选、版本化的设计意图）
            │
            ▼
现有 evaluate_pattern_document → Final 2D Geometry（派生）
            │
            ├─ FabricConfig 缺席 → 现有 ManufacturingService → 现有 STL/GLB
            │                       （默认路径必须保持原样）
            └─ FabricConfig 存在 → FabricPlanner（未来）
                                      → FabricInstancePlan（派生）
                                      → FabricMeshBuilder（未来）
                                      → ManufacturingMeshResult
                                      → 现有 MeshValidator
                                      → 现有结果缓存 / STLExporter / GLB artifact
```

`PatternDocument` 继续负责保存/加载、Undo/Redo 和修订号。FabricConfig 只表达用户选择及参数；不持久化实例计划、Mesh、预览或 STL。二维 Layout 决定当前图案元素的空间组织；Fabric Placement 决定如何从最终二维几何或采样点布置三维单元。两者不能混为一套布局算法。Web Canvas/Three.js 仅展示派生结果，不是 FabricPlanner 的输入或事实来源。

现有实现依据：`ppg/foundation/models.py` 定义 PatternDocument；`xiaomang_pattern_lab/evaluation.py` 生成最终二维元素；`xiaomang_pattern_lab/manufacturing_service.py` 的现有链为求值→几何验证→连通性→制造二维适配→挤出→Mesh 验证；`manufacturing_backend.py` 产生 ManufacturingMeshResult；`mesh_validation.py`、`stl_export.py` 和 `web/preview_artifact.py` 承接验证及产物。新 Fabric 不能通过修改这些既有结果的语义来“兼容”。

## 2. 设计数据与单位

建议在现有 `PatternDocument.metadata` 下使用独立、可选、版本化命名空间（示例：`xiaomang_pattern_lab.fabric`），先走现有 `to_dict/from_dict` 往返；真正字段名和迁移规则在 F1 定稿。FabricConfig 缺席必须等价于现有 Web Alpha 行为，旧工程不强制升级。未知未来版本应拒绝制造并明确提示，不静默删字段或退化到错误默认。文档 ID、`document_revision` 和现有 Web DTO `schema_version=1.0` 语义不变；Fabric 子配置单独带 `config_version`，避免仅为设计扩展就改变现有 Web 合同。将来如需公开 API 合同升级，须另立兼容版本并回归旧工程。

```text
FabricConfig（建议，未来）
  config_version
  enabled / manufacturing_mode
  base: BaseDefinition
  unit_cell: UnitCellDefinition
  placement: PlacementDefinition
  field_bindings: FieldBinding[]
  modifiers: FabricModifierDefinition[]
  manufacturing_preferences（仅能影响明确允许的制造参数）
```

| 结构 | 保存的设计意图 | 不应保存/执行 |
| --- | --- | --- |
| BaseDefinition | `kind = solid/grid/perforated`；厚度、间距、线宽、开孔率及单位 | 已三角化底板、隐式自动修复 |
| UnitCellDefinition | 稳定类型 ID、参数字典、默认姿态、基准尺寸；候选 Cylinder/Capsule/Cone/Pyramid/DoubleTower/Fin | 每个实例的一整份 Mesh、依赖 Web 表单的私有参数 |
| PlacementDefinition | `source = final_elements/samples`、定位/朝向规则、采样间距、稳定槽位规则、边界/裁切策略 | 重新识别图像、二次 Grid 算法、Canvas 屏幕坐标 |
| FieldBinding | `field_id`、目标 Fabric Modifier ID/参数、输入/输出归一化和映射范围 | 复制 Field 方程或内嵌完整 Field 定义 |
| FabricModifierDefinition | 稳定 ID、类型、启用状态、顺序、Field 引用、参数、可选 scope | 永久改写 source_elements |

所有设计坐标先按 PatternDocument world XY 解释；制造前必须从 `canvas.unit/mm_per_unit` 得到有限、正值的毫米映射，不能把屏幕像素当 mm。建议制造空间 XY 与二维 world 一致，Z 为厚度/高度方向，`z=0` 是底部基准面。角度使用明确单位（文档/UI 度数，构建时转换），尺寸和最小制造约束均用 mm。坐标约定、原点、旋转轴及变换顺序须在 F1 固定并加往返测试。

## 3. Field → Fabric Modifier，保持解耦

现有 `SharedFieldEngine`/`FieldRegistry` 输出 `0..1` 空间值，已有 Constant、Linear、Ring、Wave、Stripe、Checker、Spiral、Noise、Image、Composite 等实现；`SharedModifierStack` 已承担非破坏性二维效果。Fabric 不复制 Field 方程，不把某个 Field 专门写成 Height/Size 算法。未来用一个 Fabric 采样适配器把实例的 world XY、稳定 source/slot ID 与冻结的 FieldContext 传给现有 FieldRegistry。若 Field 实现只能接受现有 Element，适配器须提供轻量样本 Element 或在不改变方程语义的前提下抽出共同采样入口；F3 先写一致性测试再选方案。

```text
同一个 Wave field_id ──┬── HeightModifier：0..1 → min/max height_mm
                       └── UnitScaleModifier：0..1 → min/max scale
同一个 Image field_id ─┬── DensityModifier：0..1 → 保留/占用概率
                       └── HeightModifier：0..1 → mm
```

未来第一批目标为 Height、Density、Orientation、UnitScale；UnitType 是可选的后续目标。Field 自身永远不决定“高度/密度/方向”，映射属于 Modifier。FieldBindings 引用现有 Field ID，不能复制定义；删除被引用 Field 必须显式阻止或迁移。Composite 依赖与循环检查沿用现有 FieldRegistry 行为。Image Field 还需可持久解析的资产身份：现有 Web 临时 Asset Store 会过期，不能仅保存绝对路径或假定重开工程仍能找到图片。F4 必须先解决资产绑定/缺失提示，不得静默改变输出。

建议规划顺序为：最终二维元素→稳定 placement slots→Field 采样→有序 Fabric Modifier→确定性 occupancy/size/orientation→FabricInstancePlan→制造 Mesh。FieldContext 的 bounds 应来自固定的最终二维输入/采样边界，不能随着某一 modifier 改变而漂移。Density 如涉及随机取舍，要用稳定 slot ID + seed + channel 得到可复现结果；未占用槽位应在计划中明确记录或可确定性重建。既有局部 overrides 仍在二维 evaluate 阶段应用；未来单元级覆盖必须有独立、稳定 ID 和清晰优先级，不能覆盖既有 source_elements。

## 4. Placement 与派生实例计划

`FabricPlanner` 的输入仅为已求值的最终二维元素、FabricConfig、现有 Field 注册表以及明确的资产/单位上下文。它不能直接读 React/Tk 状态或再次向量化原图。建议中间结构：

```text
FabricInstancePlan（只读派生，可按 chunk 迭代）
  document_id, document_revision, config_version, world_to_mm
  base_plan / bounds_mm
  instances: FabricInstance[] 或稳定 chunk iterator
  skipped + warnings + deterministic plan fingerprint

FabricInstance
  instance_id（由稳定 slot/source ID 派生，不依赖遍历顺序）
  source_id? / slot_id
  position_xyz_mm
  rotation_xyz_deg / scale_xyz / height_mm
  unit_cell_type / effective_parameters / enabled
```

`final_elements` 模式的实例中心、可见性与边界来自真正的最终二维几何；`samples` 模式须明确采样域与稳定格点规则，不代表重新布局当前图案。被裁切元素、孔洞、Mask、多个连通分量及空输入必须有可测的处理结果，不能靠 Canvas 是否看见决定生产。所有槽位到实例的映射必须保持稳定，便于修改参数、Undo/Redo、缓存与未来局部编辑。

未来单元参数通过 Python 权威的 `parameter_definitions.py` 扩展同一 Parameter Definition Schema；Web Inspector 的 FABRIC BASE / UNIT CELL / HEIGHT / DENSITY / ORIENTATION 分组仍使用通用 ParameterPanel。F0 不新增 UI、Schema 或具体 Unit Cell。

## 5. 制造与预览是两条不同成本的路径

### 正式制造（未来）

```text
PatternDocument → 现有 evaluate → Final 2D Geometry
  → FabricPlanner → FabricInstancePlan → FabricMeshBuilder
  → ManufacturingMeshResult → 现有 MeshValidator
  → 现有 manufacturing_result_id/result store
  ├─ 懒生成正式 STL（现有 STLExporter，必要时按既有策略读回验证）
  └─ 从同一正式 Mesh 懒生成只读 GLB（现有 artifact 路由）
```

FabricMeshBuilder 必须输出当前 `ManufacturingMeshResult` 所要求的真实 mm bounds、顶点/面、组件和 Mesh，随后接受现有 Gate W 验证。现有 `TrimeshBackend.extrude` 只负责二维制造几何挤出，不能假装已能处理任意 3D Unit Cell。底板/单元融合、孔洞处理及三角化策略须在 F1/F2 根据真实几何做选型与测试；不默认对每个 cell 做独立 Boolean，也不默默自动 union、移动、连接或修复。基础 mesh + 单元组合后必须重新验证封闭性和组件数。多组件不是自动错误，但需明确报告/警告；是否可打印由约束和用户工艺决定。

现有 `POST /api/v1/manufacturing/build` 对无 FabricConfig 的工程保持原样。未来显式 Fabric 模式由 ManufacturingService 的上层路由/构建策略选择，最终仍产出同一制造结果合同；不能为了 Fabric 改变既有挤出工程的 STL 字节、尺寸或质量门槛。

### 快速预览（未来）

拖动参数时只更新配置临时值/廉价 FabricInstancePlan 或其摘要；Three.js 可用共享单元原型和 InstancedMesh 绘制 1k/10k/50k+ 实例，并采用视口裁剪/抽样/LOD。这个快速预览不是打印依据，不得下载为正式 STL。用户点击正式 build 后，现有 GLB 仍必须从同一个已验证制造结果生成，且与 STL 共用 `manufacturing_result_id`；预览不独立挤出、修复或改变拓扑。UI 必须区分“快速设计预览”与“已验证制造模型”，避免把简化预览误当成正式结果。

## 6. 性能与缓存边界

- **实例规划**：向量化/二维 evaluate 只在设计需要时执行一次；按稳定 ID 批量采样 Field，并允许 chunk 迭代，避免为 50k 单元复制 50k 个完整原型 Mesh。
- **几何复用**：同类型同参数可共享单元几何/模板；合批、分块与融合策略由实测决定。避免逐实例 Boolean；不能以降低闭合性、尺寸或孔洞正确性换性能。
- **交互**：滑杆移动只改 transient preview，不每帧 HTTP 传完整 mesh；松手/明确 build 后才提交并进行重型制造。未来慢任务可用后台 job、取消与真实阶段进度；F0 不引入队列服务。
- **缓存**：以完整规范化 PatternDocument DTO（含 FabricConfig）、revision、单位/高度/制造参数、依赖资产内容身份、算法/config 版本共同构成缓存身份。现有 `manufacturing_result_id` 当前由完整 DTO 与 `height_mm` 算得，未来新增制造参数或实现版本时须扩充版本化键，防止不同 Fabric 结果别名。结果缓存继续有界/TTL；cache miss 重新构建，不能引用过期 mesh。预览/STL 按现有规则从同一缓存结果懒生成。
- **测量门槛**：F1 先建立实例数、plan 时间/内存、Mesh 构建、验证、GLB/STL 大小与冷/热缓存指标。按 1k/10k/50k 分级报告，而不是承诺当前机器都可即时制造。

## 7. 制造约束与验证责任

F5 在现有 MeshValidator 之前增加只读、可解释的 Fabric 领域检查：底板过薄、单元底座过小、单元过高/细、底板与单元接触面积不足、微小孤岛/组件，并保留已有 non-manifold、watertight、法线/退化面、组件和尺寸检查。阈值依赖材料/工艺/喷嘴等真实配置，不应把未经验证的常数称为通用打印安全标准。报告包含问题代码、严重度、受影响 instance/source ID、测量值、阈值及单位；warning 不默认自动修复，error 阻止正式 STL 的规则需在 F5 与现有出口一致。实际切片/打印验收仍是独立物理里程碑，不能由 watertight 单独代替。

## 8. API / DTO 边界（仅设计，不新增 endpoint）

| 未来合同 | 最小职责 | 兼容性要求 |
| --- | --- | --- |
| FabricConfig DTO | PatternDocument 内版本化设计配置；引用既有 Fields/Modifiers、资产身份 | 旧文档无 FabricConfig 时保持旧路径；未知版本明确错误 |
| FabricBuildRequest | 当前 `PatternDocumentDTO`、`document_id`、`document_revision`、Fabric 模式/厚度及将来必要制造参数 | 继承现有版本、单位和 stale 语义；不接收前端生成的 Mesh |
| FabricBuildReport | placement/跳过统计、Fabric 领域验证、Mesh 验证、bounds、组件、warning/error | 可在现有制造响应的版本化扩展中提供；不把 summary 当成 mesh |
| FabricPreview Artifact | 已验证结果 ID 对应的只读 GLB；快速预览另有明确非制造身份 | 正式 GLB/STL 必须来自同一 `manufacturing_result_id` |

目前 Web 的 `ManufacturingBuildRequestDTO` 只含 `document_id`、`document_revision`、`height_mm`；`ManufacturingBuildResponseDTO` 记录验证、bounds、组件和结果 ID；`web/runtime_store.py` 是进程内有界 TTL 缓存，`/model.stl` 与 `/preview.glb` 懒生成。F0 不改变这些 API。未来新增 endpoint 或 DTO 字段需独立 Gate、OpenAPI/旧客户端兼容测试和明确错误码。Fabric build 只读取 PatternDocument，不改变 revision、Undo 历史或二维 Canvas。设计或厚度变化应使旧制造结果 stale。

## 9. `v 0-5.scad` 的架构映射

**Pending source-code verification.** 当前仓库、工作区和已提供附件中未找到 `v 0-5.scad`。本节只记录用户指定的架构层目标映射，不推断其源码、公式、尺寸、形状细节或可打印性。文件补充后再单独核验，不阻塞 F0。

```text
Grid Layout
+ Unit Cell
+ Wave / Composite Fields
+ Height Modifier
+ Scale Modifier
+ Rotation Modifier
+ Fabric Base
→ FabricInstancePlan → validated mesh
```

这仅说明拟议结构为上述概念预留了对应职责，并不声称已复现 SCAD、实现任何单元或完成制造验证。

## 10. F1–F5 严格顺序与验收门槛

1. **F1 Fabric Base**：定稿 FabricConfig 的可选持久化/迁移、单位、solid 基底和独立的 base manufacturing strategy；旧工程同输入制造结果完全不变。先测单个基底闭合、尺寸、Save/Load、旧工程回归。
2. **F2 Unit Cell Library**：先取简单 Cylinder/Cone/Pyramid 的最小可制造集合，建立参数 Schema、稳定实例计划和 Mesh Builder；DoubleTower/Fin/Capsule 只在对应原型验证后加入，不为赶列表虚构 PASS。测单元连接、孔洞、组件及 STL 读回。
3. **F3 Height / Density / Orientation**：复用 FieldRegistry，加入有序 Fabric Modifier 和稳定实例 ID；测同 Field 多目标、确定性 density、参数组合、source 不变、Save/Load/Undo，以及 1k/10k 性能。UnitScale 可随此阶段接入。
4. **F4 Image-driven Fabric**：解决 Image Field 资产持久身份/缺失，再测亮度→高度/密度的可复现映射、重启后恢复、资产失效提示与 SVG/PNG 来源差异。
5. **F5 Fabric Validation**：补领域警告/阻断策略和真实制造回归；测试最小连接/细长/孤岛、现有 MeshValidator、同 ID GLB/STL、切片与至少一件真实打印。自动测试不能冒充物理验收。

每 Gate 独立分支/提交/回归和回退点；任一旧 Web Alpha 功能、制造结果或实体尺寸回归则停止，不进入下一 Gate。F0 完成后只冻结本文设计，不创建 Fabric 功能稳定备份，不进入 F1。

## 11. 风险、未决问题与明确非目标

- **组合几何**：底板与大量单元融合若不可靠，可能导致非封闭或多组件；需在 F2 用实际模型选择批量构建策略，不能靠预览遮掩。
- **拓扑与性能**：50k 个单元的正式 Mesh 可能超出本机内存/HTTP；chunk 和共享原型是规划，不是容量保证。
- **Field 采样语义**：当前 Field 接口以二维 Element 为输入，Fabric 实例样本需要一致性适配；Image Field 的临时资产生命周期尤其有风险。
- **参数组合**：尺寸/高度/方向作用顺序、局部覆盖和 Mask 对单元连接的影响须在 F3 固定，不允许与现有 2D Modifier 静默互换。
- **制造工艺**：不同材料和设备的最小壁厚/悬垂/接触面积不同；F5 先报告风险，不默认修复或保证成功率。
- **参考缺失**：`v 0-5.scad` 尚未提供，映射未核验，不能据此制定具体 DoubleTower 几何或物理指标。
- **本轮非目标**：不新增 Fabric Mesh 算法、Height/Density/Orientation 实现、Web/Tk UI、endpoint、STL/GLB 行为、3MF、自动修复/连接，也不修改 Web Alpha 现有代码。
