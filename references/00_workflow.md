# 八阶段全流程

> 每个阶段都给出：输入 → 操作（GUI 或脚本）→ 判据 → 产出。
> 菜单名以 v11 本机实测为准，见 `10_gui_anchors.md`。

---

## P0 输入准备

**输入**：零件三维模型（STL/STEP）、材料牌号、工艺条件（温度、速度、摩擦）。

**操作**

```bash
python scripts/preflight_stl.py <几何目录>
```

检查项：编码（ASCII/二进制）、三角面数、包围盒、水密性、体积、退化面。
单位判定：几何坐标是 mm 还是 inch；DEFORM 算例必须与之匹配（SI=mm）。

**判据**

- 塑性体（坯料）**严格水密**：每条边恰被 2 个三角面共用。
- 包围盒与图纸一致（±0.1 mm）；典型错误是差 25.4 倍。
- 无零面积三角面、无非流形边。

**产出**：预检报告（stdout 或 `--json`）。

---

## P1 建算例与导入对象

**输入**：通过 P0 的 STL、工艺条件。

**操作（GUI）**

1. 主界面 `File → New Problem`，选 **SI**，勾 **Deformation**（热挤再勾 **Heat transfer**）。
2. Problem directory 用**纯英文路径**。
3. `Input → Pre-Processor`，逐个对象 `Geometry → Import`。
4. 对象类型：坯料 **Plastic**，模具/挤压筒/挤压杆 **Rigid**。
5. `Object Positioning` 确认装配关系（沿流动方向：杆 → 垫 → 坯料 → 工作模 → 支承）。

**判据**：恰好一个塑性体；对象之间无初始穿插；工作带在出口侧。

**产出**：`<name>.KEY`（Pre 保存时生成）。

> 注：DEFORM V14.0 起有 Python 版 DEFORM-API，可用脚本完成部分导入/设置；v11 没有，只能按上面手动做。

---

## P2 划网格

**输入**：对象几何。

**操作（GUI）**

1. 选中工件 → `Mesh → Generate Mesh`，四面体。
2. 先给一个能跑通的粗网格（10～20 万单元），确认整条链路能走通。
3. 加 **Mesh Density Windows**：在模口/变形集中区放窗口，`Weighting Factor` 2～4。
4. 重新划分，记录单元数、最小/最大边长。

**判据**（详见 `02_meshing.md`）

- 单元边长 ≤ 局部特征尺寸 / 3；薄壁厚度方向 ≥ 3～5 层。
- 每步位移 ≤ 最小边长 / 3～5。
- 无负体积；condition number 0.6～1.0 占 90% 以上。
- 总单元数在内存预算内（16 GB 机器 ≈ 60 万四面体）。

**产出**：网格统计（节点/单元/最小边长）。

---

## P3 材料与边界条件

**输入**：材料数据、工艺条件。

**操作**

- 材料：`Material → Load from Library`；库里没有牌号时用 `scripts/make_material.py` 从本构方程生成 KEY，再 `Material → Load from File`。
- 接触：`Inter-Object Relations`，默认关系 + 特例；摩擦用**剪切摩擦因子 m**（热挤铝 0.7～1.0 量级，按文献取）。
- 传热：勾 Heat transfer 后，界面换热系数用默认值或按文献；Data Check 会提示"换热系数为默认值"——这是警告不是错误。
- 运动：挤压杆给恒定速度（Primary Die）。
- 步控：按 **Die displacement** 定义步长（0.1～0.2 mm/步），总步数按目标行程/步长。

**判据**：`Database Generation → Check Data` 无 Error；每条 Warning 都能解释。

**产出**：完整的 `.KEY`。

---

## P4 生成数据库与求解

**输入**：通过 P3 的算例。

**操作**

1. `Database Generation` → `Check Data` → `Generate DB`。
   - 若提示 **LOST STEPS**（已有步将被擦除），确认后选 **Yes**。
2. 求解二选一：
   - **GUI**：主界面 `Simulation → Start`（F9）。状态栏出现 "Simulation has been started."。
   - **批处理**：`scripts/run_batch.ps1 -CaseDir <dir> -Name <name> -Wait`。
3. 监控：`<name>.LOG`（步数、行程、重划）与 `<name>.MSG`（迭代、温度计算）。

**判据**

- 日志出现 `Running 64bit simulation`（不是 32bit）。
- 步数持续推进；重划网格次数远小于步数。
- 无 `Program stopped because of bad element shape!` 反复出现。

**产出**：`<name>.DB`（含各步结果）。

---

## P5 后处理：四场与动画

**输入**：`.DB`。

**操作（GUI）**

1. `DEFORM Post` → `File → Open` 打开 `.DB`。
2. `Object control` → `Workpiece only`（否则模具把坯料罩住）。
3. 左侧图标：`σ` 等效应力、`ε` 等效应变、`V` 速度、温度计 温度。
4. 底部 Step View：`|◀` 回第一帧 → `▶` 播放；可反复。

**数值提取（脚本）**

```powershell
.\scripts\export_db_key.ps1 -CaseDir <dir> -Database <name>.DB -Out <name>_out.KEY
python scripts/key_metrics.py <name>_out.KEY --z-exit -10 --tol 0.5 -o metrics.json
```

**判据**

- 出口速度均值与理论值 `v·(A0/A1)` 偏差 < 5%。
- 应力/应变/温度分布物理合理（模口高应力、料头低温等）。
- 载荷-行程曲线有"压紧→充填→平台"三段。

**产出**：四场截图、动画、`metrics.json`。

---

## P6 指标评价

**输入**：`metrics.json`、工艺目标。

**指标表**（按问题选）

| 指标 | 定义 | 常用阈值 |
|---|---|---|
| 挤压力 | 载荷曲线平台值 / 截面应力积分 | 设备能力内 |
| 出口速度均值 | 出口截面节点速度平均 | 与理论值偏差 <5% |
| 孔间差 | (max−min)/mean（按孔分区） | 越小越好，工程上 <10% |
| 速度 CV | std/mean | 越小越好 |
| 最高温度 | 全域最大 | 低于固相线/过烧温度 |
| 等效应变不均匀度 | 出口截面应变标准差 | 越小越好 |

**判据**：指标齐全、口径一致（同一截面、同一时间点/稳定段）。

---

## P7 优化与复算

见 `07_optimization.md`。核心：

1. 一次只改一个因素（或做 L9 正交）。
2. 每个方案单独建算例，其余设置完全一致。
3. 批量求解 → 批量提指标 → 对比表 → 选优。
4. 对优选方案做复核（网格或步长敏感性）。

**判据**：关键指标改善，且没有把另一项指标推向不可接受。

---

## P8 报告与归档

**输入**：全部算例、指标、图。

**操作**

```bash
python scripts/make_report.py -i baseline.json opt1.json opt2.json -o report.html
```

**判据**：每条数值都能追到文件；结论标注证据等级；局限如实写。

**产出**：`report.html`（自包含，可直接发）+ 算例目录归档。
