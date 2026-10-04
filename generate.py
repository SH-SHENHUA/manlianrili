#!/usr/bin/env python3
"""生成曼联一线队赛程的 iCalendar(.ics) 文件。

数据来源（两条互补，合并后去重）：
1. football-data.org —— 免费档覆盖英超与欧冠，含球场(venue)、比分、UTC 时间。
   需要免费 token，通过环境变量 FOOTBALL_DATA_TOKEN 注入（GitHub Actions Secret）。
2. TheSportsDB —— 免费 key，用于补充 football-data.org 免费档**不覆盖**的杯赛
   （足总杯 / 联赛杯 / 欧联杯 / 欧协联），按轮次枚举。

输出按 RFC 5545 自己写出，保证 iOS 日历能导入：
CRLF 行尾且以 CRLF 结束、UTF-8 无 BOM、75 字节折行（不切断多字节字符）、
每个 VEVENT 都带必填的 UID / DTSTAMP / DTSTART / DTEND，UID 稳定派生。

比赛标题：未进行 = 主队 VS 客队；已结束 = 主队 比分 客队。
每个事件时长固定 2 小时，LOCATION 为比赛球场。
"""

import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

# ==========配置区域==========
# football-data.org 免费 token（必填）：注册后放到 Actions Secret，用环境变量注入。
FOOTBALL_DATA_TOKEN = (os.environ.get("FOOTBALL_DATA_TOKEN") or "").strip()
# football-data.org 里的曼联 id 和赛季起始年。
FD_TEAM_ID = 66
FD_SEASON = 2026
# 免费档覆盖的赛事：(赛事代码, 中文名)
FD_COMPETITIONS = (
    ("PL", "英格兰超级联赛"),
    ("CL", "欧洲冠军联赛"),
)

# TheSportsDB 免费 key 与需要补的杯赛（联赛 id -> 中文名）。
# 注意用 or 兜底：GitHub Actions 里未配置的 Secret 会变成空字符串。
THESPORTSDB_KEY = (os.environ.get("THESPORTSDB_KEY") or "123").strip()
TSS_CUPS = (
    ("4482", "英格兰足总杯"),
    ("4570", "英格兰联赛杯"),
    ("4481", "欧联杯"),
    ("5071", "欧协联"),
)
# 杯赛按轮次枚举；TheSportsDB 不同赛事的轮次编号不一致，所以扫一段范围。
TSS_CUP_ROUNDS = tuple(range(1, 9))
# TheSportsDB 的英超联赛 id：当 football-data.org 不可用时作为兜底来源。
TSS_PL_LEAGUE_ID = "4328"
TSS_PL_ROUNDS = tuple(range(1, 39))
# 欧冠（联赛阶段 8 轮，多扫几轮以便后续淘汰赛出现时也能补上）。
TSS_UCL_LEAGUE_ID = "4480"
TSS_UCL_ROUNDS = tuple(range(1, 13))
# 是否允许兜底（默认允许）。设为 0 则 football-data.org 不可用时直接失败。
ALLOW_PL_FALLBACK = (os.environ.get("ALLOW_PL_FALLBACK") or "1") != "0"
# 两次 TheSportsDB 请求之间的间隔（秒），避开其免费 key 的限流。
TSS_DELAY_SECONDS = float(os.environ.get("THESPORTSDB_DELAY") or 6)

OUTPUT_FILE = (os.environ.get("OUTPUT_FILE") or "matches.ics").strip()
CALENDAR_NAME = "曼联赛程"
# ============================

