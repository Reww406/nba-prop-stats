r"""
  Caclulate projections based on player stats..
"""

import re
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
from datetime import date

from player_stats import sqllite_utils

SCORE_REGEX = re.compile(r"^[WLT]{1}(\d+)[\-]{1}(\d+).*?$")
OPP_REGEX = re.compile(r"^(@|vs)(\w+)$")
DB_CON = sqllite_utils.get_db_in_mem()
NBA_SEASON_KEY = '2022-23'
NAME_LINK_REGEX = re.compile(r"^.*?/name/(\w+)/(.*?)$", re.IGNORECASE)
RESULT_REGEX = re.compile(r"^(W|L)(\d{2,3})-(\d{2,3}).*?$")

# bottom pac
TOP_D = sqllite_utils.get_n_def(8, True, DB_CON)
# print(TOP_D)
WORST_D = sqllite_utils.get_n_def(8, False, DB_CON)
# print(WORST_D)

TOP_3PT_D = sqllite_utils.get_n_three_d(12, True, DB_CON)
WORST_3PT_D = sqllite_utils.get_n_three_d(12, False, DB_CON)

TOP_2PT_D = sqllite_utils.get_n_two_d(12, True, DB_CON)
WORST_2PT_D = sqllite_utils.get_n_two_d(12, False, DB_CON)

TOP_DEF_RB_PER = sqllite_utils.get_n_deff_rb(10, True, DB_CON)
WORST_DEF_RB_PER = sqllite_utils.get_n_deff_rb(10, False, DB_CON)

TEAM_NAME_PACE = sqllite_utils.get_team_name_and_stat(DB_CON, 'pace', 'nba_adv_stats')
TEAM_NAME_2PT = sqllite_utils.get_team_name_and_stat(DB_CON, 'two_point_made', 'opp_scoring')
TEAM_NAME_3PT = sqllite_utils.get_team_name_and_stat(DB_CON, 'three_point_made', 'opp_scoring')
DEF_RTG = sqllite_utils.get_team_name_and_stat(DB_CON, 'def_rtg', 'nba_adv_stats')


def get_2_pt_freq(gls):
    two_atts = 0
    total_atts = 0
    for gl in gls:
        two_atts += (gl.get('fg_att') - gl.get('three_pt_att'))
        total_atts += (gl.get('fg_att'))
    if total_atts != 0:
        return (two_atts / total_atts) * 100
    return 0


def remove_outliers_mod(gamelogs, stat_key, lower_bound, upper_bound,
                        print_results):
    r"""
        :param stat_key = YDS, ATT, CMP, REC
        :param sec_key = Passing, Rushing or Recieving
        :param gamelogs = the players game logs
        Removes values X signma away from the mean.
        year: [stats]
    """
    values = [x.get(stat_key) for x in gamelogs]
    values = np.array(values)
    if len(values) <= 1:
        # Can't get mean if it's one stat...
        return values
    median = np.median(values)
    deviation_from_med = values - median
    mad = np.median(np.abs(deviation_from_med))
    outliers_removed = []
    for gl in gamelogs:
        stat = gl.get(stat_key)
        if mad != 0.0:
            mod_zscore = 0.6745 * (stat - median) / mad
            # print(mod_zscore)
            if mod_zscore < lower_bound or mod_zscore > upper_bound:
                if print_results:
                    print(
                        f"Removing outlier {stat_key}: {stat} for {gl.get('player_name')}"
                    )
                pass
            else:
                outliers_removed.append(gl)
        else:
            outliers_removed.append(gl)
    return outliers_removed


def get_3_pt_freq(gls):
    three_atts = 0
    total_atts = 0
    for gl in gls:
        three_atts += (gl.get('three_pt_att'))
        total_atts += (gl.get('fg_att'))
    if total_atts != 0:
        return (three_atts / total_atts) * 100
    return 0


ESPN_TEAM_NAME_TO_FD = {'los-angeles-clippers': 'la-clippers'}


def convert_team_name(team_name):
    """
        Fixes the clippers name
    """
    if ESPN_TEAM_NAME_TO_FD.get(team_name) is None:
        return team_name
    return ESPN_TEAM_NAME_TO_FD.get(team_name)


