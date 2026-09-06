import runStyles from '../run/run.module.css'
import styles from './simpleRun.module.css'

export function RunCommand({ command }: { command: string }) {
  return (
    <details className={styles.commandDisclosure}>
      <summary>执行命令</summary>
      <pre className={runStyles.command} aria-label="执行命令代码">
        <code>{command}</code>
      </pre>
    </details>
  )
}
