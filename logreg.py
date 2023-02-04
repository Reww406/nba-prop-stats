from datetime import date
import re
import time
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
from sklearn import metrics
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
from sklearn.metrics import classification_report, precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from player_stats import stats
from player_stats import sqllite_utils
from player_stats import scraper
from player_stats import constants
from pygam import LogisticGAM

DB_CON = sqllite_utils.get_db_in_mem()
NAME_LINK_REGEX = re.compile(r"^.*?/name/(\w+)/(.*?)$", re.IGNORECASE)

TN_PACE = sqllite_utils.get_team_name_and_stat(DB_CON, 'pace', 'nba_adv_stats')
TN_2PT_D = sqllite_utils.get_team_name_and_stat(DB_CON, 'two_pt_made',
                                                'opp_scoring')
TN_3PT_D = sqllite_utils.get_team_name_and_stat(DB_CON, 'three_pt_made',
                                                'opp_scoring')
TN_DEF_RTG = sqllite_utils.get_team_name_and_stat(DB_CON, 'def_rtg',
                                                  'nba_adv_stats')
TN_DEF_RB = sqllite_utils.get_team_name_and_stat(DB_CON, 'def_rebound_per',
                                                 'nba_adv_stats')
TN_OFF_RB = sqllite_utils.get_team_name_and_stat(DB_CON, 'off_rebound_per',
                                                 'nba_adv_stats')
GL_DATE_REGEX = re.compile(r"^.*?(\d{1,2})/(\d{1,2})$")
OPP_REGEX = re.compile(r"^(@|vs)(\w+)$")

RESULT_REGEX = re.compile(r"^(W|L)(\d{2,3})-(\d{2,3}).*?$")


def convert_team_name(team_name):
    """
        Fixes the clippers name
    """
    if constants.FD_TEAM_NAME_TO_ESPN.get(team_name) is None:
        return team_name
    return constants.FD_TEAM_NAME_TO_ESPN.get(team_name)


def convert_prop_date_to_game(date: str):
    month = date.split('-')[0]
    day = date.split('-')[1]
    if month[0] == '0':
        month = month[1]
    if day[0] == '0':
        day = day[1]
    return month + '/' + day


def add_over_hit(props):
    """
        1 is over, 0 is under
    """
    props_with_result = []
    for prop in props:
        if prop.get('game_total') == 0:
            continue

        date = convert_prop_date_to_game(prop.get('prop_scraped'))
        game_log = sqllite_utils.get_points_for_game(
            prop.get('player_name'), convert_team_name(prop.get('team_name')),
            date, constants.NBA_CURR_SEASON, DB_CON)

        if game_log is None:
            continue

        if game_log.get('minutes_played') < 15:
            continue

        if game_log.get('points') > prop.get('over_num'):
            prop['over_hit'] = 1
            props_with_result.append(prop)
        else:
            prop['over_hit'] = 0
            props_with_result.append(prop)
    return props_with_result


def get_alt_hit(prop, alt_line):
    """
        1 is over, 0 is under
    """
    date = convert_prop_date_to_game(prop.get('prop_scraped'))
    game_log = sqllite_utils.get_points_for_game(
        prop.get('player_name'), convert_team_name(prop.get('team_name')),
        date, constants.NBA_CURR_SEASON, DB_CON)

    if prop.get('game_total') == 0:
        return None

    if game_log is None:
        return None

    if game_log.get('minutes_played') < 15:
        return None

    if game_log.get('points') > alt_line:
        return 1
    return 0


def get_per_over(props):
    total = len(props)
    over_hit = len([prop for prop in props if prop.get('over_hit') == 1])
    print(f"{(over_hit / total)}")


def is_same_date(prop_date, game_date, season):
    """
        Checks if two dates are the same prop_date mm-dd-yy
        game_date mm_dd + season
    """
    prop_date_arr = prop_date.split('-')
    prop_date = date(int(prop_date_arr[2]), int(prop_date_arr[0]),
                     int(prop_date_arr[1]))

    game_date_match = GL_DATE_REGEX.match(game_date)
    season_splt = season.split('-')
    if game_date_match.group(1) == '1':
        year = int(season_splt[0][0:2] + season_splt[1])
    else:
        year = int(season_splt[0])
    game_date = date(year, int(game_date_match.group(1)),
                     int(game_date_match.group(2)))
    return prop_date == game_date


