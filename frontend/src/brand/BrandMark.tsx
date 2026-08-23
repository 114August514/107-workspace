export type BrandMarkCandidate = 1 | 2 | 3

interface Props {
  candidate: BrandMarkCandidate
  size: 16 | 24 | 32
  label?: string
  decorative?: boolean
}

const candidateTitles: Record<BrandMarkCandidate, string> = {
  1: '候选 1：开放数字',
  2: '候选 2：节点连接',
  3: '候选 3：数字方章',
}

/**
 * Issue #64 人工视觉门使用的三个 107 产品标识候选。
 *
 * 这些几何图形只来自数字与计算节点母题，不包含或改造 USTC 校徽、校名等官方资产。
 * 人工选定方案后删除未采用的 candidate 分支，不把候选切换能力带入产品 runtime。
 */
export function BrandMark({ candidate, size, label, decorative = false }: Props) {
  const accessibility = decorative
    ? { 'aria-hidden': true as const }
    : { role: 'img', 'aria-label': label ?? candidateTitles[candidate] }

  return (
    <svg
      {...accessibility}
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      focusable="false"
    >
      {candidate === 1 ? <OpenNumeral /> : null}
      {candidate === 2 ? <NodeNumeral /> : null}
      {candidate === 3 ? <TileNumeral /> : null}
    </svg>
  )
}

function OpenNumeral() {
  return (
    <g
      stroke="var(--brandColor-primary)"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3.5 10.5 7 7.5V24.5" />
      <rect x="11" y="7.5" width="9" height="17" rx="4.5" />
      <path d="M23 8H30L25 24.5" />
    </g>
  )
}

function NodeNumeral() {
  return (
    <>
      <rect
        x="1.5"
        y="4.5"
        width="29"
        height="23"
        rx="7"
        stroke="var(--brandColor-primary)"
        strokeWidth="2"
      />
      <circle cx="1.75" cy="16" r="2" fill="var(--brandColor-primary)" />
      <circle cx="30.25" cy="16" r="2" fill="var(--brandColor-primary)" />
      <g
        stroke="var(--brandColor-primary)"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M5 12.5 7.5 10.5V21.5" />
        <rect x="11" y="10.5" width="7" height="11" rx="3.5" />
        <path d="M21 10.5H27L23 21.5" />
      </g>
    </>
  )
}

function TileNumeral() {
  return (
    <>
      <rect width="32" height="32" rx="7" fill="var(--brandColor-primary)" />
      <g
        stroke="var(--brandColor-on-primary)"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M3.5 11 7 8V24" />
        <rect x="11" y="8" width="9" height="16" rx="4.5" />
        <path d="M23 8.5H29L25 24" />
      </g>
    </>
  )
}
