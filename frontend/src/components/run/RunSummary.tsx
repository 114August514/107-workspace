import { SegmentedControl } from '@primer/react'
import { useState } from 'react'

import type {
  ComputePlan,
  Environment,
  EnvironmentVersion,
  RunConfiguration,
  RunDetail,
} from '../../api/types'
import { RunSnapshotSummary } from './RunSnapshotSummary'
import { RunTimeline } from './RunTimeline'
import styles from './run.module.css'

const SNAPSHOT_SECTIONS = [
  { id: 'basic', label: '基本信息' },
  { id: 'environment', label: '环境与算力' },
  { id: 'execution', label: '执行配置' },
] as const

type SnapshotSection = (typeof SNAPSHOT_SECTIONS)[number]['id']

/** User outcome and immutable execution facts first; exact identities remain folded. */
export function RunSummary({
  detail,
  projectName,
  computePlan,
  computePlanLoading,
  computePlanError,
  sourceConfiguration,
  configurationLoading,
  configurationError,
  environmentView,
  environmentLoading,
  environmentError,
}: {
  detail: RunDetail
  projectName?: string
  computePlan?: ComputePlan
  computePlanLoading: boolean
  computePlanError: boolean
  sourceConfiguration?: RunConfiguration
  configurationLoading: boolean
  configurationError: boolean
  environmentView?: { environment: Environment; version: EnvironmentVersion }
  environmentLoading: boolean
  environmentError: boolean
}) {
  const [snapshotSection, setSnapshotSection] = useState<SnapshotSection>('basic')

  const selectSnapshotSection = (index: number) => {
    const section = SNAPSHOT_SECTIONS[index]
    if (section) setSnapshotSection(section.id)
  }

  return (
    <div className={styles.summarySurface} aria-label="Run Summary">
      <div className={styles.summaryOverviewGrid}>
        <section className={styles.summaryExecution} aria-labelledby="run-events-title">
          <h2 id="run-events-title" className={styles.sectionTitle}>
            执行过程
          </h2>
          <RunTimeline detail={detail} />
        </section>

        <section className={styles.snapshotSummary} aria-labelledby="run-snapshot-title">
          <header className={styles.snapshotHeading}>
            <h2 id="run-snapshot-title" className={styles.sectionTitle}>
              运行快照
            </h2>
            <p>本次 Run 的不可变执行配置</p>
          </header>
          <SegmentedControl
            aria-label="运行快照分类"
            fullWidth
            className={styles.snapshotSegments}
            onChange={selectSnapshotSection}
          >
            {SNAPSHOT_SECTIONS.map((section) => (
              <SegmentedControl.Button
                key={section.id}
                selected={snapshotSection === section.id}
                aria-controls="run-snapshot-section"
              >
                {section.label}
              </SegmentedControl.Button>
            ))}
          </SegmentedControl>
          <div
            id="run-snapshot-section"
            className={styles.snapshotSectionPanel}
            role="region"
            aria-label={`${SNAPSHOT_SECTIONS.find((section) => section.id === snapshotSection)?.label}运行快照`}
          >
            <RunSnapshotSummary
              section={snapshotSection}
              detail={detail}
              projectName={projectName}
              computePlan={computePlan}
              computePlanLoading={computePlanLoading}
              computePlanError={computePlanError}
              sourceConfiguration={sourceConfiguration}
              configurationLoading={configurationLoading}
              configurationError={configurationError}
              environmentView={environmentView}
              environmentLoading={environmentLoading}
              environmentError={environmentError}
            />
          </div>
        </section>
      </div>
    </div>
  )
}
