# 两步工作流与原生二维入口（2026-10-06，本地验收）

## 现场与边界

分支 `feature/pattern-library-reuse`，HEAD `b5338a9af41d25ccd191d34366115578265920bb` 未改变。开始时54个已修改/未跟踪文件、暂存区空；逐文件复制保护于 `work/two-step-native-design-20261006/pre-change/`。这不是稳定提交。

原1A、cells-only、实时制造检查器全部保留。本轮没有修改Python生产代码、依赖、部署配置、并发限制、Validator、生产开关，也没有恢复旧Dot补丁或进入1B。仅使用已有8792本地测试环境及独立Edge会话，不操作用户8791草稿/服务。公网、Render、切片、实物均NOT TESTED。

## 实际参考站核验（不是源码复用）

参考URL：<https://zengxb723-a11y.github.io/parametric-form-studio/>。真实Edge访问HTTP200，点击工作台选项并上传参考JPG；证据 `reference-probe.json`、`reference-workbench.png`、`reference-underlay.png`。

| 实际入口 | 点击后实际右栏 | 小芒连接/限制 |
| --- | --- | --- |
| 规则阵列 | 密度、尺寸、横纵间距、宽扁比例、随机尺寸/错位、基础旋转；错列、反转、网格 | 复用Grid参数与Python prepare/evaluate；没有照搬全部选项 |
| 线性渐变 | 渐变方向 | 已有Linear Field + Size/Rotation；保留高级参数场/效果入口，未另建二维快捷配方 |
| 径向渐变 | 中心水平/垂直位置 | 已有Ring等场可手动编辑；不将其语义强行等同于参考站 |
| 有机扰动 | 扰动尺度 | 已有Noise及Modifier；参考站尺度算法未验证，不复制 |
| 中心秩序 | 中心位置、秩序过渡 | 尚无已验证的一键等价配方，需要另确认 |
| 流场波纹 | 波纹频率、流动方向 | 已有Wave/Spiral等，不宣称等价参考算法 |
| 圆点、方形、菱形、胶囊、三角、六边形、自定义 | 共用网格与尺寸参数；前六项可点击、摘要随类型变化 | 本轮仅接通Foundation已有Circle/Ellipse/Rect；其余不新增算法/原型 |
| 添加底图 | 上传后更换/移除、透明度，明确“等比居中、不参与导出” | 复用本地Blob/草稿、世界坐标、Generic ParameterPanel，增加用户要求的锁定/可见/位置/等比缩放/旋转 |

六个逻辑切换和六个基础图形入口的选择及右栏实际操作已核验；探针检查的SVG DOM没有变化（预览并非这些SVG节点），因此**不能把该检查算作参考站算法或真实几何验证**。参考站影响区、自定义形状、灰度映射、导出、保存/恢复仅观察入口，未完成流程验收。没有取得可复制源码/许可证依据；没有复制压缩发布代码、iframe或将/patterns当原生入口。

## 生产文件与复用

| 文件 | 修改 |
| --- | --- |
| `web/src/App.tsx` | 底部两工作区、停止仅供推荐UI使用的自动analyze请求；手动布局、图形/底图/效果上下文；显示草稿预览、源元素临时变换；接回现有commit/history/draft/制造状态 |
| `web/src/state/browserState.ts` | 只有design/manufacture；旧`?mode=preview`及`#preview`映射②；内部3D动作也返回② |
| `web/src/document/InspectorControls.tsx`、`InspectorSection.tsx` | 原Generic Renderer按上下文显示。隐藏而非重复挂载表单，保留输入/折叠状态 |
| `web/src/document/nativeDesign.ts`（新增） | 标准DTO中追加一个已有circle/ellipse/rect、世界毫米换算、唯一ID、完整标准字段/Transform；不是阵列生成器 |
| `web/src/document/useLayoutPreview.ts`（新增） | 复用Python Evaluate；prepare已给出的preview可复用；180ms合并、single-flight、旧响应丢弃；不提交当前文档 |
| `web/src/document/referenceLayer.ts`、`ReferenceLayerPanel.tsx`（新增） | 仅浏览器显示层，PNG/JPG≤8MiB；Schema驱动参数、等比缩放、解码校验、对象URL释放；不作为Image/Distance输入 |
| `web/src/geometry/Workspace2D.tsx` | 原world group下面绘制底图；同Zoom/Pan、锁定pointer-events=none；解除锁定可选择属性，位置/缩放由参数编辑 |
| `web/src/draft/localDraft.ts` | 同一IndexedDB记录可选reference_layer Blob/显示配置；返回示例前作品也保存/恢复该配置。DTO与项目格式不变 |

新增测试：`App.nativeDesign.test.tsx`、`nativeDesign.test.ts`、`referenceLayer.test.ts`、`useLayoutPreview.test.tsx`。
调整受影响旧测试：App shell、P3、WM65、WM6、P1-C/D/E、Examples、P2-D、F1、WM5.5，以及已有制造错误文本断言（保留failure_id/HTTP状态）。原制造/导出/Undo检查未删除；推荐测试改成手动选择且零analyze请求。`tools/phase1a_live_manufacture_smoke.cjs`的③切换改为①↔②；算法/压力测试内容不变。

## 制造一致性诊断

新增原生图形的第一次真实标准制造返回409 `stale_revision`，正文“制造结果与指定文档内容不一致”。尺寸、位置、revision并非退化几何问题：创建记录没有包含Foundation规范化补入的Reference.preprocessing/metadata、Element.group_id/metadata、Rect.rx/ry与Transform记录。

只补齐原生创建DTO的标准默认值和变换记录；没有修改后端制造一致性检查或序列化算法。再次真实点击制造200、下载与读回通过，Circle/Ellipse/Rect均在同一普通制造路径工作。

