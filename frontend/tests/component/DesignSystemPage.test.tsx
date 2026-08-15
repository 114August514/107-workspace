// @vitest-environment jsdom

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AsyncState } from '../../src/components/common/AsyncState'
import { DesignSystemPage } from '../../src/pages/design-system/DesignSystemPage'
import { EMPTY_RECIPE } from '../../src/pages/design-system/model'

const writeText = vi.fn<(value: string) => Promise<void>>()

// jsdom 没有 ResizeObserver，Primer Dialog 的 useOverflow 需要
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}

beforeEach(() => {
  vi.stubGlobal('ResizeObserver', ResizeObserverStub)
  writeText.mockReset()
  writeText.mockResolvedValue()
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: { writeText },
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('DesignSystemPage', () => {
  it('呈现为静态 Reference，不含任何 Playground 控制器', () => {
    render(<DesignSystemPage />)

    expect(screen.getByRole('heading', { name: '107 Primer UI Reference' })).toBeInTheDocument()
    for (const section of ['Foundations', 'States', 'Patterns', 'Content']) {
      expect(screen.getByRole('heading', { name: section })).toBeInTheDocument()
    }
    // 旧 Playground 的入口全部不存在
    expect(screen.queryByText('场景控制台')).not.toBeInTheDocument()
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '恢复默认值' })).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/预设$/)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/参考画布$/)).not.toBeInTheDocument()
  })

  it('六类状态无需任何操作即可直接查看', () => {
    render(<DesignSystemPage />)

    expect(screen.getByText('正在加载共享资源…')).toBeInTheDocument()
    expect(screen.getAllByText('这里还没有共享资源。').length).toBeGreaterThan(0)
    expect(screen.getAllByText('文件预览失败。').length).toBeGreaterThan(0)
    expect(screen.getAllByText('版本已发布').length).toBeGreaterThan(0)
    expect(screen.getAllByText('无法发布这个版本。').length).toBeGreaterThan(0)
    for (const name of ['加载中', '空态', '错误', '成功', '权限', '危险操作']) {
      expect(screen.getByLabelText(`${name} 状态参考`)).toBeInTheDocument()
    }
  })

  it('危险确认 Dialog 可打开与取消', async () => {
    render(<DesignSystemPage />)

    const trigger = screen.getAllByRole('button', { name: '删除 Project' })[0]
    if (!trigger) throw new Error('缺少危险操作触发按钮')
    fireEvent.click(trigger)

    const dialog = await screen.findByRole('alertdialog')
    expect(dialog).toHaveAccessibleName('删除 Project“mnist-train”？')
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument())
  })

  it('页头提供响应式返回入口与完整规范来源', () => {
    render(<DesignSystemPage />)

    expect(screen.queryByText('Internal reference')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: '返回产品' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: '107 Workspace' })).toHaveAttribute('href', '/')
    expect(screen.getByText('docs/product/ui-copy.md')).toBeInTheDocument()
    expect(screen.getByText('frontend/README.md')).toBeInTheDocument()
  })

  it('复制范例源码并反馈结果，2 秒后恢复可复制', async () => {
    vi.useFakeTimers()
    render(<DesignSystemPage />)

    fireEvent.click(screen.getByRole('button', { name: '复制能力感知空态代码' }))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(writeText).toHaveBeenCalledWith(EMPTY_RECIPE)
    expect(screen.getByText('代码已复制')).toBeInTheDocument()

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2100)
    })
    expect(screen.queryByText('代码已复制')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: '复制能力感知空态代码' })).toBeInTheDocument()
    vi.useRealTimers()
  })
})

describe('AsyncState', () => {
  it('加载中只呈现动作描述', () => {
    render(<AsyncState loading>内容</AsyncState>)

    expect(screen.getByText('加载中')).toBeInTheDocument()
    expect(screen.queryByText('内容')).not.toBeInTheDocument()
  })

  it('错误逐条展示问题并次级保留请求标识', () => {
    render(
      <AsyncState
        loading={false}
        error={{
          message: '无法发布这个版本。',
          problems: ['文件 list.txt 已存在', '说明过长'],
          requestId: 'req_01K2ZQ',
        }}
      >
        内容
      </AsyncState>,
    )

    expect(screen.getByText('无法发布这个版本。')).toBeInTheDocument()
    expect(screen.getByText('文件 list.txt 已存在')).toBeInTheDocument()
    expect(screen.getByText('说明过长')).toBeInTheDocument()
    expect(screen.getByRole('list')).toBeInTheDocument()
    expect(screen.getByText('请求标识 req_01K2ZQ')).toBeInTheDocument()
  })

  it('单条下一步说明不渲染为列表', () => {
    render(
      <AsyncState
        loading={false}
        error={{ message: '无法发布这个版本。', problems: ['请修正文件问题后重试。'] }}
      >
        内容
      </AsyncState>,
    )

    expect(screen.getByText('请修正文件问题后重试。')).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('空态显示说明，正常状态渲染内容', () => {
    const { rerender } = render(
      <AsyncState loading={false} empty emptyText="这里还没有共享资源。">
        内容
      </AsyncState>,
    )
    expect(screen.getByText('这里还没有共享资源。')).toBeInTheDocument()

    rerender(<AsyncState loading={false}>内容</AsyncState>)
    expect(screen.getByText('内容')).toBeInTheDocument()
  })
})