# 球队翻译字典
TEAM_TRANSLATE = {
    "Manchester United": "曼联",
    "Liverpool": "利物浦",
    "Arsenal": "阿森纳",
    "Chelsea": "切尔西",
    "Manchester City": "曼城",
    "Tottenham Hotspur": "托特纳姆热刺",
    "Tottenham": "托特纳姆热刺",
    "Newcastle United": "纽卡斯尔联",
    "Newcastle": "纽卡斯尔联",
    "Aston Villa": "阿斯顿维拉",
    "Brighton & Hove Albion": "布莱顿",
    "Brighton and Hove Albion": "布莱顿",
    "Brighton": "布莱顿",
    "Crystal Palace": "水晶宫",
    "Everton": "埃弗顿",
    "Nottingham Forest": "诺丁汉森林",
    "West Ham United": "西汉姆联",
    "West Ham": "西汉姆联",
    "Bournemouth": "伯恩茅斯",
    "Fulham": "富勒姆",
    "Wolverhampton Wanderers": "狼队",
    "Wolves": "狼队",
    "Southampton": "南安普顿",
    "Leicester City": "莱斯特城",
    "Leicester": "莱斯特城",
    "Ipswich Town": "伊普斯维奇",
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
    "Atlético Madrid": "马德里竞技",
    "Sevilla": "塞维利亚",
    "Real Sociedad": "皇家社会",
    "Villarreal": "比利亚雷亚尔",
    "Real Betis": "皇家贝蒂斯",
    "Betis": "皇家贝蒂斯",
    "Bayern Munich": "拜仁慕尼黑",
    "Borussia Dortmund": "多特蒙德",
    "Bayer Leverkusen": "勒沃库森",
    "RB Leipzig": "莱比锡红牛",
    "Eintracht Frankfurt": "法兰克福",
    "Freiburg": "弗赖堡",
    "Union Berlin": "柏林联合",
    "Stuttgart": "斯图加特",
    "Juventus": "尤文图斯",
    "Inter Milan": "国际米兰",
    "Inter": "国际米兰",
    "AC Milan": "AC米兰",
    "Milan": "AC米兰",
    "Napoli": "那不勒斯",
    "Roma": "罗马",
    "Lazio": "拉齐奥",
    "Atalanta": "亚特兰大",
    "Fiorentina": "佛罗伦萨",
    "Como": "科莫",
    "Paris Saint-Germain": "巴黎圣日耳曼",
    "Paris FC": "巴黎FC",
    "Monaco": "摩纳哥",
    "Marseille": "马赛",
    "Lyon": "里昂",
    "Lille": "里尔",
    "Benfica": "本菲卡",
    "Porto": "波尔图",
    "Sporting CP": "葡萄牙体育",
    "Ajax": "阿贾克斯",
    "PSV Eindhoven": "埃因霍温",
    "Feyenoord": "费耶诺德",
    "Celtic": "凯尔特人",
    "Rangers": "格拉斯哥流浪者",
    "Club Brugge": "布鲁日",
    "Galatasaray": "加拉塔萨雷",
    "Fenerbahçe": "费内巴切",
    "Fenerbahce": "费内巴切",
    "Olympiacos": "奥林匹亚科斯",
    "Slavia Prague": "布拉格斯拉维亚",
    "Shakhtar Donetsk": "顿涅茨克矿工",
    "Lens": "朗斯",
    "Bodø/Glimt": "博多闪耀",
    "Slovan Bratislava": "布拉迪斯拉发斯拉夫人",
    "Viking": "维京",
    "LASK": "林茨",
    "AEK Athens": "雅典AEK",
    "Sabah Baku": "萨巴巴库",
    "Barnsley": "巴恩斯利",
}

# football-data.org 的比赛状态
FD_FINISHED_STATUS = ("FINISHED", "AWARDED")
FD_SKIP_STATUS = ("CANCELLED",)

FINISHED = "finished"
NOT_STARTED = "not_started"
CANCELLED = "cancelled"

CRLF = "\r\n"
MAX_LINE_OCTETS = 75

# 用于跨数据源对齐队名的后缀/前缀
_NAME_PREFIXES = ("AFC ", "FC ", "AS ", "AC ", "SV ", "SK ")
_NAME_SUFFIXES = (" FC", " AFC", " CF", " SC", " AC", " SV", " Club", " Football Club")


# ---------- 通用工具 ----------

