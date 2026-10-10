# 单元造型、线性局部范围及输出分类 — 本地验收（2026-10-09）

## 边界与版本

分支 `feature/pattern-library-reuse`，基线/当前 HEAD `dd16f64aab07e894cdc09218c56a416579b45203`。
本轮成果尚未提交；未 push、部署、改依赖或生产开关。稳定引用
`backup/web-native-design-local-validated` 不移动。开始暂存区为空，13个旧未跟踪脚本原地保留。
保护源码 ZIP：`work/unit-range-ui-20261009/baseline-source.zip`，不包含运行资产或未跟踪文件。
独立本地生产构建服务 `http://127.0.0.1:8793/`，仅此测试进程使用已有 staging/test-export 环境开关。
其他开发服务不停止。最后一次 Python 精确兼容调整后，仅重启本轮核实创建的8793进程。

## 实现文件

| 文件 | 最小变更 |
| --- | --- |
| `web/src/manufacturing/ManufacturingPanel.tsx` | 分开生成方式、单元输出、条件显示基底类型；无单元时提示/禁用预览、预检、融合；中文造型缩略图入口 |
| `web/src/document/fabricCell.ts` | 六个稳定ID及缩略图目录；沿用不可变尺寸/类型编辑和Schema校验 |
| `web/src/document/InspectorControls.tsx`、`App.tsx` | 明确多选只读状态；局部范围下的单一待应用配置及上下文接线 |
| `web/src/styles.css` | 共用检查器标签14px，数字输入14px/38px高/112px宽；换行不溢出，保留焦点及实际精度；轻量缩略图 |
| `web/src/document/linearSize.ts` | 全图兼容默认；局部中心/长宽/过渡；世界单位持久化，已有专用ID/引用隔离复用 |
| `web/src/geometry/gradientControls.ts`、`Workspace2D.tsx` | 局部矩形、两端/中心/侧向控制柄；复用屏幕世界转换/Pointer交互，不成为几何 |
| `xiaomang_pattern_lab/shared_fields.py` | SizeModifier可选LinearSizeRegion；按本层输入中心取范围/Linear值；只在过渡带混合本层缩放差，外部完全跳过本层；全图原计算不多做混合 |
| `xiaomang_pattern_lab/fabric_cells.py` | 六个原型工厂；圆环显式内外壁及环形上下盖，Dome单顶点；沿用缓存/TRS/融合/Validator/Exporter |
| `xiaomang_pattern_lab/parameter_definitions.py` | 六种Cell的正式Schema及圆台顶部/十字臂宽/圆环孔径比例（0.1–0.9） |

新增测试 `tests/test_unit_shapes_and_linear_region.py`、`web/src/document/linearRegion.test.ts`、
`web/src/manufacturing/outputClassification.test.tsx`；复现工具
`tools/unit_range_ui_smoke.cjs`、`unit_range_ui_layout.cjs`、`unit_shapes_benchmark.py`、`unit_range_readback.py`。
无第二套制造、Field算法、UI库或项目格式；MeshValidator阈值保持不变。

## 输出分类与兼容

生成方式：按原图轮廓挤出 / 使用立体单元。立体单元再选择仅单元 / 单元＋基底；只有带基底显示Solid/Grid类型。
仅单元保留的Base配置只提供布点/边距参考，不创建实体，Z=0。不把无单元偷偷改成普通挤出。
旧缺失output_mode的作品保持带基底；旧缺失region的Size层保持全图。Undo、草稿、指纹、旧结果失效仍走原路径。
多选防御状态只读提示已测；本轮不新增多选手势或批量编辑。参数化/派生元素维持不能直接编辑的限制。

## 真实范围与交互证据