# IF total = 0 it was locked
# Spread and total
def get_points_ats(prop_dict):
    """
        Return [over, under] percentages
    """

    # player_name, over_num, team_spread, total, team_name
    gls = sqllite_utils.get_player_gls(
        prop_dict.get('player_name'), prop_dict.get('season'),
        convert_team_name(prop_dict.get('team_name')), DB_CON)

    gls_no_outliers = remove_outliers_mod(gls, 'minutes_played', -2.5, 3,
                                          False)

    over_odds = 0.0

    total = len(gls_no_outliers)
    for game in gls_no_outliers:
        if game.get('points') >= prop_dict.get('over_num'):
            over_odds += 1.0

    if total > 0:
        over = (over_odds / total) * 100
    else:
        over = 0

    if total > 0:
        return "{:.1f}%".format(over)

    return 0


def create_int_to_team_name(team_urls):
    r"""
        Creates dict with team_name : initial
    """
    team_name_to_int = {}
    for url in team_urls:
        match = NAME_LINK_REGEX.match(url.strip())
        team_name_to_int[match.group(1).upper()] = match.group(2)
    return team_name_to_int


def get_stat_mean_for_player(player_name, team_name, stat_key):
    """
    get mean of stat
    """
    player_gls = sqllite_utils.get_player_gls(player_name, NBA_SEASON_KEY,
                                              team_name, DB_CON)
    gls_no_outliers = remove_outliers_mod(player_gls, 'minutes_played', -2.6,
                                          3, False)

    stats = [x.get(stat_key) for x in gls_no_outliers]
    return float("{:.1f}".format(np.mean(stats)))


def points_histogram():
    all_gls = []
    for player in sqllite_utils.get_unique_player_names(DB_CON):
        all_gls.extend(
            remove_outliers_mod(
                sqllite_utils.get_player_gls(player.get('player_name'),
                                             NBA_SEASON_KEY,
                                             player.get('team_name'), DB_CON),
                'minutes_played', -2.6, 3, False))

    bins = np.array(range(0, 41))
    count = np.zeros(41)
    for gl in all_gls:
        points = gl.get("points")
        if points <= 40:
            count[points] += 1
    count[0] = 0
    print(f"{len(bins.shape)}\n{len(count.shape)}")
    plt.hist(bins, 61, weights=count)
    plt.show()


def _get_weights(stat_key, flip_sign, player_name, team_name):
    corr = sqllite_utils.get_player_correlations(player_name,
                                                 convert_team_name(team_name),
                                                 DB_CON).get(stat_key)
    if flip_sign:
        corr = corr * -1
    return corr * 28


def _get_player_weights(player_name, team_name, points_mean):
    weights = {}

    weights['faster_diff'] = per_of_proj(
        _get_weights('pace_corr', False, player_name, team_name), points_mean)
    weights['slower_diff'] = per_of_proj(
        _get_weights('pace_corr', True, player_name, team_name), points_mean)

    weights['rested'] = per_of_proj(
        _get_weights('rest_corr', False, player_name, team_name), points_mean)
    weights['no_rest'] = per_of_proj(
        _get_weights('rest_corr', True, player_name, team_name), points_mean)

    weights['top_3pt_def_w'] = per_of_proj(
        _get_weights('three_pt_corr', True, player_name, team_name),
        points_mean)
    weights['worst_3pt_def_w'] = per_of_proj(
        _get_weights('three_pt_corr', False, player_name, team_name),
        points_mean)

    weights['top_2pt_def'] = per_of_proj(
        _get_weights('two_pt_corr', True, player_name, team_name), points_mean)
    weights['worst_2pt_def'] = per_of_proj(
        _get_weights('two_pt_corr', False, player_name, team_name),
        points_mean)

    weights['big_fav_weight'] = per_of_proj(-8, points_mean)

    weights['high_total_weight'] = per_of_proj(
        _get_weights('total_corr', False, player_name, team_name), points_mean)
    weights['low_total_weight'] = per_of_proj(
        _get_weights('total_corr', True, player_name, team_name), points_mean)

    weights['top_def_rb_perr_weight'] = per_of_proj(
        _get_weights('opp_def_rb_per_corr', False, player_name, team_name),
        points_mean)
    weights['worst_def_rb_perr_weight'] = per_of_proj(
        _get_weights('opp_def_rb_per_corr', True, player_name, team_name),
        points_mean)
    return weights


