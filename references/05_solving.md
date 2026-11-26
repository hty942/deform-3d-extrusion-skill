# 生成数据库与求解

## 1. 生成数据库

1. Pre 里 `Database Generation` → `Check Data`。
2. 无 Error 后 `Generate DB`。
3. 若已有结果步，会弹 **LOST STEPS**（"最后一个已存步是 N，其后的步将被擦除"）→ 确认后选 **Yes**。
4. 成功标志：`Done writing database`，Step Info 显示 Current / Last / Stored。

**DB 正在写入时不要开 Post**，会锁库或读到半成品。

## 2. 两种启动方式（关键区别）

| 方式 | 路径 | 是否需要服务器 | 本机结论 |
|---|---|---|---|
| **GUI 本地** | 主界面 `Simulation → Start`（F9） | 否 | **推荐**，本机实测可用 |
| **Run (options) → Start** | 主界面右侧 `Run (options)` | 是（批处理队列 + 共享点） | 单机没配时只报 `Can not submit job!` / `Neither batch queue server nor simulation server is ready!` |
| **批处理** | `3D\DEF_ARM.COM <name> B` | 否 | 可用；目录里必须有空文件 `64bit.dat` |

> `Run (options)` 里的 `Check Server` 在没配服务器时会把 `SYS_SERVER_NAME` 写成 `none`，反而把界面搞坏。**不要点它。**

## 3. 64 位陷阱

- `DEF_ARM.COM` 在算例目录里找不到 **`64bit.dat`** 时，会打印 `Running 32bit simulation` 并在 1 秒内退出（日志里 FEM MESSAGE 为空）。
- 解决：在算例目录建一个**空文件** `64bit.dat`。
- GUI 路径对应 `Run Option → Machine = 64 bit`；F9 使用 Run Option 里保存的机器设置（本次实测为 64 bit），**以日志里的 `Running 64bit simulation` 为准**，不要只信界面。

## 4. 监控

```powershell
Get-Content <name>.LOG -Tail 20
Get-Content <name>.MSG -Tail 20
```

| 文件 | 看什么 |
|---|---|
| `.LOG` | 每一步的 `STEP`、`STROKE`、`TIME`、`Remeshing at Step`、`bad element shape` |
| `.MSG` | 每步的迭代收敛、温度计算（`TEMPERATURE CALCULATION FOR STEP`）、单元质量分布 |
| `DEF_SIMULATION.log` | JobId 与启动过程 |

正常特征：步数稳定推进；重划次数远小于步数。
异常特征：`PROGRAM STOPPED FOR REMESHING!` 连续出现且行程几乎不前进 → 网格问题，见 `09_troubleshooting.md`。

## 5. 中止与恢复

- GUI：`Simulation → Stop`（F10）；主界面显示 `Aborting <name>`。
- 停止后求解进程可能残留（`DEF_SIM_64`、`DEF_ARM`、`DEF_ARM_CTL3`、`DEF_SIMULATION`），确认结束再操作 DB。
- 求解中 DB 会临时改名为 `FOR003`，`tr.DB` 此时不存在是正常的；结束后自动改回。
- 异常退出后若留下 `FOR003.LOCK` / `DEFORM_RUNNING_JOB_STATUS.TXT` / `JobId`，会造成"Database 被占用 / 无法生成"，需清理后再继续。

## 6. 批处理脚本

```powershell
.\scripts\run_batch.ps1 -CaseDir C:\cases\c10 -Name c10 -Wait
```

脚本做的事：检查/创建 `64bit.dat` → 以算例目录为工作目录启动 `DEF_ARM.COM <name> B` → 轮询日志打印进度 → 结束时报告步数与耗时。

## 7. 时间预期（本机实测，16 GB）

- 19 万单元瞬态、含传热：约 40 s/步（含温度迭代），13 步 + 5 次重划 ≈ 26 分钟。
- 61 万单元稳态 ALE：分钟级到十几分钟（视迭代）。
- 加密到 60 万单元的瞬态：预计 1～2 分钟/步，跑 100 步要数小时——排计划时按这个量级估。