def norm_team(name: str) -> str:
    """把不同数据源的队名归一化，用于翻译和跨源去重。

    注意 "&" 与 "and" 的差异：TheSportsDB 写 "Brighton and Hove Albion"，
    football-data.org 写 "Brighton & Hove Albion FC"，不统一就会漏掉重复事件。
    """
    cleaned = (name or "").strip().replace(" & ", " and ")
    for prefix in _NAME_PREFIXES:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
    for suffix in _NAME_SUFFIXES:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
    return re.sub(r"\s+", " ", cleaned).strip()


def cn_team(name: str) -> str:
    cleaned = norm_team(name)
    if cleaned in TEAM_TRANSLATE:
        return TEAM_TRANSLATE[cleaned]
    lowered = cleaned.lower()
    for key, value in TEAM_TRANSLATE.items():
        if key.lower() == lowered:
            return value
    for key, value in TEAM_TRANSLATE.items():
        if lowered.startswith(key.lower()) or key.lower().startswith(lowered):
            return value
    return cleaned


def dedupe_key(event) -> tuple:
    return (
        event["start"].astimezone(timezone.utc).date().isoformat(),
        norm_team(event["home"]).lower(),
        norm_team(event["away"]).lower(),
    )


def _is_man_utd(team) -> bool:
    """判断一个 football-data.org 的球队对象是不是曼联。

    既认 id，也认队名：万一 id 与我们记录的 66 不一致，也不会取到 0 场而失败。
    """
    if not team:
        return False
    if team.get("id") == FD_TEAM_ID:
        return True
    return norm_team(team.get("name") or "").lower() == "manchester united"


# ---------- 数据源 1：football-data.org ----------

def _fd_fetch_matches(code: str, season):
    """请求某个赛事的比赛列表。season 为 None 时表示用 API 默认（当前赛季）。"""
    url = f"https://api.football-data.org/v4/competitions/{code}/matches"
    params = {} if season is None else {"season": season}
    resp = requests.get(url, headers={"X-Auth-Token": FOOTBALL_DATA_TOKEN}, params=params, timeout=40)
    resp.raise_for_status()
    return resp.json()


def fetch_football_data() -> list:
    if not FOOTBALL_DATA_TOKEN:
        raise SystemExit(
            "错误：缺少 FOOTBALL_DATA_TOKEN。\n"
            "请到 https://www.football-data.org/client/register 免费注册并取得 token，\n"
            "然后在本机设为环境变量，或在 GitHub 仓库里加 Actions Secret（名字用 FOOTBALL_DATA_TOKEN）。"
        )

    events = []
    for code, cn_name in FD_COMPETITIONS:
        payload = None
        matches = []
        # 先用配置的赛季；取不到就退回 API 默认（当前赛季），避免赛季编号不一致直接失败。
        for season in (FD_SEASON, None):
            label = f"season={season}" if season is not None else "当前赛季"
            try:
                payload = _fd_fetch_matches(code, season)
            except requests.RequestException as exc:
                print(f"[football-data] {cn_name}({code}) {label} 请求失败：{exc}")
                payload = None
                continue

            matches = payload.get("matches") or []
            result_count = (payload.get("resultSet") or {}).get("count")
            print(f"[football-data] {cn_name}({code}) {label} 返回 {len(matches)} 场"
                  + (f"（resultSet.count={result_count}）" if result_count is not None else ""))
            if result_count is not None and result_count > len(matches):
                print(f"[football-data] 警告：接口只返回 {len(matches)} 场，少于 resultSet.count="
                      f"{result_count}，结果可能被截断")
            if matches:
                break
            print(f"[football-data] {cn_name}({code}) {label} 没有数据，尝试赛季回退")

        if not matches:
            print(f"[football-data] 警告：{cn_name}({code}) 两个赛季都没取到比赛")
            continue

        for match in matches:
            home = match.get("homeTeam") or {}
            away = match.get("awayTeam") or {}
            if not (_is_man_utd(home) or _is_man_utd(away)):
                continue
            for team in (home, away):
                if _is_man_utd(team) and team.get("id") != FD_TEAM_ID:
                    print(
                        f"[提示] 通过队名匹配到曼联，但 id={team.get('id')} 与配置的 "
                        f"FD_TEAM_ID={FD_TEAM_ID} 不同，请更新配置。"
                    )
                    break
            status = match.get("status")
            if status in FD_SKIP_STATUS:
                continue
            score = ((match.get("score") or {}).get("fullTime") or {})
            finished = status in FD_FINISHED_STATUS and score.get("home") is not None
            if finished:
                state = FINISHED
            else:
                state = NOT_STARTED
            events.append(
                {
                    "source": "football-data",
                    "key": f"fd-{match['id']}",
                    "start": datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00")),
                    "home": home.get("name") or "?",
                    "away": away.get("name") or "?",
                    "competition": cn_name,
                    "venue": (match.get("venue") or "").strip(),
                    "score": (score.get("home"), score.get("away")) if finished else None,
                    "state": state,
                    "detail": f"比赛ID：{match['id']}",
                }
            )
    return events


