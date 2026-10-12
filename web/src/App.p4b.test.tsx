import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { linearCatalog } from './test/linearSizeFixture'
import type { PatternDocumentDTO } from './model/types'

function backend(rejectCandidate = false) {
  const requests: PatternDocumentDTO[] = []
  vi.stubGlobal('fetch', vi.fn<typeof fetch>(async (url, init) => {
    const reply = (data: unknown) => new Response(JSON.stringify(data), { status: 200 })
    if (String(url).endsWith('/health')) return reply({ status: 'ok', contract_version: '1.0' })
    if (String(url).endsWith('/contract')) return reply({ schema_version: '1.0', units: 'mm', parameter_definitions: linearCatalog })
    expect(String(url)).toMatch(/\/evaluate$/)
    const dto = JSON.parse(String(init?.body)).document as PatternDocumentDTO
    requests.push(dto)
    if (rejectCandidate && dto.document.modifiers.length) return new Response(JSON.stringify({
      code: 'invalid_document', message: '候选测试拒绝', recoverable: true, details: {},
    }), { status: 422 })
    return reply({ schema_version: '1.0', document_id: dto.document_id, document_revision: dto.document_revision,
      geometry: dto.document.elements.map(e => ({ ...e, units: 'mm' })),
      bounds_mm: { min_x: 0, min_y: 0, max_x: 40, max_y: 40, width: 40, height: 40, units: 'mm' }, warnings: [] })
  }))
  return requests
}
describe('P4-B single left panel without new document state', () => {
  it('keeps structured candidate failure text visible in the status strip and preserves the formal design', async () => {
    backend(true); const view = render(<App />); await screen.findByText('Backend Online')
    fireEvent.click(screen.getByRole('button', { name: '打开示例：基础圆点阵列' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '尺寸变化' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: '尺寸变化' }))
    await within(screen.getByLabelText('画布状态')).findByText(/候选测试拒绝/)
    expect(screen.getByRole('button', { name: '应用效果' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    expect(view.container.querySelectorAll('[data-element-id]')).toHaveLength(9)
    expect(view.container.querySelector('.canvas-stage')).not.toContainElement(screen.getByLabelText('画布状态'))
    fireEvent.click(screen.getByRole('button', { name: '取消效果' }))
    expect(screen.getByLabelText('画布状态')).toBeEmptyDOMElement()
  })
  it('B2 leaves navigation subgroups folded and keeps size keys ahead of opt-in settings', async () => {
    const requests = backend(); const view = render(<App />); await screen.findByText('Backend Online')
    const menu = screen.getByRole('navigation', { name: '左侧工具栏' })
    expect([...menu.querySelectorAll('details')].every(group => !group.open)).toBe(true)
    expect(menu.querySelector('.side-item-mark')).toBeNull()
    expect(menu.querySelectorAll('.panel-icon[aria-hidden=true]').length).toBeGreaterThanOrEqual(7)
    expect([...menu.querySelectorAll(':scope > button.side-item')].every(button =>
      button.lastElementChild?.classList.contains('disclosure-chevron'))).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: '打开示例：基础圆点阵列' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '尺寸变化' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: '尺寸变化' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '应用效果' })).toBeEnabled())
    const input = screen.getByRole('spinbutton', { name: '最小尺寸比例' })
    const feedback = screen.getByLabelText('画布状态')
    expect(feedback).toContainElement(screen.getByText(/未应用的尺寸渐变预览/))
    expect(view.container.querySelector('.canvas-stage')).not.toContainElement(feedback)
    expect(screen.getByRole('button', { name: '下载设计SVG' })).toBeDisabled()
    const extra = view.container.querySelector('details.parameter-extra:has(summary)')!
    expect(extra).not.toHaveAttribute('open')
    const count = requests.length, official = requests[0].document_revision
    fireEvent.click(screen.getByText('作用说明与图案范围'))
    fireEvent.click(screen.getByText('预览与保存边界'))
    expect(screen.getByRole('spinbutton', { name: '最小尺寸比例' })).toBe(input)
    expect(requests).toHaveLength(count)
    expect(requests[0].document_revision).toBe(official)
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '应用效果' })).toBeEnabled()
    fireEvent.click(screen.getByRole('button', { name: '取消效果' }))
    expect(screen.queryByRole('button', { name: '应用效果' })).toBeNull()
  })
  it('keeps one inspector, eight preset cards and all navigation inside the left panel', async () => {
    backend(); const view = render(<App />); await screen.findByText('Backend Online')
    const panel = screen.getByRole('complementary', { name: '功能与参数面板' })
    expect(view.container.querySelectorAll('.inspector')).toHaveLength(1)
    expect(panel).toContainElement(screen.getByLabelText('当前功能参数'))
    expect(screen.getByRole('main')).not.toContainElement(screen.getByLabelText('当前功能参数'))
    fireEvent.click(within(panel).getByRole('button', { name: '图案预设 · 8套' }))
    expect(within(panel).getAllByRole('button', { name: /^创建/ })).toHaveLength(8)
    expect(within(panel).getByRole('button', { name: '图案预设 · 8套' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.queryByLabelText('右侧检查器')).toBeNull()
  })
  it('keeps export and connection outside the foldable parameter card without changing document state', async () => {
    const requests = backend(); const view = render(<App />); await screen.findByText('Backend Online')
    fireEvent.click(screen.getByRole('button', { name: '打开示例：基础圆点阵列' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '下载设计SVG' })).toBeEnabled())
    const parameters = view.container.querySelector('details.function-details')!
    const exporter = screen.getByRole('region', { name: '当前设计导出' })
    const connection = view.container.querySelector<HTMLElement>('.connection-card')!
    expect(parameters).not.toContainElement(exporter)
    expect(parameters).not.toContainElement(connection)
    expect(exporter.querySelector('details')).not.toHaveAttribute('open')
    const count = requests.length, revision = requests.at(-1)!.document_revision
    fireEvent.click(within(exporter).getByText('导出说明'))
    expect(screen.getByRole('button', { name: '下载设计SVG' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '下载透明PNG' })).toBeEnabled()
    expect(requests).toHaveLength(count)
    expect(requests.at(-1)!.document_revision).toBe(revision)
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
  })
  it('hide/show preserves candidate controls and canvas; effect actions stay outside the scrolling content', async () => {
    const requests = backend(); const view = render(<App />); await screen.findByText('Backend Online')
    fireEvent.click(screen.getByRole('button', { name: '打开示例：基础圆点阵列' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '尺寸变化' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: '尺寸变化' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '应用效果' })).toBeEnabled())
    const input = screen.getByRole('spinbutton', { name: '最小尺寸比例' })
    const main = screen.getByRole('main'), revision = requests.at(-1)!.document_revision
    const count = requests.length
    const dock = screen.getByRole('contentinfo', { name: '待应用效果操作' })
    expect(view.container.querySelector('.function-panel-scroll')).not.toContainElement(dock)
    fireEvent.click(screen.getByRole('button', { name: '收起功能面板' }))
    expect(screen.queryByRole('button', { name: '应用效果' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '功能与参数' }))
    expect(screen.getByRole('spinbutton', { name: '最小尺寸比例' })).toBe(input)
    expect(screen.getByRole('main')).toBe(main)
    expect(requests.length).toBe(count)
    expect(requests.at(-1)!.document_revision).toBe(revision)
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    fireEvent.click(screen.getByRole('button', { name: '取消效果' }))
    expect(screen.queryByRole('button', { name: '应用效果' })).toBeNull()
  })
  it('left navigation does not apply or discard a candidate when the existing switch confirmation is rejected', async () => {
    const requests = backend(); render(<App />); await screen.findByText('Backend Online')
    fireEvent.click(screen.getByRole('button', { name: '打开示例：基础圆点阵列' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '尺寸变化' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: '尺寸变化' }))
    await waitFor(() => expect(screen.getByRole('button', { name: '应用效果' })).toBeEnabled())
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    const input = screen.getByRole('spinbutton', { name: '最小尺寸比例' })
    const count = requests.length
    fireEvent.click(screen.getByRole('button', { name: '参数场与效果' }))
    expect(confirm).toHaveBeenCalledOnce()
    expect(screen.getByRole('spinbutton', { name: '最小尺寸比例' })).toBe(input)
    expect(screen.getByRole('button', { name: '应用效果' })).toBeEnabled()
    expect(screen.getByRole('button', { name: '撤销' })).toBeDisabled()
    expect(requests).toHaveLength(count)
    confirm.mockRestore()
  })
  it('narrow-screen drawer can close without removing the workspace or entering manufacture', async () => {
    backend(); vi.stubGlobal('innerWidth', 390)
    const view = render(<App />); await screen.findByText('Backend Online')
    const main = screen.getByRole('main')
    expect(screen.getByRole('button', { name: '功能与参数' })).toHaveAttribute('aria-expanded', 'false')
    fireEvent.click(screen.getByRole('button', { name: '功能与参数' }))
    expect(screen.getByRole('complementary', { name: '功能与参数面板' })).toBeVisible()
    act(() => { window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' })) })
    expect(screen.queryByRole('complementary', { name: '功能与参数面板' })).toBeNull()
    expect(screen.getByRole('main')).toBe(main)
    expect(view.container.querySelectorAll('.inspector')).toHaveLength(1)
    expect(screen.getByRole('navigation', { name: '工作模式' })).toContainElement(screen.getByRole('button', { name: /设计 Design/ }))
  })
})
