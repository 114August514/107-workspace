import {
  BellIcon,
  GearIcon,
  OrganizationIcon,
  PackageIcon,
  PlayIcon,
  PlusIcon,
  ProjectIcon,
} from '@primer/octicons-react'
import { Button, Heading, Label, Link, Stack, Text } from '@primer/react'
import { Card } from '@primer/react/experimental'
import type { ComponentType } from 'react'

import { BrandMark, type BrandMarkCandidate } from '../../brand/BrandMark'
import styles from './BrandReference.module.css'

const candidates: Array<{
  id: BrandMarkCandidate
  name: string
  description: string
}> = [
  {
    id: 1,
    name: '候选 1 · 开放数字',
    description: '最少笔画的 107 几何表达；透明底，在中性界面中最克制。',
  },
  {
    id: 2,
    name: '候选 2 · 节点连接（image2）',
    description: '用一条带端点的计算节点轨道包住 107；轮廓化表达比候选 1 更强调 compute。',
  },
  {
    id: 3,
    name: '候选 3 · 数字方章',
    description: '将 107 置于有限品牌色块；favicon 识别最强，但在 TopBar 中也最醒目。',
  },
]

const iconMappings: Array<{
  subject: string
  icon: ComponentType<{ size?: number; 'aria-hidden'?: boolean }>
  rationale: string
}> = [
  { subject: 'Project', icon: ProjectIcon, rationale: '项目与版本化工作入口' },
  { subject: 'User Group', icon: OrganizationIcon, rationale: '成员与协作边界' },
  { subject: 'Run', icon: PlayIcon, rationale: '发起或查看一次执行' },
  { subject: '共享资源', icon: PackageIcon, rationale: '可复用的数据或资源版本' },
  { subject: '通知', icon: BellIcon, rationale: '全局通知入口' },
  { subject: '设置', icon: GearIcon, rationale: '对象设置与治理' },
  { subject: '创建', icon: PlusIcon, rationale: '创建当前上下文中的对象' },
]

export function IdentityBoundary() {
  return (
    <div className={styles.identityGrid}>
      <Card padding="normal">
        <Stack gap="condensed">
          <Heading as="h3" variant="small">
            USTC affiliation
          </Heading>
          <Text as="div" weight="semibold">
            官方校徽 / 校名 / 学校归属
          </Text>
          <Text as="p" className={styles.mutedText}>
            只使用官方原始资产与规定组合；不裁切、改色、拆解或改造成 107 产品图标。
          </Text>
          <Link
            href="https://djyszw.ustc.edu.cn/info/1070/6829.htm"
            target="_blank"
            rel="noreferrer"
          >
            USTC 官方 VIS 来源
          </Link>
        </Stack>
      </Card>
      <Card padding="normal">
        <Stack gap="condensed">
          <Heading as="h3" variant="small">
            107 product identity
          </Heading>
          <Text as="div" weight="semibold">
            Brand Mark / 107 Workspace / App Icon
          </Text>
          <Text as="p" className={styles.mutedText}>
            独立的产品识别层；只使用数字与计算母题，不复刻校徽。当前候选仅供人工视觉门选择。
          </Text>
        </Stack>
      </Card>
      <Card padding="normal">
        <Stack gap="condensed">
          <Heading as="h3" variant="small">
            Product and status icons
          </Heading>
          <Text as="div" weight="semibold">
            Primer Octicons
          </Text>
          <Text as="p" className={styles.mutedText}>
            功能与状态继续使用成熟图标和语义色；Brand Mark 不承担状态或操作含义。
          </Text>
        </Stack>
      </Card>
    </div>
  )
}

