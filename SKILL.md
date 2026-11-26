---
name: deform-3d-extrusion-workflow
description: 用 DEFORM-3D v11 完成金属塑性成形（挤压/锻造/镦粗）的完整有限元流程——从零件三维模型与材料数据出发，建算例、划网格、设边界、求解，输出应力/应变/速度/温度四场与挤压动画，按指标做参数优化并重算，最后生成报告。Use when a task involves DEFORM-3D, 挤压仿真, 锻造仿真, 有限元模拟, 材料成形工艺仿真, .DB/.KEY 文件, STL 导入 DEFORM, 网格划分, 或需要从模拟结果做工艺参数优化（杆速、温度、摩擦、工作带、模具结构）。
---

# DEFORM-3D 挤压全流程 Skill

本技能把一条完整的「模型 + 材料 → 仿真 → 四场 + 动画 → 优化 → 复算 → 报告」流水线固化成可执行契约。**先读完本节，再动手。**

## 0. 输入契约（缺一不可）

| 输入 | 形式 | 缺了怎么办 |
|---|---|---|
| 零件三维模型 | STL（优先）或 STEP，**mm**，水密 | 先按 `references/01_geometry.md` 修几何；不水密的塑性体必然划网格失败 |
| 材料 | DEFORM 材料库名，或 σ=f(ε, ε̇, T) 数据/本构方程 | 用 `scripts/make_material.py` 生成 KEY；**不许**用弹性模量代替流动应力 |
| 工艺条件 | 坯料温度、模具温度、杆速、摩擦、传热系数 | 按 `references/04_boundary.md` 给默认值，并在报告里注明是假设 |

## 1. 自动化分级（决定你该写脚本还是点鼠标）

| 级别 | 环节 | 手段 |
|---|---|---|
| L0 | 几何预检、单位判定、材料生成、KEY 参数批改、批处理求解、指标提取、报告、优化循环 | 脚本 |
| L1 | 生成数据库、DB→KEY 导出、求解监控、帧合成视频 | 脚本 + 一次界面点击 |
| L2 | 新建算例、导入几何、划网格、对象定位、边界条件 | 人工 GUI（`references/00_workflow.md`） |
| L3 | 指标是否达标、改哪个参数、结果是否可接受 | 决策表（`references/07_optimization.md`） |

**v11 没有建模 API。** 不要承诺"全自动建模"；第一次建模必须走 L2。之后所有参数研究都走 L0。

> 版本补充：DEFORM **V14.0 起**官方提供 **Python 版 DEFORM-API**（官方 2025 春季通讯），已开放大部分核心功能，可用于几何/网格自动化、参数化设置与结果提取。若目标机是 V14+，先查安装目录里的 API 文档与示例，再决定是否把 L2 自动化；本技能其余部分仍适用。

## 2. 八阶段与阶段门

| 阶段 | 做什么 | 通过判据（Gate） | 参考 |
|---|---|---|---|
| P0 输入 | 几何预检、单位、材料 | 水密、包围盒与图纸一致、单位 SI | `01_geometry.md` |
| P1 算例 | 新建算例、纯英文目录、导入对象 | 对象类型正确（塑性 1 个，其余 Rigid） | `00_workflow.md` |
| P2 网格 | 划分 + 密度窗口 | 最小边 ≥ 特征尺寸/5；壁厚方向 ≥3 层；无负体积 | `02_meshing.md` |
| P3 边界 | 接触、摩擦、传热、运动、步控 | Data Check 无 Error，只有可解释的 Warning | `04_boundary.md` |
| P4 求解 | 生成 DB → 求解 | 步数推进、无 `bad element shape` 循环 | `05_solving.md` |
| P5 结果 | 四场 + 载荷曲线 + 动画 | 出口速度与理论值偏差 <5%；场分布物理合理 | `06_post.md` |
| P6 评价 | 指标表 | 指标齐全、与基线可比 | `07_optimization.md` |
| P7 优化 | 改参数 → 重算 → 对比 | 单因素或 L9；关键指标改善且未引入新问题 | `07_optimization.md` |
| P8 交付 | 报告 + 归档 | 数值可追溯到文件；结论标明证据等级 | `08_report.md` |

## 3. 铁律

1. **先问单位，再碰几何。** STL 不含单位；算例选 English 时同一份 mm 几何会被当成英寸（差 25.4 倍）。用 `scripts/read_key_unit.py` 判定既有算例，用 `preflight_stl.py` 看包围盒。
2. **纯英文路径。** 中文路径会让 v11 在读写 `.DB`、临时文件时静默出错。
3. **不臆造界面文字。** 菜单名以 `references/10_gui_anchors.md` 中「本机实测」为准；没核过的写"按你界面上的 XX"。
4. **没有证据不下结论。** 每条结论标注：**本机实测 / 厂商文档 / 推断**。"网格划好了""仿真收敛了"必须对应文件或日志。
5. **64 位求解需要 `64bit.dat`。** 批处理目录里没有这个空文件，`DEF_ARM.COM` 会静默走 32 位并在 1 秒内退出。
6. **启动求解用 `Simulation → Start`（F9），不要用 `Run (options)` 的 Start。** 后者要求批处理队列服务器与共享点，单机没配时只报 `Can not submit job!`。
7. **动画库不能当报告数据源。** 瞬态动画用于看过程；工艺结论必须来自稳态或足够步数的算例，并在报告中写明口径。

## 4. 产出物（每次任务至少交付）

1. 算例目录（`.DB` + `.KEY` + 日志）
2. 指标 JSON/CSV（`key_metrics.py` 输出）
3. 四场截图 + 动画观看说明（`06_post.md`）
4. 自包含 HTML 报告（`make_report.py`）
5. 优化记录：改了什么、为什么、结果差多少

## 5. 失败处理顺序

1. 看 `tr.LOG` / `tr.MSG` 的最后 20 行，先定位是**网格、接触、收敛、许可证**哪一类。
2. 按 `references/09_troubleshooting.md` 的故障树逐条排除。
3. 不要在同一步上反复重试超过 2 次——先降步长/加密局部网格/检查初始穿插。
4. 任何"跑不动"的结论都要附日志原文与已尝试的参数。

## 6. 快速命令

```bash
python scripts/preflight_stl.py <dir>
python scripts/read_key_unit.py <dir>
python scripts/make_material.py --config mat.json --out MAT.KEY
python scripts/key_metrics.py out.KEY --z-exit -10 --tol 0.5 -o metrics.json
python scripts/make_report.py -i baseline.json metrics.json -o report.html
```

```powershell
.\scripts\export_db_key.ps1 -CaseDir <dir> -Db <name>.DB -Out <name>_out.KEY
.\scripts\run_batch.ps1 -CaseDir <dir> -Name <name> -Wait
.\scripts\frames_to_video.ps1 -Frames <dir>\*.png -Fps 6 -Out anim.mp4
```
