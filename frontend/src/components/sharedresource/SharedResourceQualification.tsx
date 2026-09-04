import { Label, Text } from '@primer/react'

import type { SharedResourceUseQualification } from '../../api/types'

interface Props {
  qualifications: SharedResourceUseQualification[]
}

function qualificationKey(qualification: SharedResourceUseQualification, index: number) {
  return qualification.scope === 'owner'
    ? `${qualification.scope}-${index}`
    : `${qualification.scope}-${qualification.grantee.id}`
}

export function QualificationLabels({ qualifications }: Props) {
  if (qualifications.length === 0) {
    return <Label variant="secondary">无使用资格</Label>
  }
  return (
    <>
      {qualifications.map((qualification, index) => {
        const key = qualificationKey(qualification, index)
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
                {qualification.grantee.display_name} USE 授权
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
    case 'user_group_grant':
      return `Owner 已授权给「${qualification.grantee.display_name}」；需保持该组有效成员身份，并在该组拥有且你有权提交的 Project 中引用它。`
  }
}

export function QualificationNotice({ qualifications }: Props) {
  return (
    <div>
      <Text as="p">这里仅说明当前账号的使用资格，不代表具体 Run 已通过 Preflight。</Text>
      {qualifications.length === 0 && <Text as="p">当前没有可说明的使用资格。</Text>}
      {qualifications.map((qualification, index) => (
        <div key={qualificationKey(qualification, index)}>
          <Text as="p">{qualificationNote(qualification)}</Text>
          {qualification.scope !== 'owner' &&
            qualification.grants.map((grant) => (
              <Text as="p" key={grant.id} size="small">
                USE 授权：授予 {qualification.grantee.display_name}
                {grant.target_all ? '（覆盖 Owner 全部资产）' : '（仅限此资源）'}
              </Text>
            ))}
        </div>
      ))}
    </div>
  )
}
