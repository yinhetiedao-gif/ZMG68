# WM5：Web 二维查看与基础编辑

## 启动

在仓库根目录启动已有 WM3 本机 API：

```powershell
.\xiaomang_pattern_lab\.venv\Scripts\python.exe -m xiaomang_pattern_lab.web
```

另一个终端进入 `web`，执行 `npm install`（仅首次）和 `npm run dev`，打开 Vite 显示的本机地址。前端读取 `VITE_API_BASE_URL`，不写死用户机器路径。

## 数据边界

“打开本地项目”读取正式 `.pattern.json` 项目格式，包装成 WM2 `PatternDocumentDTO` 后 POST `/api/v1/evaluate`。Python 仍负责所有参数、替换、随机与最终几何求值。前端只绘制合同返回的圆、椭圆、矩形、路径和实心区域；路径按合同的元素局部坐标和项目毫米映射显示，`evenodd` 保留镂空孔洞。当前合同没有独立 line/polyline 类型，不伪造支持。

唯一的 World(mm)↔Screen(px) 变换位于 `web/src/geometry/view.ts`。缩放、平移和选中状态只存在浏览器；不写入 PatternDocument。

只有无 Field/Modifier/参数化元数据且最终 ID、类型、中心坐标明确对应源元素时允许拖动。拖动过程仅更新当前 SVG 元素的临时 transform，不克隆文档、不调用后端；鼠标松开才更新一处源元素和文档 revision、请求一次 Evaluate。Pointer Cancel 不提交；后端求值失败会回退本次文档改动。其它对象可选择但只读。

已知本机图片/矢量路径会在发给后端前清除，未知本机绝对路径会阻止打开。WM5 没有资产上传接口，因此依赖本机 ImageField/参考文件的结果可能不完整。旧项目若缺少 `mm_per_unit` 且画布不是 mm，必须由用户填写比例，不猜打印尺寸。

## 验证和范围

前端：`npm test`、`npm run build`。Python：`python -m unittest discover -s tests`、`python -m xiaomang_pattern_lab.main --self-test`、`python -m unittest tests.test_gate0_tk_smoke`，均使用项目 `.venv`。

真实浏览器分别打开 144 圆点项目和三颗打印星项目，检查元素数量、实心显示、选择/拖动、适合窗口、缩放与平移；另用 `web/test-fixtures/hole.pattern.json` 检查白色孔洞。WM5 不包含网页项目保存、撤销/重做、形变/旋转、参数化控件、图片上传、制造按钮、三维 Viewer 或 STL 下载。浏览器拖动只改变本次会话，刷新页面会丢失；不要用于保存正式设计修改。
