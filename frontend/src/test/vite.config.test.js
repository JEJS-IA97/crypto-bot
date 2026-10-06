import { describe, expect, it } from 'vitest'

import viteConfig from '../../vite.config.js'

function resolve(command) {
  if (typeof viteConfig === 'function') {
    return viteConfig({ command, mode: command === 'build' ? 'production' : 'development' })
  }
  return viteConfig
}

describe('vite.config base (RF-8, Pages)', () => {
  it('en dev sirve en la raíz', () => {
    expect(resolve('serve').base ?? '/').toBe('/')
  })

  it('en build sirve bajo /crypto-bot/ para GitHub Pages', () => {
    expect(resolve('build').base).toBe('/crypto-bot/')
  })
})
