#!/usr/bin/env python3
"""生成曼联赛程的 iCalendar(.ics) 文件。

本文件负责两件事：
1. 从 API-Sports 取曼联的比赛数据。免费套餐只开放 season 2022-2024，
   但会把请求当 HTTP 200 正常返回、只在 ``errors.plan`` 里说明拒绝原因，
   所以这里从配置赛季开始逐个向前回退，取到数据为止，并把 API 的错误原样打出来。
2. 按 RFC 5545 自己写出 .ics（不再依赖 ics.py），保证 iOS 日历能导入：
   - CRLF 行尾，且文件以 CRLF 结束；
   - UTF-8 无 BOM；
   - 超过 75 字节的行按 UTF-8 字符边界折行；
   - 每个 VEVENT 都带 RFC 必填的 UID / DTSTAMP / DTSTART / DTEND；
   - UID 由比赛 ID 稳定派生，重复导入是更新而不是新增重复事件。
"""

import os
import sys
from datetime import datetime, timedelta, timezone

import requests

# ==========配置区域==========
# 建议把 key 放进 GitHub Actions Secret，并以环境变量 APISPORTS_KEY 注入。
API_KEY = os.environ.get("APISPORTS_KEY", "c57992dce30fc408d01e13b57ffd4a09")
TEAM_ID = 33
# 期望使用的赛季（起始年份）。若当前套餐不允许，会自动向前回退。
SEASON = 2026
# 最多向前回退多少个赛季。
SEASON_FALLBACK_YEARS = 6
OUTPUT_FILE = "matches.ics"
CALENDAR_NAME = "曼联赛程"
# ============================

# 球队翻译字典
TEAM_TRANSLATE = {
    "Manchester United": "曼联",
    "Liverpool": "利物浦",
    "Arsenal": "阿森纳",
    "Chelsea": "切尔西",
    "Manchester City": "曼城",
    "Tottenham": "托特纳姆热刺",
    "Newcastle": "纽卡斯尔联",
    "Aston Villa": "阿斯顿维拉",
    "Brighton": "布莱顿",
    "Crystal Palace": "水晶宫",
    "Everton": "埃弗顿",
    "Nottingham Forest": "诺丁汉森林",
    "West Ham": "西汉姆联",
    "Bournemouth": "伯恩茅斯",
    "Fulham": "富勒姆",
    "Wolves": "狼队",
    "Southampton": "南安普顿",
    "Leicester": "莱斯特城",
    "Ipswich": "伊普斯维奇",
    "Brentford": "布伦特福德",
    "Leeds United": "利兹联",
    "Coventry City": "考文垂",
    "Hull City": "赫尔城",
    "Middlesbrough": "米德尔斯堡",
    "Sunderland": "桑德兰",
    "Norwich City": "诺维奇",
    "West Bromwich Albion": "西布罗姆维奇",
    "Watford": "沃特福德",
    "Stoke City": "斯托克城",
    "Swansea City": "斯旺西",
    "Bristol City": "布里斯托尔城",
    "Burnley": "伯恩利",
    "Blackburn Rovers": "布莱克本",
    "Millwall": "米尔沃尔",
    "Preston North End": "普雷斯顿",
    "Queens Park Rangers": "女王公园巡游者",
    "Birmingham City": "伯明翰",
    "Cardiff City": "加的夫城",
    "Plymouth Argyle": "普利茅斯",
    "Sheffield United": "谢菲尔德联",
    "Derby County": "德比郡",
    "Portsmouth": "朴茨茅斯",
    "Real Madrid": "皇家马德里",
    "Barcelona": "巴塞罗那",
    "Atletico Madrid": "马德里竞技",
    "Sevilla": "塞维利亚",
    "Real Sociedad": "皇家社会",
    "Villarreal": "比利亚雷亚尔",
    "Betis": "皇家贝蒂斯",
    "Bayern Munich": "拜仁慕尼黑",
    "Borussia Dortmund": "多特蒙德",
    "Bayer Leverkusen": "勒沃库森",
    "RB Leipzig": "莱比锡红牛",
    "Eintracht Frankfurt": "法兰克福",
    "Freiburg": "弗赖堡",
    "Union Berlin": "柏林联合",
    "Juventus": "尤文图斯",
    "Inter Milan": "国际米兰",
    "AC Milan": "AC米兰",
    "Napoli": "那不勒斯",
    "Roma": "罗马",
    "Lazio": "拉齐奥",
    "Atalanta": "亚特兰大",
    "Fiorentina": "佛罗伦萨",
    "Paris Saint-Germain": "巴黎圣日耳曼",
    "Monaco": "摩纳哥",
    "Marseille": "马赛",
    "Lyon": "里昂",
    "Benfica": "本菲卡",
    "Porto": "波尔图",
    "Ajax": "阿贾克斯",
    "PSV Eindhoven": "埃因霍温",
    "Feyenoord": "费耶诺德",
    "Celtic": "凯尔特人",
    "Rangers": "格拉斯哥流浪者",
    "Club Brugge": "布鲁日",
    "Galatasaray": "加拉塔萨雷",
    "Fenerbahce": "费内巴切",
    "Olympiacos": "奥林匹亚科斯"
}

