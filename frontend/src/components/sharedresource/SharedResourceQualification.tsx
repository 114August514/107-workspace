import { Label, Text } from '@primer/react'

import type { SharedResourceUseQualification } from '../../api/types'

interface Props {
  qualifications: SharedResourceUseQualification[]
}

function groupGrantee(qualification: SharedResourceUseQualification) {
  const grant = qualification.grants[0]
  if (!grant || grant.grantee.kind !== 'user_group') {
    throw new Error('UserGroup Grant 资格必须包含同一 User Group 的 USE Grant')
  }
  return grant.grantee
}

function qualificationKey(qualification: SharedResourceUseQualification, index: number) {
  return qualification.scope === 'user_group_grant'
    ? `${qualification.scope}-${groupGrantee(qualification).id}`
    : `${qualification.scope}-${index}`
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
                {groupGrantee(qualification).display_name} USE 授权
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
      const group = groupGrantee(qualification)
      return `Owner 已授权给「${group.display_name}」；需保持该组有效成员身份，并在该组拥有且你有权提交的 Project 中引用它。`
    }
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
