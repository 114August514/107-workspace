export type DataState = 'normal' | 'loading' | 'empty' | 'error' | 'success'
export type Capability = 'operate' | 'read' | 'none'
export type ContentScale = 'short' | 'long-name' | 'long-id'

export interface ScenarioOption<T extends string> {
  value: T
  label: string
}

export const DATA_STATES: ScenarioOption<DataState>[] = [
  { value: 'normal', label: '正常' },
  { value: 'loading', label: 'Loading' },
  { value: 'empty', label: 'Empty' },
  { value: 'error', label: 'Error' },
  { value: 'success', label: 'Success' },
]

export const CAPABILITIES: ScenarioOption<Capability>[] = [
  { value: 'operate', label: '可操作' },
  { value: 'read', label: '只读' },
  { value: 'none', label: '无访问权限' },
]

export const CONTENT_SCALES: ScenarioOption<ContentScale>[] = [
  { value: 'short', label: '短内容' },
  { value: 'long-name', label: '长名称' },
  { value: 'long-id', label: '超长 ID' },
]

export const CONTENT = {
  short: {
    resourceName: 'imagenet-mini',
    requestId: 'req_01K2ZQ',
  },
  'long-name': {
    resourceName: 'imagenet-2026-competition-training-subset-with-verified-labels',
    requestId: 'req_01K2ZQM6WD7T4AW8',
  },
  'long-id': {
    resourceName: 'imagenet-subset',
    requestId: 'req_01K2ZQM6WD7T4AW8N9JH3C5P0R7B6Q2M8F4X1',
  },
} satisfies Record<ContentScale, { resourceName: string; requestId: string }>

export const EMPTY_RECIPE = `import { FileDirectoryIcon } from '@primer/octicons-react'
import { Blankslate } from '@primer/react/experimental'

<Blankslate narrow>
  <Blankslate.Visual>
    <FileDirectoryIcon size={24} />
  </Blankslate.Visual>
  <Blankslate.Heading>这里还没有共享资源。</Blankslate.Heading>
  <Blankslate.Description>
    创建共享资源后，可以在多个 Project 中复用同一份版本化内容。
  </Blankslate.Description>
  {canCreate ? (
    <Blankslate.PrimaryAction>创建共享资源</Blankslate.PrimaryAction>
  ) : null}
</Blankslate>`

export const ERROR_RECIPE = `import { Banner } from '@primer/react'

<Banner variant="critical">
  <Banner.Title>文件预览失败。</Banner.Title>
  <Banner.Description>
    请检查网络连接后重试。
  </Banner.Description>
  <Banner.PrimaryAction onClick={retry}>重试</Banner.PrimaryAction>
</Banner>`

export const DESTRUCTIVE_RECIPE = `import { Button, ConfirmationDialog } from '@primer/react'

<Button variant="danger" onClick={() => setOpen(true)}>
  删除 Project
</Button>
{open ? (
  <ConfirmationDialog
    title="删除 Project“mnist-train”？"
    confirmButtonContent="删除 Project"
    confirmButtonType="danger"
    cancelButtonContent="取消"
    onClose={() => setOpen(false)}
  >
    删除后，其当前文件、版本、分支、运行方案、Run 和从属运行产物将一并删除。
  </ConfirmationDialog>
) : null}`
