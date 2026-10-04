# manlianrili

生成曼联比赛日程的 `.ics` 日历文件，可直接导入 iPhone 的「日历」App。

## 文件

| 文件 | 作用 |
| --- | --- |
| `generate.py` | 从 API-Sports 取比赛数据，输出 `matches.ics` |
| `validate_ics.py` | 校验 `matches.ics` 是否符合导入要求（CI 会在提交前运行） |
| `matches.ics` | 生成结果，GitHub Actions 每 8 小时自动更新 |

## 导入 iPhone 日历

1. 用 iPhone 的 Safari 打开 `matches.ics` 的 raw 地址；
2. 系统会提示「在“日历”中打开」，选择要加入的日历后确认；
3. 若同一场比赛在后续更新中改了标题（例如补上比分），重复导入会**更新**原事件，不会产生重复条目——因为每个事件的 `UID` 由比赛 ID 稳定派生。

## 关于 API 套餐的重要说明

`API_KEY` 当前使用的是 API-Sports 的 **Free** 套餐，该套餐只开放 `season` 2022–2024，
并且禁用 `next` / `last` 参数（`team` 查询强制要求 `season`）。因此：

- 脚本会从 `SEASON`（默认 2026）开始向前回退，选用套餐允许的**最新**赛季；
  当前实际生效的是 **2024/25 赛季**，即日历里都是已经结束的比赛。
- 想要 2025/26 及之后的赛季，需要把 API-Sports 升级为付费套餐；升级后无需改代码，
  脚本会自动用上更新的赛季。

建议把 key 放到仓库 Secret，并通过环境变量注入，避免公开仓库里泄露 key：

```yaml
env:
  APISPORTS_KEY: ${{ secrets.APISPORTS_KEY }}
```

## 本地运行

```bash
pip install -r requirements.txt
python generate.py
python validate_ics.py matches.ics
```