export function MarkCandidates() {
  return (
    <div className={styles.candidateGrid} aria-label="107 Brand Mark 候选对比">
      {candidates.map((candidate) => (
        <article
          key={candidate.id}
          className={styles.candidateCard}
          aria-labelledby={`mark-${candidate.id}`}
        >
          <div className={styles.candidateHeading}>
            <Heading as="h3" variant="small" id={`mark-${candidate.id}`}>
              {candidate.name}
            </Heading>
            <Label variant={candidate.id === 1 ? 'accent' : 'secondary'}>
              {candidate.id === 1 ? '建议起点' : '待比较'}
            </Label>
          </div>
          <p className={styles.mutedText}>{candidate.description}</p>

          <div className={styles.topbarSpecimen} aria-label={`${candidate.name} TopBar 示例`}>
            <BrandMark candidate={candidate.id} size={24} decorative />
            <span className={styles.wordmark}>107 Workspace</span>
            <span className={styles.topbarMeta}>neutral TopBar</span>
          </div>

          <div className={styles.sizeSamples} aria-label={`${candidate.name} 小尺寸样本`}>
            {([16, 24, 32] as const).map((size) => (
              <figure key={size} className={styles.sizeSample}>
                <span className={styles.sizeCanvas}>
                  <BrandMark
                    candidate={candidate.id}
                    size={size}
                    label={`${candidate.name}，${size} 像素`}
                  />
                </span>
                <figcaption>{size}px</figcaption>
              </figure>
            ))}
          </div>
        </article>
      ))}
    </div>
  )
}

export function ColorOwnership() {
  return (
    <div className={styles.colorLayout}>
      <div className={styles.paletteGrid} aria-label="107 provisional web color samples">
        <ColorSwatch name="primary" value="#0057B8" className={styles.primarySwatch} />
        <ColorSwatch name="primary hover" value="#00458F" className={styles.hoverSwatch} />
        <ColorSwatch name="on primary" value="#FFFFFF" className={styles.onPrimarySwatch} />
        <ColorSwatch name="subtle" value="#DDEBFF" className={styles.subtleSwatch} />
        <ColorSwatch name="foreground" value="#003B78" className={styles.foregroundSwatch} />
        <ColorSwatch name="border" value="#4F83BE" className={styles.borderSwatch} />
      </div>

      <Card padding="normal">
        <Stack gap="condensed">
          <Heading as="h3" variant="small">
            色彩职责
          </Heading>
          <Text as="p" className={styles.mutedText}>
            官方标准色的权威输入是 CMYK C100 M80 Y0 K0；上方 HEX 是 107 Workspace
            为屏幕与可访问性选择的临时 web adaptation，不是官方 USTC HEX。
          </Text>
          <div className={styles.semanticRow} aria-label="Primer semantic colors remain distinct">
            <Label variant="success">成功</Label>
            <Label variant="attention">警告</Label>
            <Label variant="danger">危险</Label>
            <span className={styles.semanticNote}>继续由 Primer semantic tokens 负责</span>
          </div>
        </Stack>
      </Card>

      <Card padding="normal">
        <Stack gap="condensed">
          <Heading as="h3" variant="small">
            Brand-aware affordances
          </Heading>
          <div className={styles.affordanceRow}>
            <a href="#brand-colors-heading" className={styles.brandLink}>
              品牌链接
            </a>
            <a
              href="#brand-colors-heading"
              className={styles.selectedNavigation}
              aria-current="page"
            >
              已选导航
            </a>
            <button type="button" className={styles.focusSpecimen}>
              Focus 示例
            </button>
            <Button className={styles.brandPrimaryButton}>主要操作</Button>
          </div>
          <Text as="p" className={styles.mutedText}>
            neutral canvas、正文、边框与状态色仍使用 Primer；品牌色只进入少量识别和高意图状态。
          </Text>
        </Stack>
      </Card>
    </div>
  )
}

function ColorSwatch({
  name,
  value,
  className,
}: {
  name: string
  value: string
  className?: string
}) {
  return (
    <div className={styles.swatch}>
      <span
        className={[styles.swatchColor, className].filter(Boolean).join(' ')}
        aria-hidden="true"
      />
      <span className={styles.swatchName}>{name}</span>
      <code>{value}</code>
    </div>
  )
}

export function ProductIconMapping() {
  return (
    <div className={styles.iconGrid} aria-label="产品对象 Octicon mapping">
      {iconMappings.map(({ subject, icon: Icon, rationale }) => (
        <Card key={subject} padding="normal">
          <div className={styles.iconCard}>
            <span className={styles.iconVisual} aria-hidden="true">
              <Icon size={24} />
            </span>
            <span>
              <strong>{subject}</strong>
              <span className={styles.iconRationale}>{rationale}</span>
            </span>
          </div>
        </Card>
      ))}
    </div>
  )
}
