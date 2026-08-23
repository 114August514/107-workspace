# 接口契约

本目录保存跨组件共享的机器可读契约，不保存人工维护的产品或接口说明。当前只有
[`openapi.json`](openapi.json)，它由 FastAPI 后端导出，并用于生成前端 TypeScript 类型。

```text
backend 路由与 DTO
        |
        v
contracts/openapi.json
        |
        v
frontend/src/api/schema.d.ts
```

两个生成物都不得手工编辑。在仓库根目录运行统一入口：

```bash
make contract
make contract-check
```

修改后端 DTO 或路由时，应提交 `openapi.json` 与
`frontend/src/api/schema.d.ts` 的对应变化。`make check` 会重新生成两者并拒绝未提交的
漂移。

面向人的产品、工程与运维说明仍放在 [`docs/`](../docs/README.md)；后端实现细节属于
[`backend/`](../backend/README.md)，前端类型消费方式见
[`frontend/README.md`](../frontend/README.md)。
