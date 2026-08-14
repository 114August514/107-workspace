// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DesignSystemPage } from '../../src/pages/design-system/DesignSystemPage'
import { EMPTY_RECIPE } from '../../src/pages/design-system/model'

const writeText = vi.fn<(value: string) => Promise<void>>()

beforeEach(() => {
  writeText.mockReset()
  writeText.mockResolvedValue()
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText },
  })
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('DesignSystemPage', () => {
  it('展示六类状态和三个可复制组合范例', () => {
    render(<DesignSystemPage />)

    expect(screen.getByRole('heading', { name: '107 交互参考台' })).toBeInTheDocument()
    for (const state of ['Loading', 'Empty', 'Error', 'Success', 'Permission', 'Destructive']) {
      expect(screen.getAllByText(state).length).toBeGreaterThan(0)
    }
    expect(screen.getAllByRole('button', { name: '复制代码' })).toHaveLength(3)
  })

  it('允许精确输入画布宽度，并拒绝越界值', () => {
    render(<DesignSystemPage />)

    const widthInput = screen.getByRole('spinbutton', { name: '画布宽度' })
    expect(widthInput).toHaveValue(null)
    expect(widthInput).toHaveAttribute('placeholder', '自适应')
    fireEvent.change(widthInput, { target: { value: '411' } })
    fireEvent.keyDown(widthInput, { key: 'Enter' })
    expect(screen.getByLabelText('411 px 参考画布')).toBeInTheDocument()

    fireEvent.change(widthInput, { target: { value: '200' } })
    fireEvent.keyDown(widthInput, { key: 'Enter' })
    expect(screen.getByText('请输入 320–1440 之间的整数')).toBeInTheDocument()
    expect(screen.getByLabelText('411 px 参考画布')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '恢复默认值' }))
    expect(screen.getByLabelText('自适应 参考画布')).toBeInTheDocument()
    expect(widthInput).toHaveValue(null)
  })

  it('宽度预设段与输入共享选中语义，自定义值选中「自定义」段', () => {
    render(<DesignSystemPage />)

    const presets = screen.getByRole('list', { name: '画布宽度预设' })
    const pressed = () => within(presets).getByRole('button', { pressed: true })

    expect(pressed()).toHaveTextContent('自适应')

    fireEvent.click(within(presets).getByRole('button', { name: '375 px' }))
    expect(pressed()).toHaveTextContent('375 px')
    expect(screen.getByLabelText('375 px 参考画布')).toBeInTheDocument()
    expect(screen.getByRole('spinbutton', { name: '画布宽度' })).toHaveValue(375)

    const widthInput = screen.getByRole('spinbutton', { name: '画布宽度' })
    fireEvent.change(widthInput, { target: { value: '411' } })
    fireEvent.keyDown(widthInput, { key: 'Enter' })
    expect(pressed()).toHaveTextContent('自定义')
  })

  it('点击「自定义」段聚焦输入且不改变当前值', () => {
    render(<DesignSystemPage />)

    const widthInput = screen.getByRole('spinbutton', { name: '画布宽度' })
    const presets = screen.getByRole('list', { name: '画布宽度预设' })
    fireEvent.click(within(presets).getByRole('button', { name: '自定义' }))

    expect(widthInput).toHaveFocus()
    expect(screen.getByLabelText('自适应 参考画布')).toBeInTheDocument()
  })

  it('权限不足时优先显示权限反馈', () => {
    render(<DesignSystemPage />)

    fireEvent.click(screen.getByRole('button', { name: '无访问权限' }))
    const canvas = screen.getByLabelText('自适应 参考画布')
    expect(within(canvas).getByText('无法查看这个共享资源。')).toBeInTheDocument()
    expect(within(canvas).queryByRole('button', { name: '发布版本' })).not.toBeInTheDocument()
  })

  it('按精确延迟执行重试状态转换', async () => {
    vi.useFakeTimers()
    render(<DesignSystemPage />)

    fireEvent.click(screen.getByRole('button', { name: 'Error' }))
    const delayInput = screen.getByRole('spinbutton', { name: '请求延迟' })
    fireEvent.change(delayInput, { target: { value: '1250' } })
    fireEvent.keyDown(delayInput, { key: 'Enter' })

    const canvas = screen.getByLabelText('自适应 参考画布')
    fireEvent.click(within(canvas).getByRole('button', { name: '重试' }))
    expect(within(canvas).getByText('正在加载共享资源…')).toBeInTheDocument()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1249)
    })
    expect(within(canvas).queryByText('版本已发布')).not.toBeInTheDocument()
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1)
    })
    expect(within(canvas).getByText('版本已发布')).toBeInTheDocument()
  })

  it('复制范例源码并反馈结果', async () => {
    render(<DesignSystemPage />)

    const copyButton = screen.getAllByRole('button', { name: '复制代码' })[0]
    if (!copyButton) throw new Error('缺少组合范例复制按钮')
    fireEvent.click(copyButton)

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(EMPTY_RECIPE))
    expect(screen.getByText('代码已复制')).toBeInTheDocument()
  })
})
