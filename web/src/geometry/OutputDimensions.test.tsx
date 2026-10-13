import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { OutputDimensions } from './OutputDimensions'
import { createBlankDesign } from '../document/nativeDesign'

describe('actual export dimensions, not geometry normalization', () => {
  it('distinguishes non-square artboard, nonzero pattern bounds and PNG resolution without mutation', () => {
    const dto = createBlankDesign('dimensions')
    dto.document.canvas = { width: 30, height: 20, origin_x: 5, origin_y: -2, unit: 'px', mm_per_unit: 2 }
    const before = JSON.stringify(dto)
    render(<OutputDimensions document={dto} pngWidth={1200} bounds={{ min_x: 11, max_x: 31, min_y: -3, max_y: 7, width: 20, height: 10, units: 'mm' }} />)
    expect(screen.getByText('画板尺寸：60 × 40 mm')).toBeInTheDocument()
    expect(screen.getByText(/X 11–31，Y -3–7 mm/)).toBeInTheDocument()
    expect(screen.getByText('PNG：1200 × 800 px · 透明背景')).toBeInTheDocument()
    expect(screen.getByText(/STL 使用实际制造几何，不按画板裁切/)).toBeInTheDocument()
    expect(screen.queryByText(/STL.*XYZ/)).not.toBeInTheDocument()
    expect(JSON.stringify(dto)).toBe(before)
  })
})
