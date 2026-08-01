/**
 * 把「字段名字符串」约束到真实类型上。
 *
 * antd 的 `ColumnsType<T>` 把 `dataIndex` 声明成 `string | number | ...`，
 * 并不检查这个名字在 T 上是否存在。于是后端改一个字段名、生成的类型也跟着变了，
 * 表格里的 `dataIndex: 'exit_code'` 仍然安安静静地渲染成空列——
 * 这正是「接口靠猜」最难发现的一种。
 *
 * 用法：
 *
 *     { title: '退出码', dataIndex: field<Run>('exit_code') }
 *
 * 字段不存在时 TypeScript 直接报错。运行时它就是原样返回字符串，没有任何开销。
 */
export function field<T>(name: Extract<keyof T, string>): string {
  return name
}
