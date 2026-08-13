import { Alert, Select, Space, Table, Tag, Typography } from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useEffect, useMemo, useState } from 'react'

import { api } from '../../api/client'
import type { ChangeKind, ProjectVersionPage, VersionDiff } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { field } from '../../utils/field'

const CHANGE_LABEL: Record<ChangeKind, { text: string; color: string }> = {
  added: { text: '新增', color: 'green' },
  modified: { text: '修改', color: 'blue' },
  removed: { text: '删除', color: 'red' },
}

interface Props {
  projectId: string
  currentVersionId: string
  currentVersionSequence: number
}

/**
 * 版本比较：把当前版本和选定基准版本做文件级 Diff。
 *
 * 后端只提供文件级粒度（哪些文件增删改），不提供行级 Diff。
 */
export function VersionDiffPanel({ projectId, currentVersionId, currentVersionSequence }: Props) {
  const versions = useAsync<ProjectVersionPage>(async () => {
    // 拉取全部版本，确保较老版本的前序版本也在可选基准里。
    // 版本不可变，集合有界；循环到 has_more=false 即可。
    const all: ProjectVersionPage['items'] = []
    let page = 1
    let resp: ProjectVersionPage
    do {
      resp = await api.listVersions(projectId, { page, page_size: 100 })
      all.push(...resp.items)
      page += 1
    } while (resp.has_more)
    return { ...resp, items: all, has_more: false }
  }, [projectId])

  // 可选的基准版本：排除当前版本自身，按 sequence 降序
  const baseOptions = useMemo(() => {
    const all = versions.data?.items ?? []
    return all.filter((v) => v.id !== currentVersionId).sort((a, b) => b.sequence - a.sequence)
  }, [versions.data, currentVersionId])

  // 默认选当前版本的前一个版本
  const defaultBase = useMemo(() => {
    return baseOptions.find((v) => v.sequence < currentVersionSequence) ?? baseOptions[0] ?? null
  }, [baseOptions, currentVersionSequence])

  const [baseVersionId, setBaseVersionId] = useState<string | null>(null)

  useEffect(() => {
    if (baseVersionId === null && defaultBase) {
      setBaseVersionId(defaultBase.id)
    }
  }, [defaultBase, baseVersionId])

  const diff = useAsync<VersionDiff[]>(
    async () =>
      baseVersionId ? api.diffVersions(currentVersionId, baseVersionId) : Promise.resolve([]),
    [currentVersionId, baseVersionId],
  )

  const columns: ColumnsType<VersionDiff> = [
    {
      title: '变更',
      dataIndex: field<VersionDiff>('change'),
      width: 80,
      render: (change: ChangeKind) => (
        <Tag color={CHANGE_LABEL[change].color}>{CHANGE_LABEL[change].text}</Tag>
      ),
    },
    { title: '路径', dataIndex: field<VersionDiff>('path') },
  ]

  if (baseOptions.length === 0) {
    return <Alert type="info" showIcon message="这是第一个版本，没有可比较的历史版本" />
  }

  const diffData = diff.data ?? []

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Space>
        <Typography.Text>对比基准版本：</Typography.Text>
        <Select
          style={{ width: 200 }}
          value={baseVersionId ?? undefined}
          onChange={setBaseVersionId}
          options={baseOptions.map((v) => ({
            value: v.id,
            label: v.label,
          }))}
        />
      </Space>

      {diff.error && <Alert type="error" showIcon message={diff.error.message} />}

      {baseVersionId && !diff.loading && !diff.error && diffData.length === 0 && (
        <Alert type="success" showIcon message="两个版本内容完全相同" />
      )}

      {(diff.loading || diffData.length > 0) && (
        <Table
          rowKey="path"
          size="small"
          dataSource={diffData}
          columns={columns}
          pagination={false}
          loading={diff.loading}
        />
      )}
    </Space>
  )
}
