import { ContainerIcon, HomeIcon } from '@primer/octicons-react'
import { Label, Link, Text } from '@primer/react'
import { Link as RouterLink, useParams } from 'react-router-dom'

import { api } from '../api/client'
import type { Environment } from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { normalizeError } from '../components/common/asyncStateError'
import { EnvironmentPublicationPanel } from '../components/environment/EnvironmentPublicationPanel'
import { PrimerListCard } from '../components/primer/PrimerListCard'
import styles from './Environment.module.css'

export function EnvironmentPage() {
  const { environmentId = '' } = useParams()
  const environment = useAsync<Environment>(() => api.environment(environmentId), [environmentId])

  return (
    <div className={styles.page}>
      <AsyncState
        loading={environment.loading}
        loadingText="正在加载运行环境…"
        error={normalizeError(environment.error)}
        onRetry={environment.reload}
      >
        {environment.data ? (
          <>
            <header className={styles.header}>
              <nav className={styles.breadcrumb} aria-label="面包屑">
                <HomeIcon aria-hidden="true" />
                <Link as={RouterLink} to="/">
                  首页
                </Link>
                <span aria-hidden="true">/</span>
                <Link as={RouterLink} to="/environments">
                  运行环境
                </Link>
                <span aria-hidden="true">/</span>
                <span>{environment.data.name}</span>
              </nav>
              <div className={styles.titleRow}>
                <ContainerIcon className={styles.titleIcon} size={24} aria-hidden="true" />
                <h1 className={styles.title}>{environment.data.name}</h1>
                <Label>归属：{environment.data.owner.display_name}</Label>
              </div>
              <Text as="p" className={styles.description}>
                {environment.data.description || '这个运行环境还没有填写说明。'}
              </Text>
            </header>

            <EnvironmentPublicationPanel environmentId={environment.data.id} />

            <PrimerListCard title="已发布版本" padded>
              {environment.data.versions.length === 0 ? (
                <AsyncState
                  loadingText="正在加载运行环境版本…"
                  loading={false}
                  empty
                  emptyText="这个运行环境还没有已发布版本。"
                  emptyDescription="没有确定版本时，Run Configuration 不能引用这个环境。"
                >
                  {null}
                </AsyncState>
              ) : (
                <ul className={styles.versionList}>
                  {environment.data.versions.map((version) => (
                    <li key={version.id}>
                      <RouterLink
                        className={styles.versionLink}
                        to={`/environment-versions/${version.id}`}
                      >
                        <span className={styles.itemMain}>
                          <span className={styles.itemTitle}>{version.version}</span>
                          <span className={styles.itemMeta}>
                            {version.description || '这个版本还没有填写说明。'}
                          </span>
                          <span className={styles.monoMeta}>
                            {version.runtime_kind} · {version.definition_hash.slice(0, 12)}
                          </span>
                        </span>
                        <span className={styles.itemLabels}>
                          <Label
                            variant={version.availability === 'available' ? 'success' : 'attention'}
                          >
                            {version.availability === 'available' ? '可用' : '不可用'}
                          </Label>
                        </span>
                      </RouterLink>
                    </li>
                  ))}
                </ul>
              )}
            </PrimerListCard>
          </>
        ) : null}
      </AsyncState>
    </div>
  )
}
