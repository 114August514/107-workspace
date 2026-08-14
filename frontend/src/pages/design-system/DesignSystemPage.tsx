import '@primer/primitives/dist/css/base/size/size.css'
import '@primer/primitives/dist/css/base/typography/typography.css'
import '@primer/primitives/dist/css/functional/size/border.css'
import '@primer/primitives/dist/css/functional/size/radius.css'
import '@primer/primitives/dist/css/functional/typography/typography.css'
import '@primer/primitives/dist/css/functional/themes/light.css'

import { BookIcon, MarkGithubIcon } from '@primer/octicons-react'
import { Label, Link, PageHeader, Stack, ThemeProvider } from '@primer/react'
import { Card } from '@primer/react/experimental'
import { useEffect, useRef, useState } from 'react'

import { CompositionRecipes } from './CompositionRecipes'
import type { Capability, ContentScale, DataState } from './model'
import { CONTENT } from './model'
import { ScenarioToolbar } from './ScenarioToolbar'
import { LivePreview, StatusGallery } from './StatusExamples'
import styles from './DesignSystemPage.module.css'

const DEFAULTS = {
  dataState: 'normal' as DataState,
  capability: 'operate' as Capability,
  contentScale: 'short' as ContentScale,
  canvasWidth: null as number | null,
  delayMs: 800,
}

function SectionHeading({
  id,
  title,
  description,
}: {
  id: string
  title: string
  description: string
}) {
  return (
    <div className={styles.sectionHeading}>
      <h2 id={id}>{title}</h2>
      <p>{description}</p>
    </div>
  )
}

