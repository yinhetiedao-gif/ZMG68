# P1 首批三套图案预设：本地限定验收

日期：2026-10-11。基线 `3b41af3c93bfd24e54730d07a2d038dc8a49f683`，分支 `feature/pattern-library-reuse`。本批产品、测试与本文均未提交；没有 push、部署、生产配置修改、依赖升级或新场算法。原有 30 个未跟踪探查脚本保留。

## 返回入口补充核验与最小修复（2026-10-11）

用户已确认首批三套本地试用，本节只补本地收口审核发现的返回问题；不将其等同于提交、冻结或上线。

- **修前真实复现**：同一隔离Edge会话、8803、`index-RWHjP4JC.js`，导入既有新建带孔回归样本→创建光谱渐隐→高级驱动改Stripe→Apply。原作品ID `c0133b8332c24f3a8928bd6d4a84c415` 的before-example-draft仍存在，当前自定义ID `f3bf914c-8730-4a01-ae30-c0b7c7fd1333` 的会话仍active，但返回按钮1→0。原因是App原显示条件同时要求example/preset身份；高级自定义正确移除了preset身份，错误连带隐藏有效返回上下文。未用纯代码推断代替浏览器复现。
- 同一会话Undo恢复身份后返回，原作品恢复，但等待自动保存后两个草稿槽都指向原作品，退出的预设不再留存。此为本次实际确认的第二个保护缺口，不伪称旧流程已满足“不得覆盖当前预设成果”。修前JSON和截图在 `work/preset-return-20261011/before-reproduction.json`、`before-return-missing.png`。
- **最小修复**：App依据现有active session、已校验返回草稿与不同文档ID显示返回入口，不依赖recipe身份；无上下文、相同ID或会话结束时不显示。处理入口沿用recipeSavingRef锁、当前文档快照检查及保存失败不切换。捕获原作时补保留已有design_display。
- `localDraft.saveExampleReturn`使用现有两个key、同一IndexedDB事务：原作品→last-working-draft，退出前的完整已应用预设/自定义作品→before-example-draft，两份session标记false。验证继续复用原DTO/资产/底图/pending规则；第二次put失败或事务失败时整体回滚，两份都不丢。没有新key、项目格式、导航系统、项目列表或历史栈。
- **真实浏览器修后**：同一8803服务、不重启后端/改权限，当前产物`index-BODxwr7-.js`；三个全新隔离context分别验证精密错列、光谱渐隐、斜向潮汐。原作公共尺寸提交revision1时，磁盘仍revision0；创建前保护实际保存最新revision1。普通关键参数编辑/Cancel/一次Apply/Undo/Redo→高级自定义Stripe→刷新恢复→返回原作品→等待autosave→再次刷新，完整正式DTO、真实5元素几何、孔洞、毫米映射及源Blob信息保持，退出作品仍保存于另一槽，旧Undo刷新后为空，无无效返回入口。精密错列高级公共参数不是Field面板，转自定义时显式选择既有“尺寸变化”入口，不虚构其内置场能力。
- Wave案例另注入第二次IndexedDB put抛QuotaExceededError：页面保留当前自定义、原作槽不变，锁释放、返回按钮可重试；解除注入后返回成功。其他两套不重复故障注入，不能将其标为三个独立quota测试。总54POST（3assets、3import、48evaluate）全200、pageerror0，0最终制造/融合/STL请求。证据 `browser-return-evidence.json`、`browser-return-final.log` 及每套 `*-custom-return.png`、`*-original-restored.png`。
- **定向自动化**：5文件39/39 PASS、exit0（`App.patternPresets`8、`App.examples`12、`App.draft`2、`draft/localDraft`7、`document/patternPresets`10），命令：从web执行 `node node_modules/vitest/vitest.mjs run src/App.patternPresets.test.tsx src/App.examples.test.tsx src/App.draft.test.tsx src/draft/localDraft.test.ts src/document/patternPresets.test.ts --maxWorkers=1`。覆盖pending Layout不偷应用、原作cm/grid/PNG设置、三套custom/Undo/Redo/刷新返回、无/同ID上下文、保存失败及原子回滚。与下方历史60/17/29不累加。tsc、vite build exit0，bundle warning保留；没有Python/Tk全量或重复STL制造。
- 初次测试因confirm未模拟、查询未展示的布局控件、测试TS类型错误失败；修正验收接线而非产品规则。第二批精密错列完整往返超过默认5秒一次；未扩大超时，按maxWorkers=1顺序定向运行39/39通过。浏览器首次严格对象比较仅因IndexedDB保留可选undefined、HTTP JSON省略同字段失败；按正式DTO序列化规则比较全部可序列化字段后通过。初始失败日志保留，不冒称首次PASS。glance仍未安装，用DOM/真实操作/截图检查，不伪报该工具视觉结果。
- **提交候选变更**：上一轮17项完整保留，本次额外需要 `web/src/draft/localDraft.ts` 与 `web/src/draft/localDraft.test.ts`，合计19项；App、App.patternPresets、App.examples及两份记录已有在白名单中。32个未跟踪tools、忽略work脚本/截图/日志全部保留，不纳入候选。不暂存、提交、创建备份、推送或部署。
- **保留边界**：仅保留一份退出作品；后续显式新示例/作品切换按原机制可复用该槽，不提供新历史访问入口。未应用快捷表单仍需确认丢弃、不能保存成已应用；已应用配置/pending Layout与原作资产受保护；Undo历史刷新仍重置。几何和导出未改，本轮STL未重新下载，仍引用前批限定文件证据；全部其他历史OPEN、公网/Linux/切片/实物NOT TESTED不变。

