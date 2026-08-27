import { DeleteOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Col, Form, Input, Row, Select, Space, Typography } from 'antd'
import { useCallback, useEffect, useMemo, useState } from 'react'

import { api } from '../../api/client'
import type { SharedResourceDetail } from '../../api/types'

export interface SharedResourceInputRow {
  resource_id?: string
  source_id?: string
  source_subpath?: string
  access_path?: string
}

function normalizeAccessPath(value: string): string | null {
  const candidate = value.trim().replaceAll('\\', '/')
  if (!candidate.startsWith('/')) return null
  const parts = candidate.split('/')
  if (parts.includes('..')) return null
  const normalized: string[] = []
  for (const part of parts) {
    if (!part || part === '.') continue
    normalized.push(part)
  }
  return `/${normalized.join('/')}`
}

function accessPathsConflict(left: string, right: string): boolean {
  if (left === right || left === '/' || right === '/') return true
  return left.startsWith(`${right}/`) || right.startsWith(`${left}/`)
}

function validateSourceSubpath(value: string): string | null {
  const candidate = value.trim().replaceAll('\\', '/').replace(/^\/+/, '')
  if (!candidate) return null
  const parts: string[] = []
  for (const part of candidate.split('/')) {
    if (!part || part === '.') continue
    if (part === '..') {
      if (parts.length === 0) return '来源子路径不能越出资源版本根目录'
      parts.pop()
    } else {
      parts.push(part)
    }
  }
  return null
}

