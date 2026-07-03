# 11 PRODUCT ROUTE ISOLATION GATE

只有 Gate 2 logits 和 Gate 3 generation quality 都明确通过后，才允许执行本任务。

不得影响 18888 foreground route。

## 目标

验证 experimental 18889 route 是否可以作为 shadow/candidate route。

## 任务

### 1. 审计当前 route

```text
18888 must remain OpenClaw -> diffuse-resident/GGUF
18889 may point to BPU experimental route only
```

### 2. 新建或更新

```text
tools/audit_product_route_isolation.py
```

### 3. 验证

```text
18888 health
18889 health
fallback to 18888
rollback script
queue drain
failure-rate logs
latency p50/p95/p99
no foreground traffic accidentally routed to 18889
```

### 4. 运行 shadow replay

不得接真实 foreground traffic。

## 输出

```text
reports/090_product_route_isolation_gate.json
reports/090_product_route_isolation_gate.md
```

## 判定

`product_route_valid` pass only if:

```text
isolation
fallback
rollback
health
queue drain
latency
failure-rate evidence
```

全部通过。

如果任何一项失败，标记 `product_route_valid fail`，但不要影响 18888。