固定规则点阵：Canvas60×40mm，原点(10,20)mm，0.5mm/源单位；中心XY为X20/40/60、Y30/40/50mm。
局部中心(40,40)mm、长40mm、宽15mm、0°、比例0.6→1.2；只改变中间一行，另外六个元素宽度与关闭本层时完全一致，所有XY不变。
API额外验证圆/椭圆/矩形、0.5和2mm比例、先前Size及Position层、过渡和保存往返；区域外保留前层结果，不用场值0伪装无影响。
范围长度决定Linear start/end，侧向宽度决定区域判断；候选始终以正式文档为源，不累乘自身。
零长/零宽、非有限坐标、非法过渡拒绝。过渡从矩形边缘向内，最大半长/半宽；仅混合本层缩放差。

真实Edge、同一配置：端点、中心和宽度各30次pointermove约10次HTTP200 evaluate，最多1在途；松手前9–10份响应，未发融合/校验/STL。
中心/端点各10种几何宽度反馈，宽度控制2种（该9点样本以离散中心判断是否进入区域）。
Zoom+Pan后再次拖中心同样10次请求，面板/世界坐标一致；pointer拖动/松手0正式commit，Apply1次commit/Undo。
Reset仍为未应用配置且保留局部模式；Cancel、Undo/Redo、刷新重开保留已应用区域及专用ID。
未应用快捷表单不保存；刷新后Undo历史重新开始，沿用现有说明。

证据目录 `work/unit-range-ui-20261009/`：
`browser-evidence.json`、`local-authority.json`、`local-region.png`、`local-region-dragged.png`、`browser-final.log`。
这是实际请求/指针/权威几何记录，不是录屏，不宣称固定FPS。数值控件仍松手/确认后预览。

## 六种造型与真实文件

六种均完成：共享原型 → 最终TRS → WebGL预览 → 实际浏览器下载 → 原Exporter读回严格Validator。
另有每种Solid/Grid附着、融合及STL定向测试，以及二维Size/Rotation＋Fabric Height/Scale/Density/Orientation的逐顶点矩阵对照。

| 类型 | 9单元预览/制造/实际下载/读回 | STL字节 |
| --- | --- | ---: |
| 圆顶 dome | PASS；单一顶部采样顶点，平底封闭 | 172884 |
| 圆台 frustum | PASS；顶部比例有效 | 43284 |
| 六角柱 hex_prism | PASS | 9084 |
| 楔形脊 wedge | PASS；复用原Fin正确面绕序的棱柱拓扑 | 3684 |
| 十字凸台 cross | PASS；臂宽比例有效 | 19884 |
| 圆环 ring | PASS；读回Euler=0，真实贯穿孔，非透明显示假孔 | 86484 |

无基底上述文件均9封闭正体积实体、绕序一致、零退化、底部Z=0；XYZ约44.400002×24×3mm（实际图案Bounds，不等于Canvas60×40）。
Solid/Grid浏览器文件均1组件、约44.400002×24×3.5999999mm、零退化；普通二维9组件、44.400002×24×2mm。
Grid线宽1mm时真实拒绝1个孔洞悬空单元，预检422且下载禁用；记录 `grid-hole-rejection.json`。
明确把线宽改为2.5mm后才获得通过Grid STL；不删除、移动单元或改Validator。
所有读取结果 `stl-readback.json` / `readback-final.log`。400圆环实际下载3840084字节、118×118×3mm、400组件、封闭正体积/零退化。
截图 `dome.png`、`frustum.png`、`hex_prism.png`、`wedge.png`、`cross.png`、`ring.png`，已直接检查真实模型。

## 性能与元素可读性

100/400实例浏览器进入制造分别约0.42–0.67s / 0.44–0.51s，均1个预览请求；实例创建实测约4.9–7.4ms / 8.2–10.6ms。
原型按完整definition（含shape_ratio）复用，不按每实例运行生成器。

