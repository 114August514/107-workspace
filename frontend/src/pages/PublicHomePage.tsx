import { Button } from '@primer/react'

import { startLogin } from '../auth/AuthProvider'
import { authCopy } from '../auth/authCopy'
import styles from './PublicHomePage.module.css'

export function PublicHomePage() {
  return (
    <div className={styles.page}>
      <header>
        <h1 className={styles.title}>{authCopy.publicTitle}</h1>
        <p className={styles.subtitle}>{authCopy.publicSubtitle}</p>
      </header>
      <div className={styles.actions}>
        <Button variant="primary" onClick={() => startLogin()}>
          {authCopy.login}
        </Button>
      </div>
    </div>
  )
}
