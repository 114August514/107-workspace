import { Text } from '@primer/react'
import { Link } from 'react-router-dom'

import type { SharedResource } from '../../api/types'
import { PrimerRelativeTime } from '../primer/PrimerMono'
import { QualificationLabels } from './SharedResourceQualification'
import styles from './sharedResource.module.css'

interface Props {
  resources: SharedResource[]
}

/**
 * 共享资源列表。原生 table 替代 antd Table，列定义内联，
 * 长期视觉规则走 CSS Modules + Primer token，不复制 GitHub 色值。
 *
 * 空态由外层 AsyncState 负责（Blankslate + 能力感知 CTA），
 * 表格自身只渲染有数据的行，避免空态出现两遍。
 */
export function SharedResourceTable({ resources }: Props) {
  return (
    <table className={styles.table}>
      <thead>
        <tr>
          <th className={`${styles.th} ${styles.colName}`}>名称</th>
          <th className={styles.th}>说明</th>
          <th className={`${styles.th} ${styles.colOwner}`}>归属</th>
          <th className={`${styles.th} ${styles.colStatus}`}>使用资格</th>
          <th className={`${styles.th} ${styles.colCreated}`}>创建时间</th>
        </tr>
      </thead>
      <tbody>
        {resources.map((resource) => (
          <tr key={resource.id} className={styles.row}>
            <td className={styles.td}>
              <Link to={`/shared-resources/${resource.id}`} className={styles.nameLink}>
                {resource.name}
              </Link>
            </td>
            <td className={styles.td}>
              <Text size="small" className={styles.desc}>
                {resource.description || '—'}
              </Text>
            </td>
            <td className={styles.td}>{resource.owner.display_name}</td>
            <td className={styles.td}>
              <QualificationLabels qualifications={resource.use_qualifications} />
            </td>
            <td className={styles.td}>
              <PrimerRelativeTime value={resource.created_at} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
