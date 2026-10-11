# 参数场驱动二维尺寸变化：本地验收（2026-10-10）

## 版本与边界

- 实际工作区：ParametricPatternGenerator；分支 feature/pattern-library-reuse；开始及结束 HEAD 均为 `4a1c799255ca71002dc4cd9bae88e38ef0fea69e`。
- 开始暂存区与 tracked 差异为空，22个旧手工验收/探查脚本保留。源码快照在 `work/field-size-20261010/` 的 App.tsx、linearSize.ts、Workspace2D.tsx、gradientControls.ts。
- 本轮全部新成果未提交；未推送、部署、改变生产权限、恢复旧补丁或新增依赖。没有修改 Python 产品算法、制造、Validator、STLExporter 或正式 schema_version。
- 独立 Uvicorn 本地8798（本轮进程32356），当前工作区 `web/dist`，独立 Edge/IndexedDB会话，不覆盖用户8797草稿。测试导出沿用本地 staging 已授权开关；不是公网验收。
- 最后实际浏览器加载 `index-Bw680_BK.js`；本地提交号不等于未提交源码身份。证据目录 `work/field-size-20261010/`。

## 连接与保存

- 左侧原线性入口扩展为“尺寸变化”；右侧依次为驱动来源/变化方式、真实Schema场参数、尺寸映射、全图/局部作用范围。高级Field/Modifier及旧径向快捷入口保留。
- `web/src/document/linearSize.ts`：延用同一draft/candidate、`web_linear_size_effect` v1归属及Size ID；增加按类型专用ID映射、已有场来源和显式Linear投影域记录。Linear→Wave→Stripe→Linear更新同一Size层，保留其他层顺序、原图、Layout、位置/旋转、Fabric及用户场。
- `sizeFieldTypes/sizeFieldGroup/sizeFieldValues` 读取Python目录；`selectSizeField/changeSizeFieldParameter` 使用真实默认值和校验，不按字段名跨类型复制。二维世界长度按现有mm_per_unit显示/回写；Distance.max_distance_mm已是物理毫米，不再次换算。
- `linearSizeCandidate` 使用现有 addField/addModifier/bindScalarModifierField/fieldReferencedOutside；原样绑定已有场，参数修改后只改本效果私有副本。disabled消费者、Fabric/Composite引用仍触发隔离，不删除共享场。已有Linear显式start/end复制并刷新后不重新拟合。
- 所有候选从正式输入构造，正式revision不变、无Undo/存储提交；apply一次revision+1、一次evaluate和一条Undo，Cancel不写回过期快照，Reset只改当前draft。已应用Wave完整引用/局部范围刷新恢复；旧线性及径向回归通过。
- 退出快捷上下文或切换作品前明确确认未应用内容的丢弃，切换布局取消确认不会准备新布局；作品切换继续先flush正式草稿。切换制造工作区保留待应用配置并禁制造/下载，说明中央3D只是已应用设计。
- `useDocumentPreview`、共享计算协调器未重写；保留单在途/最新槽/过期结果丢弃与真实错误。数值确认或滑杆松手后求值，不能宣称逐帧实时。快速4次类型切换实际2次evaluate、0正式commit、0manufacturing。

## 实际目录、采样与支持状态

同一100元素规则点阵，圆/椭圆/矩形混合；源canvas120×80、origin20/40、mm_per_unit=.5，实际世界范围60×40；位置、旋转固定。尺寸映射.6–1.2、strength1。每项截图、候选DTO、Python响应均留存；读回工具再次使用原Python采样/Size核对全部100元素。

| 类型 | 实际采样范围 | 实际宽度mm | 本轮支持证据 |
| --- | --- | --- | --- |
| Linear | .02212–.97788 | 1.22655–2.37345 | 候选/旧配置/全图与局部 |
| Wave（波长17mm） | .00213–.99787 | 1.20256–2.39744 | 连续变化、Apply/Undo/Redo/Reset/Cancel/恢复、真实STL |
| Stripe（周期13mm） | 0–1 | 1.2–2.4 | 两组尺寸、共用Schema/切换 |
| Checker（格7×9mm） | 0–1 | 1.2–2.4 | 分组尺寸、共用Schema |
| Noise（尺度11mm/seed19） | .22832–.91898 | 1.47399–2.30278 | 100不同采样，切换回来同配置逐项一致 |
| Constant | .5 | 1.8 | 正常固定尺寸，不伪称存在变化 |
| Ring | 0–.43212 | 1.2–1.71855 | 现有环带采样，不等于旧径向快捷 |
| Spiral | .00009–.99580 | 1.20011–2.39495 | 现有螺旋标量，真实Schema参数；上下文取实际源元素范围 |
| Image | 0–1（7种采样） | 1.2–2.4 | 显式PNG上传及权威图片采样 |
| Distance | 0–.72975（12种采样） | 1.2–2.07570 | 显式PNG及原距离采样，auto normalize |

Image/Distance缺源时明确提示、Apply disabled、0evaluate；不借参考底图。有效源使用已存在imageAssets传输/IndexedDB Blob边界。Composite无快捷参数Schema，本入口不创建/编辑其图；保留原高级图及引用保护。不得将这一限制当作算法失败。

## 局部范围与控制柄

