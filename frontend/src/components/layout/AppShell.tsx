import { Layout, Space, Typography } from 'antd'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { colors } from '../../theme'
import { NotificationBell } from '../notification/NotificationBell'
import { UserSwitcher } from './UserSwitcher'

const { Header, Content, Footer } = Layout

interface Props {
  username: string
  onUsernameChange: (username: string) => void
  children: ReactNode
}

export function AppShell({ username, onUsernameChange, children }: Props) {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 16,
        }}
      >
        <Link to="/">
          <Typography.Text style={{ color: colors.onDark, fontSize: 16, fontWeight: 600 }}>
            107 Workspace
          </Typography.Text>
        </Link>
        <Space size={4}>
          <NotificationBell username={username} />
          <UserSwitcher value={username} onChange={onUsernameChange} />
        </Space>
      </Header>

      <Content style={{ padding: '24px 32px', maxWidth: 1280, width: '100%', margin: '0 auto' }}>
        {children}
      </Content>

      <Footer style={{ borderTop: `1px solid ${colors.border}`, marginTop: 24 }}>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
          GPU 型号、分区、QoS 和配额等信息以平台页面为准。
        </Typography.Text>
      </Footer>
    </Layout>
  )
}
