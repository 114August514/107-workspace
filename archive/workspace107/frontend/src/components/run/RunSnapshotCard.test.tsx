import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { RunSnapshot } from '../../api/types'
import { RunSnapshotCard } from './RunSnapshotCard'

const SNAPSHOT: RunSnapshot = {
  id: 'snap_1',
  project_id: 'prj_1',
  project_version_id: 'pv_1',
  source_run_configuration_id: 'rc_1',
  working_directory: '.',
  command: 'python train.py',
  environment_version_id: 'ev_python_312',
  environment_image: 'python:3.12-slim',
  environment_setup_command: '',
  environment_variables: { EPOCHS: '3' },
  secret_references: { TOKEN: 'HF_TOKEN' },
  input_bindings: [
    {
      source_type: 'artifact',
      source_id: 'art_1',
      access_path: '/inputs/stage1',
      source_subpath: '',
    },
  ],
  compute_plan_id: 'plan_cpu_quick',
  compute_request: {
    nodes: 1,
    cpus: 2,
    memory_mb: 4096,
    gpus: 0,
    time_limit_minutes: 15,
  },
  scheduler: {
    cluster: '107',
    account: 'undergraduate',
    partition: 'debug',
    qos: 'normal',
    nodes: 1,
    cpus: 2,
    memory_mb: 4096,
    gpus: 0,
    time_limit_minutes: 15,
  },
  artifact_rules: [{ path: 'outputs', name: '结果', optional: false }],
  created_by: 'usr_1',
  created_at: '2026-07-26T12:00:00+00:00',
}

describe('RunSnapshotCard', () => {
  it('展示复现所需的执行事实', () => {
    render(<RunSnapshotCard snapshot={SNAPSHOT} />)

    expect(screen.getByText('pv_1')).toBeInTheDocument()
    expect(screen.getByText('python train.py')).toBeInTheDocument()
    expect(screen.getByText('python:3.12-slim')).toBeInTheDocument()
    expect(screen.getByText('Partition debug')).toBeInTheDocument()
    expect(screen.getByText('EPOCHS=3')).toBeInTheDocument()
  })

  it('Secret 只显示引用名称，不显示值', () => {
    render(<RunSnapshotCard snapshot={SNAPSHOT} />)

    expect(screen.getByText('TOKEN')).toBeInTheDocument()
    expect(screen.getByText(/来自 Secret HF_TOKEN/)).toBeInTheDocument()
    // 快照本身就不携带值，界面自然也拿不到。
    expect(document.body.textContent).not.toContain('hf_')
  })

  it('输入绑定标注为只读', () => {
    render(<RunSnapshotCard snapshot={SNAPSHOT} />)
    expect(screen.getByText(/art_1 → \/inputs\/stage1（只读）/)).toBeInTheDocument()
  })
})
