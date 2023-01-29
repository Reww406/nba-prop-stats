import re

ESPN_TEAM_NAME_TO_FD = {'la-clippers': 'los-angeles-clippers'}
FD_TEAM_NAME_TO_ESPN = {'los-angeles-clippers': 'la-clippers'}
NBA_CURR_SEASON = '2022-23'
NBA_LAST_SEASON = '2021-22'
#NBA TEAMS
NBA_TEAMS = [
    "https://www.espn.com/nba/team/_/name/bos/boston-celtics",
    "https://www.espn.com/nba/team/_/name/bkn/brooklyn-nets",
    "https://www.espn.com/nba/team/_/name/ny/new-york-knicks",
    "https://www.espn.com/nba/team/_/name/phi/philadelphia-76ers",
    "https://www.espn.com/nba/team/_/name/tor/toronto-raptors",
    "https://www.espn.com/nba/team/_/name/chi/chicago-bulls",
    "https://www.espn.com/nba/team/_/name/cle/cleveland-cavaliers",
    "https://www.espn.com/nba/team/_/name/det/detroit-pistons",
    "https://www.espn.com/nba/team/_/name/ind/indiana-pacers",
    "https://www.espn.com/nba/team/_/name/mil/milwaukee-bucks",
    "https://www.espn.com/nba/team/_/name/den/denver-nuggets",
    "https://www.espn.com/nba/team/_/name/min/minnesota-timberwolves",
    "https://www.espn.com/nba/team/_/name/okc/oklahoma-city-thunder",
    "https://www.espn.com/nba/team/_/name/por/portland-trail-blazers",
    "https://www.espn.com/nba/team/_/name/utah/utah-jazz",
    "https://www.espn.com/nba/team/_/name/gs/golden-state-warriors",
    "https://www.espn.com/nba/team/_/name/lac/la-clippers",
    "https://www.espn.com/nba/team/_/name/lal/los-angeles-lakers",
    "https://www.espn.com/nba/team/_/name/phx/phoenix-suns",
    "https://www.espn.com/nba/team/_/name/sac/sacramento-kings",
    "https://www.espn.com/nba/team/_/name/atl/atlanta-hawks",
    "https://www.espn.com/nba/team/_/name/cha/charlotte-hornets",
    "https://www.espn.com/nba/team/_/name/orl/orlando-magic",
    "https://www.espn.com/nba/team/_/name/wsh/washington-wizards",
    "https://www.espn.com/nba/team/_/name/dal/dallas-mavericks",
    "https://www.espn.com/nba/team/_/name/hou/houston-rockets",
    "https://www.espn.com/nba/team/_/name/mem/memphis-grizzlies",
    "https://www.espn.com/nba/team/_/name/no/new-orleans-pelicans",
    "https://www.espn.com/nba/team/_/name/sa/san-antonio-spurs",
    "https://www.espn.com/nba/team/_/name/mia/miami-heat"
]

# No Pistons, magic, rockets
# Change to team -> [players]
# This data had no effect on the logistic regression
TEAM_TO_STAR_PLAYERS = {
    "boston-celtics": ['jayson-tatum', 'jaylen-brown'],
    "brooklyn-nets": ['kevin-durant', "kyrie-irving"],
    "indiana-pacers": ["tyrese-haliburton", "buddy-hield"],
    "new-york-knicks": ['julius-randle', 'jalen-brunson'],
    "philadelphia-76ers": ['joel-embiid', 'james-harden'],
    "toronto-raptors": ['pascal-siakam', 'fred-vanvleet'],
    "golden-state-warriors": ["stephen-curry", "jordan-poole"],
    "los-angeles-lakers": ['lebron-james', 'russell-westbrook'],
    "phoenix-suns": ['deandre-ayton'],
    "sacramento-kings": ["de'aaron-fox", "domantas-sabonis"],
    "chicago-bulls": ["demar-derozan", "zach-lavine"],
    "cleveland-cavaliers": ['donovan-mitchell', 'darius-garland'],
    "milwaukee-bucks": ['giannis-antetokounmpo', 'jrue-holiday'],
    "charlotte-hornets": ['lamelo-ball', "terry-rozier"],
    "atlanta-hawks": ['trae-young', 'dejounte-murray'],
    "miami-heat": ['jimmy-butler', 'tyler-herro'],
    "washington-wizards": ['bradley-beal', 'kristaps-porzingis'],
    "denver-nuggets": ['nikola-jokic', 'jamal-murray'],
    "minnesota-timberwolves": ['anthony-edwards', "d'angelo-russell"],
    "la-clippers": ['kawhi-leonard', 'paul-george'],
    "oklahoma-city-thunder": ['shai-gilgeous-alexander', 'josh-giddey'],
    "portland-trail-blazers": ['damian-lillard', 'anfernee-simons'],
    "utah-jazz": ['lauri-markkanen', 'jordan-clarkson'],
    "dallas-mavericks": ["luka-doncic", 'christian-wood'],
    "memphis-grizzlies": ["ja-morant", 'desmond-bane'],
    "new-orleans-pelicans": ['zion-williamson', 'cj-mccollum'],
    'detroit-pistons': ['bojan-bogdanovic', 'jaden-ivey'],
    "orlando-magic": ['franz-wagner', 'paolo-banchero'],
    "houston-rockets": ['jalen-green', 'kevin-porter-jr'],
    "san-antonio-spurs": ['keldon-johnson', 'devin-vassell']
}

