# P2 第二批三套图案预设：本地限定验收

日期：2026-10-11。基线 `18b40d0e9b6167eb3df6e888f4394406e64ac012`，分支 `feature/pattern-library-reuse`。实现和记录未提交；未推送、部署、创建稳定分支或改变Production权限/依赖。32个既有未跟踪探查脚本保留。

## 实现与作用范围

复用 `patternPresets`、`PatternPresetPicker`、PatternDocument、Grid、Field/Size、同一候选预览及Apply/Cancel/history/draft。没有新算法、公共DTO、项目格式或第二套预设系统。

| 配方 | 新建默认配置 | 当前作品应用 | 关键参数 |
| --- | --- | --- | --- |
| 局部呼吸 local-breath | 60×60mm，9×9圆Grid，直径3.2mm/间距6mm；专用Constant .5，Size 1.30/1.30，强度1；椭圆启用、曲线停用 | 仅受管Size、专用场、本层影响区；不重排、不改原图或Fabric | 倍率、当前区宽度、边缘过渡 |
| 珊瑚微粒 coral-grains | 11×11，间距4.6mm；现有Grid及形状变换生成2.8×1.7mm真实椭圆；Noise尺度14mm/3层/对比度1.5/强度1/seed27/偏移0/不反转；Size .60–1.12；尺寸随机±.10、各轴错位±.35mm、旋转±35°、公共seed27 | 默认只应用Noise尺寸；已有公共参数原样保留，没有公共随机配置时不写隐式默认配置。主动错位/旋转时说明会改变坐标/方向 | 噪声尺度、尺寸范围（两个端点）、错位幅度 |
| 涟心扩散 ripple-center | 9×9圆Grid，直径3.2mm/间距6mm；中心取初始化Bounds中心，半径为其半对角线，默认约36.204mm；中心1.25/外围.65/强度1 | 使用现有有序径向尺寸层，不是Ring或Radial排列；XY不变，半径外继续外围倍率 | 半径、中心倍率、外围倍率；中心沿用高级控件和画布控制柄 |

局部区从首次应用的世界Bounds初始化：椭圆中心 `(cx-.08w,cy)`、直径`.59w×.43h`、-20°、过渡`min(4mm,短轴/4)`；曲线 `(cx-.32w,cy+.24h)`→控制点`(cx,cy-.36h)`→`(cx+.36w,cy+.20h)`、宽`.20h`、过渡`min(3mm,.05h)`。宽高下限.1mm。具体参数全部保存，不每次求值重新定位。

身份继续使用version1 `web_pattern_preset`，增加已声明的作用范围、初始化Bounds/毫米比例、径向层ID及受管随机键前后值。既有公共DTO不改。径向层只引用自己的ID，不抢占用户原 `web_radial_size_effect`；P1旧默认fixtures不改。标量/径向切换停用旧预设实际拥有的层，保留被引用字段和用户独立效果；重复切回复用原层ID，不增加活动Size层。

Noise/Constant沿用 `linearSizeCandidate` 的专用字段、类型ID映射和 `fieldReferencedOutside` 复制隔离。原字段被Fabric Height引用时不改该字段和绑定。随机只记录本配方主动改变的键；Reset不动未声明的公共旋转/大小/用户seed。离开珊瑚时只恢复仍等于配方最后值的受管键，用户后来独立修改的键保留。坐标随机的归属值按原生单位保存，UI按现有mm映射转换。

`radialSize.ts`只补可选受管层ID/候选身份，默认独立径向快捷入口行为不变。P2初始化Bounds记录mm_per_unit；明确改变实际尺寸映射时按同一比例转换保存的初始化框，Reset不回到旧毫米中心。没有历史作品自动迁移。

## 真实浏览器证据

证据目录 `work/pattern-presets-p2-20261011/`。独立Edge context与本地8804/current web/dist；未覆盖原用户草稿。测试进程单独使用已有 `XIAOMANG_ENV=staging` 与 `XIAOMANG_FABRIC_STL_TEST_EXPORT=1`，单任务槽和服务端导出校验保留，未更改生产开关。后端提交身份UNKNOWN，已记录启动来源为当前工作区。