GL_DATE_REGEX = re.compile(r"^.*?(\d{1,2})/(\d{1,2})$")


def days_since_last_game(prop_date, gls, player_name):
    #12-19-2022
    prop_date_arr = prop_date.split('-')
    prop_date = date(int(prop_date_arr[2]), int(prop_date_arr[0]),
                     int(prop_date_arr[1]))
    # print(f"prop date {prop_date}")
    #Fri 12/16
    days = 15
    g_date = None
    for gl in gls:
        game_date_match = GL_DATE_REGEX.match(gl.get('game_date'))
        year = 2022
        if game_date_match.group(1) == '1':
            year = 2023
        game_date = date(year, int(game_date_match.group(1)),
                         int(game_date_match.group(2)))
        delta = prop_date - game_date
        if int(delta.days) < days and prop_date != game_date and int(
                delta.days) > 0:
            days = int(delta.days)
            g_date = game_date
    # print(f"Game data: {g_date}")
    # print(f'Its been {days} since {player_name} the last game')
    return days


def get_pace_diff(opp, players_team):
    # print(f"{opp} : {players_team}")
    return TN_PACE.get(convert_team_name(opp)) - TN_PACE.get(
        convert_team_name(players_team))


# IF total = 0 it was locked
# Spread and total
def get_points_proj(prop_dict):
    """
        Return [over, under] percentages
    """
    # print(f"Processing: {prop_dict.get('player_name')}")

    gls = sqllite_utils.get_player_gls(
        prop_dict.get('player_name'), prop_dict.get('season'),
        convert_team_name(prop_dict.get('team_name')), DB_CON)

    gls_no_outliers = remove_outliers_mod(gls, 'minutes_played', -2.5, 3,
                                          False)

    rest_days = days_since_last_game(prop_dict.get('prop_scraped'), gls,
                                     prop_dict.get('player_name'))

    points = [x.get('points') for x in gls_no_outliers]
    points_mean = np.mean(points)

    opp = convert_team_name(prop_dict.get('opp_name'))

    three_point_shooter = get_3_pt_freq(gls_no_outliers) >= 50
    two_point_shooter = get_2_pt_freq(gls_no_outliers) >= 52

    weights = _get_player_weights(prop_dict.get('player_name'),
                                  prop_dict.get('team_name'), points_mean)

    pace_diff = get_pace_diff(opp, prop_dict.get('team_name'))

    if pace_diff > 2:
        points_mean += weights['faster_diff'] / 2
    if pace_diff < -2:
        points_mean += weights['slower_diff'] / 2

    if three_point_shooter:
        if opp in TOP_3PT_D:
            points_mean += weights["top_3pt_def_w"]
        if opp in WORST_3PT_D:
            points_mean += weights["worst_3pt_def_w"]
    if two_point_shooter:
        if opp in TOP_2PT_D:
            points_mean += weights["top_2pt_def"]
        if opp in WORST_2PT_D:
            points_mean += weights["worst_2pt_def"]

    # Worse score with this added..
    # # Big lead probably sitting..
    # if prop_dict.get("team_spread") <= -9.5:
    #     points_mean += weights['big_fav_weight']

    # if prop_dict.get('team_spread') >= 9.5:
    #     points_mean += weights['big_fav_weight']

    if prop_dict.get('game_total') > 230:
        points_mean += weights['high_total_weight']

    if prop_dict.get('game_total') < 216:
        points_mean += weights['low_total_weight']

    if opp in WORST_DEF_RB_PER:
        points_mean += weights["worst_def_rb_perr_weight"]

    if opp in TOP_DEF_RB_PER:
        points_mean += weights["top_def_rb_perr_weight"]

    if rest_days <= 1:
        points_mean += weights["no_rest"]

    if rest_days >= 3:
        points_mean += weights["rested"]

    return format_proj(points_mean)


def format_proj(projection) -> str():
    r"""
      Create project string for file
    """
    return "{:.1f}".format(projection)


def per_of_proj(weight, proj):
    """
        Get percentage of proj based on weight
    """
    return proj * (float(weight) / 100.00)
