from ics import Calendar, Event
from datetime import datetime, timedelta
import requests
import sys

# ==========配置区域==========
API_KEY = "c57992dce30fc408d01e13b57ffd4a09"
TEAM_ID = 33
SEASON = 2025
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


def cn_team(name: str) -> str:
    return TEAM_TRANSLATE.get(name, name)


def cn_league(name: str) -> str:
    return LEAGUE_TRANSLATE.get(name, name)


def main():
    url = "https://v3.football.api-sports.io/fixtures"
    headers = {
        "x-apisports-key": API_KEY.encode("ascii").decode("ascii")
    }
    params = {
        "team": TEAM_ID,
        "season": SEASON
    }

    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json()

    match_count = len(data["response"])
    print(f"API 返回比赛数量：{match_count}")

    if match_count == 0:
        print("错误：API 未返回任何比赛数据，请检查 season 参数或球队 ID")
        sys.exit(1)

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
        if status_short in ("FT", "AET", "PEN") and goals_home is not None and goals_away is not None:
            event.name = f"{home_cn} {goals_home}-{goals_away} {away_cn}"
        else:
            event.name = f"{home_cn} 对阵 {away_cn}"

        event.begin = match_start
        event.duration = timedelta(hours=2)
        
        venue_name = "未知球场"
        if fixture.get("venue") and fixture["venue"].get("name"):
            venue_name = fixture["venue"]["name"]
        
        event.description = (
            f"赛事：{league_cn}\n"
            f"球场：{venue_name}\n"
            f"比赛ID：{fixture['id']}"
        )
        cal.events.add(event)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as fp:
        fp.write(str(cal))
    
    print(f"成功生成 {len(cal.events)} 场比赛的日历文件")


if __name__ == "__main__":
    main()
