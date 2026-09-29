# WM5.6 编辑时元素可见性回归（2026-09-29）

## 根因

类别 **A：transient rendering bug**。`Workspace2D` 的 pointermove/pointerup 直接给 SVG `<g>` 写 `transform`；同一属性同时由 React 的 `pendingPreview` 控制。若 Evaluate 很快完成，React 可能在同一批次只看到最终 `pendingPreview=null`，不会移除浏览器直接写入的旧属性。新几何坐标再叠加旧位移，元素会被二次平移，严重时离开视口。修复为提交后的 layout 阶段显式协调/清理该临时属性；失败时也还原旧画面。

附加防线：接口收到零/负尺寸或重复 final ID 时拒绝替换上一个有效画面；数字框空白草稿不再使滑杆显示为零。已确认 SVG 节点原来就以 final `id` 为 key；真实 Python Evaluate 的 source/final ID 未丢失，选择框 `fill:none` 不会遮蔽黑色元素。本轮未修改后端几何算法。

## 身份、坐标与边界记录

实际网页打开固定 144 点 `work/foundation0/test_dot_grid/document.pattern.json`，1 SVG 单位 = 1 mm。选中第一个元素：source ID `layer-1`，final ID `layer-1`，类型 ellipse。全画布 144 个 ID、144 个唯一 ID。

| 阶段 | 中心 (mm) | 元素宽×高 (mm) | 元素包围框 [xmin,ymin,xmax,ymax] (mm) | 画布元素数 |
| --- | --- | --- | --- | --- |
| width 前 | (39.500, 20.588) | 9.000×8.824 | [35.000,16.176,44.000,25.000] | 144 |
| 输入草稿 12，未提交 | (39.500, 20.588) | 9.000×8.824（上一有效几何） | [35.000,16.176,44.000,25.000] | 144 |
| width Evaluate 后 | (39.500, 20.588) | 12.000×8.824 | [33.500,16.176,45.500,25.000] | 144 |
| 直接拖动 Evaluate 后 | (48.144, 22.749) | 12.000×8.824 | [42.144,18.337,54.144,27.161] | 144 |

直接拖动后 DOM 中 final ID 仍为 `layer-1`，椭圆 `cx=48.14379417504961`，父 `<g>` 的临时 `transform=null`，revision 从 1 变为 2。位置、宽度、高度、旋转四种数字编辑在 144 元素前端用例中分别核验：草稿阶段不调用后端；提交一次产生 revision +1、一个 Evaluate；loading 阶段保留原 144 个节点；响应后仍为 144。真实 Python 后端对导入的规则点阵 PNG、星形半调 PNG 分别执行 x/y/width/height/rotation 编辑与 Evaluate，几何数量、ID、正尺寸和 bounds 均保持有效。

## 测试

- Web Vitest：51/51 PASS（含 WM5.6 新增直接拖动、数字编辑加载/失败、响应尺寸/重复 ID）。
- TypeScript + Vite 生产构建：PASS。
- Python 全量：339/339 PASS；WM5.6 真实导入/Evaluate 专项：1/1 PASS。
- 固定图：6/6 PASS；Tk smoke：2/2 PASS。
- 实际浏览器：144/144 个黑色实心元素持续可见；width 9→12 mm、拖动后 revision 2、ID 稳定、临时 transform 清除。

## 运行环境限制

现有 127.0.0.1:8765 的后台是早先启动的 WM3 进程：Health 与 Evaluate 可用，但 `POST /api/v1/assets` 返回 404。因此这次实际浏览器的 PNG 文件选择出现“无法连接图片上传服务”。这不由 WM5.6 改动引起，也不是新版源码的 WM5.5 上传接口失效；已由 TestClient 对当前源码的真实 PNG 导入与后续 Evaluate 验证。未强行终止用户当前后台进程；要在浏览器中重测图片上传，需要重新启动当前源码的 WM5.5 后端进程。
