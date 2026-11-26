# 界面路径速查（DEFORM-3D v11，本机实测）

> 只收录本机点过、截图核对过的路径。没核过的会标「未实测」。

## 1. 主界面（DEF_GUI23.exe）

| 位置 | 内容 |
|---|---|
| 顶部菜单 | File / Simulation / Tool / View / Option / Help |
| Simulation 菜单 | Start（F9）、Stop（F10）、Continue（Ctrl+F9）、Add to Batch Queue、Process Monitor、Simulation Graphics |
| Tool 菜单 | DB Manager、Clean up Files |
| 右上 Pre Processor | DEFORM-2D/3D Pre、DEFORM MO、Forming、Shape Rolling… |
| 右侧 Simulator | Run、Run (options)、Stop、Continue、Process Monitor、Simulation Graphics、Add to Queue |
| 右下 Post Processor | DEFORM-2D/3D Post、DEFORM Post、DEFORM DOE Post、DEFORM Mat |
| 地址栏 | 输入算例目录后回车 |

## 2. Pre（DEF_GUI_PRE23.EXE）

| 功能 | 路径 |
|---|---|
| 对象树 | 左侧；双击对象打开编辑器 |
| 仿真控制 | `Simulation Controls` → Main（Mode: Deformation / Heat transfer） |
| 数据库生成 | `Database Generation` → Check Data / Generate DB |
| 网格 | `Mesh → Generate Mesh`；`Mesh Density Windows` |
| 材料 | `Material → Load from library` / `Load from file`（程序字符串：`Load from lib`、`load from file`） |
| 对象定位 | `Object Positioning` |
| 对象间关系 | `Inter-Object`（对象间关系；程序字符串为 `Inter-Object`） |
| 打开指定 DB | 主界面 `-m open -f <十六进制全路径>`（DEF_GUI_MO 用法） |

## 3. Database Generation 对话框

| 按钮 | 说明 |
|---|---|
| Check Data | 先跑，看 Error/Warning |
| Generate DB | 生成；已有步会弹 LOST STEPS，选 Yes |
| Close | 关闭 |

生成成功标志：`Done writing database`。

## 4. 求解相关

| 操作 | 路径 |
|---|---|
| 本地求解 | `Simulation → Start`（F9） |
| 中止 | `Simulation → Stop`（F10） |
| 远程/队列 | `Run (options)` —— 单机没配服务器时**不要用** |
| 批处理 | `3D\DEF_ARM.COM <name> B`，目录需 `64bit.dat` |

## 5. Post（DEF_GUI_PST_64.exe）

| 功能 | 位置 |
|---|---|
| 打开库 | `File → Open`（文件对话框里逐级进入目录，双击 .DB） |
| 对象显示 | 右上 `Object Tree → Object control` |
| 变量图标 | 左侧竖排，从上到下：σT、红叉、温度计、D、V、U、σ、ε、ε̇ |
| 播放 | 底部 Step View：◀\| 上一帧、\|▶ 下一帧、\|◀ 第一帧、▶\| 末帧、◀ 倒放、▶ 正放 |
| 色标 | 视图右侧，Min/Max 在下方 |
| 动画导出 | 程序里有 `Animation Export` / `Animation Setup`（AVI/WMV/PPT/HTML）；界面未逐项点开验证 |

## 6. 已验证的坑（都踩过）

1. `Run (options) → Start` 在单机报 `Can not submit job!`；本机观察到点 `Check Server` 后 `SYS_SERVER_NAME` 变成 `none`（推断由它写入）。
2. `DEF_ARM.COM` 没有 `64bit.dat` → 静默 32 位、1 秒退出。
3. 求解中 `tr.DB` 改名 `FOR003`，此时打不开是正常的。
4. 主窗口文件树不刷新：新建目录后看不到，重启或直接用 `-m open -f`。
5. Post 的 `Object control` 下拉必须选 `Workpiece only` 才能看到坯料。
6. 色标每帧自动定标，跨帧比较必须看 Min/Max。
7. 中文路径可能静默出错——算例目录全用 ASCII。

## 7. 本机安装位置

```
D:\Program Files\SFTC\DEFORM\v11.0\
  DEF_GUI23.exe              主界面
  DEF_GUI_PRE23.EXE          Pre
  DEF_GUI_PST_64.exe         Post（64 位）
  3D\DEF_SIM_64.EXE          求解器
  3D\DEF_ARM.COM             批处理启动器
  3D\MANUALS\PDF\            厂商文档与挤压算例
```
