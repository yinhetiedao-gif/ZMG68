# 二维线性尺寸渐变快捷入口（2026-10-06，本地待用户确认）

## 现场与授权边界

- 分支 `feature/pattern-library-reuse`，HEAD仍为 `b5338a9af41d25ccd191d34366115578265920bb`。本次成果未提交，不属于该HEAD，不是冻结/上线版本。
- 开始时82个既有修改/未跟踪文件，暂存区空；逐文件保护在 `work/linear-size-shortcut-20261006/pre-change/`。没有reset、clean、恢复旧补丁、换分支、提交、推送、部署。
- 沿用已有独立8792本地生产构建/FastAPI，独立Edge上下文，不覆盖用户8791草稿。未改Python生产代码、依赖、部署/生产开关、Validator、制造算法。未做径向、其他逻辑、1B或混合追加能力。

## 实际文件与连接

| 文件 | 本次修改及入口 |
| --- | --- |
| `web/src/App.tsx` | `selectLinearSize` / `applyLinearSize`；左侧尺寸变化效果、右侧Schema四参数与Reset/Cancel/Apply；候选显示、pending/stale/正式文档检查；继续使用原commit/history/draft/制造失效 |
| `web/src/document/linearSize.ts`（新增） | `openLinearSize` / `linearSizeCandidate` / `linearSizeGroup`；只构造正式DTO的独立配置候选、归属ID、范围/单位元数据，不求二维几何 |
| `web/src/document/editor.ts` | `fieldReferencedOutside`；抽取已有1A保守引用扫描，复用原addField/addModifier/bind；没有第二套专用场系统 |
| `web/src/document/fabricModifiers.ts` | 已有高度归属扫描调用上述公用函数，消费者排除语义不变；定向8项回归保留 |
| `web/src/document/useLayoutPreview.ts` | 从现有布局候选hook抽取`useDocumentPreview`；180ms合并、single-flight、排空旧请求、旧响应丢弃；错误保留同会话最后有效画面，失败候选不能Apply |
| 测试 | 新增`linearSize.test.ts` / `App.linearSize.test.tsx` / `test/linearSizeFixture.ts`；扩展原`useLayoutPreview.test.tsx`错误保画面用例 |
| 验收工具 | `tools/linear_size_smoke.cjs`、`tools/linear_size_readback.py`；真实浏览器交互、响应/截图、下载文件严格读回 |

## 产品与算法语义

不是新的PatternFamily，不切换/删除Grid，不重排元素。高级场/效果入口保留。

控件来自现有Python Schema：方向为角度，尺寸比例无单位，强度0–1。默认方向0°、最小比例0.6、最大比例1.2、强度1；推荐滑杆及真实合法范围仍由Schema决定，非法数值不clamp文档。默认不会把单元缩到接近0。

线性场的start/end为**文档世界单位**投影坐标；快捷入口取首次实际最终图案bounds并按mm_per_unit换算。Python `LinearField.evaluate` 输出clamp的0–1标量，原`SizeModifier/FieldMapping`执行尺寸映射，作用强度按原neutral=1混合。范围外保持端点值。React只计算绑定范围的坐标转换，不计算元素的Field结果。

归属存于现有metadata的`web_linear_size_effect`：version、field_id、modifier_id、bounds_mm、mm_per_unit。已应用后重开读取自己的参数和范围，毫米比例变更时范围显示按已存单位映射换算。Field/Size标量阶段及其他堆栈顺序不变；已有其他Size效果显示叠加提示，不关闭它们。参考底图不是效果对象。

## 草稿、提交、引用和请求

- 预览DTO保持正式revision，不修改正式文档/source/Layout、Undo或草稿。只有Python Evaluate，不调用制造/融合/STL。
- 数值确认/滑杆松手才更新候选并限频预览，不宣称拖动逐帧实时。一个进行中的请求排空，只发送最新待处理值。
- Apply须最新候选求值成功、源DTO内容完整匹配、无未提交控件/待应用Layout。只一次commit，正式revision+1、一条Undo、一次正式Evaluate及原正常autosave/stale。
- Cancel只清候选，不把旧快照写回当前作品。正式设计在编辑候选期间被Undo等改变，旧候选禁用Apply，显示重开提示。
- Reset只重置四项快捷输入，仍待Apply。候选失败保留最后有效画面且不允许Apply。
- 不借用用户同类型Linear；重复更新沿用自己Field/Size ID。字段被其他Fabric消费者、Composite、旧metadata或其他Modifier引用（包括disabled）时，仅为当前消费者复制隔离；保留其他对象、旧场及效果顺序，不重复追加Size。高级入口重绑定或移除专用场后，重新接通快捷效果仍更新原有Size ID，不叠加第二层。
- 已应用全部参数、引用与归属沿用现有IndexedDB DTO保存，刷新可编辑；刷新Undo历史仍重新开始。
- **未应用快捷表单不持久化**：明确提示刷新/切换上下文丢弃，正式作品不受影响；没有改草稿存储系统或伪称恢复。已有pending Layout必须先Apply/Cancel，不自动清除。

