import { Button, Popconfirm, Space, Tabs, Tag, Typography, message } from 'antd'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { can } from '../api/types'
import type { Project, ProjectVersionDetail } from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncSection } from '../components/common/AsyncSection'
import { PageHeader } from '../components/layout/PageHeader'
import { Stack } from '../components/layout/Stack'
import { ForkModal } from '../components/project/ForkModal'
import { VersionDiffPanel } from '../components/project/VersionDiffPanel'
import { VersionFileBrowser } from '../components/project/VersionFileBrowser'
import { RunFromVersionModal } from '../components/run/RunFromVersionModal'
import { formatBytes, formatTime } from '../utils/format'

export function VersionDetailPage() {
  const { versionId = '' } = useParams()
  const navigate = useNavigate()
  const [forking, setForking] = useState(false)
  const [running, setRunning] = useState(false)

  const version = useAsync<ProjectVersionDetail>(() => api.getVersion(versionId), [versionId])
  const project = useAsync<Project | undefined>(
    async () => (version.data ? api.getProject(version.data.project_id) : undefined),
    [version.data?.project_id],
  )

  const canWrite = can(project.data, 'project.content.write')
  const canRun = can(project.data, 'run.submit')

  const restore = async () => {
    if (!version.data || !project.data) return
    try {
      await api.restoreVersion(versionId)
      message.success(`已恢复到 ${version.data.label}`)
      navigate(`/projects/${version.data.project_id}`)
    } catch (error) {
      message.error((error as Error).message)
    }
  }

  return (
    <Stack gap="large">
      <AsyncSection loading={version.loading} error={version.error}>
        {version.data && project.data && (
          <PageHeader
            breadcrumb={[
              { title: <Link to="/">首页</Link> },
              {
                title:
                  project.data.owner.kind === 'user_group' ? (
                    <Link to={`/user-groups/${project.data.owner.id}`}>
                      {project.data.owner.display_name}
                    </Link>
                  ) : (
                    project.data.owner.display_name
                  ),
              },
              {
                title: <Link to={`/projects/${project.data.id}`}>{project.data.name}</Link>,
              },
              { title: `Version ${version.data.label}` },
            ]}
            title={version.data.label}
            tags={<Tag color="geekblue">不可变版本</Tag>}
            description={version.data.message}
            actions={
              <Space>
                {canRun && (
                  <Button type="primary" onClick={() => setRunning(true)}>
                    运行此版本
                  </Button>
                )}
                {canWrite && (
                  <Popconfirm
                    title={`把工作区恢复到 ${version.data.label}？`}
                    description="当前未保存的修改会被覆盖。历史版本本身不受影响。"
                    okText="恢复"
                    cancelText="取消"
                    onConfirm={restore}
                  >
                    <Button>恢复到此版本</Button>
                  </Popconfirm>
                )}
                {/*
                  派生只需要能看见这个版本，不需要对当前空间有写权限。
                  写权限是目标空间的事，由后端和弹窗里的空间列表一起把关。
                */}
                <Button onClick={() => setForking(true)}>派生</Button>
              </Space>
            }
          />
        )}
      </AsyncSection>

      {version.data && (
        <Stack>
          <AsyncSection loading={version.loading} error={version.error}>
            <Space size="large">
              <Typography.Text type="secondary">创建人：{version.data.created_by}</Typography.Text>
              <Typography.Text type="secondary">
                保存时间：{formatTime(version.data.created_at)}
              </Typography.Text>
              <Typography.Text type="secondary">文件数：{version.data.file_count}</Typography.Text>
              <Typography.Text type="secondary">
                总大小：{formatBytes(version.data.total_size)}
              </Typography.Text>
            </Space>
          </AsyncSection>

          <Tabs
            defaultActiveKey="files"
            items={[
              {
                key: 'files',
                label: '文件',
                children: <VersionFileBrowser versionId={versionId} files={version.data.files} />,
              },
              {
                key: 'diff',
                label: '版本比较',
                children: (
                  <VersionDiffPanel
                    projectId={version.data.project_id}
                    currentVersionId={versionId}
                    currentVersionSequence={version.data.sequence}
                  />
                ),
              },
            ]}
          />
        </Stack>
      )}

      {version.data && (
        <>
          <RunFromVersionModal
            open={running}
            versionId={versionId}
            versionLabel={version.data.label}
            projectId={version.data.project_id}
            defaultRunConfigurationId={project.data?.default_run_configuration_id ?? null}
            onClose={() => setRunning(false)}
            onSubmitted={(run) => navigate(`/runs/${run.id}`)}
          />
          <ForkModal
            open={forking}
            version={version.data}
            sourceProjectName={project.data?.name ?? ''}
            onClose={() => setForking(false)}
            onForked={(p) => navigate(`/projects/${p.id}`)}
          />
        </>
      )}
    </Stack>
  )
}
