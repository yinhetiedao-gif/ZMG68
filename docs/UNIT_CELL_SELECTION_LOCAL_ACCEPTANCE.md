# Unit Cell 选择与参数加载（2026-10-09，本地、未提交）

## 现场与证据边界

- 分支 `feature/pattern-library-reuse`，HEAD `dd16f64aab07e894cdc09218c56a416579b45203`；原有未提交文件及未跟踪验收脚本保留，暂存区为空。没有提交、推送、部署、修改开关或重启服务。
- 用户当前 IAB 页为 `http://127.0.0.1:8793/`，另一页8792；核查开始时两页都是空白设计，而不是带错误的Fin现场。原错误**本轮未复现**，历史请求具体缺失字段 UNKNOWN，不能证明历史失败由旧后端造成。
- 原提示来自 `web/src/document/fabricCell.ts / setFabricUnitCellType()`：类型Schema或regular布点Schema任一个缺失均抛出同一句。`App`原先将无效/缺失参数目录默默置null，但仍显示后端已连接，没有独立加载状态。
- 同源 `/api/v1/contract` 实际HTTP200、JSON，`parameter_definitions.schema_version=1.0`、`units=mm`，`definitions.fabric_cell`包括11个稳定ID：cylinder/cone/pyramid/double_tower/fin/dome/frustum/hex_prism/wedge/cross/ring；`fabric_placement.regular`存在。当前Schema本身没有缺失。
- 8793进程PID23972，12:14:18启动，实际命令为本项目runtime Python运行 `xiaomang_pattern_lab.web.app:create_app`；健康报告backend_commit=UNKNOWN、staging、测试导出true。未将HEAD或Contract版本当作运行提交证明。API包含新6种定义，未修改Python源码，本轮无重启依据。
- 浏览器原载入 `index-DzqKWy6X.js`（本轮修改前当前生产构建），修改后构建 `index-CAA61geS.js`。通过已有草稿保存/恢复刷新原8793页加载新文件，未清草稿。后端同一个PID，同源API。系统代理的PowerShell请求502不代表服务失败；直连curl和浏览器/服务日志均200。

## 最小修正

- `App.tsx`：参数目录单独loading/ready/error，重试仍用已有health/contract握手；旧握手响应保留Abort/current保护。缺目录/版本单位错误不再被解释为“后端没单元”。处理函数也检查加载状态，失败明确指出请求类型及仍保留的旧类型。
- `ManufacturingPanel.tsx`：加载提示、具体失败及重试；缺某类型只禁该选项/卡片；卡片和下拉同一入口与document选中状态。同步拒绝选择时将原生select恢复为真实文档类型，避免标签与模型脱节。
- `fabricCell.ts`：区分目录、类型和布点Schema错误；保留已有布点时不要求重新取得其默认值；保留合法宽深高、size_mode、输出/基底/场及其他配置，新增类型特有值仍取PythonSchema。保留值不合法则拒绝，不静默clamp或伪造参数。
- 没有更改Registry、原型、预览求值、制造算法、Validator或生产依赖。沿用自动预览latest-only、revision/content与制造stale机制。

## 当前页验收

- 在原8793空白页使用基础圆点示例：9元素、Pattern Points、仅单元、4×4×3mm、均匀高度。全部11种实际选择后，document来源下拉值、卡片pressed、预览摘要类型一致、9实例预览就绪；未出现原Schema提示。
- 下拉与卡片均实际使用；IAB截图视口仅461×560，右栏在可视范围外，部分鼠标click没有触发，使用按钮Enter键真实激活卡片/制造/下载。**不能据此称11张卡片全部鼠标点击视觉验收通过**；自动化DOM测试覆盖11种各自的mouse change/click共同入口。窄视口全面布局不在本任务范围。
- 冷刷新→恢复Fin草稿→切换正常。真实“重新加载单元参数”先显示loading并禁类型，成功后恢复，当前Ring未改变。真实网络失败后重试本轮未故意破坏运行服务；由组件定向测试覆盖，不冒称浏览器失败注入PASS。
- Fin→Dome后最终结果stale、下载禁用；一次Undo回Fin、Redo回Dome，尺寸仍4×4×3。快速Dome→Ring最终Ring；服务日志两次evaluate、一次preview，未自动fusion/STL。旧请求晚到/同帧去重/失败busy恢复由原hook/协调器定向回归覆盖。
- 当前页Fin：显式生成最终模型200、STL200，实际浏览器文件 `xiaomang-fabric.stl`（3684B），保留副本 `work/unit-cell-selection-20261009/fin.stl`。
- 当前页Ring：显式最终模型200、STL200，实际浏览器文件 `xiaomang-fabric (1).stl`（86484B），保留副本 `work/unit-cell-selection-20261009/ring.stl`。
- 原Exporter读回+原Validator：Fin72面、Ring1728面，均9组件、watertight、正体积、绕序一致、0退化；bounds [12,12,0]–[48,48,3]mm，尺寸36×36×3mm。Ring Euler=0保留真实孔。不是重新制造代替浏览器下载。

## 本轮命令与结果

- `cd web; npm.cmd test -- src/manufacturing/unitCellSelection.test.tsx src/document/fabricCell.test.ts src/manufacturing/outputClassification.test.tsx src/App.test.tsx --maxWorkers=2`：20/20，4文件。
- `cd web; npm.cmd test -- src/App.phase1a.test.tsx src/manufacturing/unitCellSelection.test.tsx src/manufacturing/useFabricPreview.test.tsx src/manufacturing/computeRequests.test.ts src/manufacturing/FabricFusionPanel.test.tsx src/manufacturing/FabricPreflightPanel.test.tsx src/document/fabricCell.test.ts src/manufacturing/outputClassification.test.tsx --maxWorkers=2`：40/40，8文件。与前组重叠，不相加。
- `cd web; npm.cmd run build`：PASS，已有>500kB bundle warning保留。
- `python -B -m pytest tests/test_parameter_definitions_p1a.py tests/test_fabric_cells_f2.py tests/test_unit_shapes_and_linear_region.py -q`：58 PASS及15子测试，已有Starlette warning。第一次误写不存在的 `tests/test_parameter_definitions.py`，退出1且0用例；核对实际文件后使用正确命令，非产品失败。
- `python -B -m tools.unit_cell_selection_readback`：上述两个真实文件严格读回PASS。
- `git diff --check`：PASS。未运行无关Tk全量、5000压力；公网、切片、实物NOT TESTED。

## 剩余限制

历史截图错误的具体请求无法还原，本轮正常页面并不等于已证明历史根因。已修可确认的加载/选择连接缺口，当前8793链路已可操作。原有未提交新单元/局部范围工作仍未冻结；旧warning、历史5000退化、Tk/1000慢项未在本轮关闭。
