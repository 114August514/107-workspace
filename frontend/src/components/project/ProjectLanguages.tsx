import { Spinner } from '@primer/react'

import type { ProjectLanguages as ProjectLanguagesData } from '../../api/types'
import { toAsyncError } from '../../api/errors'
import styles from './ProjectLanguages.module.css'

const LANGUAGE_COLORS: Record<string, string> = {
  C: '#555555',
  'C++': '#f34b7d',
  CSS: '#663399',
  Go: '#00add8',
  HTML: '#e34c26',
  Java: '#b07219',
  JavaScript: '#f1e05a',
  Julia: '#a270ba',
  Kotlin: '#a97bff',
  Lua: '#000080',
  Markdown: '#083fa1',
  Python: '#3572a5',
  R: '#198ce7',
  Ruby: '#701516',
  Rust: '#dea584',
  Shell: '#89e051',
  Swift: '#f05138',
  TypeScript: '#3178c6',
}

const FALLBACK_COLORS = ['#8250df', '#1f883d', '#0969da', '#bf8700', '#cf222e', '#0550ae']
const PERCENTAGE_FORMAT = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 })

interface Props {
  statistics: ProjectLanguagesData | undefined
  loading: boolean
  error: Error | undefined
  onRetry: () => void
}

function colorFor(name: string): string {
  const known = LANGUAGE_COLORS[name]
  if (known) return known

  let hash = 0
  for (let index = 0; index < name.length; index += 1) {
    hash = (hash * 31 + name.charCodeAt(index)) >>> 0
  }
  return FALLBACK_COLORS[hash % FALLBACK_COLORS.length]!
}

function formatPercentage(value: number): string {
  return `${PERCENTAGE_FORMAT.format(value)}%`
}

export function ProjectLanguages({ statistics, loading, error, onRetry }: Props) {
  const errorView = toAsyncError(error)
  const languages = statistics?.languages ?? []

  return (
    <section className={styles.section} aria-labelledby="project-languages-title">
      <h3 className={styles.title} id="project-languages-title">
        Languages
      </h3>

      {loading && !statistics ? (
        <p className={styles.loading} role="status">
          <Spinner size="small" srText="正在加载语言统计" /> 正在加载语言统计…
        </p>
      ) : errorView ? (
        <div className={styles.error} role="alert">
          <span>无法加载语言统计。</span>
          {errorView.problems?.map((problem) => (
            <span key={problem}>{problem}</span>
          ))}
          {errorView.requestId ? <span>请求标识 {errorView.requestId}</span> : null}
          <button className={styles.retry} type="button" onClick={onRetry}>
            重试
          </button>
        </div>
      ) : languages.length === 0 || statistics?.total_code_lines === 0 ? (
        <p className={styles.empty}>保存包含代码的 Project Version 后，这里会显示语言构成。</p>
      ) : (
        <>
          <div
            className={styles.bar}
            role="img"
            aria-label={`最新 Project Version 的语言构成，共 ${statistics?.total_code_lines ?? 0} 行代码`}
          >
            {languages.map((language) => (
              <span
                key={language.name}
                className={styles.segment}
                style={{
                  width: `${Math.min(100, Math.max(0, language.percentage))}%`,
                  backgroundColor: colorFor(language.name),
                }}
                title={`${language.name} ${formatPercentage(language.percentage)} · ${language.code_lines} 行代码`}
              />
            ))}
          </div>
          <ul className={styles.list}>
            {languages.map((language) => (
              <li className={styles.item} key={language.name}>
                <span
                  className={styles.dot}
                  style={{ backgroundColor: colorFor(language.name) }}
                  aria-hidden="true"
                />
                <span className={styles.name}>{language.name}</span>
                <span className={styles.percentage}>{formatPercentage(language.percentage)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
