from ics import Calendar, Event
from datetime import datetime, timedelta
import requests

# ==========配置区域==========
API_KEY = "粘贴你的api‑sports密钥到双引号内部，不要空格换行"
TEAM_ID = 40
SEASON = 2026
OUTPUT_FILE = "matches.ics"
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
    "Brentford": "布伦特福德"
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


def cn_team(name: str) -> str:
    return TEAM_TRANSLATE.get(name, name)


def cn_league(name: str) -> str:
    return LEAGUE_TRANSLATE.get(name, name)


def main():
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {
        "x-apisports-key": API_KEY
    }
    params = {
        "team": TEAM_ID,
        "season": SEASON
    }

    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json()

    cal = Calendar()

    for item in data["response"]:
        fixture = item["fixture"]
        home_en = item["teams"]["home"]["name"]
        away_en = item["teams"]["away"]["name"]
        league_en = item["league"]["name"]

        home_cn = cn_team(home_en)
        away_cn = cn_team(away_en)
        league_cn = cn_league(league_en)

        match_date_raw = fixture["date"]
        match_start = datetime.fromisoformat(match_date_raw.replace("Z", "+00:00"))

        status_short = fixture["status"]["short"]
        goals_home = item["goals"]["home"]
        goals_away = item["goals"]["away"]

        event = Event()
        # 比赛结束状态：FT/AET/PEN，标题替换成分数；未开赛显示VS
        if status_short in ("FT", "AET", "PEN") and goals_home is not None and goals_away is not None:
            event.name = f"{home_cn} {goals_home}‑{goals_away} {away_cn}"
        else:
            event.name = f"{home_cn} VS {away_cn}"

        event.begin = match_start
        event.duration = timedelta(hours=2)
        venue = fixture["venue"]["name"] if fixture["venue"] and fixture["venue"]["name"] else "未知球场"
        event.description = (
            f"赛事：{league_cn}\n"
            f"球场：{venue}\n"
            f"比赛ID：{fixture['id']}"
        )
        cal.events.add(event)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as fp:
        fp.writelines(cal)


if __name__ == "__main__":
    main()