## 实现与声明作用范围

复用 `PatternDocument`、正式 Grid、Linear/Wave Field、Size Modifier、`linearSizeCandidate`、现有 Apply/Cancel、history、草稿保护与二维导出。核心在 `web/src/document/patternPresets.ts`，入口在 `PatternPresetPicker.tsx` 与 `App.tsx`。不是独立项目格式或渲染器。

| 预设 | 默认配方（60×60mm，9×9，中心30/30mm） | 调整截图的实际参数 | 应用范围 |
| --- | --- | --- | --- |
| 精密错列 | 圆直径3.2mm；X/Y间距6/5.2mm；错列；尺寸100% | 尺寸130%；间距6.3/5.5mm | 只创建新图案；仅该预设创建的Grid可编辑间距、错列和尺寸，不重排已有导入作品 |
| 光谱渐隐 | 圆直径3.4mm；间距6/6mm；Linear方向0°；Size .55–1.15；强度1 | 45°；Size .5–1.25 | 创建或应用到当前图案；管理现有尺寸快捷层、专用场和本层范围 |
| 斜向潮汐 | 圆直径3.4mm；间距6/6mm；Wave波长23mm/35°/相位0/幅值1/偏移0；Size .65–1.15 | 波长31mm；-25°；最大比例1.25 | 创建或应用到当前图案；管理同一尺寸快捷层、专用场和本层范围 |

尺寸比例是无量纲比例，不是毫米。Wave波长通过现有毫米映射转换一次；phase遵循现有Schema。精密错列的Reset只恢复声明的间距、错列和尺寸，不恢复整份项目或擅自改用户后续行列。另两套Reset恢复完整受管场参数、映射和范围，不覆盖原图、二维布局、Fabric或用户其他效果。

创建复用已有示例/作品切换入口：成功保存当前草稿和必要UI状态后才替换，保存失败保留当前作品；进入示例会话可返回原作品。候选预览不递增正式revision，不进入Undo、不自动保存为已应用结果。Apply一次提交完整配置、一次Undo。重复编辑更新同一Size层，专用场被其他消费者引用时沿用既有复制隔离。切换受管效果前明确显示范围并确认，不移除无关场/效果。

三个主要参数来自实际Schema，高级编辑沿用同一表单和同一草稿。明确换用其他类型或已有共享场后，Apply转为自定义尺寸效果、移除本预设身份；不错误保留预设标签，也不删除字段/效果。预设缩略图由便携fixture经Python正式evaluate与现有SVG输出生成；数值对照真实81个中心和半径，非AI宣传图。

## 浏览器与文件证据

独立本地服务 `http://127.0.0.1:8803/`，启动来源为当前工作区、当前 `web/dist`；`XIAOMANG_ENV=staging`、现有 `XIAOMANG_FABRIC_STL_TEST_EXPORT=1` 仅赋予此本地测试进程。health运行提交为UNKNOWN，不能用基线SHA冒充未提交运行内容。原8802进程没有重启或改导出开关；原用户浏览器草稿未覆盖。用户试用页已打开三套预设选择区。

证据目录：`work/pattern-presets-p1-20261011/`。

