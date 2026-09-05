import { EyeClosedIcon, EyeIcon } from '@primer/octicons-react'
import { Banner, Button, FormControl, TextInput } from '@primer/react'
import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { startLogin } from '../auth/AuthProvider'
import { authCopy } from '../auth/authCopy'
import { BrandMark } from '../brand/BrandMark'
import styles from './PublicHomePage.module.css'

export function PublicHomePage() {
  const [params] = useSearchParams()
  const loginError = params.get('login_error') === '1'
  const [showPassword, setShowPassword] = useState(false)

  return (
    <div className={styles.page}>
      <div className={styles.body}>
        <section className={styles.intro} aria-labelledby="public-home-title">
          <h1 id="public-home-title" className={styles.title}>
            {authCopy.publicTitle}
          </h1>
          <p className={styles.lead}>{authCopy.publicLead}</p>
          <p className={styles.audience}>{authCopy.publicAudience}</p>
          <h2 className={styles.notesTitle}>{authCopy.publicNotesTitle}</h2>
          <ul className={styles.notes}>
            {authCopy.publicNotes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </section>

        <section className={styles.panel} aria-label={authCopy.passwordLogin}>
          <div className={styles.mark} aria-hidden>
            <BrandMark size={32} decorative />
          </div>
          {loginError ? (
            <Banner variant="critical">
              <Banner.Title>{authCopy.passwordLoginFailed}</Banner.Title>
            </Banner>
          ) : null}
          <form method="post" action="/login/password" className={styles.form}>
            <h2 className={styles.visuallyHidden}>{authCopy.passwordLogin}</h2>
            <FormControl>
              <FormControl.Label>{authCopy.username}</FormControl.Label>
              <TextInput name="username" autoComplete="username" block />
            </FormControl>
            <FormControl>
              <FormControl.Label>{authCopy.password}</FormControl.Label>
              <TextInput
                name="password"
                type={showPassword ? 'text' : 'password'}
                autoComplete="current-password"
                block
                trailingAction={
                  <TextInput.Action
                    icon={showPassword ? EyeClosedIcon : EyeIcon}
                    aria-label={showPassword ? authCopy.hidePassword : authCopy.showPassword}
                    onClick={() => setShowPassword((visible) => !visible)}
                  />
                }
              />
            </FormControl>
            <Button type="submit" variant="primary" className={styles.fullWidth}>
              {authCopy.passwordSubmit}
            </Button>
          </form>
          <p className={styles.divider}>
            <span>{authCopy.orSignInWith}</span>
          </p>
          <Button
            type="button"
            variant="default"
            className={styles.fullWidth}
            onClick={() => startLogin()}
          >
            {authCopy.login}
          </Button>
        </section>
      </div>
      <footer className={styles.footer}>{authCopy.publicFooter}</footer>
    </div>
  )
}
