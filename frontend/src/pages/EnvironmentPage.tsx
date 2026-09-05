import { ContainerIcon, ChevronRightIcon } from '@primer/octicons-react'
import { Label } from '@primer/react'
import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import type { EnvironmentPublicationAttempt } from '../api/types'
import { AsyncState } from '../components/common/AsyncState'
import { normalizeError } from '../components/common/asyncStateError'
import { useCurrentEnvironment } from '../components/environment/environmentContext'
import { EnvironmentLayout } from '../components/environment/EnvironmentLayout'
import { EnvironmentPublicationPanel } from '../components/environment/EnvironmentPublicationPanel'
import overview from '../components/usergroup/overview.module.css'
import styles from './Environment.module.css'

export function EnvironmentPage() {
  const detail = useCurrentEnvironment()
  const location = useLocation()
  const [retry, setRetry] = useState<EnvironmentPublicationAttempt>()
  const environment = detail.data?.environment
  const tab = new URLSearchParams(location.search).get('tab') ?? 'overview'
  const history =
    tab === 'history' && environment?.capabilities?.includes('environment.version.create')
  return (
    <AsyncState
      loading={detail.loading}
      loadingText="正在加载运行环境…"
      error={normalizeError(detail.error)}
      onRetry={detail.reload}
    >
      {environment && (
        <EnvironmentLayout
          environment={environment}
          initial={retry}
          onCloseRetry={() => setRetry(undefined)}
        >
          {history ? (
            <EnvironmentPublicationPanel
              key={location.key}
              environmentId={environment.id}
              onRetry={setRetry}
              onPublished={() => void detail.reload({ silent: true })}
            />
          ) : (
            <>
              <div className={overview.sectionHeader}>
                <h2 className={overview.sectionTitle}>已发布版本</h2>
                <span className={styles.itemMeta}>{environment.versions.length} 个版本</span>
              </div>
              <AsyncState
                loading={false}
                loadingText="正在加载版本…"
                empty={environment.versions.length === 0}
                emptyText="这个运行环境还没有已发布版本。"
                emptyDescription="发布并通过校验后，版本才会出现在这里。"
              >
                <ul className={overview.rowList}>
                  {environment.versions.map((version) => (
                    <li key={version.id} className={overview.row}>
                      <Link className={overview.rowLink} to={`/environment-versions/${version.id}`}>
                        <span className={overview.rowIcon}>
                          <ContainerIcon />
                        </span>
                        <span className={overview.rowBody}>
                          <span className={overview.rowName}>{version.version}</span>
                          <span className={styles.wrappedMeta}>
                            {version.description || '暂无版本说明'}
                          </span>
                          <span className={styles.itemMeta}>
                            {version.runtime_kind === 'modules'
                              ? 'Environment Modules'
                              : 'Apptainer SIF'}
                          </span>
                          {version.availability !== 'available' && (
                            <span className={styles.wrappedMeta}>
                              {version.availability_detail || version.availability_reason}
                            </span>
                          )}
                        </span>
                        <Label
                          variant={version.availability === 'available' ? 'success' : 'attention'}
                        >
                          {version.availability === 'available' ? '可用' : '不可用'}
                        </Label>
                        <ChevronRightIcon className={overview.rowChevron} />
                      </Link>
                    </li>
                  ))}
                </ul>
              </AsyncState>
            </>
          )}
        </EnvironmentLayout>
      )}
    </AsyncState>
  )
}
