from datetime import date
import re
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
from sklearn import metrics
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression, LogisticRegressionCV
from sklearn.metrics import classification_report, precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from player_stats import stats
from player_stats import sqllite_utils
from player_stats import scraper

DB_CON = sqllite_utils.get_conn()
NBA_SEASON_KEY = '2022-23'
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


def create_team_name_to_int(team_urls):
    r"""
        Creates dict with team_name : initial
    """
    team_name_to_int = {}
    for url in team_urls:
        match = NAME_LINK_REGEX.match(url.strip())
        team_name_to_int[match.group(2)] = match.group(1).upper()
    return team_name_to_int


TEAM_NAME_TO_INT = create_team_name_to_int(scraper.TEAMS)


def _get_pace_diff(opp, players_team):
    # print(f"{opp} : {players_team}")
    return TN_PACE.get(opp) - TN_PACE.get(players_team)


ESPN_TEAM_NAME_TO_FD = {'los-angeles-clippers': 'la-clippers'}


def convert_team_name(team_name):
    """
        Fixes the clippers name
    """
    if ESPN_TEAM_NAME_TO_FD.get(team_name) is None:
        return team_name
    return ESPN_TEAM_NAME_TO_FD.get(team_name)


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
            date, DB_CON)

        if game_log is None:
            continue

        if game_log.get('minutes_played') < 5:
            continue

        if game_log.get('points') > prop.get('over_num'):
            prop['over_hit'] = 1
            props_with_result.append(prop)
        else:
            prop['over_hit'] = 0
            props_with_result.append(prop)
    return props_with_result


def get_per_over(props):
    total = len(props)
    over_hit = len([prop for prop in props if prop.get('over_hit') == 1])
    # for prop in props:
    #     print(f"{prop}\n")
    print(f"{(over_hit / total)}")
    # print(total)


def same_date(prop_date, game_date):
    #12-19-2022
    prop_date_arr = prop_date.split('-')
    prop_date = date(int(prop_date_arr[2]), int(prop_date_arr[0]),
                     int(prop_date_arr[1]))
    # print(f"prop date {prop_date}")
    #Fri 12/16
    game_date_match = GL_DATE_REGEX.match(game_date)
    year = 2022
    if game_date_match.group(1) == '1':
        year = 2023
    game_date = date(year, int(game_date_match.group(1)),
                     int(game_date_match.group(2)))
    return prop_date == game_date


def get_past_performance(prop):
    match = convert_team_name(prop.get('opp_name'))
    opp = TEAM_NAME_TO_INT.get(match)

    games_vs_opp = sqllite_utils.get_player_games_vs_opp(
        prop.get('player_name'), prop.get('season'),
        convert_team_name(prop.get('team_name')), opp, DB_CON)

    filtered_games = []
    for game in games_vs_opp:
        if not same_date(prop.get('prop_scraped'), game.get('game_date')):
            filtered_games.append(game)
        # else:
        #     print(f"{prop.get('prop_scraped')} and {game.get('game_date')}")

    if len(filtered_games) == 0:
        # print("Filtered is zero")
        return None

    if len(filtered_games) == 1:
        return games_vs_opp[0].get('points')

    return np.mean([gl.get('points') for gl in filtered_games])


def create_logistic_regression_pipe():
    props = sqllite_utils.get_all_props_for_type('points', DB_CON)
    prop_with_results = add_over_hit(props)
    print(f"Samples: {len(prop_with_results)}")
    avg_vs_opp_diff = []
    get_per_over(prop_with_results)
    data = []
    for prop in prop_with_results:
        gls = sqllite_utils.get_player_gls(
            prop.get('player_name'), prop.get('season'),
            convert_team_name(prop.get('team_name')), DB_CON)

        gls_no_outliers = stats.remove_outliers_mod(gls, 'minutes_played',
                                                    -2.5, 3, False)

        rest_days = stats.days_since_last_game(prop.get('prop_scraped'), gls)
        points_mean = np.mean([x.get('points') for x in gls_no_outliers])
        total = prop.get('game_total')
        opp = convert_team_name(prop.get('opp_name'))
        three_point_shooter = stats.get_3_pt_freq(gls_no_outliers) >= 50
        two_point_shooter = stats.get_2_pt_freq(gls_no_outliers) >= 52
        avg_points_vs_opp = get_past_performance(prop)
        if avg_points_vs_opp is None:
            continue
        three_point_shooter_vs_bad_d = 0
        two_point_shooter_vs_bad_d = 0
        if three_point_shooter and opp in stats.WORST_3PT_D:
            three_point_shooter_vs_bad_d = 1
        if two_point_shooter and opp in stats.WORST_2PT_D:
            two_point_shooter_vs_bad_d = 1

        opp_pace = stats.TEAM_NAME_PACE.get(opp)
        opp_def_rtg = stats.DEF_RTG.get(opp)
        over = prop.get('over_num')
        over_hit = prop.get('over_hit')
        spread = prop.get('team_spread')
        # pace and def were .70
        data.append({
            'pace': opp_pace,
            # "three_point_shooter_vs_bad_d": three_point_shooter_vs_bad_d,
            # "two_point_shooter_vs_bad_d": two_point_shooter_vs_bad_d,
            "opp_def_rtg": opp_def_rtg,
            'total': total,
            # 'rest_days': rest_days,
            'avg_points_vs_opp': avg_points_vs_opp,
            # 'avg_points': points_mean,
            'over': over,
            # 'spread': spread,
            'over_hit': over_hit
        })

    df = pd.DataFrame(data)
    print(df.shape[0])
    # print(df.describe())
    x = np.array(df.loc[:, df.columns != 'over_hit'])
    y = np.array(df['over_hit'])
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
            #  solver="liblinear",
            class_weight='balanced',
            verbose=0))
    pipe.fit(X_train, y_train)
    print(pipe.score(X_test, y_test))
    correct_over = 0
    total = 0
    for x1, y1 in zip(np.array(X_test), np.array(y_test)):
        chance_of_over = pipe.predict_proba(x1.reshape(1, -1))[0, 1]
        if chance_of_over > 0.55:
            total += 1
            if pipe.predict(x1.reshape(1, -1)) == 1 and y1.reshape(1, -1) == 1:
                correct_over += 1
    print(total)
    # print(f"correct over x {correct_over / total}")
    print(classification_report(pipe.predict(X_test), y_test))
    print(roc_auc_score(pipe.predict(X_test), y_test))
    # print(np.mean(avg_vs_opp_diff))
    return pipe


