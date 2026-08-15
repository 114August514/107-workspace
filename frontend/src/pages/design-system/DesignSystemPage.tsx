import { BookIcon } from '@primer/octicons-react'
import { Label, Link, PageHeader, Stack } from '@primer/react'
import { Card } from '@primer/react/experimental'

import { PrimerRoot } from '../../primer/setup'
import { CompositionRecipes } from './CompositionRecipes'
import { StatusGallery } from './StatusExamples'
import styles from './DesignSystemPage.module.css'

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

function Foundations() {
  return (
    <div className={styles.formatGrid}>
      <Card padding="normal">
        <Card.Metadata>语气</Card.Metadata>
        <Card.Heading as="h3">简洁、中性、明确</Card.Heading>
        <Card.Description>
          从用户任务出发，主动语态和具体动词；不使用拟人化或娱乐化表达。
        </Card.Description>
      </Card>
      <Card padding="normal">
        <Card.Metadata>术语</Card.Metadata>
        <Card.Heading as="h3">共享资源 / 资源版本</Card.Heading>
        <Card.Description>
          同一概念在所有页面使用同一写法；不把 API 类型名当用户术语。
        </Card.Description>
      </Card>
      <Card padding="normal">
        <Card.Metadata>Token</Card.Metadata>
        <Card.Heading as="h3" className={styles.breakableText}>
          <code>var(--fgColor-muted)</code>
        </Card.Heading>
        <Card.Description>
          颜色、间距、圆角和字体使用 Primer Primitives，不复制 GitHub 色值。
        </Card.Description>
      </Card>
    </div>
  )
}

function ContentFormat() {
  return (
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
  )
}

export function DesignSystemPage() {
  return (
    <PrimerRoot>
      <div className={styles.page}>
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
              <PageHeader.TitleArea>
                <PageHeader.LeadingVisual>
                  <BookIcon />
                </PageHeader.LeadingVisual>
                <PageHeader.Title as="h1">107 Primer UI Reference</PageHeader.Title>
              </PageHeader.TitleArea>
              <PageHeader.Description>
                107 Workspace 实际采用的 Primer 状态、组合与文案基线，供迁移与 Review 对照。
              </PageHeader.Description>
            </PageHeader>
            <div className={styles.headerSource}>
              权威规范 <code>docs/product/ui-copy.md</code>
            </div>
          </div>
        </header>

        <Stack
          as="main"
          gap="spacious"
          paddingBlock={{ narrow: 'normal', regular: 'spacious' }}
          className={styles.shell}
        >
          <section aria-labelledby="foundations-heading">
            <SectionHeading
              id="foundations-heading"
              title="Foundations"
              description="语气、术语与 token 的使用边界，来自 docs/product/ui-copy.md 与 frontend/README.md。"
            />
            <Foundations />
          </section>

          <section aria-labelledby="states-heading">
            <SectionHeading
              id="states-heading"
              title="States"
              description="六类稳定状态参考，使用固定、可重复的示例；文案遵循 ui-copy.md 第四章。"
            />
            <StatusGallery />
          </section>

          <section aria-labelledby="patterns-heading">
            <SectionHeading
              id="patterns-heading"
              title="Patterns"
              description="跨页面复用的 Primer 组合：能力感知空态、可恢复错误与危险确认。"
            />
            <CompositionRecipes />
          </section>

          <section aria-labelledby="content-heading">
            <SectionHeading
              id="content-heading"
              title="Content"
              description="标题、按钮与时间、容量、ID、版本号的展示格式，来自 ui-copy.md 第三章与第五章。"
            />
            <ContentFormat />
          </section>
        </Stack>
      </div>
    </PrimerRoot>
  )
}
