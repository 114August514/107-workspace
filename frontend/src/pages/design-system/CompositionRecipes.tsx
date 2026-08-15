import { CheckIcon, CopyIcon, FileDirectoryIcon } from '@primer/octicons-react'
import { Banner, Button, ConfirmationDialog, Stack } from '@primer/react'
import { Blankslate, Card, InlineMessage } from '@primer/react/experimental'
import { useState } from 'react'

import { DESTRUCTIVE_RECIPE, EMPTY_RECIPE, ERROR_RECIPE } from './model'
import styles from './DesignSystemPage.module.css'

type CopyState = 'idle' | 'copied' | 'error'

function Recipe({
  title,
  description,
  code,
  children,
}: {
  title: string
  description: string
  code: string
  children: React.ReactNode
}) {
  const [copyState, setCopyState] = useState<CopyState>('idle')

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopyState('copied')
    } catch {
      setCopyState('error')
    }
  }

  return (
    <Card as="section" padding="normal" className={styles.recipe} aria-label={title}>
      <div className={styles.cardContent}>
        <h3 className={styles.cardTitle}>{title}</h3>
        <p className={styles.cardDescription}>{description}</p>
        <div className={styles.recipePreview}>{children}</div>
        <div className={styles.codeBlockWrap}>
          <pre className={styles.codeBlock} tabIndex={0}>
            <code>{code}</code>
          </pre>
          <button
            type="button"
            className={styles.copyButton}
            data-copied={copyState === 'copied'}
            aria-label={copyState === 'copied' ? '已复制' : `复制${title}代码`}
            onClick={copyCode}
          >
            {copyState === 'copied' ? <CheckIcon /> : <CopyIcon />}
          </button>
        </div>
        <div className={styles.copyFeedback} aria-live="polite">
          {copyState === 'copied' ? (
            <InlineMessage variant="success">代码已复制</InlineMessage>
          ) : null}
          {copyState === 'error' ? (
            <InlineMessage variant="critical">复制失败，请从代码区域手动复制。</InlineMessage>
          ) : null}
        </div>
      </div>
    </Card>
  )
}

export function CompositionRecipes() {
  const [deleteOpen, setDeleteOpen] = useState(false)

  return (
    <Stack gap="normal">
      <Recipe
        title="能力感知空态"
        description="只有用户具备创建能力时才展示主操作。"
        code={EMPTY_RECIPE}
      >
        <Blankslate narrow>
          <Blankslate.Visual>
            <FileDirectoryIcon size={24} />
          </Blankslate.Visual>
          <Blankslate.Heading as="h4">这里还没有共享资源。</Blankslate.Heading>
          <Blankslate.Description>
            创建共享资源后，可以在多个 Project 中复用同一份版本化内容。
          </Blankslate.Description>
          <Blankslate.PrimaryAction>创建共享资源</Blankslate.PrimaryAction>
        </Blankslate>
      </Recipe>

      <Recipe
        title="可恢复错误"
        description="主要提示表达问题和下一步，诊断信息不抢占层级。"
        code={ERROR_RECIPE}
      >
        <Banner variant="critical">
          <Banner.Title>文件预览失败。</Banner.Title>
          <Banner.Description>请检查网络连接后重试。</Banner.Description>
          <Banner.PrimaryAction>重试</Banner.PrimaryAction>
        </Banner>
      </Recipe>

      <Recipe
        title="危险确认"
        description="按钮、标题和确认操作始终使用同一个动作名称。"
        code={DESTRUCTIVE_RECIPE}
      >
        <Button variant="danger" onClick={() => setDeleteOpen(true)}>
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
            删除后，其当前文件、版本、分支、运行方案、Run 和从属运行产物将一并删除。
          </ConfirmationDialog>
        ) : null}
      </Recipe>
    </Stack>
  )
}
