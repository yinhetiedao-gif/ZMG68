import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { initialBrowserState } from './state/browserState'

function jsonResponse(value: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => value } as Response
}

function onlineFetch() {
  const mock = vi.fn<typeof fetch>()
    .mockResolvedValueOnce(jsonResponse({ status: 'ok', contract_version: '1.0' }))
    .mockResolvedValueOnce(jsonResponse({ schema_version: '1.0', units: 'mm' }))
  vi.stubGlobal('fetch', mock)
  return mock
}

describe('WM4 application shell', () => {
  it('renders the three-column shell and marks unfinished tools unavailable', async () => {
    onlineFetch()
    render(<App />)
    expect(screen.getByText('Xiaomang Pattern Lab')).toBeInTheDocument()
    expect(screen.getByLabelText('左侧工具栏')).toBeInTheDocument()
    expect(screen.getByLabelText('中央工作区')).toBeInTheDocument()
    expect(screen.getByLabelText('右侧检查器')).toBeInTheDocument()
    expect(screen.getByText('导入图片开始设计')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /基础形状 Shapes/ })).toBeDisabled()
    expect(screen.queryByRole('button', { name: '打开项目' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '打开本地项目' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '项目导出' })).not.toBeInTheDocument()
    await screen.findByText('Backend Online')
    expect(screen.getByRole('button', { name: /导入 PNG \/ JPG/ })).toBeEnabled()
    expect(screen.getByRole('button', { name: /导入 SVG/ })).toBeEnabled()
  })

  it('calls WM3 health and contract through one API client', async () => {
    const fetchMock = onlineFetch()
    render(<App />)
    await screen.findByText('Backend Online')
    expect(screen.getByText('v1.0')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain('/api/v1/health')
    expect(String(fetchMock.mock.calls[1]?.[0])).toContain('/api/v1/contract')
  })

  it('continues showing the shell when the backend is offline', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    render(<App />)
    await screen.findByText('Backend Offline')
    expect(screen.getByText('Xiaomang Pattern Lab')).toBeInTheDocument()
    expect(screen.getByText('待验证')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '重新检测连接' })).toBeEnabled()
  })

  it('rejects an incompatible health contract version', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ status: 'ok', contract_version: '2.0' })))
    render(<App />)
    await screen.findByText('Contract Error')
    expect(screen.getByText(/后端协议版本不匹配/)).toBeInTheDocument()
  })

  it('rejects wrong contract units instead of silently continuing', async () => {
    const mock = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ status: 'ok', contract_version: '1.0' }))
      .mockResolvedValueOnce(jsonResponse({ schema_version: '1.0', units: 'px' }))
    vi.stubGlobal('fetch', mock)
    render(<App />)
    await screen.findByText('Contract Error')
    expect(screen.getByText(/需要 v1.0 \/ mm/)).toBeInTheDocument()
  })

  it('opens manufacturing and preview while requiring a built result for STL', async () => {
    onlineFetch()
    render(<App />)
    await screen.findByText('Backend Online')
    fireEvent.click(screen.getByRole('button', { name: /制造 Manufacture/ }))
    expect(screen.getByRole('heading', { name: '制造检查' })).toBeInTheDocument()
    expect(screen.queryByText('导入图片开始设计')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /三维预览 3D Preview/ }))
    expect(screen.getByRole('heading', { name: '3D 模型' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '导出 STL' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: /设计 Design/ }))
    expect(screen.getByText('导入图片开始设计')).toBeInTheDocument()
  })

  it('keeps browser-only mode state out of the persistent document', async () => {
    const fetchMock = onlineFetch()
    const sentinel = JSON.stringify({ document_id: 'preserve-me', document_revision: 8 })
    window.localStorage.setItem('pattern-document', sentinel)
    expect(Object.keys(initialBrowserState)).not.toContain('document')
    render(<App />)
    await screen.findByText('Backend Online')
    fireEvent.click(screen.getByRole('button', { name: /制造 Manufacture/ }))
    await waitFor(() => expect(window.localStorage.getItem('pattern-document')).toBe(sentinel))
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })
})