def get_past_performance(prop):
    """
        Finds games played against this opp by this player
    """
    match = convert_team_name(prop.get('opp_name'))
    opp = constants.TEAM_NAME_TO_INT.get(match)

    this_seasons = sqllite_utils.get_player_games_vs_opp(
        prop.get('player_name'), constants.NBA_CURR_SEASON,
        convert_team_name(prop.get('team_name')), opp, DB_CON)

    last_seasons_games = sqllite_utils.get_player_games_vs_opp(
        prop.get('player_name'), constants.NBA_LAST_SEASON,
        convert_team_name(prop.get('team_name')), opp, DB_CON)
    # make sure games this season arn't the same as the bet,
    # only matters for training data.
    filtered_games = []
    for game in this_seasons:
        if not is_same_date(prop.get('prop_scraped'), game.get('game_date'),
                            game.get('season')):
            filtered_games.append(game)
        # else:
        #     print(f"{prop.get('prop_scraped')} and {game.get('game_date')}")

    # If no games against this opp return None
    if len(filtered_games) == 0 and len(last_seasons_games) == 0:
        return None
    # If only entry
    if len(filtered_games) == 0 and len(last_seasons_games) == 1:
        return None
    if len(filtered_games) == 1 and len(last_seasons_games) == 0:
        return None
    if len(filtered_games) == 1 and len(last_seasons_games) == 1:
        filtered_games.extend(last_seasons_games)
        return np.mean([gl.get('points') for gl in filtered_games])
    # If only one has multiple
    if len(filtered_games) > 1 and len(last_seasons_games) == 0:
        return np.mean([gl.get('points') for gl in filtered_games])
    if len(filtered_games) == 0 and len(last_seasons_games) > 1:
        return np.mean([gl.get('points') for gl in last_seasons_games])
    # Both have multiple
    this_seasons_mean = np.mean([gl.get('points') for gl in filtered_games])
    last_seasons_mean = np.mean(
        [gl.get('points') for gl in last_seasons_games])
    # print(f"{this_seasons_mean} & {last_seasons_mean}")
    return np.mean([this_seasons_mean, last_seasons_mean])


def is_star_player_out(team, season, prop_date):
    """
        Checks if star player is missing
    """
    star_players = constants.TEAM_TO_STAR_PLAYERS.get(team)
    missing = 0
    for player in star_players:
        gl = sqllite_utils.get_player_gl(player, season, team,
                                         convert_prop_date_to_game(prop_date),
                                         DB_CON)
        if gl is None or len(gl) == 0:
            missing += 1
    return missing


def create_alt_point_lines(props):
    alt_point_props = []
    alt_overs = [9.5, 14.5, 19.5, 24.5, 29.5]
    for prop in props:
        for alt_line in alt_overs:
            alt_hit = get_alt_hit(prop, alt_line)
            if alt_hit is None:
                continue
            alt_point_props.append({
                'season': prop.get('season'),
                'prop_name': prop.get('prop_name'),
                'player_name': prop.get('player_name'),
                'team_spread': prop.get('team_spread'),
                'game_total': prop.get('game_total'),
                'prop_scraped': prop.get('prop_scraped'),
                'team_name': prop.get('team_name'),
                'opp_name': prop.get('opp_name'),
                'alt_hit': alt_hit,
                'alt_line': alt_line
            })
    return alt_point_props


recent_per_times = []
consitency_times = []
avg_points_times = []
effective_fg_times = []


def _get_start_time():
    return time.time() * 1000


def _get_elapsed_time(start_time):
    return abs(start_time - time.time() * 1000)


# pull all game logs into memory..
def load_game_logs_into_memory():
    """
        Loads all game logs into memory using player_name+team_name as the key
        luka+mavs
    """
    names_and_teams = sqllite_utils.get_unique_player_and_team(DB_CON)
    player_to_gamelogs = {}
    for data in names_and_teams:
        player = data['player_name']
        team = data['team_name']
        key = player + '+' + team
        player_to_gamelogs[key] = sqllite_utils.get_player_gls(
            player, constants.NBA_CURR_SEASON, team, DB_CON)
    return player_to_gamelogs


def points_against_similar_teams(teams, gls):
    """
        Gets point mean for team with similar stats like pace or def
    """
    opps = [constants.TEAM_NAME_TO_INT.get(team) for team in teams]
    points = []
    for gl in gls:
        match = OPP_REGEX.match(gl.get('opp')).group(2)
        if match in opps:
            points.append(gl.get('points'))
    if len(points) == 1:
        return points[0]
    if len(points) == 0:
        return None
    return np.mean(points)
    

def build_test_data_frame():
    print("creating props")
    props = create_alt_point_lines(
        sqllite_utils.get_all_props_for_type('points', DB_CON))
    data = []
    print("analyzing data")

    for prop in props:
        team_name = convert_team_name(prop.get('team_name'))
        player_name = prop.get('player_name')
        total = prop.get('game_total')
        opp = convert_team_name(prop.get('opp_name'))
        gls = sqllite_utils.get_player_gls(player_name,
                                           constants.NBA_CURR_SEASON,
                                           team_name, DB_CON)
        if gls is None:
            print(f"couldn't find: {player_name}+{team_name}")
            continue

        # True shooting percentage
        # Score against opp
        # Score in similar spread games
        # Score in similar total games
        # Score in similar pace games

        prop_date_arr = prop.get('prop_scraped').split('-')
        prop_date = date(int(prop_date_arr[2]), int(prop_date_arr[0]),
                         int(prop_date_arr[1]))

        over = prop.get('alt_line')
        over_hit = prop.get('alt_hit')
        eff_fg_per = stats.calculate_eff_fg_per(gls)
        recent_performance = stats.point_avg_last_nth_games(gls, prop_date, 10)
        player_conistency = np.std([col.get('points') for col in gls])

        points_against_pace = points_against_similar_teams(
            stats.get_teams_with_similar_pace(stats.TEAM_NAME_PACE.get(opp)),
            gls)
        if points_against_pace is None:
            continue

        points_against_def = points_against_similar_teams(
            stats.get_teams_with_similar_def(stats.DEF_RTG.get(opp)), gls)
        if points_against_def is None:
            continue

        if eff_fg_per is None or eff_fg_per == 0:
            print(f"{prop.get('player_name')} eff fg = 0")
            continue

        data.append({
            "total_pace": points_against_pace,
            "conistency": player_conistency,
            "recent_per": recent_performance,
            "opp_def_rtg": points_against_def,
            'eff_shot_per': eff_fg_per,
            'alt_line': over,
            'alt_hit': over_hit
        })
    return pd.DataFrame(data)


