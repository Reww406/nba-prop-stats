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


def calculate_eff_fg_per(player_name, team_name, season):
    """
        Calculate effective fg percentage
    """
    # (FGM + 0.5 * 3PM) / FGA
    fg_made = sqllite_utils.get_sum_of_stat(player_name, team_name, season,
                                            'fg_made', DB_CON)
    three_pt_made = sqllite_utils.get_sum_of_stat(player_name, team_name,
                                                  season, 'three_pt_made',
                                                  DB_CON)
    fg_att = sqllite_utils.get_sum_of_stat(player_name, team_name, season,
                                           'fg_att', DB_CON)
    # Avoid divide by zero
    if fg_att == 0:
        return 0
    return ((fg_made + 0.5 * three_pt_made) / fg_att)


def calculate_true_shooting_per(player_name, team_name, season):
    """
        Uses true shooting percentage formula
    """
    pts = sqllite_utils.get_sum_of_stat(player_name, team_name, season,
                                        'points', DB_CON)
    fg_att = sqllite_utils.get_sum_of_stat(player_name, team_name, season,
                                           'fg_att', DB_CON)

    ft_att = sqllite_utils.get_sum_of_stat(player_name, team_name, season,
                                           'ft_att', DB_CON)
    if (2 * (fg_att + (0.44 * ft_att))) == 0:
        return 0

    return (pts / (2 * (fg_att + (0.44 * ft_att)))) * 100


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


def _convert_gl_date_to_obj(g_date, season):
    season_splt = season.split('-')
    game_date_match = GL_DATE_REGEX.match(g_date)
    if game_date_match.group(1) == '1':
        year = int(season_splt[0][0:2] + season_splt[1])
    else:
        year = int(season_splt[0])
    return date(year, int(game_date_match.group(1)),
                int(game_date_match.group(2)))


# FIXME needs to take into account current date for test data
def point_avg_last_nth_games(player, team, start_date, nth):
    """
        Gets Averge points of nth last games
    """
    gls = sqllite_utils.get_player_gls(player, constants.NBA_CURR_SEASON, team,
                                       DB_CON)
    gls_with_date = []
    for gl in gls:
        game_date = _convert_gl_date_to_obj(gl.get('game_date'),
                                            constants.NBA_CURR_SEASON)
        if game_date < start_date:
            gl['real_date'] = game_date
            gls_with_date.append(gl)

    sorted_gls = sorted(gls_with_date, key=lambda d: d['real_date'])
    # print(
    #     f"{start_date} - { sorted_gls[-1].get('real_date')} - { sorted_gls[-1].get('points')}"
    # )
    return np.mean([gl.get('points') for gl in sorted_gls[-nth:]])


def create_logistic_regression_pipe():
    """
        Creates logistic regression pipeline
    """
    props = sqllite_utils.get_all_props_for_type('points', DB_CON)
    prop_with_results = add_over_hit(props)
    print(f"Samples: {len(prop_with_results)}")
    get_per_over(prop_with_results)
    data = []
    for prop in prop_with_results:
        team_name = convert_team_name(prop.get('team_name'))
        player_name = prop.get('player_name')
        total = prop.get('game_total')
        opp = convert_team_name(prop.get('opp_name'))
        total_pace = TN_PACE.get(opp) - TN_PACE.get(team_name)
        overs = sqllite_utils.get_all_columns_for_prop('over_num', 'points',
                                                       player_name,
                                                       prop.get('team_name'),
                                                       DB_CON)

        eff_fg_per = calculate_eff_fg_per(player_name, team_name,
                                          prop.get('season'))

        true_shooting_per = calculate_true_shooting_per(
            player_name, team_name, prop.get('season'))

        prop_date_arr = prop.get('prop_scraped').split('-')
        prop_date = date(int(prop_date_arr[2]), int(prop_date_arr[0]),
                         int(prop_date_arr[1]))
        recent_performance = point_avg_last_nth_games(player_name, team_name,
                                                      prop_date, 2)

        player_avg_over = np.mean(overs)
        over_diff = player_avg_over - prop.get('over_num')
        player_conistency = np.std([
            col.get('points') for col in sqllite_utils.get_player_gls(
                player_name, prop.get('season'), team_name, DB_CON)
        ])
        avg_points_vs_opp = get_past_performance(prop)
        if avg_points_vs_opp is None:
            continue

        if eff_fg_per is None or eff_fg_per == 0:
            print(f"{prop.get('player_name')} eff fg = 0")
            continue

        # opp_pace = stats.TEAM_NAME_PACE.get(opp)
        opp_def_rtg = stats.DEF_RTG.get(opp)
        over = prop.get('over_num')
        over_hit = prop.get('over_hit')
        # spread = prop.get('team_spread')
        data.append({
            "total_pace": total_pace,
            "conistency": player_conistency,
            "recent_per": recent_performance,
            "opp_def_rtg": opp_def_rtg,
            # 'total': total,
            # 'eff_shot_per': eff_fg_per,
            'over_diff': over_diff,
            'avg_points': avg_points_vs_opp,
            'over': over,
            'over_hit': over_hit
        })

    df = pd.DataFrame(data)
    print(df.shape[0])
    print(df.describe())
    # printing the result
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
            # solver="liblinear",
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


def get_class_and_proba(prop, pipeline):
    """
        Return (class, probability)
    """
    team_name = convert_team_name(prop.get('team_name'))
    player_name = prop.get('player_name')
    opp = convert_team_name(prop.get('opp_name'))
    overs = sqllite_utils.get_all_columns_for_prop('over_num', 'points',
                                                   player_name,
                                                   prop.get('team_name'),
                                                   DB_CON)

    eff_fg_per = calculate_eff_fg_per(player_name, team_name,
                                      prop.get('season'))

    player_avg_over = np.mean(overs)
    over_diff = player_avg_over - prop.get('over_num')

    player_consistency = np.std([
        col.get('points') for col in sqllite_utils.get_player_gls(
            player_name, prop.get('season'), team_name, DB_CON)
    ])
    avg_points_vs_opp = get_past_performance(prop)
    if avg_points_vs_opp is None:
        return None
    total_pace = TN_PACE.get(opp) - TN_PACE.get(team_name)
    opp_def_rtg = stats.DEF_RTG.get(opp)
    over = prop.get('over_num')

    prop_date_arr = prop.get('prop_scraped').split('-')
    prop_date = date(int(prop_date_arr[2]), int(prop_date_arr[0]),
                     int(prop_date_arr[1]))
    recent_performance = point_avg_last_nth_games(player_name, team_name,
                                                  prop_date, 2)
    data = [{
        "total_pace": total_pace,
        "conistency": player_consistency,
        "recent_per": recent_performance,
        "opp_def_rtg": opp_def_rtg,
        # 'total': total,
        # 'eff_shot_per': eff_fg_per,
        'over_diff': over_diff,
        'avg_points': avg_points_vs_opp,
        'over': over
    }]
    df = pd.DataFrame(data)
    # print(df.describe())
    proba_class = int(pipeline.predict(np.array(df).reshape(1, -1)))
    if proba_class == 1:
        proba_class_name = 'Pick Over'
    else:
        proba_class_name = 'Pick Under'

    proba = '{:.3f}'.format(
        pipeline.predict_proba(np.array(df).reshape(1, -1))[0, proba_class])
    return (proba_class_name, proba)


# print(calculate_eff_fg_per('bradley-beal', 'washington-wizards', '2022-23'))
# print(
#     calculate_true_shooting_per('bradley-beal', 'washington-wizards',
#                                 '2022-23'))
# create_logistic_regression_pipe()
