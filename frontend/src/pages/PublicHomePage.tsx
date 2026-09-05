import { Banner, Button, FormControl, TextInput } from '@primer/react'
import { useSearchParams } from 'react-router-dom'

import { startLogin } from '../auth/AuthProvider'
import { authCopy } from '../auth/authCopy'
import styles from './PublicHomePage.module.css'

export function PublicHomePage() {
  const [params] = useSearchParams()
  const loginError = params.get('login_error') === '1'

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
      <section className={styles.admin} aria-label={authCopy.adminLogin}>
        <h2 className={styles.adminTitle}>{authCopy.adminLogin}</h2>
        <p className={styles.subtitle}>{authCopy.adminHint}</p>
        {loginError ? (
          <Banner variant="critical">
            <Banner.Title>{authCopy.adminLoginFailed}</Banner.Title>
          </Banner>
        ) : null}
        <form method="post" action="/login/password" className={styles.adminForm}>
          <FormControl>
            <FormControl.Label>{authCopy.adminUsername}</FormControl.Label>
            <TextInput name="username" autoComplete="username" block />
          </FormControl>
          <FormControl>
            <FormControl.Label>{authCopy.adminPassword}</FormControl.Label>
            <TextInput name="password" type="password" autoComplete="current-password" block />
          </FormControl>
          <Button type="submit" variant="default">
            {authCopy.adminLogin}
          </Button>
        </form>
      </section>
    </div>
  )
}