# ---------- 数据源 2：TheSportsDB（补杯赛 / 兜底） ----------

# 记录失败的请求。TheSportsDB 免费 key 限流很严，一旦某轮取不到，
# 该赛事的覆盖就不完整——这一点必须让日志和日历描述都体现出来，不能静默。
TSS_FAILURES = []


def _tss_get(url: str):
    """带限流退避的 GET；失败返回 None 并记录，便于判断覆盖是否完整。"""
    for attempt in range(1, 4):
        try:
            resp = requests.get(url, timeout=40, headers={"User-Agent": "manlianrili-calendar/1.0"})
            if resp.status_code == 429:
                wait = 20 * attempt
                print(f"[thesportsdb] 被限流，等 {wait}s 后重试")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            time.sleep(TSS_DELAY_SECONDS)
            return resp.json()
        except requests.RequestException as exc:
            print(f"[thesportsdb] 请求失败：{exc}")
            time.sleep(TSS_DELAY_SECONDS)
            TSS_FAILURES.append(f"{url.split('id=')[-1]}: {exc}")
            return None
    print("[thesportsdb] 重试仍被限流，跳过")
    TSS_FAILURES.append(f"{url.split('id=')[-1]}: 429 限流")
    return None


def _is_man_utd_tsdb(name: str) -> bool:
    """TheSportsDB 里曼联就叫 Manchester United，用归一化后的全等判断。"""
    return norm_team(name or "").lower() == "manchester united"


def _tss_round_events(league_id: str, cn_name: str, rounds) -> list:
    """按轮次枚举某赛事并抽出曼联的比赛。任何一轮失败就停止该赛事（返回已取到的部分）。"""
    events = []
    for rnd in rounds:
        url = (
            f"https://www.thesportsdb.com/api/v1/json/{THESPORTSDB_KEY}/eventsround.php"
            f"?id={league_id}&r={rnd}&s={FD_SEASON}-{FD_SEASON + 1}"
        )
        data = _tss_get(url)
        if not data:
            break
        for item in data.get("events") or []:
            home = item.get("strHomeTeam") or ""
            away = item.get("strAwayTeam") or ""
            if not (_is_man_utd_tsdb(home) or _is_man_utd_tsdb(away)):
                continue
            stamp = (item.get("strTimestamp") or "").strip()
            date_text = item.get("dateEvent")
            time_text = item.get("strTime")
            # TheSportsDB 的 strTimestamp / strTime 是 UTC（已用 openfootball 独立核对过）。
            if stamp:
                start = datetime.fromisoformat(stamp.replace("Z", ""))
            elif date_text:
                start = datetime.fromisoformat(f"{date_text}T{(time_text or '00:00:00')}")
            else:
                continue
            start = start.replace(tzinfo=timezone.utc)

            home_score, away_score = item.get("intHomeScore"), item.get("intAwayScore")
            finished = home_score is not None and away_score is not None
            events.append(
                {
                    "source": "thesportsdb",
                    "key": f"tsdb-{item.get('idEvent')}",
                    "start": start,
                    "home": home,
                    "away": away,
                    "competition": cn_name,
                    "venue": (item.get("strVenue") or "").strip(),
                    "score": (int(home_score), int(away_score)) if finished else None,
                    "state": FINISHED if finished else NOT_STARTED,
                    "detail": f"比赛ID：{item.get('idEvent')}",
                }
            )
    return events


