import brandMarkUrl from '../assets/brand/107_pig_final.svg'

/**
 * Issue #64 终局确认的 107 Brand Mark。
 *
 * 几何来自 frontend/src/assets/brand/107_pig_final.svg，是独立的产品资产：不引用或复刻
 * USTC 校徽、校名等官方资产。页面 Brand Mark 与 favicon 复用同一份几何与 #0455B6 静态填充，
 * 不保留运行时的 Mark 切换或候选 fallback。
 */

interface Props {
  size: 16 | 24 | 32
  label?: string
  decorative?: boolean
}

export function BrandMark({ size, label, decorative = false }: Props) {
  return (
    <img
      src={brandMarkUrl}
      width={size}
      height={size}
      alt={decorative ? '' : (label ?? '107 Brand Mark')}
      aria-hidden={decorative || undefined}
      draggable={false}
    />
  )
}