每套默认、variant1、variant2均有真实浏览器 `*-view.png`、正式DTO/result JSON及实际下载SVG/透明PNG：

- 局部：默认1.30/宽约22.016mm/过渡4mm；变体1倍率.80、宽18mm；变体2倍率1.45、宽18mm、过渡5mm。中央局部放大/缩小清楚，外围保持。
- 珊瑚：默认如上；变体1尺度9mm、范围.55–1.22；变体2尺度22mm、范围.55–1.22、错位.60mm。真实颗粒簇尺度和错位变化，不冒称Poisson分布。
- 涟心：默认中心1.25/外围.65/半径36.204mm；变体1半径18mm、中心1.35；变体2半径45mm、中心.65/外围1.20。正反径向趋势明显，元素中心不移动。

`browser-fourth.log`与`fourth-artifacts/browser-evidence.json`：三套创建、候选不提交、Cancel、Apply一次一个evaluate/一条Undo、Undo/Redo、Reset候选、已应用保存/刷新恢复、返回同一原作品；与P1 Linear/Wave交叉切换。90条记录请求全200，evaluate最大在途1，pageerror0。三套全部返回原带孔SVG的完整正式文档。显示样式沿用已有实现，没有整站改造。

真实椭圆中心拖动12个pointermove合并为1次evaluate，正式revision不变。另 `handles-browser.log` / `handles-evidence.json`：规则81点中停用=中性；椭圆/曲线单独都有命中；组合尺寸逐项等于两者最大值，XY不动；曲线控制点12步拖动2次evaluate、径向中心12步拖动1次evaluate，均不提交。对应 `local-grid-ellipse/curve/combined/disabled/curve-drag`、`radial-center-drag`截图及JSON。没有逐事件最终制造、伪造逐帧反馈或固定FPS声明。

数值控件仍为松手/确认后候选更新；辅助控制柄不进入几何、SVG/PNG/STL。默认停用曲线显示为淡色辅助对象，不代表它已参与计算。

## 文件及制造读回

`readback-final.log` / `readback.json`：九组SVG与对应Python正式求值的中心、尺寸、旋转一致，局部/径向各81矢量、珊瑚121真实椭圆；均为60×60mm/viewBox0 0 60 60。九张实际PNG均1600×1600 RGBA，alpha范围0–255，有内容且背景透明，不包含控制柄/参考底图。

带孔导入沿用既有**新建回归样本**full_design_holes.svg，非历史缺失原文件。非零原点、0.5mm映射、60×40mm画板。初始自动局部框在此稀疏样本命中全0，未把该结果冒称真实局部变化。

`browser-output-targeted.log` / `browser-evidence.json`只补这个输出缺口：恢复先前真实已应用DTO，在页面把椭圆移到hole实际中心(20,47.5)mm、长短轴14mm、倍率.85，再Apply一次。权重`0/0/0/1/0`，孔洞元素宽高均为原值.85，四个外围元素完整不变。SVG5矢量/60×40mm/viewBox10 20 60 40、evenodd真孔；PNG1600×1067 RGBA，孔中心透明。19条记录请求均200，与前批90条分开记录。

| 实际浏览器下载 | 字节/面/组件 | XYZ(mm) | 读回 |
| --- | --- | --- | --- |
| p2-standard.stl | 10084 / 200 / 5 | 33×24.25×2 | Z0、水密、正体积、绕序一致、零退化；各轮廓含孔边界与权威Adapter逐项一致 |
| p2-fabric.stl | 10084 / 200 / 5 | 33×24.25×约5.992389 | 保留原图、仅图案，不加底板；真实Wave Height；每实例XY/轮廓顶点/高度与实际计划一致 |

仅图案有效多组件不强制单体。不改融合算法、MeshValidator阈值，不repair/删面。代表性实际STL是局部作用的带孔原图；没有额外宣称每套默认×每种单元×每种基底全部制造通过。

## 自动化、构建及首批失败