def fetch_thesportsdb_cups() -> list:
    events = []
    for league_id, cn_name in TSS_CUPS:
        found = _tss_round_events(league_id, cn_name, TSS_CUP_ROUNDS)
        print(f"[thesportsdb] {cn_name} 找到曼联比赛 {len(found)} 场")
        events.extend(found)
    return events


def fetch_thesportsdb_pl() -> list:
    """兜底：从 TheSportsDB 按轮次枚举英超与欧冠，取出曼联的整季比赛。"""
    events = _tss_round_events(TSS_PL_LEAGUE_ID, "英格兰超级联赛", TSS_PL_ROUNDS)
    print(f"[thesportsdb] 英超兜底找到曼联比赛 {len(events)} 场")
    ucl = _tss_round_events(TSS_UCL_LEAGUE_ID, "欧洲冠军联赛", TSS_UCL_ROUNDS)
    print(f"[thesportsdb] 欧冠兜底找到曼联比赛 {len(ucl)} 场")
    return events + ucl


# ---------- 合并 ----------

def collect_events():
    """收集事件并合并去重。返回 (events, coverage_note)。

    football-data.org 是主来源；它不可用时，若允许兜底，就用 TheSportsDB 顶上，
    并在日志与日历描述里明确标注这是降级结果。
    """
    failures_before = len(TSS_FAILURES)

    primary = []
    degraded = False
    try:
        primary = fetch_football_data()
    except SystemExit as exc:
        print(f"[警告] football-data.org 不可用：{exc}")

    try:
        supplement = fetch_thesportsdb_cups()
    except Exception as exc:  # 杯赛是补充来源，失败不应导致整次运行失败
        print(f"[thesportsdb] 补充杯赛时出错，已跳过：{type(exc).__name__}: {exc}")
        supplement = []

    fallback = []
    if not primary:
        if not ALLOW_PL_FALLBACK:
            raise SystemExit(
                f"错误：football-data.org 没有返回任何曼联比赛"
                f"（已尝试 season={FD_SEASON} 与「当前赛季」），且已禁用兜底，拒绝生成不完整的日历。\n"
                f"请检查：token 是否有效、免费档是否包含 "
                f"{'/'.join(c for c, _ in FD_COMPETITIONS)}、以及该赛季是否已经开始。\n"
                f"（想先用 TheSportsDB 的英超/欧冠数据兜底，去掉 ALLOW_PL_FALLBACK=0 即可。）"
            )
        degraded = True
        print("=" * 62)
        print("[警告] 正在进行降级运行：改用 TheSportsDB 的数据。")
        print("[警告] 覆盖范围取决于 TheSportsDB 免费库当前有什么（实测含英超与欧冠联赛阶段）。")
        print("[警告] 配置 FOOTBALL_DATA_TOKEN 后会自动改用 football-data.org 的权威数据。")
        print("=" * 62)
        try:
            fallback = fetch_thesportsdb_pl()
        except Exception as exc:
            print(f"[thesportsdb] 兜底出错：{type(exc).__name__}: {exc}")
            fallback = []

    seen = set()
    merged = []
    skipped = 0
    for event in list(primary) + list(fallback) + list(supplement):
        key = dedupe_key(event)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        merged.append(event)

    if not merged:
        raise SystemExit(
            "错误：所有数据源都没有取到任何比赛，拒绝写出空日历。"
            "请检查 token / 网络 / 赛季配置。"
        )

    print(
        f"合并后共 {len(merged)} 场"
        f"（football-data {len(primary)} 场，TheSportsDB 英超兜底 {len(fallback)} 场，"
        f"TheSportsDB 杯赛 {len(supplement)} 场，去重丢弃 {skipped} 场）"
    )
    merged.sort(key=lambda e: e["start"])

    competitions = []
    for event in merged:
        if event["competition"] not in competitions:
            competitions.append(event["competition"])
    sources = []
    for event in merged:
        if event["source"] not in sources:
            sources.append(event["source"])
    note = f"数据来源：{' + '.join(sources)}；覆盖：{'、'.join(competitions)}"
    if degraded:
        note += "（降级运行：未配置 FOOTBALL_DATA_TOKEN，数据来自 TheSportsDB）"
    new_failures = TSS_FAILURES[failures_before:]
    if new_failures:
        print(f"[警告] TheSportsDB 有 {len(new_failures)} 个请求失败，本次覆盖可能不完整：")
        for item in new_failures[:5]:
            print(f"         {item}")
        note += f"（注意：{len(new_failures)} 个接口请求失败，覆盖可能不完整）"
    print(f"[覆盖] {note}")
    return merged, note


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
        while end > start and end < len(data) and (data[end] & 0xC0) == 0x80:
            end -= 1
        chunks.append(data[start:end].decode("utf-8"))
        start = end
        limit = MAX_LINE_OCTETS - 1  # 续行首的空格占 1 字节
    return (CRLF + " ").join(chunks)


