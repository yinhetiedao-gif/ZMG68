import { phase1aCatalog } from './phase1aFixture'
import type { ParameterCatalog } from '../document/parameterSchema'
export const linearCatalog: ParameterCatalog = { ...phase1aCatalog, definitions: { ...phase1aCatalog.definitions,
  modifier: { size: { label: '尺寸', parameters: ['min_output', 'max_output', 'strength', 'falloff'].map(id => ({
    id, label: id, type: 'number', min: id === 'falloff' ? .01 : 0, max: id === 'strength' ? 1 : 10000,
    step: .01, unit: '', options: [], default: id === 'min_output' ? 0 : 1, value: 1, slider_min: 0, slider_max: 3,
  })) } },
} }
