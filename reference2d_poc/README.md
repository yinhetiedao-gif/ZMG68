# Reference2D POC — Stage A: Geometry Reconstruction

这个独立模块验证并提供正式 Canvas 使用的 Stage A 链路：`PNG/JPG → VTracer SVG → SVGParser → PrimitiveRecognizer → DotObject[] → Document2D`。

它不调用 Generator、3D、STL，也不尝试 `GridFitter`、密度场或其它 Parametric Inference；Canvas 只消费其真实 GeometryLayer。

## 运行

```powershell
$env:PYTHONPATH = "$PWD\build-tools\vtracer-runtime;$PWD"
python -m reference2d_poc.poc_runner --output reference2d_poc/artifacts
python -m unittest tests.test_reference2d_poc -v
```

`VectorizerAdapter` 只依赖官方 Python binding `vtracer==0.6.15`。适配器会优先读取项目内的 `build-tools/vtracer-runtime`，因此不依赖用户系统的 Python 环境或 `trace` 命令。

## 分层约束

- `ReferenceLayer` 只存源文件及其可见状态。
- `GeometryLayer` 只存真实的 `DotObject`。
- 隐藏/删除 `ReferenceLayer` 后，`GeometryLayer` 不会重新分析图像，仍可选择、改半径、拖动、删除和保存。自动化恢复由新的 Python 进程执行，且在测试中先删除源 PNG。
- `trace` 仅用于开发和验证真实 SVG 路径；运行时使用 `VectorizerAdapter` 调官方 VTracer binding，不以 Skill CLI 为依赖。

### trace 交叉验证（开发时）

安装的 Anionex `vision-skills` 提供本地 `trace` 工作流。它可对同一张 PNG 独立生成 SVG，再把该 SVG 传回 POC 统计路径和 DOT 数量：

```powershell
python <agent-vision-toolkit>\bin\trace reference2d_poc\artifacts\dot_halftone_input.png -o reference2d_poc\artifacts\dot_halftone_trace_validation.svg
python -m reference2d_poc.poc_runner --output reference2d_poc\artifacts --trace-validation-svg reference2d_poc\artifacts\dot_halftone_trace_validation.svg
```

该步骤只验证像素到 SVG 的几何一致性，不会进入用户软件的正式运行时依赖链。
