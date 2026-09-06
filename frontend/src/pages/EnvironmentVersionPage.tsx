import { Label } from '@primer/react'
import { Link } from 'react-router-dom'
import { AsyncState } from '../components/common/AsyncState'
import { normalizeError } from '../components/common/asyncStateError'
import { useCurrentEnvironment } from '../components/environment/environmentContext'
import { EnvironmentLayout } from '../components/environment/EnvironmentLayout'
import overview from '../components/usergroup/overview.module.css'
import styles from './Environment.module.css'

export function EnvironmentVersionPage() {
  const detail = useCurrentEnvironment()
  const environment = detail.data?.environment
  const version = detail.data?.version
  const definition = version?.definition ?? {}
  return (
    <AsyncState
      loading={detail.loading}
      loadingText="正在加载运行环境版本…"
      error={normalizeError(detail.error)}
      onRetry={detail.reload}
    >
      {environment && version && (
        <EnvironmentLayout environment={environment}>
          <Link to={`/environments/${environment.id}?tab=versions`}>返回版本列表</Link>
          <div className={styles.sectionHeading}>
            <h2 className={overview.sectionTitle}>{version.version}</h2>
            <Label variant={version.availability === 'available' ? 'success' : 'attention'}>
              {version.availability === 'available' ? '当前可用' : '当前不可用'}
            </Label>
          </div>
          <p className={styles.description}>{version.description || '这个版本还没有填写说明。'}</p>
          <dl className={styles.detailGrid}>
            <dt>运行方式</dt>
            <dd>{version.runtime_kind === 'modules' ? 'Environment Modules' : 'Apptainer SIF'}</dd>
            {version.runtime_kind === 'modules' ? (
              <>
                <dt>加载模块</dt>
                <dd>
                  <ol className={styles.modules}>
                    {(Array.isArray(definition.modules) ? definition.modules : []).map(
                      (module, index) => (
                        <li key={index}>{String(module)}</li>
                      ),
                    )}
                  </ol>
                </dd>
              </>
            ) : (
              <>
                <dt>镜像文件</dt>
                <dd>
                  SIF ·{' '}
                  {typeof definition.size === 'number'
                    ? `${(definition.size / 1024 ** 2).toFixed(1)} MiB`
                    : '大小未记录'}
                </dd>
                <dt>文件 SHA-256</dt>
                <dd className={styles.monoMeta}>{String(definition.sha256 ?? '未记录')}</dd>
                <dt>架构</dt>
                <dd>{String(definition.architecture ?? '未记录')}</dd>
                {Boolean(definition.source_uri) && (
                  <>
                    <dt>镜像来源</dt>
                    <dd>{String(definition.source_uri)}</dd>
                  </>
                )}
              </>
            )}
            <dt>验证结果</dt>
            <dd>{version.validation_summary}</dd>
            <dt>可用性</dt>
            <dd>{version.availability_detail || version.availability_reason}</dd>
            <dt>最近检查</dt>
            <dd>{new Date(version.availability_checked_at).toLocaleString()}</dd>
          </dl>
          <details className={styles.disclosure}>
            <summary>技术信息</summary>
            <dl className={styles.detailGrid}>
              <dt>确定版本 ID</dt>
              <dd>{version.id}</dd>
              <dt>Definition SHA-256</dt>
              <dd>{version.definition_hash}</dd>
            </dl>
            <h3 className={overview.sectionTitle}>不可变定义</h3>
            <pre className={styles.codeBlock}>{JSON.stringify(version.definition, null, 2)}</pre>
            <h3 className={overview.sectionTitle}>验证证据</h3>
            <pre className={styles.codeBlock}>
              {JSON.stringify(version.validation_evidence, null, 2)}
            </pre>
          </details>
        </EnvironmentLayout>
      )}
    </AsyncState>
  )
}
