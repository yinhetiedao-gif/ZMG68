import basicGrid from './fixtures/basic-grid.pattern.json'
import gradientGrid from './fixtures/gradient-grid.pattern.json'
import { prepareProject } from '../model/project'
import type { PatternDocumentDTO } from '../model/types'

export type ExampleId = 'basic-grid' | 'gradient-grid'
export type ExampleCapability = 'editable' | 'standard_stl' | 'preview_only'

export interface BuiltInExample {
  id: ExampleId
  title: string
  description: string
  thumbnail: 'dots' | 'gradient'
  capabilities: ExampleCapability[]
  document: typeof basicGrid | typeof gradientGrid
}

export const examples: BuiltInExample[] = [
  { id: 'basic-grid', title: '基础圆点阵列', description: '调整行列、间距和尺寸',
    thumbnail: 'dots', capabilities: ['editable', 'standard_stl'], document: basicGrid },
  { id: 'gradient-grid', title: '参数渐变', description: '体验参数场驱动的尺寸与旋转',
    thumbnail: 'gradient', capabilities: ['editable', 'standard_stl'], document: gradientGrid },
]

export function exampleIdFromDocument(dto: PatternDocumentDTO | null): ExampleId | null {
  const id = dto?.document.metadata['xiaomang_pattern_lab.example_id']
  return id === 'basic-grid' || id === 'gradient-grid' ? id : null
}

export function createExampleDocument(id: ExampleId, documentId: string): PatternDocumentDTO {
  const example = examples.find((item) => item.id === id)
  if (!example) throw new Error('找不到内置示例。')
  const prepared = prepareProject(JSON.stringify(example.document), documentId)
  if (prepared.needsMillimetreMapping || prepared.warnings.length) throw new Error('内置示例的毫米项目数据无效。')
  return prepared.dto
}
