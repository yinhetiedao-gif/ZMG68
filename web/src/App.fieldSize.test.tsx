import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'
import catalog from './test/sizeFieldCatalog.json'
import type { PatternDocumentDTO } from './model/types'
import * as drafts from './draft/localDraft'
const reply = (value: unknown) => new Response(JSON.stringify(value), {status:200,headers:{'Content-Type':'application/json'}})
function backend() {
  const requests: PatternDocumentDTO[] = []
  vi.stubGlobal('fetch',vi.fn<typeof fetch>(async (url,init) => {
    if (String(url).endsWith('/health')) return reply({status:'ok',contract_version:'1.0'})
    if (String(url).endsWith('/contract')) return reply({schema_version:'1.0',units:'mm',parameter_definitions:catalog})
    expect(String(url)).toMatch(/\/evaluate$/)
    const dto = JSON.parse(String(init?.body)).document as PatternDocumentDTO; requests.push(dto)
    return reply({schema_version:'1.0',document_id:dto.document_id,document_revision:dto.document_revision,
      geometry:dto.document.elements.map(e=>({...e,units:'mm'})),bounds_mm:{min_x:0,min_y:0,max_x:60,max_y:60,width:60,height:60,units:'mm'},warnings:[]})
  }))
  return requests
}
async function open() {
  render(<App/>); await screen.findByText('Backend Online')
  fireEvent.click(screen.getByRole('button',{name:'打开示例：基础圆点阵列'}))
  await waitFor(()=>expect(screen.getByRole('button',{name:'尺寸变化'})).toBeEnabled())
  fireEvent.click(screen.getByRole('button',{name:'尺寸变化'}))
  await waitFor(()=>expect(screen.getByRole('button',{name:'应用效果'})).toBeEnabled())
}
describe('field driven candidate lifecycle uses the existing shortcut controller',()=>{
  it('failed draft protection keeps formal design and pending proposal without a commit',async()=>{
    const requests=backend();await open();const revision=requests.at(-1)!.document_revision
    const save=vi.spyOn(drafts,'saveDraft').mockRejectedValue(new Error('IndexedDB write blocked'))
    const count=requests.length;fireEvent.click(screen.getByRole('button',{name:'应用效果'}))
    await screen.findByText(/未应用配置，正式作品已保留：IndexedDB write blocked/)
    expect(requests.length).toBe(count);expect(requests.at(-1)!.document_revision).toBe(revision)
    expect(screen.getByRole('button',{name:'撤销'})).toBeDisabled();expect(screen.getByText('有未应用修改')).toBeVisible()
    save.mockRestore()
  })
  it('Wave/Stripe change schema without commits, Apply once, Undo/Redo and update the same layer',async()=>{
    const requests=backend(); await open(); const rev=requests.at(-1)!.document_revision
    fireEvent.change(screen.getByLabelText('变化方式'),{target:{value:'wave'}})
    await waitFor(()=>expect(requests.at(-1)?.document.fields.at(-1)?.type).toBe('wave'))
    expect(screen.getByRole('spinbutton',{name:'波长 (mm)'})).toBeVisible()
    expect(screen.queryByRole('spinbutton',{name:'渐变方向'})).not.toBeInTheDocument()
    expect(requests.at(-1)!.document_revision).toBe(rev)
    expect(screen.getByRole('button',{name:'撤销'})).toBeDisabled()
    fireEvent.change(screen.getByLabelText('变化方式'),{target:{value:'stripe'}})
    await waitFor(()=>expect(requests.at(-1)?.document.fields.at(-1)?.type).toBe('stripe'))
    expect(screen.getByRole('spinbutton',{name:'周期 (mm)'})).toBeVisible()
    await waitFor(()=>expect(screen.getByRole('button',{name:'应用效果'})).toBeEnabled())
    const count=requests.length; fireEvent.click(screen.getByRole('button',{name:'应用效果'}))
    await waitFor(()=>expect(requests.length).toBe(count+1)); expect(requests.at(-1)!.document_revision).toBe(rev+1)
    fireEvent.click(screen.getByRole('button',{name:'撤销'})); await waitFor(()=>expect(requests.at(-1)!.document.modifiers).toHaveLength(0))
    fireEvent.click(screen.getByRole('button',{name:'重做'})); await waitFor(()=>expect(requests.at(-1)!.document.modifiers).toHaveLength(1))
    fireEvent.click(screen.getByRole('button',{name:'尺寸变化'})); await waitFor(()=>expect(screen.getByLabelText('变化方式')).toHaveValue('stripe'))
    fireEvent.change(screen.getByLabelText('变化方式'),{target:{value:'wave'}})
    await waitFor(()=>expect(screen.getByRole('button',{name:'应用效果'})).toBeEnabled())
    fireEvent.click(screen.getByRole('button',{name:'应用效果'})); await waitFor(()=>expect(requests.at(-1)!.document_revision).toBe(rev+4))
    expect(requests.at(-1)!.document.modifiers).toHaveLength(1)
  })
  it('missing image/distance assets explain the error without evaluating or pretending to apply',async()=>{
    const requests=backend(); await open(); const count=requests.length
    fireEvent.change(screen.getByLabelText('变化方式'),{target:{value:'image'}})
    expect(screen.getByText(/此尺寸效果缺少有效源图片/)).toBeVisible()
    expect(screen.getByRole('button',{name:'应用效果'})).toBeDisabled()
    expect(requests).toHaveLength(count)
    fireEvent.change(screen.getByLabelText('变化方式'),{target:{value:'distance'}})
    expect(screen.getByRole('button',{name:'选择尺寸效果源图片'})).toBeEnabled()
    expect(requests).toHaveLength(count)
    fireEvent.click(screen.getByRole('button',{name:'取消效果'})); expect(screen.getByRole('button',{name:'撤销'})).toBeDisabled()
  })
  it('local non-linear range is only a rectangle, and declined context switch retains pending input',async()=>{
    backend(); await open(); vi.spyOn(window,'confirm').mockReturnValue(false)
    fireEvent.change(screen.getByLabelText('变化方式'),{target:{value:'noise'}})
    fireEvent.change(screen.getByLabelText('作用范围'),{target:{value:'local'}})
    await waitFor(()=>expect(screen.getByRole('button',{name:'应用效果'})).toBeEnabled())
    expect(document.querySelector('[data-gradient-controls="region"]')).toBeInTheDocument()
    expect(document.querySelector('[data-gradient-axis]')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button',{name:'参数场与效果'}))
    expect(window.confirm).toHaveBeenCalledOnce(); expect(screen.getByLabelText('变化方式')).toHaveValue('noise')
    expect(screen.getByText('有未应用修改')).toBeVisible()
  })
  it('switching workspace keeps pending candidate separate and cannot manufacture the old formal design as new',async()=>{
    backend(); await open()
    fireEvent.change(screen.getByLabelText('变化方式'),{target:{value:'wave'}})
    await waitFor(()=>expect(screen.getByRole('button',{name:'应用效果'})).toBeEnabled())
    fireEvent.click(screen.getByRole('button',{name:/制造 Manufacture/}))
    expect(screen.getByText(/二维尺寸效果尚未应用。当前3D仅显示已应用设计/)).toBeVisible()
    expect(screen.getByRole('button',{name:'检查并生成'})).toBeDisabled()
    fireEvent.click(screen.getByRole('button',{name:/设计 Design/}))
    expect(screen.getByLabelText('变化方式')).toHaveValue('wave')
  })
})
