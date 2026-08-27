import requests
from ics import Calendar, Event
from datetime import datetime

# ========== 配置区 ==========
API_KEY = "2ab7d451fdbe4e6d8c4503af82851b57"
TEAM_ID = 40  # 曼联一线队 ID
TIME_ZONE_OFFSET = 8
MATCH_DURATION_HOURS = 2
OUTPUT_FILE = "manu.ics"

# 球队中英对照，后续缺队伍在这里追加
team_map = {
    "Manchester United": "曼联",
    "Arsenal": "阿森纳",
    "Liverpool": "利物浦",
    "Chelsea": "切尔西",
    "Manchester City": "曼城",
    "Tottenham Hotspur": "热刺",
    "Newcastle United": "纽卡斯尔联",
    "Aston Villa": "阿斯顿维拉",
    "Brighton & Hove Albion": "布莱顿",
    "West Ham United": "西汉姆联",
    "Crystal Palace": "水晶宫",
    "Brentford": "布伦特福德",
    "Wolverhampton Wanderers": "狼队",
    "Everton": "埃弗顿",
    "Nottingham Forest": "诺丁汉森林",
    "Fulham": "富勒姆",
    "Bournemouth": "伯恩茅斯",
    "Southampton": "南安普顿",
    "Leicester City": "莱斯特城",
    "Ipswich Town": "伊普斯维奇"
}

comp_map = {
    "Premier League": "英超",
    "UEFA Champions League": "欧冠",
    "UEFA Europa League": "欧联杯",
    "UEFA Conference League": "欧协联",
    "FA Cup": "足总杯",
    "League Cup": "联赛杯"
}
# ============================

headers = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "api-football-v1.p.rapidapi.com"
}

def trans_team(name):
    return team_map.get(name, name)

def trans_comp(name):
    return comp_map.get(name, name)

def main():
    url = "https://api-football-v1.p.rapidapi.com/fixtures"
    params = {"team": TEAM_ID, "season": 2026}
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json()
    cal = Calendar()

    for item in data["response"]:
        fixture = item["fixture"]
        teams = item["teams"]
        league = item["league"]
        score = item["score"]

        fixture_id = fixture["id"]
        status_short = fixture["status"]["short"]

        # 跳过取消/延期取消
        if status_short in ["CANC","ABD"]:
            continue

        # UTC时间转北京时间
        utc_ts = fixture["timestamp"]
        start_bj = datetime.fromtimestamp(utc_ts)

        home_name = teams["home"]["name"]
        away_name = teams["away"]["name"]
        comp_name = league["name"]

        home_cn = trans_team(home_name)
        away_cn = trans_team(away_name)
        comp_cn = trans_comp(comp_name)

        home_goals = score["fulltime"]["home"]
        away_goals = score["fulltime"]["away"]
        is_finished = status_short == "FT"

        # 生成标题：完场带比分，未结束显示VS
        if home_name == "Manchester United":
            if is_finished and home_goals is not None and away_goals is not None:
                title = f"{comp_cn}：{home_cn} {home_goals}‑{away_goals} {away_cn}"
            else:
                title = f"{comp_cn}：{home_cn} VS {away_cn}"
        else:
            if is_finished and home_goals is not None and away_goals is not None:
                title = f"{comp_cn}：{away_cn} {away_goals}‑{home_goals} {home_cn}"
            else:
                title = f"{comp_cn}：{away_cn} VS {home_cn}"

        e = Event()
        e.uid = f"{fixture_id}@man‑utd‑cal.local"
        e.name = title
        e.begin = start_bj
        e.duration = {"hours": MATCH_DURATION_HOURS}

        desc_lines = [f"比赛状态：{fixture['status']['long']}"]
        if is_finished:
            ht_h = score["halftime"]["home"]
            ht_a = score["halftime"]["away"]
            desc_lines.append(f"全场比分：{home_goals}‑{away_goals}")
            desc_lines.append(f"半场比分：{ht_h}‑{ht_a}")
        e.description = "\n".join(desc_lines)
        cal.events.add(e)

    with open(OUTPUT_FILE, "w", encoding="utf‑8") as f:
        f.write(cal.serialize())

if __name__ == "__main__":
    main()
