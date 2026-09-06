import { Banner, Button, Dialog, FormControl, Select } from '@primer/react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import type { Project, RunConfiguration } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { AsyncState } from '../common/AsyncState'

export function SubmitRunButton({
  project,
  onSubmit,
}: {
  project: Project
  onSubmit: (configuration: RunConfiguration) => void
}) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <Button variant="primary" onClick={() => setOpen(true)}>
        提交 Run
      </Button>
      {open && (
        <SelectConfiguration
          project={project}
          onClose={() => setOpen(false)}
          onSubmit={(configuration) => {
            setOpen(false)
            onSubmit(configuration)
          }}
        />
      )}
    </>
  )
}

function SelectConfiguration({
  project,
  onSubmit,
  onClose,
}: {
  project: Project
  onSubmit: (configuration: RunConfiguration) => void
  onClose: () => void
}) {
  const navigate = useNavigate()
  const configurations = useAsync(() => api.listRunConfigurations(project.id), [project.id])
  const [selected, setSelected] = useState(project.default_run_configuration_id ?? '')
  const items = configurations.data ?? []
  const configuration = items.find((item) => item.id === selected) ?? items[0]
  return (
    <Dialog
      title="提交 Run"
      onClose={onClose}
      footerButtons={[
        { content: '取消', onClick: onClose },
        {
          content: '继续',
          buttonType: 'primary',
          disabled: configurations.loading || !!configurations.error || !configuration,
          onClick: () => {
            if (configuration) onSubmit(configuration)
          },
        },
      ]}
    >
      <AsyncState
        loading={configurations.loading}
        loadingText="正在加载运行方案…"
        error={configurations.error ? { message: '无法加载运行方案。' } : undefined}
        onRetry={configurations.reload}
      >
        {items.length === 0 ? (
          <Banner variant="info">
            <Banner.Title>先创建一个运行方案</Banner.Title>
            <Banner.Description>保存程序的运行方式后，即可提交 Run。</Banner.Description>
            <Button
              onClick={() => {
                onClose()
                navigate(`/projects/${project.id}/runs/configurations`)
              }}
            >
              前往运行方案
            </Button>
          </Banner>
        ) : (
          <FormControl>
            <FormControl.Label>运行方案</FormControl.Label>
            <Select
              block
              value={configuration?.id ?? ''}
              onChange={(event) => setSelected(event.target.value)}
            >
              {items.map((item) => (
                <Select.Option key={item.id} value={item.id}>
                  {item.name}
                  {item.id === project.default_run_configuration_id ? '（默认）' : ''}
                </Select.Option>
              ))}
            </Select>
            <FormControl.Caption>下一步确认运行版本和输入。</FormControl.Caption>
          </FormControl>
        )}
      </AsyncState>
    </Dialog>
  )
}