export function SharedResourceInputBindings() {
  const form = Form.useFormInstance()
  const rows = (Form.useWatch('inputs', form) ?? []) as SharedResourceInputRow[]
  const [resources, setResources] = useState<SharedResourceDetail[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  const loadResources = useCallback(() => setReloadToken((value) => value + 1), [])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    api
      .listSharedResources()
      .then((items) => Promise.all(items.map((item) => api.getSharedResource(item.id))))
      .then((details) => {
        if (!active) return
        setResources(details)
        const resourceByVersion = new Map(
          details.flatMap((resource) =>
            resource.versions.map((version) => [version.id, resource.id] as const),
          ),
        )
        const currentRows = (form.getFieldValue('inputs') ?? []) as SharedResourceInputRow[]
        form.setFieldValue(
          'inputs',
          currentRows.map((row) => ({
            ...row,
            resource_id: row.resource_id ?? resourceByVersion.get(row.source_id ?? ''),
          })),
        )
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason : new Error(String(reason)))
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [form, reloadToken])

  const resourcesById = useMemo(
    () => new Map(resources.map((resource) => [resource.id, resource])),
    [resources],
  )
  const availableVersionCount = resources.reduce(
    (count, resource) => count + resource.versions.length,
    0,
  )

  const validateAccessPath = (rowIndex: number, value: string | undefined) => {
    const normalized = normalizeAccessPath(value ?? '')
    if (normalized === null) {
      return Promise.reject(new Error('请输入以 / 开头且不包含 .. 的绝对路径'))
    }
    const conflict = rows.some((row, index) => {
      if (index === rowIndex || !row?.access_path) return false
      const other = normalizeAccessPath(row.access_path)
      return other !== null && accessPathsConflict(normalized, other)
    })
    return conflict
      ? Promise.reject(new Error('输入访问路径不能重复或互相包含'))
      : Promise.resolve()
  }

  return (
    <Space direction="vertical" size="small" style={{ width: '100%' }}>
      <Typography.Title level={5} style={{ marginBottom: 0 }}>
        运行输入
      </Typography.Title>
      <Typography.Paragraph type="secondary" style={{ margin: 0 }}>
        每项输入固定一个确定的资源版本，并以只读方式暴露到输入访问路径。保存后不会自动切换版本。
      </Typography.Paragraph>

      {loading ? (
        <Alert type="info" showIcon message="正在读取当前可使用的共享资源…" />
      ) : error ? (
        <Alert
          type="error"
          showIcon
          message="无法读取当前可使用的共享资源"
          description={
            <Button size="small" icon={<ReloadOutlined />} onClick={loadResources}>
              重试
            </Button>
          }
        />
      ) : availableVersionCount === 0 ? (
        <Alert
          type="warning"
          showIcon
          message="当前没有可使用的资源版本"
          description="请先发布资源版本，或让资源 Owner 为 Project Owner 建立 USE Grant。"
        />
      ) : null}

      <Form.List name="inputs">
        {(fields, { add, remove }) => (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            {fields.length === 0 && !loading && !error && (
              <Typography.Text type="secondary">这个运行方案还没有运行输入。</Typography.Text>
            )}
            {fields.map((field, index) => {
              const row = rows[index]
              const resource = resourcesById.get(row?.resource_id ?? '')
              const versionOptions = (resource?.versions ?? []).map((version) => ({
                value: version.id,
                label: `${version.label} · ${version.file_count} 个文件`,
              }))
              if (
                row?.source_id &&
                !versionOptions.some((option) => option.value === row.source_id)
              ) {
                versionOptions.push({
                  value: row.source_id,
                  label: `已保存版本 ${row.source_id} · 当前不可用`,
                })
              }
              return (
                <Card key={field.key} size="small">
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Row gutter={12} align="middle">
                      <Col xs={24} md={11}>
                        <Form.Item
                          name={[field.name, 'resource_id']}
                          label="共享资源"
                          rules={[{ required: true, message: '请选择共享资源' }]}
                        >
                          <Select
                            placeholder="选择当前可使用的共享资源"
                            options={resources.map((item) => ({
                              value: item.id,
                              label: `${item.name} · ${item.owner.display_name}`,
                              disabled: item.versions.length === 0,
                            }))}
                            onChange={() => {
                              form.setFieldValue(['inputs', field.name, 'source_id'], undefined)
                            }}
                          />
                        </Form.Item>
                      </Col>
                      <Col xs={24} md={11}>
                        <Form.Item
                          name={[field.name, 'source_id']}
                          label="资源版本"
                          rules={[{ required: true, message: '请选择确定的资源版本' }]}
                        >
                          <Select
                            placeholder={resource ? '选择确定的资源版本' : '请先选择共享资源'}
                            disabled={!resource}
                            options={versionOptions}
                          />
                        </Form.Item>
                      </Col>
                      <Col xs={24} md={2}>
                        <Button
                          type="text"
                          danger
                          icon={<DeleteOutlined />}
                          aria-label={`删除运行输入 ${index + 1}`}
                          onClick={() => remove(field.name)}
                        />
                      </Col>
                    </Row>
                    <Row gutter={12}>
                      <Col xs={24} md={12}>
                        <Form.Item
                          name={[field.name, 'source_subpath']}
                          label="来源子路径"
                          rules={[
                            {
                              validator: (_, value: string | undefined) => {
                                const problem = validateSourceSubpath(value ?? '')
                                return problem
                                  ? Promise.reject(new Error(problem))
                                  : Promise.resolve()
                              },
                            },
                          ]}
                        >
                          <Input placeholder="例如：train/" />
                        </Form.Item>
                      </Col>
                      <Col xs={24} md={12}>
                        <Form.Item
                          name={[field.name, 'access_path']}
                          label="输入访问路径"
                          rules={[
                            { required: true, message: '请填写输入访问路径' },
                            {
                              validator: (_, value: string | undefined) =>
                                validateAccessPath(index, value),
                            },
                          ]}
                        >
                          <Input placeholder="/inputs/train" />
                        </Form.Item>
                      </Col>
                    </Row>
                  </Space>
                </Card>
              )
            })}
            <Button
              type="dashed"
              icon={<PlusOutlined />}
              disabled={loading || Boolean(error) || availableVersionCount === 0}
              onClick={() =>
                add({
                  resource_id: undefined,
                  source_id: undefined,
                  source_subpath: '',
                  access_path: '',
                })
              }
            >
              添加运行输入
            </Button>
          </Space>
        )}
      </Form.List>
    </Space>
  )
}