- Web相关8文件51/51：`App.patternPresets`、`App.patternPresetsP2`、`App.examples`、`App.fieldSize`、`App.draft`、`document/patternPresetsP2`、`document/patternPresets`、`document/radialSize`，`--maxWorkers=1`，`web-combined.log`。
- Python相关4文件32/32：`tests/test_pattern_presets_p2.py tests/test_pattern_presets_p1.py tests/test_full_design_panel.py tests/test_radial_size_shortcut.py`，`python-second.log`。涵盖噪声确定性、真范围、径向半径外、原图实际旋转轮廓与Fin单次尺寸继承/高度绑定。
- 后续Noise无公共随机配置保护/宽度标签调整只补相关2文件19/19及tsc/vite，`adjusted-build.log`。最后毫米初始化边界补相关3文件22/22及tsc/vite，`mapping-final-build.log`；重新生成正式fixtures后只补P1/P2 Python两文件17/17，`python-fixtures-final.log`。不同批次不累加为全量。
- tsc与Vite生产构建均exit0；无依赖修改。bundle大于500kB、Starlette/httpx既有warning保留。
- 初始珊瑚构造调用updateGrid额外递增revision，真实测试失败后修为新建0。测试原图错误把已烘焙旋转当第二次实例角度，改为比较实际轮廓边界（未改算法）。TS检查暴露缩略图映射、空值和测试参数类型错误，均有失败日志。
- 六卡片完整往返测试实际约5–6秒，原5秒测试预算超时；P1对应长流程明确用10秒、P2长流程15秒，不删除断言、不改变业务超时/后端任务保护。没有声称原默认5秒仍PASS。
- 独立服务首次未传现有XIAOMANG_WEB_DIST导致首页404，仅重启本轮已确认的测试进程。原服务不动，startup失败截图/日志保留。
- 浏览器先直接fill带小数控件，focus恢复完整精度时把新值追加至旧值；真实请求证明半径未变。修验收脚本为先click、fill并断言实际输入，再Enter；不改共享控件。旧文件保留third-artifacts。稀疏导入样本默认全0权重另保留fourth-artifacts；补真实命中后才确认输出。
- SVG radius×2读回浮点比较沿用1e-9绝对容差，不用浮点逐位相等；未放宽制造Validator。
- 最后新建单位边界用例实际复现：mm_per_unit改.5后编辑中心15正确、Reset错误回30；只补保存/换算初始化比例，并定向复验。
- 最终当前构建 `index-Blxfgr8n.js` 在独立Edge实际刷新/恢复：mm_per_unit .5、涟心中心(15,15)，Reset仍(15,15)/半径18.102mm，revision0/Undo为空；所有evaluate200、pageerror0。`mapping-browser-evidence.json`、`mapping-reset-view.png`。此补批不替代先前完整截图/下载批次，也没有伪报旧批运行的是这个hash。
- 随后只增加局部重新编辑/Reset初始化框断言，`bounds-frame-before.log`实际1PASS/9skipped：现有openLinearSize专用归属已保存并换算初始化Bounds；未复现重新编辑漂移，没有为猜测增加产品修复或重跑整批。

## 边界

本批只限这些本地样本。公网、当前批Linux/Render、切片、实物NOT TESTED；带基底能力未重复全矩阵制造。噪声及径向默认未单独额外下载STL，已有计划数值与代表性严格输出证据分开声明。

稀疏导入作品的自动局部区域可能没有命中中心，需要用户调整位置/范围；局部所有区域共用一个倍率，曲线沿用128段距离计算。大尺寸/错位可能重叠，仍由严格制造流程判断，不宣称全面可打印。

glance未安装，截图直接实际查看，不伪报该工具自动视觉PASS。未应用快捷表单刷新不持久化，旧Undo刷新重置；返回只留一份退出作品。旧故障页鼠标确认、混合追加、旧隐式非中性堆栈、Arc/Skew/通用曲线/自动毫米映射/历史作品迁移等历史OPEN保持。

用户已于2026-10-11确认“局部呼吸、珊瑚微粒、涟心扩散”本地使用正常。此确认仅补充用户本地试用状态，不扩大上述限定样本验收、制造验证范围或关闭任何历史OPEN事项。
