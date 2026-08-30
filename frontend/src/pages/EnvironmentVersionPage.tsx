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
                <Label
                  variant={
                    detail.data.version.availability === 'available' ? 'success' : 'attention'
                  }
                >
                  {detail.data.version.availability === 'available' ? '当前可用' : '当前不可用'}
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
              <dt>Runtime kind</dt>
              <dd className={styles.monoMeta}>{detail.data.version.runtime_kind}</dd>
              <dt>Definition SHA-256</dt>
              <dd className={styles.monoMeta}>{detail.data.version.definition_hash}</dd>
              <dt>不可变定义</dt>
              <dd>
                <code className={styles.codeBlock}>
                  {JSON.stringify(detail.data.version.definition)}
                </code>
              </dd>
              <dt>验证摘要</dt>
              <dd>{detail.data.version.validation_summary}</dd>
              <dt>验证证据</dt>
              <dd>
                <code className={styles.codeBlock}>
                  {JSON.stringify(detail.data.version.validation_evidence)}
                </code>
              </dd>
              <dt>可用性</dt>
              <dd>
                {detail.data.version.availability_detail || detail.data.version.availability_reason}
              </dd>
              <dt>检查时间</dt>
              <dd>{new Date(detail.data.version.availability_checked_at).toLocaleString()}</dd>
            </dl>
          </>
        ) : null}
      </AsyncState>
    </div>
  )
}
