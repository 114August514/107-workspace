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

import { BrandMark } from '../../brand/BrandMark'
import styles from './BrandReference.module.css'

const markSpecimenSizes: Array<{ size: 16 | 24 | 32; caption: string }> = [
  { size: 16, caption: '16px' },
  { size: 24, caption: '24px' },
  { size: 32, caption: '32px' },
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
            独立的产品识别层；最终 Mark 为 owner 确认的 107 小猪图形，不复刻校徽，无运行时的 Mark
            切换。
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

export function BrandMarkSpecimen() {
  return (
    <article className={styles.specimenCard} aria-label="107 Brand Mark 最终规格">
      <div className={styles.topbarSpecimen} aria-label="107 Brand Mark TopBar 示例">
        <BrandMark size={32} decorative />
        <span className={styles.wordmark}>107 Workspace</span>
        <span className={styles.topbarMeta}>neutral TopBar</span>
      </div>

      <div className={styles.sizeSamples} aria-label="107 Brand Mark 小尺寸样本">
        {markSpecimenSizes.map(({ size, caption }) => (
          <figure key={size} className={styles.sizeSample}>
            <span className={styles.sizeCanvas}>
              <BrandMark size={size} label={`107 Brand Mark，${size} 像素`} />
            </span>
            <figcaption>{caption}</figcaption>
          </figure>
        ))}
      </div>
    </article>
  )
}

export function ColorOwnership() {
  return (
    <div className={styles.colorLayout}>
      <div className={styles.paletteGrid} aria-label="107 current monochrome color roles">
        <ColorSwatch
          name="primary"
          value="var(--fgColor-default)"
          className={styles.primarySwatch}
        />
        <ColorSwatch
          name="primary hover"
          value="var(--fgColor-muted)"
          className={styles.hoverSwatch}
        />
        <ColorSwatch
          name="on primary"
          value="var(--bgColor-default)"
          className={styles.onPrimarySwatch}
        />
        <ColorSwatch name="subtle" value="var(--bgColor-muted)" className={styles.subtleSwatch} />
        <ColorSwatch
          name="foreground"
          value="var(--fgColor-default)"
          className={styles.foregroundSwatch}
        />
        <ColorSwatch
          name="border"
          value="var(--borderColor-default)"
          className={styles.borderSwatch}
        />
      </div>

      <Card padding="normal">
        <Stack gap="condensed">
          <Heading as="h3" variant="small">
            色彩职责
          </Heading>
          <Text as="p" className={styles.mutedText}>
            官方标准色的权威输入仍为 CMYK C100 M80 Y0 K0；当前 Brand Mark 与 active UI
            采用黑白灰：图形本身只使用 黑色填充与透明负空间；灰色由 Primer neutral 与 state tokens
            负责。蓝白配色保留在品牌参考文档中，作为后续 调研候选，不进入当前 UI。
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