- 每套 `*-default-view.png`、`*-adjusted-view.png` 均为真实Edge浏览器截图，已实际检查：错列节奏、单向/对角渐变、斜向波带有明显区别；相应修改确实改变几何而非镜头。
- 同名 `*-default.svg/png`、`*-adjusted.svg/png` 共六组为真实下载；每个SVG包含81个真实矢量圆，中心/半径与Python正式结果一致；每个PNG为1600×1600 RGBA，有真实透明背景。辅助网格、控制柄与参考底图不加入默认输出。
- 三套浏览器均覆盖候选revision不变、Cancel、Apply、Undo/Redo、Reset候选及刷新恢复已应用配置。每次Apply一条正式提交、一个evaluate请求；专用场/图层数量检查和Reset完整历史由定向自动化补充。
- `browser-defaults-evidence.json` 保存第一批真实记录：44个POST均200，最大evaluate在途1，页面异常0；三套和两种STL实际成功。该脚本随后因错误假设Fin初始化为Pattern Points而超时，**整批运行不标为PASS**。实际初始化为Area Fill是现有合法行为，未修改产品来迎合脚本。
- 补充脚本显式选择Pattern Points，验证Fin实际计划及尺寸仅继承一次。返回作品初次脚本因未等异步保存恢复完成而读取旧界面，原失败证据保留；正确等文档身份后 `browser-cross-final.log` PASS。此批14个POST均200，最大evaluate在途1，页面异常0；覆盖旧Fabric结果失效、Fin计划、带孔SVG导入后应用效果与创建/返回保护。两批请求数分别记录，不混合称作一次全流程PASS。
- 带孔导入采用既有**新建回归样本** `tests/fixtures/full_design_holes.svg`，不是历史缺失原文件。非零原点viewBox10/20/60/40、0.5mm比例、非正方形画板；应用Linear45°后正式原始元素、孔洞、Layout、坐标、旋转和单位保持。导出SVG5矢量、evenodd孔洞；透明PNG1600×1067，孔洞中心alpha=0。

### 真实STL下载及读回

斜向潮汐调整方案分别走普通二维与Fabric；Fabric再明确应用既有波浪高度效果，保留原图形状、仅单元，无底板。不是把标准均匀挤出冒充Fabric高度输出。

| 文件 | 字节/三角面/组件 | 实际XYZ(mm) | 验证 |
| --- | --- | --- | --- |
| `wave-standard.stl` | 216684 / 4332 / 81 | 52.02296448×52.20272541×2 | Z底0、水密、正体积、绕序一致、零退化；逐元素XY/高度/顶点与权威结果一致 |
| `wave-fabric.stl` | 216684 / 4332 / 81 | 52.02296448×52.20272541×5.73205090 | 同上；逐元素高度与真实实例采样、预览原型变换吻合 |

仅单元有效独立实体允许81组件，不宣称已融合。高度范围2–6mm的离散采样不要求出现理论最大6mm。没有降低Validator、repair或自动删面。Fin本轮覆盖计划数值一致，未额外下载Fin STL；不能以此宣称所有单元制造验收。`readback.json`、`readback-final.log` PASS。

## 测试与构建（分批，不累加重叠用例）

- Python：`xiaomang_pattern_lab/.venv/Scripts/python.exe -m pytest -q tests/test_pattern_presets_p1.py tests/test_full_design_panel.py tests/test_fabric_original_shape.py`：29/29 PASS，`python-targeted.log`。
- Web相关十套：Vitest运行 `patternPresets`、`App.patternPresets`、`App.linearSize`、`App.fieldSize`、`App.fullDesign`、`App.examples`、`App.draft`、`fieldSize`、`fullDesign`、`fabricOriginal`：60/60 PASS，`web-final.log`。
- 最后高级驱动身份连接修改后只补相关三套：`node node_modules/vitest/vitest.mjs run src/document/patternPresets.test.ts src/App.patternPresets.test.tsx src/App.fieldSize.test.tsx`：17/17 PASS，`web-advanced-final.log`。不是将60+17相加为77个不重复用例。
- 初次Web运行暴露两个既有草稿断言未包括基线已保存的design_display，以及新测试fixture URL被Vite转换。修复测试路径与精确期望（未放宽保存断言），失败日志保留。不冒称初次运行全PASS。
- 从web目录实际执行 `node node_modules/typescript/bin/tsc -b`、`node node_modules/vite/bin/vite.js build`，均exit0；`tsc-release.log`、`vite-release.log`。这与package.json构建内容一致，未虚称执行了不可用的npm启动链。
- 没有无关Python/Tk全量回归。便携fixtures纳入本批代码目录；运行截图/STL/日志保留work，不默认成为Git提交内容。

## 边界与保留OPEN

数值控件为松手/确认后候选更新，不宣称逐帧实时。未应用快捷表单刷新不持久化，旧Undo历史刷新后重新开始，沿用现有提示。未应用Layout不能偷偷应用或清除。三套可高级编辑，不意味着默认构图适用于所有导入形状；缩放叠加和重叠可能被严格制造校验拒绝。

bundle约1307.63kB的既有大小warning、Starlette/httpx warning保留。混合独立图形追加、旧非中性隐式效果堆栈、Arc、Skew、通用曲线/任意Transform、自动毫米映射及历史作品迁移等既有OPEN不由预设演示关闭；旧8792故障页鼠标确认不由独立测试服务代替。glance未安装，未伪报该工具自动视觉验证。

本轮仅这些本地样本PASS，不是全局可打印认证。公网、当前批Linux/Render、切片和实物 NOT TESTED。未创建稳定备份、未提交、未推送、未部署；完成后停止，等待用户试用，不进入剩余五套。