# 联赛翻译字典
LEAGUE_TRANSLATE = {
    "Premier League": "英格兰超级联赛",
    "FA Cup": "英格兰足总杯",
    "League Cup": "英格兰联赛杯",
    "UEFA Champions League": "欧洲冠军联赛",
    "UEFA Europa League": "欧联杯",
    "UEFA Conference League": "欧协联"
}

# API-Sports 的比赛状态：已结束 / 已取消
FINISHED_STATUS = ("FT", "AET", "PEN")
CANCELLED_STATUS = ("PST", "CANC", "ABD", "AWD", "WO", "SUSP", "INT")

CRLF = "\r\n"
MAX_LINE_OCTETS = 75


def cn_team(name: str) -> str:
    return TEAM_TRANSLATE.get(name, name)


def cn_league(name: str) -> str:
    return LEAGUE_TRANSLATE.get(name, name)


# ---------- 取数据 ----------

def fetch_fixtures():
    """返回 (season, fixtures)。从 SEASON 起向前回退，直到取到比赛数据。"""
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {"x-apisports-key": API_KEY}
    last_problem = "尚未请求"

    for season in range(SEASON, SEASON - SEASON_FALLBACK_YEARS, -1):
        params = {"team": TEAM_ID, "season": season}
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            # 一定要让 CI 失败，并且不要写出任何文件，避免把坏日历推到仓库里。
            raise SystemExit(
                f"错误：请求 API 失败（{exc}）。常见原因：API key 无效或被禁用、"
                f"超出每日请求额度、网络不可达。"
            )
        data = resp.json()

        # 套餐限制、参数错误等都以 HTTP 200 + errors 返回，必须显式检查。
        errors = data.get("errors")
        fixtures = data.get("response") or []

        if errors:
            last_problem = f"season={season} 被 API 拒绝：{errors}"
            print(f"[跳过] {last_problem}")
            continue
        if not fixtures:
            last_problem = f"season={season} 返回 0 场比赛"
            print(f"[跳过] {last_problem}")
            continue

        print(f"[使用] season={season}，共 {len(fixtures)} 场比赛")
        return season, fixtures

    raise SystemExit(
        f"错误：从 {SEASON} 起连续 {SEASON_FALLBACK_YEARS} 个赛季都没取到数据。"
        f"最后一条原因：{last_problem}"
    )


# ---------- 写 iCalendar ----------

