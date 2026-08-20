/** 版本文件预览的类型判断：按扩展名分流，判断不了的不硬猜。 */

const IMAGE_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'ico', 'avif', 'svg'])

// 按文本解码不会损坏、适合以源码形式展示的类型。
const TEXT_EXTENSIONS = new Set([
  'txt',
  'md',
  'rst',
  'py',
  'ipynb',
  'js',
  'jsx',
  'ts',
  'tsx',
  'json',
  'yaml',
  'yml',
  'toml',
  'ini',
  'cfg',
  'conf',
  'csv',
  'tsv',
  'sh',
  'bash',
  'zsh',
  'html',
  'htm',
  'css',
  'xml',
  'sql',
  'gitignore',
  'dockerfile',
  'license',
])

export type PreviewKind = 'image' | 'text' | 'unknown'

export function previewKind(path: string): PreviewKind {
  const name = path.split('/').pop() ?? path
  const extension = name.split('.').pop()?.toLowerCase() ?? ''
  if (IMAGE_EXTENSIONS.has(extension)) return 'image'
  if (TEXT_EXTENSIONS.has(extension)) return 'text'
  return 'unknown'
}