export function DesignSystemPage() {
  const [dataState, setDataState] = useState<DataState>(DEFAULTS.dataState)
  const [capability, setCapability] = useState<Capability>(DEFAULTS.capability)
  const [contentScale, setContentScale] = useState<ContentScale>(DEFAULTS.contentScale)
  const [canvasWidth, setCanvasWidth] = useState<number | null>(DEFAULTS.canvasWidth)
  const [delayMs, setDelayMs] = useState(DEFAULTS.delayMs)
  const retryTimer = useRef<number | null>(null)

  const clearRetryTimer = () => {
    if (retryTimer.current !== null) {
      window.clearTimeout(retryTimer.current)
      retryTimer.current = null
    }
  }

  useEffect(() => clearRetryTimer, [])

  const retry = () => {
    clearRetryTimer()
    if (delayMs === 0) {
      setDataState('success')
      return
    }

    setDataState('loading')
    retryTimer.current = window.setTimeout(() => {
      setDataState('success')
      retryTimer.current = null
    }, delayMs)
  }

  const reset = () => {
    clearRetryTimer()
    setDataState(DEFAULTS.dataState)
    setCapability(DEFAULTS.capability)
    setContentScale(DEFAULTS.contentScale)
    setCanvasWidth(DEFAULTS.canvasWidth)
    setDelayMs(DEFAULTS.delayMs)
  }

  const content = CONTENT[contentScale]
  const canvasLabel = canvasWidth === null ? '自适应' : `${canvasWidth} px`

  return (
    <ThemeProvider colorMode="light" dayScheme="light">
      <div className={styles.primerRoot}>
        <header className={styles.header}>
          <div className={styles.shell}>
            <PageHeader as="div">
              <PageHeader.ContextArea hidden={false}>
                <Stack direction="horizontal" align="center" gap="condensed" wrap="wrap">
                  <Label variant="accent">Internal reference</Label>
                  <Link href="/" muted>
                    返回产品
                  </Link>
                </Stack>
              </PageHeader.ContextArea>
              <PageHeader.TitleArea variant="large">
                <PageHeader.LeadingVisual>
                  <BookIcon />
                </PageHeader.LeadingVisual>
                <PageHeader.Title as="h1">107 交互参考台</PageHeader.Title>
              </PageHeader.TitleArea>
              <PageHeader.Description>
                用真实 Primer 组件校准产品文案、权限边界、异步反馈和响应式组合。
              </PageHeader.Description>
            </PageHeader>
            <div className={styles.sourceLine}>
              <MarkGithubIcon aria-hidden="true" />
              <span>权威规范</span>
              <code>docs/product/ui-copy.md</code>
            </div>
          </div>
        </header>

        <Stack as="main" gap="spacious" className={`${styles.shell} ${styles.main}`}>
          <ScenarioToolbar
            dataState={dataState}
            capability={capability}
            contentScale={contentScale}
            canvasWidth={canvasWidth}
            delayMs={delayMs}
            onDataStateChange={setDataState}
            onCapabilityChange={setCapability}
            onContentScaleChange={setContentScale}
            onCanvasWidthChange={setCanvasWidth}
            onDelayChange={setDelayMs}
            onReset={reset}
          />

          <section aria-labelledby="live-preview-heading">
            <SectionHeading
              id="live-preview-heading"
              title="实时场景"
              description="控制条改变同一表面的输入条件；权限不足优先于请求状态。"
            />
            <div className={styles.stage}>
              <div
                className={styles.canvas}
                style={{ width: canvasWidth === null ? '100%' : `${canvasWidth}px` }}
                aria-label={`${canvasLabel} 参考画布`}
              >
                <div className={styles.ruler} aria-hidden="true">
                  <span>0</span>
                  <span>¼</span>
                  <strong>{canvasLabel}</strong>
                  <span>¾</span>
                  <span>1</span>
                </div>
                <div className={styles.canvasBody}>
                  <Stack direction="horizontal" align="center" gap="condensed" wrap="wrap">
                    <Label variant="accent">{canvasLabel}</Label>
                    <Label>
                      {capability === 'operate'
                        ? '可操作'
                        : capability === 'read'
                          ? '只读'
                          : '无权限'}
                    </Label>
                    <Label>
                      {contentScale === 'short'
                        ? '短内容'
                        : contentScale === 'long-name'
                          ? '长名称'
                          : '超长 ID'}
                    </Label>
                  </Stack>
                  <LivePreview
                    dataState={dataState}
                    capability={capability}
                    resourceName={content.resourceName}
                    requestId={content.requestId}
                    onRetry={retry}
                  />
                </div>
              </div>
            </div>
          </section>

          <section aria-labelledby="status-reference-heading">
            <SectionHeading
              id="status-reference-heading"
              title="状态参考"
              description="六类状态同时保留为稳定基线，不随实时场景控制条隐藏。"
            />
            <StatusGallery />
          </section>

          <section aria-labelledby="format-reference-heading">
            <SectionHeading
              id="format-reference-heading"
              title="信息与文案格式"
              description="标题说对象，按钮说动作；精确值可复制，相对信息只辅助浏览。"
            />
            <div className={styles.formatGrid}>
              <Card padding="normal">
                <Card.Metadata>标题</Card.Metadata>
                <Card.Heading as="h3">发布资源版本</Card.Heading>
                <Card.Description>使用对象或任务名称，末尾不加句号。</Card.Description>
              </Card>
              <Card padding="normal">
                <Card.Metadata>按钮</Card.Metadata>
                <Card.Heading as="h3">发布版本</Card.Heading>
                <Card.Description>使用“动作 + 对象”，避免“确定”或“处理”。</Card.Description>
              </Card>
              <Card padding="normal">
                <Card.Metadata>时间</Card.Metadata>
                <Card.Heading as="h3">2026-08-14 15:40:12</Card.Heading>
                <Card.Description>相对时间不能替代精确时间。</Card.Description>
              </Card>
              <Card padding="normal">
                <Card.Metadata>容量</Card.Metadata>
                <Card.Heading as="h3">2.4 GB</Card.Heading>
                <Card.Description>按 1024 进位，数值与单位之间保留空格。</Card.Description>
              </Card>
              <Card padding="normal">
                <Card.Metadata>请求标识</Card.Metadata>
                <Card.Heading as="h3" className={styles.breakableText}>
                  <code>req_01K2ZQM6WD7T4AW8</code>
                </Card.Heading>
                <Card.Description>视觉可截断，复制值保留完整内容。</Card.Description>
              </Card>
              <Card padding="normal">
                <Card.Metadata>版本</Card.Metadata>
                <Card.Heading as="h3">v3</Card.Heading>
                <Card.Description>使用后端提供的稳定标签，不自行发明 latest。</Card.Description>
              </Card>
            </div>
          </section>

          <section aria-labelledby="recipes-heading">
            <SectionHeading
              id="recipes-heading"
              title="组合范例"
              description="复制必要的 Primer 结构，再接入业务状态；不要复制参考页布局或模拟数据。"
            />
            <CompositionRecipes />
          </section>
        </Stack>
      </div>
    </ThemeProvider>
  )
}