| 仅单元样本 | plan ms | candidate ms | fusion+validation ms | export+readback ms | total ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 圆顶100 | 23.59 | 47.95 | 2456.46 | 3427.52 | 5955.52 |
| 圆台100 | 6.38 | 24.71 | 539.29 | 870.72 | 1441.09 |
| 六角柱100 | 9.18 | 17.90 | 117.51 | 170.97 | 315.56 |
| 楔形100 | 5.77 | 18.46 | 54.19 | 69.31 | 147.74 |
| 十字100 | 9.84 | 22.88 | 238.50 | 425.05 | 696.26 |
| 圆环100 | 25.11 | 29.44 | 1220.37 | 1704.53 | 2979.45 |
| 圆环400 | 20.09 | 108.28 | 6729.49 | 6240.13 | 13098.00 |

完整数据 `performance.json` / `performance.log`。400圆环候选顶点+面数组估计2,764,800字节，不冒称进程峰值内存。
浏览器首次冷制造到下载实测22.810s；缓存复用约0.974–1.056s，不能把暖缓存当冷性能。
造型/输出/大小变化仍使旧下载失效；现有共享busy、429业务码、失败恢复/旧请求序号均通过原定向回归。

元素标签/输入14px、输入高38px。实际桌面1440×1000、1280×800、1024×768无右栏/页面横向溢出，画布和操作保持可用。
819×614 CSS视口模拟1024×768下125%缩放的布局压力测试通过；**原生浏览器工具栏缩放NOT TESTED**，不把CSS zoom或DPR当作真实浏览器缩放证明。
证据 `layout-performance.json`、`layout-browser.log`、`element-*.png`；狭窄视口部分文字换行，未开展整体UI重构。

## 测试批次与失败记录

- Web受影响24文件116/116：命令完整保存 `web-final.log`。最后范围文案/合法滑杆起点/端点标签微调后5文件18/18（与前批重叠，不相加），`web-refinement.log`。
- Python受影响最终99/99 PASS，另28个subtest PASS（不与历史/重叠批次相加）。最终命令/结果 `python-final.log`；覆盖新Shape/Region、径向旧快捷、SharedModifier、F2/F3、仅单元、尺寸、普通Manufacturing和STL。
- `cd web; npm.cmd run build` PASS，`build-final.log`；最终产物 `index-DzqKWy6X.js` / `index-BDzASBM6.css`。
- `$env:PLAYWRIGHT_MODULE='<现有Playwright模块>'; node tools/unit_range_ui_smoke.cjs` PASS；同目录运行 `node tools/unit_range_ui_layout.cjs` PASS。
- `python -m tools.unit_shapes_benchmark`、`python -m tools.unit_range_readback` PASS。
- 未执行无关Tk全量、5000反复压力、Render/公网、切片或实物。

首轮真实失败保留说明：圆环earcut在对称桥接生成近零三角，改为明确索引环面，未删坏面/Repair；六角浮点Bounds改为准确归一化六顶点。
测试早期失败另包括调用section引入未安装Scipy（改用Euler及平面面片证明，不新增依赖）、测试把Rect改type导致不合法序列化（改为正式类构造）、漏传instance_matrix的cell参数；
原全图精确测试错误期待裸mapping输出，已改为严格比较旧mapping.scale本身，非放宽容差。
浏览器选择器缺准确标签已补显式label；输入fill与聚焦切换精度冲突，验收脚本先点击聚焦再输入。
生产不存在测试专用JSON入口，性能会话通过现有IndexedDB草稿恢复加载规范fixture，不新增产品导入能力。

## 尚未关闭

圆顶/圆环高面数下严格融合及STL验证较慢；现有bundle>500KB和Starlette警告保留。
旧5000退化限制不修复。本轮未增加混合追加/多选操作；旧非中性隐式堆栈不迁移。
公网、Linux/Render运行、切片、物理打印及原生工具栏缩放未验收，不能宣称上线/Physical PASS。
可选glance CLI不存在；本轮直接查看实际截图，没有虚构识图/录屏附件。
已停止，不进入其他效果，不创建新稳定提交或Physical引用。