def create_logistic_regression_pipe():
    """
        Creates logistic regression pipeline
    """
    df = build_test_data_frame()
    print(df.shape[0])
    print(df.describe())
    # printing the result
    x = np.array(df.loc[:, df.columns != 'alt_hit'])
    y = np.array(df['alt_hit'])
    print("training model")
    X_train, X_test, y_train, y_test = train_test_split(x,
                                                        y,
                                                        test_size=0.20,
                                                        random_state=40)
    pipe = make_pipeline(
        StandardScaler(),
        LogisticRegressionCV(
            cv=5,
            random_state=0,
            scoring="recall",
            # scoring="average_precision",
            # solver="liblinear",
            class_weight='balanced',
            verbose=0))
    pipe.fit(X_train, y_train)
    print(pipe.score(X_test, y_test))
    print(classification_report(pipe.predict(X_test), y_test))
    print(roc_auc_score(pipe.predict(X_test), y_test))
    return pipe


def create_random_forest():
    """
        Creates logistic regression pipeline
    """
    df = build_test_data_frame()
    print(df.shape[0])
    print(df.describe())
    # printing the result
    x = np.array(df.loc[:, df.columns != 'alt_hit'])
    y = np.array(df['alt_hit'])
    print("training model")
    X_train, X_test, y_train, y_test = train_test_split(x,
                                                        y,
                                                        test_size=0.20,
                                                        random_state=40)
    pipe = make_pipeline(StandardScaler(),
                         RandomForestClassifier(
                             max_depth=3,
                             random_state=0,
                         ))
    pipe.fit(X_train, y_train)
    print(pipe.score(X_test, y_test))
    correct_over = 0
    # print(f"correct over x {correct_over / total}")
    print(classification_report(pipe.predict(X_test), y_test))
    print(roc_auc_score(pipe.predict(X_test), y_test))
    # print(np.mean(avg_vs_opp_diff))
    return pipe


def per_to_american_odds(proba):
    proba = proba * 100
    if proba < 50:
        return '+{:.0f}'.format((100 / (proba / 100)))
    else:
        return '{:.0f}'.format((proba / (1 - (proba / 100))) * -1)


def get_alt_line_proba(prop, pipeline, alt_line):
    """
        Return (class, probability)
    """
    team_name = convert_team_name(prop.get('team_name'))
    player_name = prop.get('player_name')
    opp = convert_team_name(prop.get('opp_name'))

    gls = sqllite_utils.get_player_gls(player_name, constants.NBA_CURR_SEASON,
                                       team_name, DB_CON)
    if gls is None:
        print(f"couldn't find: {player_name}+{team_name}")
        return None

    prop_date_arr = prop.get('prop_scraped').split('-')
    prop_date = date(int(prop_date_arr[2]), int(prop_date_arr[0]),
                     int(prop_date_arr[1]))

    over = prop.get('alt_line')
    over_hit = prop.get('alt_hit')
    eff_fg_per = stats.calculate_eff_fg_per(gls)
    recent_performance = stats.point_avg_last_nth_games(gls, prop_date, 10)
    player_conistency = np.std([col.get('points') for col in gls])

    points_against_pace = points_against_similar_teams(
        stats.get_teams_with_similar_pace(stats.TEAM_NAME_PACE.get(opp)), gls)
    if points_against_pace is None:
        return None

    points_against_def = points_against_similar_teams(
        stats.get_teams_with_similar_def(stats.DEF_RTG.get(opp)), gls)
    if points_against_def is None:
        return None

    if eff_fg_per is None or eff_fg_per == 0:
        print(f"{prop.get('player_name')} eff fg = 0")
        return None

    data = [{
        "total_pace": points_against_pace,
        "conistency": player_conistency,
        "recent_per": recent_performance,
        "opp_def_rtg": points_against_def,
        'eff_shot_per': eff_fg_per,
        'alt_line': alt_line
    }]
    df = pd.DataFrame(data)
    # print(df.describe())
    proba = pipeline.predict_proba(np.array(df).reshape(1, -1))[0, 1]
    if proba < 0.60:
        return ""
    proba_str = "{:.1f}".format(proba * 100)
    return f"{proba_str}% or {per_to_american_odds(proba)}"


# create_random_forest()
