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
