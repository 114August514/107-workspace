import { Label, Text } from '@primer/react'
import { Link } from 'react-router-dom'

import type { SharedResource } from '../../api/types'
import { PrimerRelativeTime } from '../primer/PrimerMono'

interface Props {
  resources: SharedResource[]
}

/** 原生 table 替代 antd Table，列定义内联以避免 ColumnsType 依赖。 */
export function SharedResourceTable({ resources }: Props) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          <th
            style={{
              textAlign: 'left',
              padding: '8px 16px',
              fontSize: 14,
              fontWeight: 600,
              color: 'var(--fgColor-muted)',
              borderBottom: '1px solid var(--borderColor-default)',
              width: 240,
            }}
          >
            名称
          </th>
          <th
            style={{
              textAlign: 'left',
              padding: '8px 16px',
              fontSize: 14,
              fontWeight: 600,
              color: 'var(--fgColor-muted)',
              borderBottom: '1px solid var(--borderColor-default)',
            }}
          >
            说明
          </th>
          <th
            style={{
              textAlign: 'left',
              padding: '8px 16px',
              fontSize: 14,
              fontWeight: 600,
              color: 'var(--fgColor-muted)',
              borderBottom: '1px solid var(--borderColor-default)',
              width: 110,
            }}
          >
            归属
          </th>
          <th
            style={{
              textAlign: 'left',
              padding: '8px 16px',
              fontSize: 14,
              fontWeight: 600,
              color: 'var(--fgColor-muted)',
              borderBottom: '1px solid var(--borderColor-default)',
              width: 130,
            }}
          >
            创建时间
          </th>
        </tr>
      </thead>
      <tbody>
        {resources.map((resource) => (
          <tr key={resource.id} style={{ borderBottom: '1px solid var(--borderColor-default)' }}>
            <td style={{ padding: '8px 16px' }}>
              <Link
                to={`/shared-resources/${resource.id}`}
                style={{ fontWeight: 500, color: 'var(--fgColor-accent)' }}
              >
                {resource.name}
              </Link>
            </td>
            <td style={{ padding: '8px 16px' }}>
              <Text size="small" style={{ color: 'var(--fgColor-muted)' }}>
                {resource.description || '—'}
              </Text>
            </td>
            <td style={{ padding: '8px 16px' }}>
              {resource.is_platform_owned ? (
                <Label variant="attention">平台</Label>
              ) : (
                <Label variant="done">本空间</Label>
              )}
            </td>
            <td style={{ padding: '8px 16px' }}>
              <PrimerRelativeTime value={resource.created_at} />
            </td>
          </tr>
        ))}
        {resources.length === 0 && (
          <tr>
            <td colSpan={4} style={{ padding: '32px 16px', textAlign: 'center' }}>
              <Text size="small" style={{ color: 'var(--fgColor-muted)' }}>
                暂无 Shared Resource
              </Text>
            </td>
          </tr>
        )}
      </tbody>
    </table>
  )
}