## 实际本地验收

固定输入：3×3 Grid、画布60×40mm、source unit=svg、mm_per_unit=0.5、canvas原点(20,40)source units即(10,20)mm。元素中心X=20/40/60mm、Y=30/40/50mm；原始单元宽4mm。初次实际元素bounds X18–62、Y28–52mm；布局范围、元素bounds和最终STL尺寸不机械等同。

- 水平0°：向右变大；反向180°：向左变大；对角45°：沿右下方向变大。相同视角截图`horizontal.png` / `reverse.png` / `diagonal.png`，比例0.6–1.2，强度1。
- 三个案例各9元素，所有ID/中心与原Grid逐项一致；宽度数值与Python返回线性映射趋势对照。参考底图已上传并隐藏以便观察黑色图元，Blob/显示配置仍保存，非效果/制造元素。
- Circle Grid与已有自由混合Circle/Ellipse/Rect fixture通过；混合样本仅作测试输入，不新增生成阵列外混合追加产品能力。每个元素XY不动，宽/高同比例变化。
- 预览/Cancel正式revision和Undo不变；一次Apply一个正式请求、revision+1；Undo恢复无效果、Redo完整恢复；刷新恢复全部DTO和底图Blob；重开修改同一效果，仍一个Size。
- 未应用Layout行数4被完整保留，快捷入口明确要求先Apply/Cancel。
- 对真实Evaluate响应在客户端延迟，10°请求执行期间输入60°再90°：只有延迟旧请求+90°最新请求，共2次；旧画面不覆盖最新。
- 注入422用于错误恢复验证（不是Engine真实失败）：保留最后有效画面，禁用Apply；Reset后正常恢复。
- Pattern Points跟随Final XY；实际cell_width=base_cell_width×final_2D_width/source_2D_width一次，不重复二维Scale。已有Fabric方向高度仍变化，二维修改前后高度配置及绑定相同。
- 真实WebGL Fabric画面见`fabric-parity.png`。没有拿接口/摘要替代3D画面验证。

## 实际下载与严格读回

| 文件 | XYZ mm | 组件 | 字节 | 结果 |
| --- | --- | --- | --- | --- |
| `linear-standard.stl` | 43.95294×24.30588×2 | 9 | 25484 | 真实标准制造下载，Bounds与最终2D轮廓对照，水密/正体积/绕序一致/退化0 |
| `linear-fabric.stl` | 43.96235×24.24471×5.78801 | 9 | 2784 | 无基底Fabric，底Z0、保留单元、Bounds与最终报告对照，同样严格通过 |

复用原STLExporter reload + MeshValidator，没有重新生成替代文件、删面、Repair或降低epsilon。普通与无基底多组件均按原规则验收，不宣称已融合单体。导出仅用原本授权的本地测试环境。

## 测试与真实失败记录

- 受影响Web17文件 **66/66 PASS，exit0**：App线性/原生/1A/草稿/Layout/Field/Modifier/参数交互，editor/真实尺寸/Fabric高度与配方/无基底/请求协调/预览。
- 最后补充高级重绑定/移除的Size ID保护后，4文件定向 **19/19 PASS，exit0**，并重新生产构建与浏览器下载/读回；没有把前一轮66项冒称为最后全部代码再次全量运行。
- `npm.cmd run build`：TS/Vite production PASS，既有大bundle warning保留。
- Python：`python -B -m pytest tests/test_web_fields_p1c.py tests/test_web_modifiers_p1d.py tests/test_fabric_cells_only_1a.py tests/test_phase1a_dimensions.py -q`：**16 PASS +10子测试，exit0**。没有无关Tk全量。
- 真实浏览器：设置已有PLAYWRIGHT_MODULE后`node tools/linear_size_smoke.cjs`，独立生产页面操作/HTTP请求/两个真实下载通过。
- `python -B -m tools.linear_size_readback`：两个实际下载严格读回通过。
- 初次抽取引用扫描漏掉没有ID的旧消费者，原高度测试真实失败1项；已仅修扫描排除条件，原断言保留并复测通过。
- 首次browser脚本方向定位器漏角度单位；另一次过早读到旧9实例计划；另一次把二进制下载响应按JSON读取。分别修正定位器、按revision等待及只对JSON路由采集，没有改产品算法/校验来通过脚本。
- 初次Python命令使用不存在的历史测试名，exit4/未执行；更正为仓库实际文件后16项通过，不将未执行记作PASS。
- `glance`工具未安装，按skill说明记录限制；真实截图已用现有图像查看工具检查，不伪造CLI运行。

## 限制与停止

仅本地验收，公网/Render/切片/实物NOT TESTED。未应用表单刷新不恢复；已应用正常恢复。原1000实例校准性能、5000退化、bundle/Tk风险不在本次修复范围，不宣称已关闭。不新增主编辑器SVG导出，不以/patterns代替验收。

完成后STOP，等待用户确认。径向暂停；没有提交、推送、部署、稳定备份或1B。
