# 故障树（按报错原文查）

## A. 网格类

### `Program stopped because of bad element shape!`
**含义**：某处单元畸变到不可用（负体积/翻转）。
**排查**：
1. 看 `.LOG` 里最后一次 `Remeshing at Step` 的位置与 `.MSG` 里报错的节点号 → 定位区域（通常是模口/工作带）。
2. 局部单元太小或太扁 → 加密度窗口重划。
3. 步长相对最小边长太大 → 步长降到边长/5。
4. 模具与坯料初始穿插 → 检查 Object Positioning。

### `PROGRAM STOPPED FOR REMESHING! THE RELATIVE INTERFERENCE ERROR ... HAS REACHED THE SPECIFIED LIMIT 0.7000000`
**含义**：穿透量达到重划限值，触发自动重划。
**判断**：重划后能继续推进就是正常；连续重划且行程不前进（每次只进 0.02～0.05 mm）就是网格问题，见上一条。

### `***Info: Repeat Remeshing 1` 反复出现
**含义**：重划后仍不合格，系统重试。
**处理**：两次以上就停下来改网格，不要硬等。

## B. 求解启动类

### 1 秒内退出，日志只有 `Running 32bit simulation`
**原因**：目录缺 `64bit.dat`。
**处理**：建空文件 `64bit.dat`。

### `Can not submit job!` / `Neither batch queue server nor simulation server is ready!`
**原因**：用了 `Run (options)` 的 Start，单机没有批处理队列/共享点。
**处理**：改用 `Simulation → Start`（F9）或 `DEF_ARM.COM <name> B`。
**注意**：`Check Server` 会把 `SYS_SERVER_NAME` 写成 `none`，不要点。

### `There's an active job under current directory` / `FOR003.LOCK`
**原因**：上一次求解异常退出，锁未释放。
**处理**：确认求解进程已结束 → 删除 `FOR003.LOCK`、`DEFORM_RUNNING_JOB_STATUS.TXT`、`JobId`、`fort.53` → 若 DB 还被改名成 `FOR003`，改回 `<name>.DB`。

### `Conflict: There is a running job with the same DB name`
**原因**：残留的 job 状态文件。
**处理**：同上。

## C. 数据库/文件类

### `Workpiece (Object 1) needs to have a contact with the primary die (Object 4)`
**原因**：改了 `BCCDEF` 里坯料顶面的接触记录，或初始位置不接触。
**处理**：改杆速只能改 `MOVCTL` + 按比例缩放 `URZ`，**不要动 `BCCDEF` 的 −4 记录**。

### DB 打不开 / 读到一半报错
**原因**：正在求解（DB 被改名成 `FOR003`）、上次写入未完成、路径含中文。
**处理**：确认求解结束；换纯英文路径；用备份。

### 导入 STL 报错
**原因**：路径中文、文件损坏、非水密。
**处理**：`preflight_stl.py` 先查。

## D. 结果类

### 模型小了/大了 25.4 倍
单位制选错（English vs SI）。改算例单位制或缩放几何。

### 坯料完全不动
1. 支承叠放在工作模入口侧（装反了）。
2. 接触关系没定义。
3. 主运动对象没设成 Primary Die，或速度方向错。

### 温度场全是一个颜色
没勾 Heat transfer。回 Pre 勾上 → 重新生成 DB（会擦除旧步）→ 重算。

### 只有一步，没法做动画
稳态 ALE 算例本来就只有一步。要动画必须瞬态（Lagrangian incremental）重算。

### 载荷曲线没有平台段
行程不够，或摩擦/边界条件有问题。短坯料更快进入稳定段。

## E. 内存/性能

### 求解中途被杀、内存爆
- 单元数超预算（16 GB 机器 > 100 万四面体基本没戏）。
- 先用粗网格确认流程，再加密；优先局部密度窗口，不要整体加密。
- 关掉其他占内存程序；DEFORM 单进程比多进程稳。

### 求解极慢
- 每步迭代次数暴涨 → 接触刚度/步长问题。
- 重划过于频繁 → 网格或重划判据太紧。
- 多进程在小内存机器上反而更慢。

## F. 后处理

### Post 里看不到坯料
Object control 还在 `All objects`，被挤压筒罩住。改 `Workpiece only`。

### `[V] Folding` 红字
网格折叠提示，对应模口单元问题；不影响看图，但说明该处结果不可信。

### 色标每帧变，图无法比较
DEFORM 自动定标。读 Min/Max，或手动锁定范围后重新截图。