def utc_stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_event(event, stamp: str) -> list:
    start = event["start"].astimezone(timezone.utc)
    end = start + timedelta(hours=2)

    home_cn = cn_team(event["home"])
    away_cn = cn_team(event["away"])

    if event["state"] == FINISHED and event.get("score"):
        summary = f"{home_cn} {event['score'][0]}-{event['score'][1]} {away_cn}"
    else:
        summary = f"{home_cn} VS {away_cn}"

    venue = event.get("venue") or "待定球场"
    description = (
        f"赛事：{event['competition']}\n"
        f"球场：{venue}\n"
        f"{event.get('detail', '')}"
    ).rstrip()

    uid = f"{event['key']}@manlianrili"
    status = "CANCELLED" if event["state"] == CANCELLED else "CONFIRMED"

    return [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{utc_stamp(start)}",
        f"DTEND:{utc_stamp(end)}",
        f"SUMMARY:{escape_text(summary)}",
        f"LOCATION:{escape_text(venue)}",
        f"DESCRIPTION:{escape_text(description)}",
        f"STATUS:{status}",
        "TRANSP:OPAQUE",
        "END:VEVENT",
    ]


def build_calendar(events, stamp: str, calendar_note: str = "") -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//manlianrili//Manchester United fixtures//CN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_text(CALENDAR_NAME)}",
        "X-WR-TIMEZONE:Asia/Shanghai",
    ]
    if calendar_note:
        # 写进日历描述：在 iPhone 上也能看到覆盖范围与数据来源，降级运行不会是"静默"的。
        lines.append(f"X-WR-CALDESC:{escape_text(calendar_note)}")
    for event in events:
        lines.extend(build_event(event, stamp))
    lines.append("END:VCALENDAR")
    return CRLF.join(fold_line(line) for line in lines) + CRLF


def main():
    events, calendar_note = collect_events()

    stamp = utc_stamp(datetime.now(timezone.utc))
    ics = build_calendar(events, stamp, calendar_note)

    if ics.count("BEGIN:VEVENT") == 0:
        raise SystemExit("错误：生成的日历里没有任何事件，拒绝写出空日历")

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as fp:
        fp.write(ics)

    upcoming = sum(1 for e in events if e["state"] == NOT_STARTED)
    print(f"成功生成 {len(events)} 场比赛（其中未进行 {upcoming} 场）-> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
