import { Button, Flash, FormControl, Label, Select, TextInput } from '@primer/react'
import { useEffect, useState } from 'react'

import { api } from '../../api/client'
import type { EnvironmentPublicationAttempt } from '../../api/types'

type RuntimeKind = 'modules' | 'apptainer_sif'

export function EnvironmentPublicationPanel({ environmentId }: { environmentId: string }) {
  const [runtimeKind, setRuntimeKind] = useState<RuntimeKind>('modules')
  const [version, setVersion] = useState('')
  const [modules, setModules] = useState('python3.12/3.12')
  const [sif, setSif] = useState<File | null>(null)
  const [sourceUri, setSourceUri] = useState('')
  const [sourceDigest, setSourceDigest] = useState('')
  const [attempt, setAttempt] = useState<EnvironmentPublicationAttempt | null>(null)
  const [loadingAttempts, setLoadingAttempts] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoadingAttempts(true)
    setError('')
    void api
      .environmentPublicationAttempts(environmentId)
      .then((attempts) => {
        if (active) setAttempt(attempts[0] ?? null)
      })
      .catch((cause: Error) => {
        if (active) setError(cause.message)
      })
      .finally(() => {
        if (active) setLoadingAttempts(false)
      })
    return () => {
      active = false
    }
  }, [environmentId])

  useEffect(() => {
    if (!attempt || ['succeeded', 'failed'].includes(attempt.status)) return
    let active = true
    const timer = window.setInterval(() => {
      void api
        .environmentPublicationAttempt(attempt.id)
        .then((current) => {
          if (active) setAttempt(current)
        })
        .catch((cause: Error) => {
          if (active) setError(cause.message)
        })
    }, 1000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [attempt])

  const publish = async () => {
    setSubmitting(true)
    setError('')
    try {
      const created =
        runtimeKind === 'modules'
          ? await api.publishModulesEnvironment(environmentId, {
              version,
              description: '',
              modules: modules
                .split(',')
                .map((item) => item.trim())
                .filter(Boolean),
            })
          : await api.publishSifEnvironment(environmentId, {
              version,
              sif: sif!,
              source_uri: sourceUri,
              source_digest: sourceDigest,
              architecture: 'x86_64',
            })
      setAttempt(created)
    } catch (cause) {
      setError((cause as Error).message)
    } finally {
      setSubmitting(false)
    }
  }

  const refresh = async () => {
    if (!attempt) return
    setError('')
    try {
      setAttempt(await api.environmentPublicationAttempt(attempt.id))
    } catch (cause) {
      setError((cause as Error).message)
    }
  }

  const ready = version.trim() && (runtimeKind === 'modules' ? modules.trim() : sif)

  return (
    <section aria-labelledby="environment-publication-title">
      <h2 id="environment-publication-title">发布运行环境版本</h2>
      <FormControl id="environment-runtime-kind" required>
        <FormControl.Label>Runtime kind</FormControl.Label>
        <Select
          value={runtimeKind}
          onChange={(event) => setRuntimeKind(event.target.value as RuntimeKind)}
        >
          <Select.Option value="modules">Environment Modules</Select.Option>
          <Select.Option value="apptainer_sif">Apptainer SIF</Select.Option>
        </Select>
      </FormControl>
      <FormControl id="environment-version-label" required>
        <FormControl.Label>版本标签</FormControl.Label>
        <TextInput value={version} onChange={(event) => setVersion(event.target.value)} />
      </FormControl>
      {runtimeKind === 'modules' ? (
        <FormControl id="environment-modules" required>
          <FormControl.Label>平台模块（按加载顺序，以逗号分隔）</FormControl.Label>
          <TextInput value={modules} onChange={(event) => setModules(event.target.value)} block />
        </FormControl>
      ) : (
        <>
          <FormControl id="environment-sif" required>
            <FormControl.Label>SIF 文件</FormControl.Label>
            <TextInput
              type="file"
              accept=".sif,application/octet-stream"
              onChange={(event) => setSif(event.target.files?.[0] ?? null)}
            />
          </FormControl>
          <FormControl id="environment-source-uri">
            <FormControl.Label>来源 URI</FormControl.Label>
            <TextInput value={sourceUri} onChange={(event) => setSourceUri(event.target.value)} />
          </FormControl>
          <FormControl id="environment-source-digest">
            <FormControl.Label>来源摘要</FormControl.Label>
            <TextInput
              value={sourceDigest}
              onChange={(event) => setSourceDigest(event.target.value)}
            />
          </FormControl>
          <FormControl id="environment-architecture" disabled>
            <FormControl.Label>架构</FormControl.Label>
            <TextInput value="x86_64" />
          </FormControl>
        </>
      )}
      <Button variant="primary" disabled={!ready || submitting} onClick={publish}>
        {submitting ? '正在创建发布尝试…' : '创建发布尝试'}
      </Button>
      {loadingAttempts ? <Flash>正在加载最近发布尝试…</Flash> : null}
      {error ? <Flash variant="danger">{error}</Flash> : null}
      {attempt ? (
        <Flash variant={attempt.status === 'failed' ? 'danger' : 'default'}>
          <Label>{attempt.status}</Label> {attempt.validation_summary}
          {attempt.failure_reason ? `：${attempt.failure_reason}` : ''}
          {!['succeeded', 'failed'].includes(attempt.status) ? (
            <Button onClick={refresh}>刷新校验状态</Button>
          ) : null}
        </Flash>
      ) : null}
    </section>
  )
}
