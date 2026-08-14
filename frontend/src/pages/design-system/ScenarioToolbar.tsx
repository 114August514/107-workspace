import { SyncIcon } from '@primer/octicons-react'
import { Button, ButtonGroup, FormControl, SegmentedControl, Stack, TextInput } from '@primer/react'
import { useEffect, useState } from 'react'

import type { Capability, ContentScale, DataState, ScenarioOption } from './model'
import { CAPABILITIES, CONTENT_SCALES, DATA_STATES } from './model'
import styles from './DesignSystemPage.module.css'

interface Props {
  dataState: DataState
  capability: Capability
  contentScale: ContentScale
  canvasWidth: number | null
  delayMs: number
  onDataStateChange: (value: DataState) => void
  onCapabilityChange: (value: Capability) => void
  onContentScaleChange: (value: ContentScale) => void
  onCanvasWidthChange: (value: number | null) => void
  onDelayChange: (value: number) => void
  onReset: () => void
}

interface NumericControlProps {
  id: string
  label: string
  caption: string
  unit: string
  value: number | null
  min: number
  max: number
  presets: { label: string; value: number }[]
  extraPreset?: { label: string; selected: boolean; onSelect: () => void }
  onCommit: (value: number) => void
}

function NumericControl({
  id,
  label,
  caption,
  unit,
  value,
  min,
  max,
  presets,
  extraPreset,
  onCommit,
}: NumericControlProps) {
  const [draft, setDraft] = useState(value === null ? '' : String(value))
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setDraft(value === null ? '' : String(value))
    setError(null)
  }, [value])

  const commit = () => {
    if (draft.trim() === '') {
      setError(`请输入${label}`)
      return
    }

    const parsed = Number(draft)
    if (!Number.isInteger(parsed) || parsed < min || parsed > max) {
      setError(`请输入 ${min}–${max} 之间的整数`)
      return
    }

    setError(null)
    onCommit(parsed)
  }

  return (
    <div className={styles.numericControl}>
      <FormControl id={id}>
        <FormControl.Label>{label}</FormControl.Label>
        <TextInput
          type="number"
          inputMode="numeric"
          min={min}
          max={max}
          step={1}
          placeholder={value === null ? '自适应' : undefined}
          value={draft}
          validationStatus={error ? 'error' : undefined}
          trailingVisual={<span className={styles.inputUnit}>{unit}</span>}
          onChange={(event) => setDraft(event.currentTarget.value)}
          onBlur={commit}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              commit()
            }
          }}
        />
        {error ? <FormControl.Validation variant="error">{error}</FormControl.Validation> : null}
        <FormControl.Caption>{caption}</FormControl.Caption>
      </FormControl>
      <ButtonGroup aria-label={`${label}预设`}>
        {presets.map((preset) => (
          <Button
            key={preset.value}
            size="small"
            variant={value === preset.value ? 'primary' : 'default'}
            onClick={() => onCommit(preset.value)}
          >
            {preset.label}
          </Button>
        ))}
        {extraPreset ? (
          <Button
            size="small"
            variant={extraPreset.selected ? 'primary' : 'default'}
            onClick={extraPreset.onSelect}
          >
            {extraPreset.label}
          </Button>
        ) : null}
      </ButtonGroup>
    </div>
  )
}

function SegmentedField<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: T
  options: ScenarioOption<T>[]
  onChange: (value: T) => void
}) {
  return (
    <div className={styles.segmentedField}>
      <span className={styles.controlLabel}>{label}</span>
      <SegmentedControl
        aria-label={label}
        fullWidth
        variant={{ narrow: 'dropdown', regular: 'default' }}
        onChange={(selectedIndex) => {
          const selected = options[selectedIndex]
          if (selected) onChange(selected.value)
        }}
      >
        {options.map((option) => (
          <SegmentedControl.Button key={option.value} selected={option.value === value}>
            {option.label}
          </SegmentedControl.Button>
        ))}
      </SegmentedControl>
    </div>
  )
}

export function ScenarioToolbar({
  dataState,
  capability,
  contentScale,
  canvasWidth,
  delayMs,
  onDataStateChange,
  onCapabilityChange,
  onContentScaleChange,
  onCanvasWidthChange,
  onDelayChange,
  onReset,
}: Props) {
  return (
    <Stack as="section" gap="normal" padding="normal" className={styles.toolbar}>
      <Stack direction="horizontal" align="center" justify="space-between" gap="normal" wrap="wrap">
        <div>
          <h2 className={styles.toolbarTitle}>场景控制台</h2>
          <p className={styles.toolbarDescription}>精确复现状态、权限、内容边界和请求节奏。</p>
        </div>
        <Button leadingVisual={SyncIcon} onClick={onReset}>
          恢复默认值
        </Button>
      </Stack>

      <div className={styles.segmentedGrid}>
        <SegmentedField
          label="数据状态"
          value={dataState}
          options={DATA_STATES}
          onChange={onDataStateChange}
        />
        <SegmentedField
          label="用户能力"
          value={capability}
          options={CAPABILITIES}
          onChange={onCapabilityChange}
        />
        <SegmentedField
          label="内容长度"
          value={contentScale}
          options={CONTENT_SCALES}
          onChange={onContentScaleChange}
        />
      </div>

      <div className={styles.numericGrid}>
        <NumericControl
          id="canvas-width"
          label="画布宽度"
          caption="320–1440 px；预设与精确输入共享同一值。"
          unit="px"
          value={canvasWidth}
          min={320}
          max={1440}
          presets={[
            { label: '375 px', value: 375 },
            { label: '768 px', value: 768 },
          ]}
          extraPreset={{
            label: '自适应',
            selected: canvasWidth === null,
            onSelect: () => onCanvasWidthChange(null),
          }}
          onCommit={onCanvasWidthChange}
        />
        <NumericControl
          id="request-delay"
          label="请求延迟"
          caption="0–10000 ms；用于观察 loading 到结果的转换。"
          unit="ms"
          value={delayMs}
          min={0}
          max={10_000}
          presets={[
            { label: '即时', value: 0 },
            { label: '800 ms', value: 800 },
            { label: '3 s', value: 3000 },
          ]}
          onCommit={onDelayChange}
        />
      </div>
    </Stack>
  )
}
