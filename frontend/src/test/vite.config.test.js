import { describe, expect, it } from 'vitest'

import viteConfig from '../../vite.config.js'

function resolve(command) {
  if (typeof viteConfig === 'function') {
    return viteConfig({ command, mode: command === 'build' ? 'production' : 'development' })
  }
  return viteConfig
}

describe('vite.config base (spec 014: el backend sirve el panel)', () => {
  it('en dev sirve en la raíz', () => {
    expect(resolve('serve').base ?? '/').toBe('/')
  })

  it('en build también sirve en la raíz (http://127.0.0.1:8000/)', () => {
    expect(resolve('build').base).toBe('/')
  })
})
