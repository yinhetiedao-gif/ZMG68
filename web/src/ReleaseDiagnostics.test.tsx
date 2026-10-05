import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ReleaseDiagnostics } from './ReleaseDiagnostics'

afterEach(() => vi.unstubAllEnvs())
describe('independent release identities', () => {
  it('uses frontend build metadata separately from backend metadata', () => {
    vi.stubEnv('VITE_BUILD_COMMIT', 'a'.repeat(40))
    render(<ReleaseDiagnostics health={{ status: 'ok', contract_version: '1.0',
      backend_commit: 'b'.repeat(40), environment: 'staging', capabilities: {
        fabric_preflight: true, fabric_final_mesh: true, fabric_stl_test_export: false } }} />)
    expect(screen.getByText('前端构建提交：' + 'a'.repeat(40))).toBeInTheDocument()
    expect(screen.getByText('后端运行提交：' + 'b'.repeat(40))).toBeInTheDocument()
    expect(screen.getByText('Fabric 预检：支持')).toBeInTheDocument()
    expect(screen.getByText('测试 STL 导出：未启用')).toBeInTheDocument()
  })
  it('does not turn an old contract or backend commit into a frontend identity', () => {
    vi.stubEnv('VITE_BUILD_COMMIT', 'UNKNOWN')
    render(<ReleaseDiagnostics health={{ status: 'ok', contract_version: '1.0' }} />)
    expect(screen.getByText('前端构建提交：UNKNOWN')).toBeInTheDocument()
    expect(screen.getByText('后端运行提交：UNKNOWN')).toBeInTheDocument()
    expect(screen.getByText('Fabric 预检：UNKNOWN')).toBeInTheDocument()
  })
})
