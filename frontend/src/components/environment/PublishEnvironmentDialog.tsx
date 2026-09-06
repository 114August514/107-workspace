import {
  Button,
  Dialog,
  Flash,
  FormControl,
  SegmentedControl,
  Select,
  Stack,
  Textarea,
  TextInput,
} from '@primer/react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { EnvironmentPublicationAttempt } from '../../api/types'
import { useAsync } from '../../api/useAsync'
import { AsyncState } from '../common/AsyncState'
import { normalizeError } from '../common/asyncStateError'
import styles from '../../pages/Environment.module.css'

interface Props {
  environmentId: string
  initial?: EnvironmentPublicationAttempt
  onClose: () => void
  onCreated: () => void
}

function sizeLabel(bytes: number) {
  return `${(bytes / 1024 ** 2).toLocaleString(undefined, { maximumFractionDigits: 1 })} MiB`
}

export function PublishEnvironmentDialog({ environmentId, initial, onClose, onCreated }: Props) {
  const options = useAsync(() => api.environmentPublicationOptions(), [])
  const [version, setVersion] = useState(initial?.version ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [runtime, setRuntime] = useState<'modules' | 'apptainer_sif'>(
    initial?.runtime_kind ?? 'modules',
  )
  const [source, setSource] = useState(initial?.source_uri ?? '')
  const [mode, setMode] = useState(initial?.source_kind === 'import' ? 1 : 0)
  const [modules, setModules] = useState(initial?.modules?.join('\n') ?? '')
  const [file, setFile] = useState<File | null>(null)
  const [digest, setDigest] = useState(
    initial?.source_kind === 'import' ? initial.expected_sha256 : (initial?.source_digest ?? ''),
  )
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const guard = useRef(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const firstInput = useRef<HTMLInputElement>(null)
  useEffect(() => {
    if (options.data) firstInput.current?.focus()
  }, [options.data])
  const ready =
    options.data &&
    version.trim() &&
    (runtime === 'modules' ? modules.trim() : mode === 1 ? source.trim() : file)
  const submit = async () => {
    if (!ready || guard.current || !options.data) return
    guard.current = true
    setBusy(true)
    setError('')
    try {
      const common = { version: version.trim(), description: description.trim() }
      if (runtime === 'modules') {
        await api.publishModulesEnvironment(environmentId, {
          ...common,
          modules: modules
            .split(/[\n,]/)
            .map((item) => item.trim())
            .filter(Boolean),
        })
      } else if (mode === 1) {
        await api.importEnvironment(environmentId, {
          ...common,
          source_uri: source.trim(),
          expected_sha256: digest.trim(),
        })
      } else {
        if (!file || file.size > options.data.max_upload_bytes)
          throw new Error(`请选择不超过 ${sizeLabel(options.data.max_upload_bytes)} 的 SIF 文件。`)
        await api.publishSifEnvironment(environmentId, {
          ...common,
          sif: file,
          source_uri: source.trim(),
          source_digest: digest.trim(),
          architecture: 'x86_64',
        })
      }
      onCreated()
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      guard.current = false
      setBusy(false)
    }
  }
  return (
    <Dialog
      title="发布版本"
      width="large"
      initialFocusRef={firstInput}
      onClose={() => {
        if (!guard.current) onClose()
      }}
      footerButtons={[
        { content: '取消', disabled: busy, onClick: onClose },
        {
          content: busy && runtime === 'apptainer_sif' && mode === 0 ? '正在上传…' : '发布版本',
          buttonType: 'primary',
          loading: busy,
          disabled: !ready || busy,
          onClick: () => void submit(),
        },
      ]}
    >
      <AsyncState
        loading={options.loading}
        loadingText="正在加载发布选项…"
        error={normalizeError(options.error)}
        onRetry={options.reload}
      >
        <form
          onSubmit={(event) => {
            event.preventDefault()
            void submit()
          }}
        >
          <Stack gap="normal">
            {error && <Flash variant="danger">{error}</Flash>}
            <FormControl required disabled={busy} id="publish-version">
              <FormControl.Label>版本名称</FormControl.Label>
              <TextInput
                ref={firstInput}
                value={version}
                onChange={(e) => setVersion(e.target.value)}
                placeholder="例如：2026.09"
                maxLength={64}
                block
              />
              <FormControl.Caption>发布后内容固定；更新环境时请发布新版本。</FormControl.Caption>
            </FormControl>
            <FormControl disabled={busy} id="publish-description">
              <FormControl.Label>说明</FormControl.Label>
              <Textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="这个版本包含什么，适合哪些任务？"
                rows={2}
                block
                resize="vertical"
              />
            </FormControl>
            <FormControl disabled={busy} id="publish-runtime">
              <FormControl.Label>运行方式</FormControl.Label>
              <Select
                value={runtime}
                onChange={(e) => setRuntime(e.target.value as typeof runtime)}
                block
              >
                <Select.Option value="modules">Environment Modules</Select.Option>
                <Select.Option value="apptainer_sif">Apptainer SIF</Select.Option>
              </Select>
            </FormControl>
            {runtime === 'modules' ? (
              <>
                <FormControl required disabled={busy} id="publish-modules">
                  <FormControl.Label>加载模块</FormControl.Label>
                  <Textarea
                    value={modules}
                    onChange={(e) => setModules(e.target.value)}
                    rows={3}
                    block
                    resize="vertical"
                    placeholder="每行一个模块，按加载顺序填写"
                  />
                  <FormControl.Caption>运行时按这里的顺序加载平台模块。</FormControl.Caption>
                </FormControl>
                <details className={styles.disclosure}>
                  <summary>查看平台支持的模块</summary>
                  <ul>
                    {options.data?.modules.map((module) => (
                      <li key={module}>{module}</li>
                    ))}
                  </ul>
                  {options.data?.modules.length === 0 && <p>平台尚未配置可发布的模块。</p>}
                </details>
              </>
            ) : (
              <>
                <SegmentedControl
                  aria-label="镜像来源"
                  onChange={(index) => {
                    setMode(index)
                    setDigest('')
                    setSource('')
                  }}
                >
                  <SegmentedControl.Button selected={mode === 0} disabled={busy}>
                    上传文件
                  </SegmentedControl.Button>
                  <SegmentedControl.Button selected={mode === 1} disabled={busy}>
                    从地址导入
                  </SegmentedControl.Button>
                </SegmentedControl>
                {mode === 0 ? (
                  <div className={styles.fileCard}>
                    <input
                      ref={fileInput}
                      type="file"
                      accept=".sif"
                      aria-label="SIF 文件"
                      className={styles.fileInput}
                      disabled={busy}
                      onChange={(e) => {
                        setFile(e.target.files?.[0] ?? null)
                        setError('')
                      }}
                    />
                    <strong>{file?.name ?? '选择 SIF 镜像文件'}</strong>
                    <p className={styles.description}>
                      {file
                        ? sizeLabel(file.size)
                        : `上传上限 ${sizeLabel(options.data?.max_upload_bytes ?? 0)}。较大的镜像可从地址导入。`}
                    </p>
                    <div className={styles.actions}>
                      <Button disabled={busy} onClick={() => fileInput.current?.click()}>
                        {file ? '更换文件' : '选择文件'}
                      </Button>
                      {file && (
                        <Button
                          disabled={busy}
                          onClick={() => {
                            setFile(null)
                            if (fileInput.current) fileInput.current.value = ''
                          }}
                        >
                          移除
                        </Button>
                      )}
                    </div>
                  </div>
                ) : (
                  <FormControl required disabled={busy} id="publish-source">
                    <FormControl.Label>镜像地址</FormControl.Label>
                    <TextInput
                      value={source}
                      onChange={(e) => setSource(e.target.value)}
                      placeholder="https://…/image.sif 或 docker://…"
                      block
                    />
                    <FormControl.Caption>
                      支持公开的 HTTPS、docker://、oras:// 和 library:// 地址。Docker 镜像会转换为
                      SIF。
                    </FormControl.Caption>
                  </FormControl>
                )}
                <p className={styles.hint}>
                  平台校验架构：{options.data?.architecture}。
                  {mode === 1
                    ? `导入上限 ${sizeLabel(options.data?.max_import_bytes ?? 0)}，最长 ${Math.round((options.data?.import_timeout_seconds ?? 0) / 60)} 分钟。提交后可在发布记录查看进度。`
                    : '上传完成后进行校验，校验通过才会发布。'}
                </p>
                <details className={styles.disclosure}>
                  <summary>高级设置</summary>
                  <Stack gap="normal">
                    {mode === 0 && (
                      <FormControl disabled={busy} id="publish-upload-source">
                        <FormControl.Label>来源地址（可选）</FormControl.Label>
                        <TextInput
                          value={source}
                          onChange={(e) => setSource(e.target.value)}
                          block
                        />
                      </FormControl>
                    )}
                    <FormControl disabled={busy} id="publish-digest">
                      <FormControl.Label>
                        {mode === 1 ? '预期 SIF 文件 SHA-256（可选）' : '来源摘要（可选）'}
                      </FormControl.Label>
                      <TextInput value={digest} onChange={(e) => setDigest(e.target.value)} block />
                      <FormControl.Caption>
                        {mode === 1
                          ? '校验最终 SIF 文件，Docker 镜像摘要不能用于此项。'
                          : '仅记录来源信息；平台会另行计算实际文件摘要。'}
                      </FormControl.Caption>
                    </FormControl>
                  </Stack>
                </details>
              </>
            )}
          </Stack>
        </form>
      </AsyncState>
    </Dialog>
  )
}
