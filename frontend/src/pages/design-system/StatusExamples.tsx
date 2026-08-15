import { TrashIcon } from '@primer/octicons-react'
import { Banner, Button, ConfirmationDialog, Spinner, Stack } from '@primer/react'
import { Card, SkeletonText } from '@primer/react/experimental'
import { useState } from 'react'

import { AsyncState } from '../../components/common/AsyncState'
import styles from './DesignSystemPage.module.css'

function Specimen({
  title,
  description,
  children,
}: {
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <Card
      as="section"
      padding="normal"
      className={styles.specimen}
      aria-label={`${title} 状态参考`}
    >
      <div className={styles.cardContent}>
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
      <Specimen title="加载中" description="描述正在发生的动作，避免没有上下文的“加载中”。">
        <Stack gap="condensed" role="status">
          <Stack direction="horizontal" align="center" gap="condensed">
            <Spinner size="small" aria-label="正在加载共享资源" />
            <strong>正在加载共享资源…</strong>
          </Stack>
          <SkeletonText lines={3} size="bodyMedium" />
        </Stack>
      </Specimen>

      <Specimen
        title="空态"
        description="共享 AsyncState 组件的空态；Blankslate 能力感知空态见 Patterns。"
      >
        <AsyncState loading={false} empty emptyText="这里还没有共享资源。">
          内容
        </AsyncState>
      </Specimen>

      <Specimen
        title="错误"
        description="共享 AsyncState 组件的错误态：问题逐条展示，请求标识次级保留。"
      >
        <AsyncState
          loading={false}
          error={{
            message: '无法发布这个版本。',
            problems: ['文件 list.txt 已存在', '说明过长'],
            requestId: 'req_01K2ZQM6WD7T4AW8',
          }}
        >
          内容
        </AsyncState>
      </Specimen>

      <Specimen title="成功" description="说明已经产生的结果，不使用没有对象的“操作成功”。">
        <Banner variant="success">
          <Banner.Title>版本已发布</Banner.Title>
          <Banner.Description>资源版本 v3 现在可以由 Project 引用。</Banner.Description>
        </Banner>
      </Specimen>

      <Specimen title="权限" description="不猜测未确认的原因，无权限时不展示不可执行入口。">
        <Banner variant="warning">
          <Banner.Title>无法发布这个版本。</Banner.Title>
          <Banner.Description>你当前没有发布共享资源版本的权限。</Banner.Description>
        </Banner>
      </Specimen>

      <Specimen title="危险操作" description="明确对象与真实后果，危险操作使用 Primer 确认对话框。">
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
