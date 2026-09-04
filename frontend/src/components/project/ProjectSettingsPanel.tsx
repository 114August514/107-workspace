import { SegmentedControl } from '@primer/react'
import { useState } from 'react'

import type { Project } from '../../api/types'
import { ProjectSecretsPanel } from './ProjectSecretsPanel'
import { ProjectVariablesPanel } from './ProjectVariablesPanel'
import styles from './projectSettingsPanel.module.css'

interface Props {
  projectId: string
  access: Project | undefined
  onChanged?: () => void
}

/**
 * Project Settings 的 Variable/Secret 管理表面（Issue #54）。
 *
 * 分区切换用 Primer SegmentedControl（同 #94 RunSummary / RunLogPanel
 * 的运行结果 Tab），清单样式对齐 #94 FileBrowser；外框由挂载处的
 * Card 壳提供。
 */
export function ProjectSettingsPanel({ projectId, access, onChanged }: Props) {
  const [tab, setTab] = useState<'variables' | 'secrets'>('variables')

  return (
    <div className={styles.settings}>
      <SegmentedControl
        aria-label="Settings 分区"
        className={styles.segments}
        onChange={(index: number) => setTab(index === 0 ? 'variables' : 'secrets')}
      >
        <SegmentedControl.Button selected={tab === 'variables'} aria-controls="settings-pane">
          Variables
        </SegmentedControl.Button>
        <SegmentedControl.Button selected={tab === 'secrets'} aria-controls="settings-pane">
          Secrets
        </SegmentedControl.Button>
      </SegmentedControl>

      {tab === 'variables' ? (
        <ProjectVariablesPanel projectId={projectId} access={access} onChanged={onChanged} />
      ) : (
        <ProjectSecretsPanel projectId={projectId} access={access} onChanged={onChanged} />
      )}
    </div>
  )
}
