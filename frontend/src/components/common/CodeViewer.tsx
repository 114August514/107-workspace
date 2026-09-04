import { Highlight, themes, type Language } from 'prism-react-renderer'

import styles from './CodeViewer.module.css'

interface Props {
  id?: string
  content: string
  ariaLabel: string
  language?: string
}

/** Read-only, line-numbered viewer for immutable text and source content. */
export function CodeViewer({ id, content, ariaLabel, language }: Props) {
  if (language) {
    return (
      <Highlight code={content} language={language as Language} theme={themes.github}>
        {({ tokens, getLineProps, getTokenProps }) => (
          <pre id={id} className={styles.viewer} tabIndex={0} aria-label={ariaLabel}>
            <code className={styles.code}>
              {tokens.map((line, lineIndex) => {
                const lineProps = getLineProps({ line })
                return (
                  <span
                    key={lineIndex}
                    {...lineProps}
                    className={`${styles.line} ${lineProps.className ?? ''}`}
                  >
                    <span className={styles.lineContent}>
                      {line.map((token, tokenIndex) => (
                        <span key={tokenIndex} {...getTokenProps({ token })} />
                      ))}
                    </span>
                  </span>
                )
              })}
            </code>
          </pre>
        )}
      </Highlight>
    )
  }

  return (
    <pre id={id} className={styles.viewer} tabIndex={0} aria-label={ariaLabel}>
      <code className={styles.code}>
        {content.split('\n').map((line, index) => (
          <span key={index} className={styles.line}>
            <span className={styles.lineContent}>{line || '\u200b'}</span>
          </span>
        ))}
      </code>
    </pre>
  )
}
