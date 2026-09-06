import * as XLSX from 'xlsx'

const HEADER_ALIASES = new Set([
  'username',
  'user',
  'user_name',
  'userid',
  'user_id',
  'login',
  'account',
  '用户名',
  '账号',
  '帐户',
  '账户',
])

const MAX_USERNAMES = 500

function readFileAsArrayBuffer(file: File): Promise<ArrayBuffer> {
  if (typeof file.arrayBuffer === 'function') return file.arrayBuffer()
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as ArrayBuffer)
    reader.onerror = () => reject(reader.error ?? new Error('read failed'))
    reader.readAsArrayBuffer(file)
  })
}

function readFileAsText(file: File): Promise<string> {
  if (typeof file.text === 'function') return file.text()
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ''))
    reader.onerror = () => reject(reader.error ?? new Error('read failed'))
    reader.readAsText(file)
  })
}

export async function parseMemberImportFile(file: File): Promise<string[]> {
  const filename = file.name.toLowerCase()
  const isSpreadsheet = filename.endsWith('.xlsx') || filename.endsWith('.xls')
  if (!isSpreadsheet) {
    return extractUsernames(parseCsvText(await readFileAsText(file)))
  }
  const data = await readFileAsArrayBuffer(file)
  const workbook = XLSX.read(data, { type: 'array', raw: false })
  const sheetName = workbook.SheetNames[0]
  if (!sheetName) return []
  const sheet = workbook.Sheets[sheetName]
  if (!sheet) return []
  const rows = XLSX.utils.sheet_to_json<(string | number | boolean | null | undefined)[]>(sheet, {
    header: 1,
    raw: false,
    blankrows: false,
    defval: '',
  })
  return extractUsernames(rows.map((row) => row.map((cell) => String(cell ?? '').trim())))
}

export function parseCsvText(text: string): string[][] {
  const normalized = text
    .replace(/^\uFEFF/, '')
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
  const lines = normalized.split('\n').filter((line) => line.trim().length > 0)
  if (lines.length === 0) return []
  const delimiter = detectDelimiter(lines[0] ?? '')
  return lines.map((line) => splitCsvLine(line, delimiter).map((cell) => cell.trim()))
}

function detectDelimiter(header: string): string {
  const comma = (header.match(/,/g) ?? []).length
  const semicolon = (header.match(/;/g) ?? []).length
  const tab = (header.match(/\t/g) ?? []).length
  if (tab > comma && tab > semicolon) return '\t'
  if (semicolon > comma) return ';'
  return ','
}

function splitCsvLine(line: string, delimiter: string): string[] {
  const cells: string[] = []
  let current = ''
  let inQuotes = false
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index]
    if (char === '"') {
      if (inQuotes && line[index + 1] === '"') {
        current += '"'
        index += 1
      } else {
        inQuotes = !inQuotes
      }
      continue
    }
    if (char === delimiter && !inQuotes) {
      cells.push(current)
      current = ''
      continue
    }
    current += char
  }
  cells.push(current)
  return cells
}

export function extractUsernames(rows: string[][]): string[] {
  if (rows.length === 0) return []
  const header = rows[0] ?? []
  const headerIndex = header.findIndex((cell) => HEADER_ALIASES.has(cell.toLowerCase()))
  const column = headerIndex >= 0 ? headerIndex : 0
  const start = headerIndex >= 0 ? 1 : 0
  const names: string[] = []
  const seen = new Set<string>()
  for (let index = start; index < rows.length; index += 1) {
    const value = (rows[index]?.[column] ?? '').trim()
    if (!value) continue
    const key = value.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    names.push(value)
    if (names.length >= MAX_USERNAMES) break
  }
  return names
}
