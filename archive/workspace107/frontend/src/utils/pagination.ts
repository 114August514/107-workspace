import type { TablePaginationConfig } from 'antd'

import type { PageOf } from '../api/types'

/**
 * 把后端的分页信封转成 antd Table 的分页配置。
 *
 * 抽出来是为了三个列表页表现一致：页码、总数提示、单页时是否隐藏，
 * 都只在这里定义一次。
 */
export function tablePagination<T>(
  page: PageOf<T> | undefined,
  onChange: (next: number) => void,
): TablePaginationConfig | false {
  if (!page) return false
  return {
    current: page.page,
    pageSize: page.page_size,
    total: page.total,
    onChange,
    // 每页条数由后端决定上限，前端不提供切换，避免出现后端拒绝的取值
    showSizeChanger: false,
    hideOnSinglePage: true,
    showTotal: (total) => `共 ${total} 条`,
  }
}
