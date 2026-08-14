import { FileDirectoryIcon, TrashIcon } from '@primer/octicons-react'
import { Banner, Button, ConfirmationDialog, Label, Spinner, Stack } from '@primer/react'
import { Blankslate, Card, SkeletonText } from '@primer/react/experimental'
import { useState } from 'react'

import type { Capability, DataState } from './model'
import styles from './DesignSystemPage.module.css'

interface LivePreviewProps {
  dataState: DataState
  capability: Capability
  resourceName: string
  requestId: string
  onRetry: () => void
}

function EmptyExample({ canCreate }: { canCreate: boolean }) {
  return (
    <Blankslate narrow>
      <Blankslate.Visual>
        <FileDirectoryIcon size={24} />
      </Blankslate.Visual>
      <Blankslate.Heading as="h4">这里还没有共享资源。</Blankslate.Heading>
      <Blankslate.Description>
        {canCreate
          ? '创建共享资源后，可以在多个 Project 中复用同一份版本化内容。'
          : '当前 User Group 暂无可查看的共享资源。'}
      </Blankslate.Description>
      {canCreate ? <Blankslate.PrimaryAction>创建共享资源</Blankslate.PrimaryAction> : null}
    </Blankslate>
  )
}

function ErrorExample({ requestId, onRetry }: { requestId: string; onRetry: () => void }) {
  return (
    <Banner variant="critical">
      <Banner.Title>文件预览失败。</Banner.Title>
      <Banner.Description>
        <Stack gap="condensed">
          <span>请检查网络连接后重试。</span>
          <code className={styles.technicalValue} title={requestId}>
            请求标识：{requestId}
          </code>
        </Stack>
      </Banner.Description>
      <Banner.PrimaryAction onClick={onRetry}>重试</Banner.PrimaryAction>
    </Banner>
  )
}

export function LivePreview({
  dataState,
  capability,
  resourceName,
  requestId,
  onRetry,
}: LivePreviewProps) {
  if (capability === 'none') {
    return (
      <Banner variant="warning">
        <Banner.Title>无法查看这个共享资源。</Banner.Title>
        <Banner.Description>请确认你仍有访问权限。</Banner.Description>
      </Banner>
    )
  }

  if (dataState === 'loading') {
    return (
      <Stack gap="condensed" role="status">
        <Stack direction="horizontal" align="center" gap="condensed">
          <Spinner size="small" aria-label="正在加载共享资源" />
          <strong>正在加载共享资源…</strong>
        </Stack>
        <SkeletonText lines={3} size="bodyMedium" />
      </Stack>
    )
  }

  if (dataState === 'empty') {
    return <EmptyExample canCreate={capability === 'operate'} />
  }

  if (dataState === 'error') {
    return <ErrorExample requestId={requestId} onRetry={onRetry} />
  }

  if (dataState === 'success') {
    return (
      <Banner variant="success">
        <Banner.Title>版本已发布</Banner.Title>
        <Banner.Description>资源版本 v3 现在可以由 Project 引用。</Banner.Description>
      </Banner>
    )
  }

  return (
    <Card padding="normal">
      <Card.Metadata>
        <Stack direction="horizontal" align="center" gap="condensed" wrap="wrap">
          <Label variant="success">已发布</Label>
          {capability === 'read' ? <Label>只读</Label> : null}
        </Stack>
      </Card.Metadata>
      <Card.Heading as="h3" className={styles.breakableText}>
        {resourceName}
      </Card.Heading>
      <Card.Description>3 个版本 · 更新于 2026-08-14 15:40:12</Card.Description>
      {capability === 'operate' ? (
        <Card.Action>
          <Button size="small">发布版本</Button>
        </Card.Action>
      ) : null}
    </Card>
  )
}

function Specimen({
  label,
  title,
  description,
  children,
}: {
  label: string
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <Card
      as="section"
      padding="normal"
      className={styles.specimen}
      aria-label={`${label} 状态参考`}
    >
      <div className={styles.cardContent}>
        <Label>{label}</Label>
        <h3 className={styles.cardTitle}>{title}</h3>
        <p className={styles.cardDescription}>{description}</p>
        <div className={styles.specimenBody}>{children}</div>
      </div>
    </Card>
  )
}

export function StatusGallery() {
  const [deleteOpen, setDeleteOpen] = useState(false)

  return (
    <div className={styles.statusGrid}>
      <Specimen label="Loading" title="描述正在发生的动作" description="避免没有上下文的“加载中”。">
        <Stack gap="condensed" role="status">
          <Stack direction="horizontal" align="center" gap="condensed">
            <Spinner size="small" aria-label="正在加载共享资源" />
            <strong>正在加载共享资源…</strong>
          </Stack>
          <SkeletonText lines={3} size="bodyMedium" />
        </Stack>
      </Specimen>

      <Specimen
        label="Empty"
        title="只提供可执行的下一步"
        description="CTA 与当前用户能力保持一致。"
      >
        <EmptyExample canCreate />
      </Specimen>

      <Specimen label="Error" title="问题 + 下一步" description="请求标识保留为次级诊断信息。">
        <ErrorExample requestId="req_01K2ZQM6WD7T4AW8" onRetry={() => undefined} />
      </Specimen>

      <Specimen
        label="Success"
        title="说明已经产生的结果"
        description="不使用没有对象的“操作成功”。"
      >
        <Banner variant="success">
          <Banner.Title>版本已发布</Banner.Title>
          <Banner.Description>资源版本 v3 现在可以由 Project 引用。</Banner.Description>
        </Banner>
      </Specimen>

      <Specimen
        label="Permission"
        title="不猜测未确认的原因"
        description="无权限时不展示不可执行入口。"
      >
        <Banner variant="warning">
          <Banner.Title>无法发布这个版本。</Banner.Title>
          <Banner.Description>你当前没有发布共享资源版本的权限。</Banner.Description>
        </Banner>
      </Specimen>

      <Specimen
        label="Destructive"
        title="明确对象与真实后果"
        description="危险操作使用 Primer 确认对话框。"
      >
        <Button variant="danger" leadingVisual={TrashIcon} onClick={() => setDeleteOpen(true)}>
          删除 Project
        </Button>
        {deleteOpen ? (
          <ConfirmationDialog
            title="删除 Project“mnist-train”？"
            confirmButtonContent="删除 Project"
            confirmButtonType="danger"
            cancelButtonContent="取消"
            onClose={() => setDeleteOpen(false)}
          >
            删除后，其当前文件、版本、分支、运行方案、Run 和从属运行产物将一并删除。 由该 Project
            派生的其他 Project 和已经发布的独立资源不会受到影响。
          </ConfirmationDialog>
        ) : null}
      </Specimen>
    </div>
  )
}
