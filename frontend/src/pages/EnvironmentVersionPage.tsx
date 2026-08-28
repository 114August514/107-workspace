import { ContainerIcon, HomeIcon } from '@primer/octicons-react'
import { Label, Link, Text } from '@primer/react'
import { Link as RouterLink, useParams } from 'react-router-dom'

import { api } from '../api/client'
import type { Environment, EnvironmentVersion } from '../api/types'
import { useAsync } from '../api/useAsync'
import { AsyncState } from '../components/common/AsyncState'
import { normalizeError } from '../components/common/asyncStateError'
import styles from './Environment.module.css'

interface VersionView {
  environment: Environment
  version: EnvironmentVersion
}

export function EnvironmentVersionPage() {
  const { versionId = '' } = useParams()
  const detail = useAsync<VersionView>(async () => {
    const version = await api.environmentVersion(versionId)
    const environment = await api.environment(version.environment_id)
    return { environment, version }
  }, [versionId])

  return (
    <div className={styles.page}>
      <AsyncState
        loading={detail.loading}
        loadingText="正在加载运行环境版本…"
        error={normalizeError(detail.error)}
        onRetry={detail.reload}
      >
        {detail.data ? (
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
                <Link as={RouterLink} to={`/environments/${detail.data.environment.id}`}>
                  {detail.data.environment.name}
                </Link>
                <span aria-hidden="true">/</span>
                <span>{detail.data.version.version}</span>
              </nav>
              <div className={styles.titleRow}>
                <ContainerIcon className={styles.titleIcon} size={24} aria-hidden="true" />
                <h1 className={styles.title}>
                  {detail.data.environment.name} · {detail.data.version.version}
                </h1>
                <Label variant={detail.data.version.available ? 'success' : 'attention'}>
                  {detail.data.version.available ? '当前可用' : '当前不可用'}
                </Label>
              </div>
              <Text as="p" className={styles.description}>
                {detail.data.version.description || '这个版本还没有填写说明。'}
              </Text>
            </header>

            <dl className={styles.detailGrid}>
              <dt>Owner</dt>
              <dd>{detail.data.environment.owner.display_name}</dd>
              <dt>确定版本 ID</dt>
              <dd className={styles.monoMeta}>{detail.data.version.id}</dd>
              <dt>环境基础</dt>
              <dd className={styles.monoMeta}>{detail.data.version.image}</dd>
              <dt>准备命令</dt>
              <dd>
                {detail.data.version.setup_command ? (
                  <code className={styles.codeBlock}>{detail.data.version.setup_command}</code>
                ) : (
                  '无'
                )}
              </dd>
            </dl>
          </>
        ) : null}
      </AsyncState>
    </div>
  )
}
