import { FormControl } from '@primer/react'
import type { ReactNode } from 'react'

export function RunField({
  label,
  error,
  caption,
  children,
  required = false,
  disabled,
}: {
  label: string
  error?: string
  caption?: ReactNode
  children: ReactNode
  required?: boolean
  disabled?: boolean
}) {
  return (
    <FormControl required={required} disabled={disabled}>
      <FormControl.Label>{label}</FormControl.Label>
      {children}
      {error ? (
        <FormControl.Validation variant="error">{error}</FormControl.Validation>
      ) : caption ? (
        <FormControl.Caption>{caption}</FormControl.Caption>
      ) : null}
    </FormControl>
  )
}
