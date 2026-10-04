# manlianrili

生成曼联一线队赛程的 `.ics` 日历文件，可直接导入 iPhone 的「日历」App。

## 行为

- 比赛标题：**未进行**显示 `主队 VS 客队`，**已结束**显示 `主队 比分 客队`
- 每个日程固定 **2 小时**（从开球时间起算）
- 日程的**定位（位置）为比赛球场**
- 时间以 UTC 写入，iPhone 会按你所在时区显示
- 每个事件的 `UID` 由比赛 ID 稳定派生，**导入到同一个日历时是更新事件，不会产生重复条目**
- GitHub Actions 每 8 小时自动更新一次

## 数据来源

| 来源 | 角色 | 覆盖 |
| --- | --- | --- |
| [football-data.org](https://www.football-data.org/coverage) | **主来源**（需要免费 token） | 英格兰超级联赛、欧洲冠军联赛；含球场、比分、UTC 时间 |
| [TheSportsDB](https://www.thesportsdb.com/) | **补充 + 兜底**（免费 key） | 足总杯、联赛杯、欧联杯、欧协联；以及在主来源不可用时兜底英超与欧冠 |

两个来源的结果按 **「日期 + 主队 + 客队」合并去重**，重复时保留 football-data.org 的版本。

## 两种运行模式

| 模式 | 触发条件 | 结果 |
| --- | --- | --- |
| **完整模式** | 配置了 `FOOTBALL_DATA_TOKEN` | 英超 + 欧冠 + 各杯赛，数据来自 football-data.org（权威、含球场与比分） |
| **降级模式** | 没有 token，或主来源请求失败 | 自动改用 TheSportsDB：**英超 38 轮 + 欧冠联赛阶段**（实测各 38 / 8 场）+ TheSportsDB 能提供的杯赛 |

降级**不是静默的**：

- CI 日志里会打印醒目的警告横幅，并列出本次的数据来源与覆盖赛事；
- 覆盖范围与降级标记也会写进日历的 `X-WR-CALDESC` 字段。
  注意：**不同客户端是否显示该字段并不一致，不要依赖它来发现问题，请以运行日志为准**；
- 覆盖范围会随 TheSportsDB 免费库实际提供的数据变化（例如足总杯曼联从第 3 轮入场，抽签后才会出现）；
- 若有限流导致某个赛事扫不全，日志会列出失败原因，`X-WR-CALDESC` 里也会标注「覆盖可能不完整」。

想禁止降级、让它在主来源不可用时直接失败，把环境变量 `ALLOW_PL_FALLBACK` 设为 `0`。

## 配置 football-data.org token（推荐）

1. 到 <https://www.football-data.org/client/register> 免费注册，邮箱里会收到 token；
2. 在本仓库 `Settings → Secrets and variables → Actions` 新增 Secret，名字必须是 **`FOOTBALL_DATA_TOKEN`**；
3. 本地运行则设置同名环境变量。

不需要 token 也能跑：降级模式会从 TheSportsDB 取到英超整季与欧冠联赛阶段（实测 38 + 8 场），
以及该库当前能提供的杯赛。配上 token 后改用 football-data.org 的权威数据，覆盖更稳。

## 已知限制

- **杯赛覆盖是尽力而为**：TheSportsDB 免费 key 对各杯赛的轮次数据并不完整。
  实测结论（2026 年 10 月）：
  - **足总杯**：该库的轮次是从**资格赛**连续编号的（r1=9/4、r2=9/18、r3=10/3），
    而曼联从**第三轮正赛**（2027 年 1 月）才入场，按节奏约落在 r7~r9；
    因此脚本的足总杯扫描窗口特意留到 r12，避免永久漏掉。
  - **联赛杯**：该库 2026/27 赛季 r1~r12 **全为空**（2024/25 也只有 r1~r3 有数据），
    因此联赛杯的比赛目前拿不到；脚本保留小窗口，一旦有数据就会自动补上。
  - **欧联杯 / 欧协联**：曼联若参赛，联赛阶段通常落在前 10 轮内，已按此扫描。
  - 抽签尚未进行的轮次（如足总杯第三轮正赛）在任何数据源里都不存在，
    抽签完成后本工作流会自动补上。
- **TheSportsDB 限流较严**（Cloudflare 1015），脚本已内置退避；杯赛拿不到时会照常生成其余部分并在日志说明。
- **未来轮次的日期可能微调**：把 TheSportsDB 的 38 轮英超与独立来源
  [openfootball](https://github.com/openfootball/england) 比对，38 轮全部配对成功，
  其中 **36 轮日期完全一致、2 轮差一天**（处于电视转播调整期），比分与开球时间（按夏令时换算后）一致。
- **欧冠数据也做过独立印证**：把 TheSportsDB 的 8 场欧冠联赛阶段与
  [premierleague.com 公布的 2026/27 联赛阶段日程](https://www.premierleague.com/en/news/4699703/champions-league-league-phase-schedule-confirmed)
  比对，第 3/4/6/8 轮日期完全相同，其余 4 轮落在同一轮的 Tue/Wed 窗口内
  （联赛阶段每轮跨两天）；开球时间与官方 17:45 / 20:00 换算成 UTC 后一致。
- 想拿到 100% 完整的全赛事赛程，需要付费数据源（例如 API-Sports 付费套餐，
  `fixtures?team=33&season=2026` 一次就能拿到所有赛事）。
- 想调整杯赛清单或扫描轮次，改 `generate.py` 顶部的 `TSS_CUPS`（每个杯赛自带轮次窗口）、
  `TSS_PL_ROUNDS`、`TSS_UCL_ROUNDS`。

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
