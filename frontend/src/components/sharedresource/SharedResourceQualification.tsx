import { Label, Text } from '@primer/react'

import type { SharedResourceUseQualification } from '../../api/types'

interface Props {
  qualifications: SharedResourceUseQualification[]
}

export function QualificationLabels({ qualifications }: Props) {
  if (qualifications.length === 0) {
    return <Label variant="secondary">无使用资格</Label>
  }
  return (
    <>
      {qualifications.map((qualification, index) => {
        const key = `${qualification.scope}-${qualification.eligible_project_owner?.id ?? index}`
        const groupDisplayName =
          qualification.grants.find((grant) => grant.grantee.kind === 'user_group')?.grantee
            .display_name ??
          qualification.eligible_project_owner?.id ??
          '该用户组'
        switch (qualification.scope) {
          case 'owner':
            return (
              <Label key={key} variant="success">
                资源 Owner 范围
              </Label>
            )
          case 'user_grant':
            return (
              <Label key={key} variant="success">
                个人 USE 授权
              </Label>
            )
          case 'user_group_grant':
            return (
              <Label key={key} variant="success">
                {groupDisplayName} USE 授权
              </Label>
            )
        }
      })}
    </>
  )
}

function qualificationNote(qualification: SharedResourceUseQualification): string {
  switch (qualification.scope) {
    case 'owner':
      return '你具备在 Owner 与此资源相同的 Project 中引用它的资格。'
    case 'user_grant':
      return 'Owner 已直接授权给你；可在你有权提交的任何 Project 中引用它。'
    case 'user_group_grant': {
      const groupDisplayName =
        qualification.grants.find((grant) => grant.grantee.kind === 'user_group')?.grantee
          .display_name ??
        qualification.eligible_project_owner?.id ??
        '该用户组'
      return `Owner 已授权给「${groupDisplayName}」；需保持该组有效成员身份，并在该组作为 Owner 的 Project 中引用它。`
    }
  }
}

export function QualificationNotice({ qualifications }: Props) {
  return (
    <div>
      <Text as="p">这里仅说明当前账号的使用资格，不代表具体 Run 已通过 Preflight。</Text>
      {qualifications.length === 0 && <Text as="p">当前没有可说明的使用资格。</Text>}
      {qualifications.map((qualification, index) => (
        <div key={`${qualification.scope}-${qualification.eligible_project_owner?.id ?? index}`}>
          <Text as="p">{qualificationNote(qualification)}</Text>
          {qualification.grants.map((grant) => (
            <Text as="p" key={grant.id} size="small">
              USE 授权：授予 {grant.grantee.display_name}
              {grant.target_all ? '（覆盖 Owner 全部资产）' : '（仅限此资源）'}
            </Text>
          ))}
        </div>
      ))}
    </div>
  )
}