NAME_LINK_REGEX = re.compile(r"^.*?/name/(\w+)/(.*?)$", re.IGNORECASE)


def create_team_name_to_int(team_urls):
    r"""
        Creates dict with team_name : initial
    """
    team_name_to_int = {}
    for url in team_urls:
        match = NAME_LINK_REGEX.match(url.strip())
        team_name_to_int[match.group(2)] = match.group(1).upper()
    return team_name_to_int


TEAM_NAME_TO_INT = create_team_name_to_int(NBA_TEAMS)


def create_int_to_team_name():
    r"""
        Creates dict with team_name : initial
    """
    team_name_to_int = {}
    for url in NBA_TEAMS:
        match = NAME_LINK_REGEX.match(url.strip())
        team_name_to_int[match.group(1).upper()] = match.group(2)
    return team_name_to_int


INT_TO_TEAM_NAME = create_int_to_team_name()

# SQL Talbe conversions
OPP_SCORING_TO_SQL_COL_NAMES = {
    'TEAM': 'team_name',
    'GP': 'games_played',
    'G': 'games',
    'Freq%': 'fg_freq',
    'FGM': 'fg_made',
    'FGA': 'fg_att',
    'FG%': 'fg_per',
    'eFG%': 'fg_eff_per',
    '2FG Freq%': 'two_pt_freq',
    '2FGM': 'two_pt_made',
    '2FGA': 'two_pt_att',
    '2FG%': 'two_pt_per',
    '3FG Freq%': 'three_pt_freq',
    '3PM': 'three_pt_made',
    '3PA': 'three_pt_att',
    '3P%': 'three_pt_per'
}

ADV_STATS_TO_SQL_COL_NAMES = {
    'TEAM': 'team_name',
    'GP': 'games_played',
    'W': 'wins',
    'L': 'losses',
    'MIN': 'minutes_played',
    'OffRtg': 'off_rtg',
    'DefRtg': 'def_rtg',
    'NetRtg': 'net_rtg',
    'AST%': 'ast_per',
    'AST/TO': 'ast_to_ratio',
    'ASTRatio': 'ast_ratio',
    'OREB%': 'off_rebound_per',
    'DREB%': 'def_rebound_per',
    'REB%': 'reb_per',
    'TOV%': 'to_ratio',
    'eFG%': 'eff_fg_per',
    'TS%': 'true_shotting_per',
    'PACE': 'pace',
    'PIE': 'player_impact_est',
    'POSS': 'possions'
}

GL_TO_SQL_COL_NAMES = {
    'Date': 'game_date',
    'OPP': 'opp',
    'Result': 'result',
    'MIN': 'minutes_played',
    'FG%': 'fg_per',
    '3P%': 'three_pt_per',
    'FT%': 'ft_per',
    'REB': 'rebounds',
    'BLK': 'blocks',
    'STL': 'steals',
    'PF': 'fouls',
    'TO': 'turn_overs',
    'PTS': 'points',
    'AST': 'assists'
}
