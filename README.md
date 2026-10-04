# manlianrili

生成曼联一线队赛程的 `.ics` 日历文件，可直接导入 iPhone 的「日历」App。

## 行为

- 比赛标题：**未进行**显示 `主队 VS 客队`，**已结束**显示 `主队 比分 客队`
- 每个日程固定 **2 小时**（从开球时间起算）
- 日程的**定位（位置）为比赛球场**
- 时间以 UTC 写入，iPhone 会按你所在时区显示
- 每个事件的 `UID` 由比赛 ID 稳定派生，**重复导入是更新事件，不会产生重复条目**
- GitHub Actions 每 8 小时自动更新一次

## 数据来源

| 来源 | 角色 | 覆盖 |
| --- | --- | --- |
| [football-data.org](https://www.football-data.org/coverage) | **主来源**（需要免费 token） | 英格兰超级联赛、欧洲冠军联赛；含球场、比分、UTC 时间 |
| [TheSportsDB](https://www.thesportsdb.com/) | **补充 + 兜底**（免费 key） | 足总杯、联赛杯、欧联杯、欧协联；以及在主来源不可用时兜底英超 |

两个来源的结果按 **「日期 + 主队 + 客队」合并去重**，重复时保留 football-data.org 的版本。

## 两种运行模式

| 模式 | 触发条件 | 结果 |
| --- | --- | --- |
| **完整模式** | 配置了 `FOOTBALL_DATA_TOKEN` | 英超 + 欧冠 + 各杯赛 |
| **降级模式** | 没有 token，或主来源请求失败 | 自动改用 TheSportsDB 的英超数据 → **英超 + 杯赛，没有欧冠** |

降级**不是静默的**：

- CI 日志里会打印醒目的警告横幅；
- 日历自身的描述字段会写明「降级运行：未配置 FOOTBALL_DATA_TOKEN，缺少欧冠」，在 iPhone 上可见。

想禁止降级、让它在主来源不可用时直接失败，把环境变量 `ALLOW_PL_FALLBACK` 设为 `0`。

## 配置 football-data.org token（推荐）

1. 到 <https://www.football-data.org/client/register> 免费注册，邮箱里会收到 token；
2. 在本仓库 `Settings → Secrets and variables → Actions` 新增 Secret，名字必须是 **`FOOTBALL_DATA_TOKEN`**；
3. 本地运行则设置同名环境变量。

不需要 token 也能跑（降级模式），只是会缺欧冠。

## 已知限制

- **杯赛覆盖是尽力而为**：TheSportsDB 免费 key 对各杯赛的轮次数据并不完整
  （实测其联赛杯只到部分轮次）。而且曼联从**足总杯第 3 轮**入场，该轮抽签要到 2026 年 12 月才进行，
  在此之前任何数据源都不可能有对应赛程 —— 抽签完成后本工作流会自动补上。
- **TheSportsDB 限流较严**（Cloudflare 1015），脚本已内置退避；杯赛拿不到时会照常生成其余部分并在日志说明。
- **未来轮次的日期可能微调**：把 TheSportsDB 的 38 轮英超与独立来源
  [openfootball](https://github.com/openfootball/england) 比对，34 轮日期完全一致、2 轮差一天
  （处于电视转播调整期），比分与开球时间（按夏令时换算后）一致。
- 想拿到 100% 完整的全赛事赛程，需要付费数据源（例如 API-Sports 付费套餐，
  `fixtures?team=33&season=2026` 一次就能拿到所有赛事）。
- 想调整杯赛清单或扫描轮次，改 `generate.py` 顶部的 `TSS_CUPS` / `TSS_CUP_ROUNDS`。

## 导入 iPhone 日历

1. 用 iPhone 的 Safari 打开 `matches.ics` 的 raw 地址
   （`https://raw.githubusercontent.com/SH-SHENHUA/manlianrili/main/matches.ics`）；
2. 系统提示「在"日历"中打开」，选择要加入的日历并确认。

## 文件

| 文件 | 作用 |
| --- | --- |
| `generate.py` | 取数据并输出 `matches.ics` |
| `validate_ics.py` | 校验 `matches.ics` 是否符合 iOS 导入要求（CI 在提交前运行） |
| `matches.ics` | 生成结果 |
| `.gitattributes` | 禁止 Git 对 `*.ics` 做行尾转换（RFC 5545 要求 CRLF） |

## 本地运行

```bash
pip install -r requirements.txt
export FOOTBALL_DATA_TOKEN=你的token      # Windows: set FOOTBALL_DATA_TOKEN=你的token；不设则走降级模式
python generate.py
python validate_ics.py matches.ics
```
