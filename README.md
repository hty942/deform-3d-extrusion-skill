# DEFORM-3D 挤压有限元全流程 Skill

把「给一个零件三维模型 + 一种材料 → 建模 → 网格 → 求解 → 应力/应变/速度/温度 → 挤压动画 → 指标评价 → 改参数重算 → 出报告」这套流程，整理成可复用的技能包与脚本集合。

面向 **SFTC DEFORM-3D v11**（本机实测版本 11.0），以铝型材挤压为主线，也适用于镦粗、锻造等塑性成形问题。

---

## 一、先说清楚自动化边界（重要）

DEFORM v11 **没有建模 API**：新建算例、导几何、划网格、设边界条件只能在 Pre 图形界面里点。任何声称「丢一个 STL 进去就全自动出结果」的脚本，要么在骗人，要么是在做屏幕点击机器人（分辨率一变就废）。

所以本仓库按 **L0～L3 三档**组织：

| 档位 | 内容 | 谁来做 |
|---|---|---|
| **L0 全自动** | 几何预检、单位判定、材料 KEY 生成、KEY 参数批改、批处理求解、结果提取、指标计算、报告生成、优化循环 | 脚本 |
| **L1 半自动** | Database Generation、DB→KEY 导出、运行监控、帧序列合成视频 | 脚本 + 一次点击 |
| **L2 人工 GUI** | 新建算例、导入几何、划网格、对象定位、边界条件 | 人（步骤见 `references/`） |
| **L3 决策** | 指标是否达标、改哪个参数、是否接受结果 | 人（决策表见 `references/07_optimization.md`） |

**最低要求的落地方式**：第一次建模走 L2（照 `references/00_workflow.md` 做一遍，约 1～2 小时）；之后所有参数研究、优化迭代都走 L0——改 KEY、批跑、出指标、出报告，不再碰界面。

---

## 二、目录

```
SKILL.md                     技能入口（工作流契约、铁律、阶段门）
references/
  00_workflow.md             八阶段全流程：输入/操作/判据/产出
  01_geometry.md             三维模型与 STL 的要求、单位、水密性、装配顺序
  02_meshing.md              网格标准：尺寸/质量/运行/无关性 + 密度窗口
  03_materials.md            材料选择与流动应力数据
  04_boundary.md             对象类型、接触、摩擦、传热、运动、步控
  05_solving.md              生成 DB、启动求解（F9 vs 批处理）、监控与中止
  06_post.md                 四场查看、动画播放、帧导出
  07_optimization.md         指标定义、决策表、单因素/L9、重算循环
  08_report.md               报告结构与写法
  09_troubleshooting.md      故障树（本项目踩过的坑）
  10_gui_anchors.md          界面路径速查（v11 本机实测）
  11_key_editing.md          直接改 KEY 的规则（定宽格式、MOVCTL/URZ、BCCDEF 禁区）
  12_assisted_gui.md         让 AI 代操作界面：截图→OCR→点击→复验
scripts/
  preflight_stl.py           几何预检：编码/面数/水密/包围盒/体积
  read_key_unit.py           单位制判定（SI / English）
  make_material.py           本构方程/应力表 → DEFORM 材料 KEY
  key_metrics.py             导出 KEY → 指标 JSON/CSV（速度、温度、应力、应变）
  export_db_key.ps1          DB → KEY 无 GUI 导出（DEF_PRE_64 stdin 菜单）
  run_batch.ps1              64bit.dat + DEF_ARM 批处理求解 + 监控
  frames_to_video.ps1        截图序列 → MP4/GIF
  make_report.py             指标 JSON → 自包含 HTML 报告（支持基线/优化对比）
examples/
  423002/                    四孔模挤压案例：设置、指标、报告样例
```

---

## 三、快速开始

### 路径 A：第一次做（人工建模 + 脚本收尾）

1. `python scripts/preflight_stl.py 你的几何目录` —— 几何不过关，后面全白搭。
2. 照 `references/00_workflow.md` 的 P1～P5 在 Pre 里建好算例、生成 DB。
3. 求解：主界面 `Simulation → Start`（F9），或 `scripts/run_batch.ps1` 批跑。
4. 出结果：Post 里看 `references/06_post.md`；要数值就 `export_db_key.ps1` 导 KEY，再 `key_metrics.py` 算指标。
5. `make_report.py` 出报告。

### 路径 B：已有算例，只改参数（全自动）

```powershell
# 1) 改 KEY 里的参数（杆速、温度、摩擦、步长），用文本替换或 python
# 2) 生成 DB 需要一次 GUI（Database Generation）
# 3) 批跑
.\scripts\run_batch.ps1 -CaseDir C:\cases\c10 -Name c10 -Wait
# 4) 导结果 + 算指标
.\scripts\export_db_key.ps1 -CaseDir C:\cases\c10 -Database c10.DB -Out c10_out.KEY
python scripts/key_metrics.py c10_out.KEY --z-exit -10 --tol 0.5 -o c10_metrics.json
# 5) 出报告（可传多个 json 做对比）
python scripts/make_report.py -i baseline.json c10_metrics.json -o report.html
```

### 路径 C：优化循环（研究/答辩用）

见 `references/07_optimization.md`：定指标 → 定基线 → 单因素或 L9 → 批量算例 → 指标对比 → 选优 → 复核。

---

## 四、已验证环境

- Windows 11，DEFORM-3D v11.0，安装于 `D:\Program Files\SFTC\DEFORM\v11.0`
- 求解器 `3D\DEF_SIM_64.EXE`，批处理入口 `3D\DEF_ARM.COM`，必须存在 `64bit.dat` 才走 64 位
- Python 3.10+（脚本只用标准库）；视频合成需 ffmpeg
- 本机若没有 `python` 命令（Cherry 托管环境常见），把命令里的 `python` 换成
  `uv run --no-project --python 3.12 python`，或先 `uv python install`
- 本仓库所有脚本的「实测」结论均来自 423002 四孔模挤压算例（见 `examples/423002/`）

---

## 五、案例：423002 四孔模挤压（本仓库的验证对象）

**项目记录（4 mm/s 基准，出口截面口径）**：

| 指标 | 数值 | 说明 |
|---|---|---|
| 单元 / 节点 | 613 704 / 137 614 | 四面体 |
| 杆速 | 4 mm/s | 出口理论速度 112.945 mm/s |
| 出口速度均值 | 113.33 mm/s | 与理论值偏差 0.34% |
| 孔间差 | 10.36% | 改 3/4/5 分区工作带后 7.81% |
| 出口速度 CV | 30.89% → 24.82% | 同上 |
| 挤压力 | 5.176 → 5.769 MN | 截面应力积分口径（与 DEFORM 载荷口径 5.754 不同，勿混用） |

**本仓库可复现的示例（`examples/423002/`）**：dof_c1，杆速 **3 mm/s**，截面取 z = −10（工作带内），
由 `key_metrics.py` 从 284 MB 导出 KEY 计算：出口截面速度均值 99.74 mm/s、孔间差 10.00%。
与上表口径不同（速度、截面位置都不一样），**不要混用**；详见该目录 README。

瞬态动画版（含传热）：`tr.DB` 15 帧，行程 2.42 mm，温度 455～472 °C；受模口网格限制无法跑长行程，原因与改法见 `references/02_meshing.md`。

---

## 六、许可

MIT。脚本可自由改用；`references/` 中的工艺数值请回到自己的工艺文件与文献核定后再写进报告。
