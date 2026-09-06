import {
  ActionList,
  Banner,
  Button,
  FormControl,
  Select,
  SegmentedControl,
  Textarea,
  TextInput,
} from '@primer/react'
import { useState, type ReactNode } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { api } from '../../api/client'
import { can, type Project } from '../../api/types'
import { ProjectSecretsPanel } from './ProjectSecretsPanel'
import { ProjectVariablesPanel } from './ProjectVariablesPanel'
import styles from './projectSettingsPanel.module.css'

interface Props {
  projectId: string
  access: Project | undefined
  onChanged?: () => void
  deletion?: ReactNode
}

export function ProjectSettingsPanel({ projectId, access, onChanged, deletion }: Props) {
  const [params, setParams] = useSearchParams()
  const [variableTab, setVariableTab] = useState<'variables' | 'secrets'>('variables')
  const section = params.get('section') === 'variables' ? 'variables' : 'general'
  const selectSection = (value: string) => setParams(value === 'general' ? {} : { section: value })
  return (
    <div className={styles.layout}>
      <nav className={styles.navigation} aria-label="Project 设置分区">
        <ActionList>
          <ActionList.LinkItem as={Link} to="?section=general" active={section === 'general'}>
            常规
          </ActionList.LinkItem>
          <ActionList.LinkItem as={Link} to="?section=variables" active={section === 'variables'}>
            环境变量
          </ActionList.LinkItem>
        </ActionList>
      </nav>
      <FormControl className={styles.mobileNavigation}>
        <FormControl.Label>设置分区</FormControl.Label>
        <Select block value={section} onChange={(event) => selectSection(event.target.value)}>
          <Select.Option value="general">常规</Select.Option>
          <Select.Option value="variables">环境变量</Select.Option>
        </Select>
      </FormControl>
      <div className={styles.content}>
        {section === 'general' ? (
          <>
            {access && <GeneralSettings key={projectId} project={access} onChanged={onChanged} />}
            {deletion}
          </>
        ) : can(access, 'config.view') ? (
          <>
            <header className={styles.section}>
              <h2 className={styles.paneTitle}>环境变量</h2>
              <p className={styles.sectionDescription}>
                用于运行时注入的变量；密码、令牌等请使用敏感变量。
              </p>
            </header>
            <SegmentedControl
              aria-label="环境变量类型"
              className={styles.segments}
              onChange={(index) => setVariableTab(index === 0 ? 'variables' : 'secrets')}
            >
              <SegmentedControl.Button
                selected={variableTab === 'variables'}
                aria-controls="project-variables"
              >
                Variables
              </SegmentedControl.Button>
              <SegmentedControl.Button
                selected={variableTab === 'secrets'}
                aria-controls="project-secrets"
              >
                Secrets
              </SegmentedControl.Button>
            </SegmentedControl>
            {variableTab === 'variables' ? (
              <ProjectVariablesPanel projectId={projectId} access={access} onChanged={onChanged} />
            ) : (
              <ProjectSecretsPanel projectId={projectId} access={access} onChanged={onChanged} />
            )}
          </>
        ) : (
          <p>你没有查看此 Project 环境变量的权限。</p>
        )}
      </div>
    </div>
  )
}

function GeneralSettings({ project, onChanged }: { project: Project; onChanged?: () => void }) {
  const [name, setName] = useState(project.name)
  const [description, setDescription] = useState(project.description)
  const [visibility, setVisibility] = useState(project.visibility)
  const [busy, setBusy] = useState(false)
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string }>()
  const editable = can(project, 'project.update')
  const submit = async () => {
    if (busy || !editable) return
    if (!name.trim()) {
      setFeedback({ ok: false, text: '名称不能为空。' })
      return
    }
    setBusy(true)
    setFeedback(undefined)
    try {
      await api.updateProject(project.id, {
        name: name.trim(),
        description: description.trim(),
        visibility,
      })
      setFeedback({ ok: true, text: 'Project 设置已保存。' })
      onChanged?.()
    } catch (error) {
      setFeedback({
        ok: false,
        text: error instanceof Error ? error.message : '保存失败，请重试。',
      })
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <section className={styles.section} aria-labelledby="project-general-title">
        <h2 id="project-general-title" className={styles.paneTitle}>
          基本信息
        </h2>
        <p className={styles.sectionDescription}>修改 Project 的名称、说明与可见范围。</p>
        {feedback && (
          <Banner variant={feedback.ok ? 'success' : 'critical'}>
            <Banner.Title>{feedback.text}</Banner.Title>
          </Banner>
        )}
        <form
          className={styles.form}
          onSubmit={(event) => {
            event.preventDefault()
            void submit()
          }}
        >
          <FormControl required disabled={!editable || busy}>
            <FormControl.Label>名称</FormControl.Label>
            <TextInput
              block
              value={name}
              maxLength={128}
              onChange={(event) => setName(event.target.value)}
            />
          </FormControl>
          <FormControl disabled={!editable || busy}>
            <FormControl.Label>说明</FormControl.Label>
            <Textarea
              block
              rows={4}
              resize="vertical"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
            />
          </FormControl>
          <FormControl disabled={!editable || busy}>
            <FormControl.Label>可见范围</FormControl.Label>
            <Select
              block
              value={visibility}
              onChange={(event) => setVisibility(event.target.value as Project['visibility'])}
            >
              <Select.Option value="owner_scope">
                {project.owner.kind === 'user' ? '仅自己' : '仅所属 User Group'}
              </Select.Option>
              <Select.Option value="public">平台公开</Select.Option>
            </Select>
            <FormControl.Caption>
              平台公开后，已登录用户可以查看已保存版本并
              Fork；不会获得暂存区、运行记录、运行方案或环境变量的访问权，也不能编辑此 Project。
            </FormControl.Caption>
          </FormControl>
          {editable && (
            <Button type="submit" variant="primary" loading={busy} disabled={busy}>
              保存更改
            </Button>
          )}
        </form>
      </section>
    </>
  )
}