def escape_text(value: str) -> str:
    """转义 RFC 5545 TEXT 值里的特殊字符，并把真实换行变成 \\n。"""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def fold_line(line: str) -> str:
    """按 RFC 5545 折行：每行不超过 75 字节，续行以一个空格开头。

    折行必须在 UTF-8 字符边界上切，且续行开头那个空格也算在这 75 字节里。
    """
    data = line.encode("utf-8")
    if len(data) <= MAX_LINE_OCTETS:
        return line

    chunks = []
    start = 0
    limit = MAX_LINE_OCTETS
    while start < len(data):
        end = min(start + limit, len(data))
        # 不要把一个多字节字符切成两半。
        while end > start and end < len(data) and (data[end] & 0xC0) == 0x80:
            end -= 1
        chunks.append(data[start:end].decode("utf-8"))
        start = end
        limit = MAX_LINE_OCTETS - 1  # 续行首的空格占 1 字节

    return (CRLF + " ").join(chunks)


def utc_stamp(moment: datetime) -> str:
    """RFC 5545 UTC 时间：YYYYMMDDTHHMMSSZ。"""
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_event(item: dict, stamp: str) -> list:
    fixture = item["fixture"]
    home_cn = cn_team(item["teams"]["home"]["name"])
    away_cn = cn_team(item["teams"]["away"]["name"])
    league_cn = cn_league(item["league"]["name"])

    start = datetime.fromisoformat(fixture["date"].replace("Z", "+00:00"))
    end = start + timedelta(hours=2)

    status_short = (fixture.get("status") or {}).get("short", "")
    goals_home = (item.get("goals") or {}).get("home")
    goals_away = (item.get("goals") or {}).get("away")

    if status_short in FINISHED_STATUS and goals_home is not None and goals_away is not None:
        # 已结束：主队 比分 客队
        summary = f"{home_cn} {goals_home}-{goals_away} {away_cn}"
    else:
        # 未进行：主队 VS 客队
        summary = f"{home_cn} VS {away_cn}"

    venue_name = "未知球场"
    venue = fixture.get("venue") or {}
    if venue.get("name"):
        venue_name = venue["name"]
        if venue.get("city"):
            venue_name = f"{venue_name}（{venue['city']}）"

    description = (
        f"赛事：{league_cn}\n"
        f"球场：{venue_name}\n"
        f"比赛ID：{fixture['id']}"
    )

    # UID 由比赛 ID 派生：同一次导入/重复导入会更新同一事件，而不是产生重复条目。
    uid = f"fixture-{fixture['id']}@manlianrili"
    event_status = "CANCELLED" if status_short in CANCELLED_STATUS else "CONFIRMED"

    return [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{utc_stamp(start)}",
        f"DTEND:{utc_stamp(end)}",
        f"SUMMARY:{escape_text(summary)}",
        f"LOCATION:{escape_text(venue_name)}",
        f"DESCRIPTION:{escape_text(description)}",
        f"STATUS:{event_status}",
        "TRANSP:OPAQUE",
        "END:VEVENT",
    ]


def build_calendar(items, stamp: str) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//manlianrili//Manchester United fixtures//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_text(CALENDAR_NAME)}",
        "X-WR-TIMEZONE:Asia/Shanghai",
    ]
    for item in items:
        lines.extend(build_event(item, stamp))
    lines.append("END:VCALENDAR")

    return CRLF.join(fold_line(line) for line in lines) + CRLF


def main():
    season, fixtures = fetch_fixtures()

    stamp = utc_stamp(datetime.now(timezone.utc))
    ics = build_calendar(fixtures, stamp)

    if ics.count("BEGIN:VEVENT") == 0:
        raise SystemExit("错误：生成的日历里没有任何事件，拒绝写出空日历")

    # newline="" 避免 Windows 上把 CRLF 再翻译成 CRCRLF。
    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as fp:
        fp.write(ics)

    print(f"成功生成 {len(fixtures)} 场比赛的日历文件 {OUTPUT_FILE}（season={season}）")


if __name__ == "__main__":
    main()
