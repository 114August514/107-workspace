import { Button, Select, TextInput } from '@primer/react'
import type { InputBinding, SharedResourceDetail } from '../../api/types'
import { api } from '../../api/client'
import { toAsyncError } from '../../api/errors'
import { useAsync } from '../../api/useAsync'
import { AsyncState } from '../common/AsyncState'
import { RunField } from './RunField'
import styles from './simpleRun.module.css'

export function SharedResourceInputBindings({
  bindings,
  onChange,
}: {
  bindings: InputBinding[]
  onChange: (bindings: InputBinding[]) => void
}) {
  const resources = useAsync<SharedResourceDetail[]>(async () => {
    const items = await api.listSharedResources()
    return Promise.all(items.map((item) => api.getSharedResource(item.id)))
  }, [])
  const versions = (resources.data ?? []).flatMap((resource) =>
    resource.versions.map((version) => ({ resource, version })),
  )
  const update = (index: number, patch: Partial<InputBinding>) =>
    onChange(bindings.map((row, i) => (i === index ? { ...row, ...patch } : row)))
  return (
    <section className={styles.section} aria-label="运行输入">
      <h3 className={styles.title}>运行输入</h3>
      <p className={styles.muted}>选择确定的资源版本，作为只读输入。保存后不会自动切换版本。</p>
      <AsyncState
        loading={resources.loading}
        loadingText="正在加载共享资源…"
        error={toAsyncError(resources.error)}
        onRetry={resources.reload}
      >
        {versions.length === 0 && <p className={styles.muted}>当前没有可选择的共享资源版本。</p>}
      </AsyncState>
      {bindings.map((binding, index) => (
        <div className={`${styles.item} ${styles.section}`} key={index}>
          {binding.source_type === 'shared_resource_version' ? (
            <RunField label={`资源版本 ${index + 1}`} required>
              <Select
                block
                value={binding.source_id}
                onChange={(e) => update(index, { source_id: e.target.value })}
              >
                <Select.Option value="">选择资源版本</Select.Option>
                {binding.source_id &&
                  !versions.some(({ version }) => version.id === binding.source_id) && (
                    <Select.Option value={binding.source_id}>
                      已保存版本（当前无法确认可用性）
                    </Select.Option>
                  )}
                {versions.map(({ resource, version }) => (
                  <Select.Option key={version.id} value={version.id}>
                    {resource.name} · {version.label} · {resource.owner.display_name}
                  </Select.Option>
                ))}
              </Select>
            </RunField>
          ) : (
            <p>
              运行产物输入：<code>{binding.source_id}</code>
            </p>
          )}
          <div className={styles.grid}>
            <RunField label={`输入访问路径 ${index + 1}`} required>
              <TextInput
                block
                value={binding.access_path}
                placeholder="/inputs/data"
                onChange={(e) => update(index, { access_path: e.target.value })}
              />
            </RunField>
            <RunField label={`来源子路径 ${index + 1}`} caption="留空使用整个版本">
              <TextInput
                block
                value={binding.source_subpath}
                placeholder="例如：train/"
                onChange={(e) => update(index, { source_subpath: e.target.value })}
              />
            </RunField>
          </div>
          <div>
            <Button
              variant="invisible"
              onClick={() => onChange(bindings.filter((_, i) => i !== index))}
            >
              删除运行输入 {index + 1}
            </Button>
          </div>
        </div>
      ))}
      <div>
        <Button
          disabled={resources.loading || !!resources.error || versions.length === 0}
          onClick={() =>
            onChange([
              ...bindings,
              {
                source_type: 'shared_resource_version',
                source_id: '',
                access_path: '',
                source_subpath: '',
              },
            ])
          }
        >
          添加运行输入
        </Button>
      </div>
    </section>
  )
}
