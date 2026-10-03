import { cleanup } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { afterEach, vi } from 'vitest'
import { beforeEach } from 'vitest'
import { IDBFactory } from 'fake-indexeddb'

beforeEach(() => vi.stubGlobal('indexedDB', new IDBFactory()))

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  window.localStorage.clear()
})
