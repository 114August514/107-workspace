import { Button, Select, Space, Typography, message } from 'antd'
import { useState } from 'react'

import { api } from '../../api/client'
import { can } from '../../api/types'
import type { Environment, LegacyWorkspaceContext } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { AsyncSection } from '../common/AsyncSection'

interface Props {
  workspace: LegacyWorkspaceContext
  onChanged: () => void
}

/**
 * Workspace 默认运行环境。
 *
 * Project 不显式选环境时就继承它；创建 Run 时必须解析出确定的 Environment
 * Version，否则提交前检查会拦下来。
 */
export function DefaultEnvironmentPicker({ workspace, onChanged }: Props) {
  const environments = useAsync<Environment[]>(() => api.environments(), [])
  const [selected, setSelected] = useState<string | undefined>(
    workspace.default_environment_version_id ?? undefined,
  )
  const [saving, setSaving] = useState(false)
  const canUpdate = can(workspace, 'user_group.update')

  const options = (environments.data ?? []).map((environment) => ({
    label: environment.name,
    options: environment.versions.map((version) => ({
      value: version.id,
      label: `${environment.name} · ${version.version}${version.available ? '' : '（不可用）'}`,
      disabled: !version.available,
    })),
  }))

  const save = async () => {
    if (!selected) return
    setSaving(true)
    try {
      await api.setLegacyDefaultEnvironment(workspace.id, selected)
      message.success('已更新默认运行环境')
      onChanged()
    } catch (error) {
      message.error((error as Error).message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <AsyncSection loading={environments.loading} error={environments.error}>
      <Space direction="vertical" size="small" style={{ width: '100%' }}>
        <Space wrap>
          <Select
            style={{ minWidth: 320 }}
            placeholder="选择默认运行环境"
            value={selected}
            onChange={setSelected}
            options={options}
            disabled={!canUpdate}
          />
          {canUpdate && (
            <Button
              type="primary"
              onClick={save}
              loading={saving}
              disabled={!selected || selected === workspace.default_environment_version_id}
            >
              保存
            </Button>
          )}
        </Space>
        <Typography.Text type="secondary">
          修改默认环境不会影响已经创建的 Run——它们按各自的运行快照执行。
        </Typography.Text>
      </Space>
    </AsyncSection>
  )
}
