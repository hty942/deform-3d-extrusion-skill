# 后处理：四场、曲线与动画

## 1. 打开

1. 主界面 → `Post Processor → DEFORM Post`。
2. `File → Open` → 进入算例目录 → 双击 `<name>.DB`（1 GB 级库加载约 30～60 s）。

## 2. 只显示坯料

右上 `Object Tree → Object control` 下拉框：

`All objects` / `Workpiece only` / `P. Die only` / `User-defined`

选 **Workpiece only**。否则挤压筒/模具把坯料罩住，只能看到灰壳。

## 3. 左侧竖排图标的顺序（v11 实测）

从上到下：

1. `σT`（应力张量）
2. 红叉（隐藏）
3. **温度计（温度）**
4. `D`（损伤）
5. `V`（速度）
6. `U`（位移）
7. `σ`（等效应力）
8. `ε`（等效应变）
9. `ε̇`（应变速率）

点哪个，右侧就出现对应色标（如 `Temperature (C)`）。

## 4. 色标（Legend）的读法

- **每一步都会自动重新定标**：同一颜色在不同帧对应的数值可能不同。
- 要看具体数值，读色标旁的 **Min / Max**。
- 报告里贴图时，把 Min/Max 一并写出来，否则图无法比较。

## 5. 播放（Step View）

底部播放条右侧一排圆按钮，从左到右（本机实测顺序）：

| 按钮 | 作用 |
|---|---|
| ◀\| | 上一帧 |
| \|▶ | 下一帧 |
| **\|◀** | 回第一帧 |
| **▶\|** | 到末帧 |
| ◀ | 倒放 |
| **▶** | **正放** |

标准观看：先 `|◀` 回第一帧 → 再 `▶`。可反复，不限次数。
也可以拖滑块，或在 `Step` 输入框里键入步号（部分版本该框只读，以滑块为准）。

## 6. 四个场分别看什么

| 场 | 图标 | 看什么 |
|---|---|---|
| 等效应力 σ | `σ` | 模口/工作带高应力区、模面接触环 |
| 等效应变 ε | `ε` | 变形集中带、死区、分流焊合区 |
| 速度 V | `V` | 出口流速均匀性、死区、回流 |
| 温度 T | 温度计 | 变形热、接触冷却、料头温降 |

## 7. 载荷-行程曲线

Post 里有 Load-Stroke 图（Report/Graph 功能，视版本菜单不同）。
没有的话用导出 KEY 的应力积分口径自行计算，但**必须注明口径**：
截面应力积分与 DEFORM 载荷口径可能不同（本项目实测 5.176 vs 5.754 MN，差 11%），不能混用。

## 8. 数值提取（脚本路径）

DB 是专有格式，直接读不了。两条路：

1. **DB → KEY**：`scripts/export_db_key.ps1`（无 GUI，走 `DEF_PRE_64` 的 stdin 菜单）。
   大库导出的 KEY 很大（61 万单元约 284 MB）。
2. **KEY → 指标**：`scripts/key_metrics.py`。

```powershell
.\scripts\export_db_key.ps1 -CaseDir C:\cases\c10 -Database c10.DB -Out c10_out.KEY
python scripts/key_metrics.py c10_out.KEY --z-exit -10 --tol 0.5 -o c10_metrics.json
```

KEY 中的块：`RZ`（节点坐标）、`URZ`（速度）、`NDTMP`（温度）、`ELMCON`（单元连接）、`STRAIN`（等效应变）、`STRESS`（应力张量 6 分量）。

## 9. 动画

### 在软件内看（默认要求）

瞬态算例每步存一帧 → Post 里按第 5 节播放即可。这是"在 DEFORM 中观看、可反复"的标准做法。

### 导出视频

两条路：

1. Post 内的动画保存（AVI/WMV/PPT），配置文件 `DEFORM3_SYS.INI` 里有 `SYS_ANIM_SAVE_AVI` 等开关；界面入口视版本而定，**本机未实测**。
2. 逐帧截图 + 合成：

```powershell
# 按固定视角逐帧截图（手动或脚本），命名 frame_0001.png ...
.\scripts\frames_to_video.ps1 -Frames .\frames\frame_*.png -Fps 6 -Out .\anim.mp4
```

注意：截图前固定视角与色标范围，否则合成出来的动画会"闪"。

## 10. 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 打开 DB 只看到灰色筒 | Object control 是 All objects | 改 Workpiece only |
| 只有一张图，拖滑块没变化 | 稳态 ALE 算例只有 1 步 | 要动画必须瞬态重算 |
| 温度场全是同一个颜色 | 没勾 Heat transfer | 回 Pre 开传热、重生成 DB、重算 |
| `[V] Folding` 红字 | 网格折叠提示 | 局部网格太粗，见 `02_meshing.md` |
| 色标每帧都变 | DEFORM 自动定标 | 读 Min/Max，或手动锁定范围 |
