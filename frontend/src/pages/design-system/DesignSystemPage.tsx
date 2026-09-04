import { ArrowLeftIcon, BookIcon } from '@primer/octicons-react'
import { Heading, IconButton, PageHeader, Stack, Text } from '@primer/react'
import { Card } from '@primer/react/experimental'

import {
  BrandMarkSpecimen,
  ColorOwnership,
  IdentityBoundary,
  ProductIconMapping,
} from './BrandReference'
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
      <Heading as="h2" variant="medium" id={id} className={styles.sectionTitle}>
        {title}
      </Heading>
      <p className={styles.sectionDescription}>{description}</p>
    </div>
  )
}

function Foundations() {
  return (
    <div className={styles.formatGrid}>
      <Card padding="normal">
        <Stack gap="condensed">
          <Heading as="h3" variant="small">
            语气
          </Heading>
          <Text as="div" weight="semibold">
            简洁、中性、明确
          </Text>
          <Text as="div" className={styles.mutedText}>
            从用户任务出发，主动语态和具体动词；不使用拟人化或娱乐化表达。
          </Text>
        </Stack>
      </Card>
      <Card padding="normal">
        <Stack gap="condensed">
          <Heading as="h3" variant="small">
            术语
          </Heading>
          <Text as="div" weight="semibold">
            共享资源 / 资源版本
          </Text>
          <Text as="div" className={styles.mutedText}>
            同一概念在所有页面使用同一写法；不把 API 类型名当用户术语。
          </Text>
        </Stack>
      </Card>
      <Card padding="normal">
        <Stack gap="condensed">
          <Heading as="h3" variant="small">
            Token
          </Heading>
          <Text as="div" weight="semibold" className={styles.breakableText}>
            <code>var(--fgColor-muted)</code>
          </Text>
          <Text as="div" className={styles.mutedText}>
            颜色、间距、圆角和字体使用 Primer Primitives，不复制 GitHub 色值。
          </Text>
        </Stack>
      </Card>
    </div>
  )
}

function FormatCard({
  subject,
  title,
  description,
}: {
  subject: string
  title: React.ReactNode
  description: string
}) {
  return (
    <Card padding="normal">
      <Stack gap="condensed">
        <Heading as="h3" variant="small">
          {subject}
        </Heading>
        <Text as="div" weight="semibold" className={styles.breakableText}>
          {title}
        </Text>
        <Text as="div" className={styles.mutedText}>
          {description}
        </Text>
      </Stack>
    </Card>
  )
}

function ContentFormat() {
  return (
    <div className={styles.formatGrid}>
      <FormatCard
        subject="标题"
        title="发布资源版本"
        description="使用对象或任务名称，末尾不加句号。"
      />
      <FormatCard
        subject="按钮"
        title="发布版本"
        description="使用“动作 + 对象”，避免“确定”或“处理”。"
      />
      <FormatCard
        subject="时间"
        title="2026-08-14 15:40:12"
        description="相对时间不能替代精确时间。"
      />
      <FormatCard
        subject="容量"
        title="2.4 GB"
        description="按 1024 进位，数值与单位之间保留空格。"
      />
      <FormatCard
        subject="请求标识"
        title={<code className={styles.breakableText}>req_01K2ZQM6WD7T4AW8</code>}
        description="视觉可截断，复制值保留完整内容。"
      />
      <FormatCard
        subject="版本"
        title="v3"
        description="使用后端提供的稳定标签，不自行发明 latest。"
      />
    </div>
  )
}

export function DesignSystemPage() {
  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.shell}>
          <PageHeader as="div">
            <PageHeader.ContextArea>
              <PageHeader.ParentLink href="/">107 Workspace</PageHeader.ParentLink>
            </PageHeader.ContextArea>
            <PageHeader.LeadingAction>
              <IconButton
                as="a"
                href="/"
                icon={ArrowLeftIcon}
                variant="invisible"
                aria-label="返回产品"
              />
            </PageHeader.LeadingAction>
            <PageHeader.TitleArea>
              <PageHeader.LeadingVisual>
                <BookIcon />
              </PageHeader.LeadingVisual>
              <PageHeader.Title as="h1">107 Primer UI Reference</PageHeader.Title>
            </PageHeader.TitleArea>
            <PageHeader.Description>
              <div className={styles.headerDescription}>
                <span>
                  107 Workspace 实际采用的 Primer 状态、组合与文案基线，供迁移与 Review 对照。
                </span>
                <span className={styles.headerSource}>
                  规范来源：<code>docs/product/ui-copy.md</code>{' '}
                  <span className={styles.sourceItem}>
                    <span aria-hidden="true">·</span> <code>frontend/README.md</code>{' '}
                    <span aria-hidden="true">·</span> <code>docs/references/brand/ustc-vis.md</code>
                  </span>
                </span>
              </div>
            </PageHeader.Description>
          </PageHeader>
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

        <section aria-labelledby="brand-identity-heading">
          <SectionHeading
            id="brand-identity-heading"
            title="Brand"
            description="区分 USTC 学校归属、107 产品身份与 Primer 功能图标。"
          />
          <IdentityBoundary />
        </section>

        <section aria-labelledby="brand-marks-heading">
          <SectionHeading
            id="brand-marks-heading"
            title="Marks"
            description="最终 107 Brand Mark 在 neutral TopBar 与 16 / 24 / 32 px 样本中的呈现；所有尺寸复用同一份 SVG 资源。"
          />
          <BrandMarkSpecimen />
        </section>

        <section aria-labelledby="brand-colors-heading">
          <SectionHeading
            id="brand-colors-heading"
            title="Colors"
            description="官方 CMYK 输入、107 web adaptation 与 Primer semantic colors 的职责边界。"
          />
          <ColorOwnership />
        </section>

        <section aria-labelledby="brand-icons-heading">
          <SectionHeading
            id="brand-icons-heading"
            title="Icons"
            description="真实产品对象优先使用 Primer Octicons；Brand Mark 不充当功能或状态图标。"
          />
          <ProductIconMapping />
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
  )
}
