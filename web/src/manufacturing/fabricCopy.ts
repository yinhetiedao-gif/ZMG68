export const FABRIC_PREVIEW_NOTICE = '设计预览不代表制造校验通过。标准二维模型仍可正常制造并导出 STL。'

export function fabricExportNotice(enabled?: boolean) {
  return enabled === true ? 'Fabric STL 测试中：通过最终网格检查后可下载测试 STL，尚未完成实物验收。'
    : enabled === false ? '当前环境未启用测试导出，Fabric STL 未开放。'
    : 'Fabric STL 是否可测试导出，以后端最终网格检查响应为准；尚未完成实物验收。'
}
