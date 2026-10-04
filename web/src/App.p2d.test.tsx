import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'

const reply = (value: unknown) => ({ ok: true, status: 200, json: async () => value }) as Response

describe('P2-D product hierarchy', () => {
  it('offers both examples directly and keeps diagnostics collapsed behind plain-language status', async () => {
    vi.stubGlobal('fetch', vi.fn<typeof fetch>((url) => Promise.resolve(reply(
      String(url).endsWith('/health') ? { status: 'ok', contract_version: '1.0' }
        : { schema_version: '1.0', units: 'mm' }))))
    render(<App />)
    await screen.findByText('已连接', { selector: '.backend-badge' })
    const empty = screen.getByRole('region', { name: '空白设计工作区' })
    expect(within(empty).getByRole('button', { name: '打开示例：基础圆点阵列' })).toBeEnabled()
    expect(within(empty).getByRole('button', { name: '打开示例：参数渐变' })).toBeEnabled()
    expect(within(empty).getByRole('button', { name: '导入自己的图案' })).toHaveClass('ui-primary')
    expect(screen.getByRole('button', { name: /基础形状 Shapes/ })).toBeDisabled()
    expect(screen.getByRole('button', { name: /设计 Design/ })).toHaveAttribute('data-step-state', 'current')
    expect(screen.getByRole('button', { name: /制造 Manufacture/ })).toHaveAttribute('data-step-state', 'not-ready')
    expect(screen.queryByText('CONTRACT')).toBeNull()
    const details = screen.getByText('诊断详情').closest('details')!
    expect(details).not.toHaveAttribute('open')
    fireEvent.click(within(details).getByText('诊断详情'))
    expect(details).toHaveAttribute('open')
    expect(within(details).getByText('v1.0')).toBeInTheDocument()
  })
})
