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

| 来源 | 覆盖赛事 | 说明 |
| --- | --- | --- |
| [football-data.org](https://www.football-data.org/coverage) | 英格兰超级联赛、欧洲冠军联赛 | 免费档覆盖，含球场、比分、UTC 时间。**需要免费 token** |
| [TheSportsDB](https://www.thesportsdb.com/) | 足总杯、联赛杯、欧联杯、欧协联 | 免费 key，按轮次枚举补充 football-data.org 不覆盖的杯赛 |

两个来源的结果会**按「日期 + 主队 + 客队」合并去重**，重复时保留 football-data.org 的版本。

> football-data.org 免费档（10 次/分钟，12 个赛事）官方标注「比分与赛程更新有延迟」。
> 由于本日历每 8 小时才更新一次，这个延迟不影响使用。

### 必填：配置 football-data.org token

1. 到 <https://www.football-data.org/client/register> 免费注册，邮箱里会收到 token；
2. 在本仓库 `Settings → Secrets and variables → Actions` 新增 Secret，名字必须是 **`FOOTBALL_DATA_TOKEN`**；
3. 本地运行则设置同名环境变量。

> 没有 token 时脚本会**直接报错退出**，不会生成或提交不完整的日历。

### 已知限制

- **杯赛覆盖是尽力而为**：TheSportsDB 免费 key 对各杯赛的轮次数据并不完整
  （实测其联赛杯只到部分轮次），所以某个杯赛在数据库里有曼联比赛时才会出现在日历里。
  想拿到 100% 完整的全赛事赛程，需要付费数据源（例如 API-Sports 付费套餐，
  用 `fixtures?team=33&season=2026` 一次就能拿到所有赛事）。
- TheSportsDB 免费 key 有较严格的限流（Cloudflare 1015），脚本已内置退避与跳过：
  杯赛拿不到时会照常生成英超/欧冠部分，并在日志里说明。
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
export FOOTBALL_DATA_TOKEN=你的token      # Windows: set FOOTBALL_DATA_TOKEN=你的token
python generate.py
python validate_ics.py matches.ics
```
