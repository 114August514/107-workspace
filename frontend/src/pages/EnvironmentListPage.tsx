import { ContainerIcon, HomeIcon } from '@primer/octicons-react'
import { Label, Link, Text } from '@primer/react'
import { Link as RouterLink } from 'react-router-dom'

import { api } from '../api/client'
import type { Environment } from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { normalizeError } from '../components/common/asyncStateError'
import { PrimerListCard } from '../components/primer/PrimerListCard'
import styles from './Environment.module.css'

export function EnvironmentListPage() {
  const environments = useAsync<Environment[]>(() => api.environments(), [])

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <nav className={styles.breadcrumb} aria-label="面包屑">
          <HomeIcon aria-hidden="true" />
          <Link as={RouterLink} to="/">
            首页
          </Link>
          <span aria-hidden="true">/</span>
          <span>运行环境</span>
        </nav>
        <div className={styles.titleRow}>
          <ContainerIcon className={styles.titleIcon} size={24} aria-hidden="true" />
          <h1 className={styles.title}>运行环境</h1>
        </div>
        <Text as="p" className={styles.description}>
          当前列表包含你本人、有效 User Group，以及通过 USE Grant 可以使用的运行环境。 Run
          Configuration 保存后固定引用一个确定版本。
        </Text>
      </header>

      <PrimerListCard title="当前可使用" padded>
        <AsyncState
          loading={environments.loading}
          loadingText="正在加载运行环境…"
          error={normalizeError(environments.error)}
          onRetry={environments.reload}
          empty={!environments.loading && environments.data?.length === 0}
          emptyText="当前没有可使用的运行环境。"
          emptyDescription="请联系资产 Owner 为你本人或 User Group 建立 USE Grant。"
        >
          {environments.data && environments.data.length > 0 ? (
            <ul className={styles.environmentList}>
              {environments.data.map((environment) => {
                const availableCount = environment.versions.filter(
                  (version) => version.availability === 'available',
                ).length
                return (
                  <li key={environment.id}>
                    <RouterLink
                      className={styles.environmentLink}
                      to={`/environments/${environment.id}`}
                    >
                      <span className={styles.itemMain}>
                        <span className={styles.itemTitle}>{environment.name}</span>
                        <span className={styles.itemMeta}>
                          {environment.description || '这个运行环境还没有填写说明。'}
                        </span>
                      </span>
                      <span className={styles.itemLabels}>
                        <Label>{environment.owner.display_name}</Label>
                        <Label variant={availableCount > 0 ? 'success' : 'attention'}>
                          {availableCount}/{environment.versions.length} 个版本可用
                        </Label>
                      </span>
                    </RouterLink>
                  </li>
                )
              })}
            </ul>
          ) : null}
        </AsyncState>
      </PrimerListCard>
    </div>
  )
}
