// @vitest-environment jsdom

import { render, screen } from '@testing-library/react'
import type { ComponentProps } from 'react'
import { describe, expect, it } from 'vitest'

import { AsyncState } from '../../src/components/common/AsyncState'
import { PrimerRoot } from '../../src/primer/setup'

type AsyncStateProps = ComponentProps<typeof AsyncState>
type LoadingTextIsRequired =
  Record<never, never> extends Pick<AsyncStateProps, 'loadingText'> ? false : true

// tsc 会在 loadingText 再次变为 optional 时让这个契约赋值失败。
const loadingTextIsRequired: LoadingTextIsRequired = true

describe('AsyncState loading 文案契约', () => {
  it('类型要求调用方提供 loadingText', () => {
    expect(loadingTextIsRequired).toBe(true)
  })

  it('加载态直接展示调用方给出的动作，不出现通用 fallback', () => {
    render(
      <PrimerRoot>
        <AsyncState loading loadingText="正在读取训练日志…">
          已加载内容
        </AsyncState>
      </PrimerRoot>,
    )

    expect(screen.getByRole('status')).toHaveTextContent('正在读取训练日志…')
    expect(screen.queryByText('加载中')).toBeNull()
    expect(screen.queryByText('已加载内容')).toBeNull()
  })
})