## 本轮实际验收

使用本地production build、Edge真实WebGL及现有FastAPI：

- 两个底部按钮；不存在③/推荐按钮；32个POST记录中analyze请求0。
- Circle/Ellipse/Rect逐个追加、改位置、Undo/Redo；首次追加也可Undo回空文档。没有替换原作品。
- 右栏随元素、手动布局、底图、效果上下文切换；无选中时简短引导。
- 手动Grid prepare → 修改 → Python未应用预览 → Cancel恢复原3元素 → Apply一次提交；无推荐阈值依赖。Radial/Curve/Free的准备/应用/错误保护由Web及现有Python定向回归覆盖。
- 底图透明度/位置/显示/锁定：显示调整0 API、0 revision变化；锁定实际点击不选底图，解锁点击可选底图；Zoom/Pan共用SVG世界变换。Blob与显示配置刷新恢复；原图元素数量仍3。
- 已生成普通STL后修改底图透明度，没有让制造结果过期、没有计算请求，原下载仍可用。制造Bounds没有加入底图范围。
- 旧preview链接 + 草稿恢复进入②，不空白；当前草稿本来不保存导航模式，无需虚构持久mode迁移。
- SVG原管线保留9圆+白色背景10元素；PNG得到144个最终元素。不修改SVG提取语义。
- 现有基础圆点示例制造9组件；Fabric Pattern Points产生9实例，cells-only没有底板、底部Z=0；切换带基底后旧下载失效，重新生成后1组件。
- 100实例1A真实回归：大小/固定高度拖动期间0 Evaluate/Preview/Final；释放各1 Evaluate+1 Preview、0最终制造；自动复杂参数、旧请求保护、相机/显示风格、右侧独立滚动、现有下载流程通过。CPU最大重叠1；初次预览392ms，大小/高度释放到ready456/448ms（单机一次测量，不是FPS承诺）。400/1000本轮未重测，历史慢项不算已修复。

### 下载文件读回（不是重建替代文件）

| 实际浏览器文件 | XYZ mm | 组件 | 字节 | 严格读回 |
| --- | --- | --- | --- | --- |
| native-primitives.stl | 70×10×2 | 3 | 9884 | 水密、正体积、绕序一致、退化0 |
| standard.stl | 40×40×2 | 9 | 34284 | 同上 |
| fabric-cells.stl | 36×36×3 | 9 | 2784 | 同上、没有整张基底 |
| fabric-with-base.stl | 40×40×3.5999999 | 1 | 5184 | 同上、bounds与最终报告一致 |

普通多组件未套Fabric单体要求；仅单元模式保留9独立有效实体，不宣称融合一体。测试导出使用本来已授权的本地开关，不扩大生产权限。

## 命令与记录

- `cd web; npm.cmd test -- --maxWorkers=2 --reporter=json --outputFile=../work/two-step-native-design-20261006/web-tests.json`：227/227，53文件，退出0。新增规范字段后最终4文件定向复测12/12，退出0。
- `cd web; npm.cmd run build`：TS + Vite production build PASS，已有大bundle warning保留。
- `.\xiaomang_pattern_lab\.venv\Scripts\python.exe -B -m pytest tests/test_web_svg_grid_p0.py tests/test_phase1a_dimensions.py tests/test_fabric_cells_only_1a.py -q`：12 PASS + 2子测试，既有TestClient弃用提示，不运行Tk全量。
- 设置已有 `PLAYWRIGHT_MODULE` 后 `node tools/two_step_native_smoke.cjs`：真实浏览器PASS，0致命浏览器错误。
- `.\xiaomang_pattern_lab\.venv\Scripts\python.exe -B -m tools.two_step_native_readback`：四个实际下载严格读回PASS。
- `PHASE1A_COUNTS=100 node tools/phase1a_live_manufacture_smoke.cjs`：既有1A回归PASS；录屏及完整请求记录在 `work/phase1a-manufacture-layout-20261006/`。

首次旧Web断言仍期待推荐、③和同时展示所有属性而失败，已按新交互调整且保留原行为覆盖；制造错误旧断言未包含既有1A的HTTP422说明，同步精确断言，未回改错误解析。浏览器脚本首次定位器/异步等待假设失败已修正；没有将这些运行写成PASS。新原生DTO真实409已如上定位，不规避。`web-tests.log/json`、`browser-evidence.json`、`stl-readback.json`及各截图保存于本轮work目录。

## 明确未接通 / 待确认

- 已有参数化布局追加独立图形会被Engine重新生成覆盖，因此不自动追加/烘焙：用户须明确应用Free后才能添加。共享场/效果/形状分配项目保留已有直接编辑安全边界；仅烘焙布局并不保证清除其他效果，界面明确拒绝。支持在派生阵列外长期混合独立元素需要另外批准，不在本轮改Engine。
- 参考站更多基础类型、影响区、中心秩序/流场快捷配方、底图自由拖拽/裁切、SVG参考图片未接入。当前底图支持PNG/JPG，参数位置/等比缩放/旋转可编辑。
- Layout是参数提交后自动计算的“未应用预览”；场/效果继续松手提交后Python刷新，非浏览器逐帧重写算法。可靠自由源元素的临时变换可以拖动显示。
- 旧草稿Undo历史不持久化；底图显示配置不写几何Undo历史，仅随草稿/作品切换恢复。没有实现第二套显示历史系统。
- 1000实例历史校准较慢、本来较大bundle、Tk生命周期风险不在本轮修复。Grid带基底本轮Python回归PASS，浏览器Grid新下载NOT TESTED。

完成后STOP，无提交、推送、部署或1B。
