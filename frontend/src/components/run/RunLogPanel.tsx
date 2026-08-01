import { Alert, Empty, Tabs, Typography } from 'antd'

import type { LogChunk } from '../../api/types'
import { colors, fontFamilyCode } from '../../theme'

const LOG_STYLE: React.CSSProperties = {
  background: colors.terminalBg,
  color: colors.terminalText,
  padding: 16,
  borderRadius: 6,
  maxHeight: 480,
  overflow: 'auto',
  fontFamily: fontFamilyCode,
  fontSize: 13,
  lineHeight: 1.6,
  whiteSpace: 'pre-wrap',
  margin: 0,
}

/**
 * 打开时默认停在哪一路输出。
 *
 * 默认停在 stdout 的话，失败的 Run 打开是一片空白——报错在 stderr，
 * 用户得自己发现旁边还有一个标签页。**出问题的时候最不该让人多找一步。**
 *
 * 规则：失败的 Run 优先看 stderr；否则停在第一个有内容的。
 */
function defaultStream(chunks: LogChunk[], failed: boolean): string | undefined {
  const hasContent = (stream: string) =>
    chunks.find((chunk) => chunk.stream === stream && chunk.content.trim())

  if (failed && hasContent('stderr')) return 'stderr'
  return chunks.find((chunk) => chunk.content.trim())?.stream ?? chunks[0]?.stream
}

interface Props {
  chunks: LogChunk[]
  /** Run 是不是失败了。失败时默认展示 stderr。 */
  failed?: boolean
}

/**
 * 标准输出与标准错误。
 *
 * 后端在返回之前会把已知的 Secret 明文替换成 ***，即使用户程序自己
 * 把 Token 打到了 stdout。
 */
export function RunLogPanel({ chunks, failed = false }: Props) {
  const items = chunks.map((chunk) => ({
    key: chunk.stream,
    label: chunk.stream === 'stdout' ? '标准输出' : '标准错误',
    children: (
      <>
        {chunk.truncated && (
          <Alert
            type="warning"
            showIcon
            style={{ marginBottom: 12 }}
            message="日志过长，这里只显示尾部内容"
          />
        )}
        {chunk.content.trim() ? (
          <pre style={LOG_STYLE}>{chunk.content}</pre>
        ) : (
          <Empty description="这一路输出目前是空的" />
        )}
      </>
    ),
  }))

  return (
    <>
      <Tabs defaultActiveKey={defaultStream(chunks, failed)} items={items} />
      <Typography.Text type="secondary">
        日志中的 Secret 明文会被替换成 ***，这是防止密钥泄露的最后一道防线。
      </Typography.Text>
    </>
  )
}