- 原 `SizeModifier.region / LinearSizeRegion` 已对任意标量驱动生效；本轮仅复用通用接线，没有Python算法改动。范围判断使用本层输入中心，outside直接跳过本层，feather只混合本层factor与1，不修改共享场。
- Wave局部实际中心40/40mm、长28mm/宽20mm、区域角25°、过渡1mm；波浪场角0°。100个中77个范围外元素与关闭本层时完全相同；全部中心/旋转不变。
- Workspace2D新增display-only region类别，复用原矩形中心/端点/宽度交互；非Linear全图不画假方向轴。原线性方向轴与径向控制柄继续存在，不成为元素或制造几何。
- 本批截图与真实数值编辑、快切记录通过；没有另录每种场的专属拖动视频，不声明新专属画布工具。旧控制柄行为由原定向测试回归。

## 实际下载与读回

均为网页按钮下载、文件存在、原STLExporter读回及严格MeshValidator；无repair、删坏面、替换文件。每份100有效独立组件，封闭、正体积、绕序一致、0退化面、Z起点0。仅图案不要求单组件，不宣称融合整体。

| 文件 | 字节/三角面 | 实际XYZ mm | 核对 |
| --- | --- | --- | --- |
| wave-global.stl | 156084 / 3120 | 55.709893×38.125090×2 | 每元素XY/局部轴宽深/均匀厚度与正式2D结果一致 |
| wave-local.stl | 165684 / 3312 | 56.455142×38.224932×2 | 同上，77个范围外元素保持原状态 |
| fabric-parity.stl | 165684 / 3312 | 56.455142×38.224932×5.879385 | 原图轮廓+已有Wave Height，每个计划变换的全部顶点均与下载文件一致 |

- 原图计划宽深是已旋转轮廓的世界轴包围框，不直接与2D未旋转宽深强行相等；读回在元素自身轴及实际顶点核对。固定Unit Cell的Pattern Points尺寸只继承一次、Height不被Size覆盖另有Python定向数值测试。
- 最终独立浏览器完整流程52个POST均200、0pageerror。实际下载三份；`browser-evidence.json`、`readback.json`给出源参数、采样、逐元素与严格几何数据。
- 参考底图隔离引用现有referenceLayer三项回归（Blob/UI state不加入elements/assets、世界坐标映射、保存失败保护）；新浏览器点阵未放底图，不冒称补过底图叠加视觉截图。

## 测试批次（不叠加计数）

- 相关Web13文件66/66 PASS：App.fieldSize/App.linearSize/App.phase1a/App.nativeDesign/App.draft、document.fieldSize/linearSize/linearRegion/radialSize/useLayoutPreview、geometry.gradientControls、api.imageAssets、manufacturing.computeRequests。
- 最后面板分组改动后：App.fieldSize/App.linearSize/document.fieldSize/document.radialSize 22/22 PASS；后续仅TypeScript判别联合缩窄，最终`npm run build` PASS（index-Bw680_BK.js）。另referenceLayer 3/3 PASS。上述批次不相加称全量。
- Python：`.venv/Scripts/python -m pytest tests/test_field_size_shortcut.py tests/test_unit_shapes_and_linear_region.py -q -k "size or region or pattern"` 68/68 PASS，含新21项；不与21相加。
- 浏览器：`PLAYWRIGHT_MODULE=<现有bundled playwright> node tools/field_size_smoke.cjs` 最终PASS，52 POST/三真实下载；`python -m tools.field_size_readback` 最终PASS，11采样案例及3文件。重复运行使用独立context，未清用户草稿。
- 中途真实失败如实保留：初次tsc缺import及最后联合类型缩窄错误已最小修正；脚本曾选中隐藏Apply按钮、漏规范fixture group_id/rx/ry（409被一致性guard正确拒绝）、未先指定图片目标、遗漏角度单位与CDP观察延迟。未因此修改Validator/契约guard或场算法。原图包围框误当局部尺寸的读回断言按实际旋转语义改为顶点与自身轴核对，并非放宽几何条件。

## 文件与剩余边界

- 实现：web/src/App.tsx、document/linearSize.ts、geometry/Workspace2D.tsx、geometry/gradientControls.ts。
- 测试：App.linearSize.test.tsx、App.phase1a.test.tsx入口更新；新增App.fieldSize.test.tsx、document/fieldSize.test.ts、test/sizeFieldCatalog.json（实际Python目录fixture）、tests/test_field_size_shortcut.py。
- 可复现验收：tools/field_size_smoke.cjs、tools/field_size_readback.py；本记录与GATE_STATUS.md。没有改依赖、锁文件、部署配置、Python产品源码或旧22脚本。
- 未应用快捷表单及其新选图片不承诺刷新恢复；明确确认退出，已应用配置沿原草稿机制保存。刷新Undo历史仍重新开始。Composite快捷图编辑、各类型新画布工具未做；旧径向不迁移，既有混合追加/旧隐式堆栈限制不改变。
- 图片/距离字段本轮验证有效资产与候选；未逐类型单独做全部STL/刷新矩阵，不一概写全量PASS。实际正式输出验收为Wave全图、Wave局部、叠加Fabric高度三个代表性文件。
- 既有bundle>500kB与Starlette弃用warning保留；本轮无Tk全量、公网/Linux/切片/实物验收。旧8792原故障页鼠标确认OPEN不借本轮独立页面关闭。
- 当前Git中未提交文件没有新稳定备份或发布身份；停止等待用户确认。
