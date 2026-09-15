# API 契约索引

[后端契约](../backend/contracts/openapi.json) 由后端路由导出；
[前端消费快照](../frontend/contracts/openapi.json) 随前端提交固定。

`make contract` 在集成工作区导出后端契约、更新前端快照与来源记录并生成类型。
`make contract-check` 验证所选前后端版本的契约和生成类型一致。
前后端仓库各自的检查无需其他仓库。
