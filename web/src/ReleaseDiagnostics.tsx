import type { HealthResponse } from './api/client'

function commitIdentity(value?: string) {
  return /^[a-f0-9]{40}$/i.test(value ?? '') ? value : 'UNKNOWN'
}
function capability(value?: boolean) {
  return value === true ? '支持' : value === false ? '未启用' : 'UNKNOWN'
}

/** Frontend identity is compiled into this artifact, never borrowed from health. */
export function ReleaseDiagnostics({ health }: { health: HealthResponse | null }) {
  return <div aria-label="发布身份">
    <p>前端构建提交：{commitIdentity(import.meta.env.VITE_BUILD_COMMIT)}</p>
    <p>后端运行提交：{commitIdentity(health?.backend_commit)}</p>
    <p>环境：{['development', 'staging', 'production', 'test'].includes(health?.environment ?? '') ? health?.environment : 'UNKNOWN'}</p>
    <p>Fabric 预检：{capability(health?.capabilities?.fabric_preflight)}</p>
    <p>最终网格生成：{capability(health?.capabilities?.fabric_final_mesh)}</p>
    <p>测试 STL 导出：{capability(health?.capabilities?.fabric_stl_test_export)}</p>
  </div>
}
