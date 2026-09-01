import '@testing-library/jest-dom/vitest'

/**
 * antd 的 ResponsiveObserver 会在 mount 时调用 window.matchMedia，
 * jsdom 不实现这个 API，需要 polyfill。
 */
if (typeof window !== 'undefined' && !window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  })
}

// Primer 的 AnchoredOverlay / ActionMenu 定位要用 ResizeObserver，jsdom 不实现。
if (typeof window !== 'undefined' && !window.ResizeObserver) {
  class ResizeObserverStub {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  Object.defineProperty(window, 'ResizeObserver', {
    writable: true,
    configurable: true,
    value: ResizeObserverStub,
  })
}

// Primer SelectPanel 会滚动 active option；jsdom 没有 HTMLElement.scrollTo。
if (typeof HTMLElement !== 'undefined' && !HTMLElement.prototype.scrollTo) {
  Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
    writable: true,
    configurable: true,
    value: () => {},
  })
}

// Primer SelectPanel 的测试模式直接调用 live-region element；jsdom 只创建普通 HTMLElement。
if (typeof HTMLElement !== 'undefined' && !('announce' in HTMLElement.prototype)) {
  Object.defineProperties(HTMLElement.prototype, {
    announce: {
      writable: true,
      configurable: true,
      value: () => {},
    },
    clear: {
      writable: true,
      configurable: true,
      value: () => {},
    },
  })
}