def get_class_proba(prop, pipeline):

    gls = sqllite_utils.get_player_gls(
        prop.get('player_name'), prop.get('season'),
        convert_team_name(prop.get('team_name')), DB_CON)
    gls_no_outliers = stats.remove_outliers_mod(gls, 'minutes_played', -2.5, 3,
                                                False)
    points_mean = np.mean([x.get('points') for x in gls_no_outliers])
    total = prop.get('game_total')
    rest_days = stats.days_since_last_game(prop.get('prop_scraped'), gls,
                                           prop.get('player_name'))
    opp = convert_team_name(prop.get('opp_name'))
    avg_points_vs_opp = get_past_performance(prop)
    if avg_points_vs_opp is None:
        return "Nan"
    opp_pace = stats.TEAM_NAME_PACE.get(opp)
    opp_def_rtg = stats.DEF_RTG.get(opp)
    over = prop.get('over_num')
    spread = prop.get('team_spread')
    data = [{
        'pace': opp_pace,
        # "three_point_shooter_vs_bad_d": three_point_shooter_vs_bad_d,
        # "two_point_shooter_vs_bad_d": two_point_shooter_vs_bad_d,
        "opp_def_rtg": opp_def_rtg,
        'total': total,
        # 'rest_days': rest_days,
        'avg_points_vs_opp': avg_points_vs_opp,
        # 'avg_points': points_mean,
        'over': over
        # 'spread': spread,
    }]
    df = pd.DataFrame(data)
    proba_class = int(pipeline.predict(np.array(df).reshape(1, -1)))
    return '{:.3f}'.format(
        pipeline.predict_proba(np.array(df).reshape(1, -1))[0, proba_class])


def get_over_class(prop, pipeline):

    gls = sqllite_utils.get_player_gls(
        prop.get('player_name'), prop.get('season'),
        convert_team_name(prop.get('team_name')), DB_CON)
    gls_no_outliers = stats.remove_outliers_mod(gls, 'minutes_played', -2.5, 3,
                                                False)
    points_mean = np.mean([x.get('points') for x in gls_no_outliers])
    total = prop.get('game_total')
    rest_days = stats.days_since_last_game(prop.get('prop_scraped'), gls,
                                           prop.get('player_name'))
    opp = convert_team_name(prop.get('opp_name'))
    avg_points_vs_opp = get_past_performance(prop)
    if avg_points_vs_opp is None:
        return "Nan"
    opp_pace = stats.TEAM_NAME_PACE.get(opp)
    opp_def_rtg = stats.DEF_RTG.get(opp)
    over = prop.get('over_num')
    spread = prop.get('team_spread')
    data = [{
        'pace': opp_pace,
        # "three_point_shooter_vs_bad_d": three_point_shooter_vs_bad_d,
        # "two_point_shooter_vs_bad_d": two_point_shooter_vs_bad_d,
        "opp_def_rtg": opp_def_rtg,
        'total': total,
        # 'rest_days': rest_days,
        'avg_points_vs_opp': avg_points_vs_opp,
        # 'avg_points': points_mean,
        'over': over
        # 'spread': spread,
    }]
    df = pd.DataFrame(data)
    over_class = int(pipeline.predict(np.array(df).reshape(1, -1)))
    if over_class == 1:
        return 'Pick Over'
    else:
        return 'Pick Under'


# create_logistic_regression_pipe()
# print(metrics.get_scorer_names)