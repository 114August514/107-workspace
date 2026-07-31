/**
 * 找出运行方案里在**当前空间**解析不了的引用。
 *
 * 主要是 Fork 之后的情况：`${{ secrets.HF_TOKEN }}` 这类表达式跟着复制过来了，
 * 但值留在了源空间（GR-012 规则 4）。提交前检查会拦下，可是等到点提交才知道
 * 太晚了——**用户需要在列表上就看见「这条跑不了，缺什么」**。
 *
 * 这里只做展示，不是安全边界：真正的拦截在后端的提交前检查。
 * 判断规则和后端的 `resolve_env` 保持一致，两边都改动的时候要一起改。
 */

/** `${{ secrets.NAME }}` / `${{ vars.NAME }}`，容忍花括号内的空格。 */
const REFERENCE = /^\$\{\{\s*(secrets|vars)\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}$/

export interface MissingReference {
  /** 环境变量名，也就是表达式左边那个。 */
  envName: string
  kind: 'secret' | 'variable'
  /** 引用的 Secret 或 Variable 名称。 */
  name: string
}

export function findMissingReferences(
  environmentVariables: Record<string, string>,
  available: { secrets: string[]; variables: string[] },
): MissingReference[] {
  const missing: MissingReference[] = []
  for (const [envName, expression] of Object.entries(environmentVariables)) {
    const match = REFERENCE.exec(expression.trim())
    if (!match) continue // 字面值，不需要解析

    const [, kind, name] = match
    if (!name) continue
    const pool = kind === 'secrets' ? available.secrets : available.variables
    if (!pool.includes(name)) {
      missing.push({ envName, kind: kind === 'secrets' ? 'secret' : 'variable', name })
    }
  }
  return missing
}

export function describeMissing(missing: MissingReference[]): string {
  return missing
    .map((m) => `${m.envName} 引用的${m.kind === 'secret' ? ' Secret ' : ' Variable '}${m.name}`)
    .join('；')
}
