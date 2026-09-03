// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { FileViewer } from '../../src/components/project/FileViewer'
import type { Project, ProjectVersionDetail } from '../../src/api/types'

const mocks = vi.hoisted(() => ({
  readFile: vi.fn(),
  readVersionFile: vi.fn(),
  writeFile: vi.fn(),
  downloadFile: vi.fn(),
  movePath: vi.fn(),
  copyPath: vi.fn(),
  deletePath: vi.fn(),
}))

vi.mock('../../src/api/client', () => ({ api: mocks }))

const project: Project = {
  capabilities: ['project.content.write'],
  created_at: null,
  created_by: 'user-1',
  default_run_configuration_id: null,
  description: '',
  environment_version_id: null,
  id: 'project-1',
  name: 'Project',
  owner: { display_name: 'Owner', id: 'user-1', kind: 'user' },
  status: 'active',
  updated_at: null,
  visibility: 'owner_scope',
}

const version = { id: 'version-1', label: 'v1' } as ProjectVersionDetail

function renderViewer(props: { version?: ProjectVersionDetail; access?: Project }) {
  return render(
    <MemoryRouter>
      <FileViewer
        projectId="project-1"
        access={props.access ?? project}
        path="train.py"
        backHref="/projects/project-1/files"
        version={props.version}
      />
    </MemoryRouter>,
  )
}

describe('FileViewer', () => {
  afterEach(() => {
    cleanup()
    vi.resetAllMocks()
  })

  it('renders a read-only version without edit controls', async () => {
    mocks.readVersionFile.mockResolvedValue({
      path: 'train.py',
      content: 'print(1)',
      truncated: false,
    })

    renderViewer({ version })

    expect(await screen.findByText('v1 · 只读')).toBeVisible()
    await waitFor(() => expect(document.querySelector('pre')).toHaveTextContent('print(1)'))
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '保存' })).not.toBeInTheDocument()
    expect(mocks.readVersionFile).toHaveBeenCalledWith('version-1', 'train.py')
  })

  it('edits and saves a working-state file', async () => {
    mocks.readFile.mockResolvedValue({ path: 'train.py', content: 'print(1)', truncated: false })
    mocks.writeFile.mockResolvedValue(undefined)

    renderViewer({})

    const editor = await screen.findByRole('textbox', { name: '编辑 train.py' })
    fireEvent.change(editor, { target: { value: 'print(2)' } })
    fireEvent.click(await screen.findByRole('button', { name: /保\s*存/ }))

    await waitFor(() =>
      expect(mocks.writeFile).toHaveBeenCalledWith('project-1', 'train.py', 'print(2)'),
    )
  })
  it('keeps file actions in the file header', async () => {
    mocks.readFile.mockResolvedValue({ path: 'train.py', content: 'print(1)', truncated: false })

    render(
      <MemoryRouter>
        <FileViewer
          projectId="project-1"
          access={project}
          path="train.py"
          backHref="/projects/project-1/files"
          onChanged={() => {}}
        />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('button', { name: '下载文件' })).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: '更多文件操作 train.py' }))
    expect(await screen.findByRole('menuitem', { name: '重命名' })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: '复制' })).toBeVisible()
    expect(screen.getByRole('menuitem', { name: '删除' })).toBeVisible()
  })
})
