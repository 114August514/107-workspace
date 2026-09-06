// @vitest-environment jsdom

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { BrandMark } from '../../src/brand/BrandMark'

afterEach(cleanup)

describe('BrandMark', () => {
  it('renders the active SVG asset at the requested size', () => {
    render(<BrandMark size={24} label="107 Brand Mark" />)

    const mark = screen.getByRole('img', { name: '107 Brand Mark' })
    expect(mark).toHaveAttribute('src', expect.stringContaining('000000'))
    expect(mark).toHaveAttribute('width', '24')
    expect(mark).toHaveAttribute('height', '24')
  })

  it('hides decorative marks from assistive technology', () => {
    render(<BrandMark size={24} decorative />)

    const mark = document.querySelector('img')
    expect(mark).toHaveAttribute('alt', '')
    expect(mark).toHaveAttribute('aria-hidden', 'true')
  })
})
