r"""
  Caclulate projections based on player stats..
"""

import re
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd

from player_stats import scraper, sqllite_utils

from pygam import GAM, GammaGAM, LinearGAM, LogisticGAM, s, f, te, l

from sklearn.model_selection import train_test_split

SCORE_REGEX = re.compile(r"^[WLT]{1}(\d+)[\-]{1}(\d+).*?$")
OPP_REGEX = re.compile(r"^(@|vs)(\w+)$")
DB_CON = sqllite_utils.get_db_in_mem()
NBA_SEASON_KEY = '2022-23'
NAME_LINK_REGEX = re.compile(r"^.*?/name/(\w+)/(.*?)$", re.IGNORECASE)
RESULT_REGEX = re.compile(r"^(W|L)(\d{2,3})-(\d{2,3}).*?$")
# top pace
TOP_PACE = sqllite_utils.get_n_pace(5, True, DB_CON)
WORST_PACE = sqllite_utils.get_n_pace(5, False, DB_CON)
# bottom pac
TOP_D = sqllite_utils.get_n_def(4, True, DB_CON)
WORST_D = sqllite_utils.get_n_def(4, False, DB_CON)

TOP_3PT_D = sqllite_utils.get_n_three_d(5, True, DB_CON)
WORST_3PT_D = sqllite_utils.get_n_three_d(5, False, DB_CON)

TOP_2PT_D = sqllite_utils.get_n_two_d(5, True, DB_CON)
WORST_2PT_D = sqllite_utils.get_n_two_d(5, False, DB_CON)

TOP_DEF_RB_PER = sqllite_utils.get_n_deff_rb(5, True, DB_CON)
WORST_DEF_RB_PER = sqllite_utils.get_n_deff_rb(5, False, DB_CON)

ALL_PACE = sqllite_utils.get_n_pace(30, False, DB_CON)
ALL_2PT_D = sqllite_utils.get_n_two_d(30, True, DB_CON)
ALL_3PT_D = sqllite_utils.get_n_three_d(30, True, DB_CON)
ALL_DEF_RTG = sqllite_utils.get_n_def(30, True, DB_CON)
ALL_DEF_RB_PER = sqllite_utils.get_n_deff_rb(30, True, DB_CON)
ALL_OFF_RB_PER = sqllite_utils.get_n_off_rb(30, True, DB_CON)

TEAM_NAME_PACE = sqllite_utils.get_team_name_and_pace(DB_CON)
TEAM_NAME_2PT = sqllite_utils.get_team_name_and_2pt_made(DB_CON)
TEAM_NAME_3PT = sqllite_utils.get_team_name_and_3pt_made(DB_CON)
DEF_RTG = sqllite_utils.get_team_name_and_def_rating(DB_CON)


def get_2_pt_freq(gls):
    two_atts = 0
    total_atts = 0
    for gl in gls:
        two_atts += (gl.get('fg_att') - gl.get('three_pt_att'))
        total_atts += (gl.get('fg_att'))
    if total_atts != 0:
        return (two_atts / total_atts) * 100
    return 0


def _remove_outliers_mod(gamelogs, stat_key, lower_bound, upper_bound,
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

    gls_no_outliers = _remove_outliers_mod(gls, 'minutes_played', -2.5, 3,
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
    gls_no_outliers = _remove_outliers_mod(player_gls, 'minutes_played', -2.6,
                                           3, False)

    stats = [x.get(stat_key) for x in gls_no_outliers]
    return float("{:.1f}".format(np.mean(stats)))


def points_histogram():
    all_gls = []
    for player in sqllite_utils.get_unique_player_names(DB_CON):
        all_gls.extend(
            _remove_outliers_mod(
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

    corr = min(corr, 0.8)
    if flip_sign:
        corr = corr * -1
    return corr * 25


def _get_player_weights(player_name, team_name, points_mean):
    weights = {}

    weights['high_pace_w'] = per_of_proj(
        _get_weights('pace_corr', False, player_name, team_name), points_mean)
    weights['low_pace_w'] = per_of_proj(
        _get_weights('pace_corr', True, player_name, team_name), points_mean)

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
        _get_weights('opp_def_rb_per_corr', True, player_name, team_name),
        points_mean)
    weights['worst_def_rb_perr_weight'] = per_of_proj(
        _get_weights('opp_def_rb_per_corr', False, player_name, team_name),
        points_mean)
    return weights


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

    gls_no_outliers = _remove_outliers_mod(gls, 'minutes_played', -2.5, 3,
                                           False)

    points = [x.get('points') for x in gls_no_outliers]
    points_mean = np.mean(points)

    opp = prop_dict.get('opp_name')

    three_point_shooter = get_3_pt_freq(gls_no_outliers) >= 50
    two_point_shooter = get_2_pt_freq(gls_no_outliers) >= 60

    # print(f"Mean before modifyer {points_mean}")

    weights = _get_player_weights(prop_dict.get('player_name'),
                                  prop_dict.get('team_name'), points_mean)

    if opp in WORST_PACE:
        # print(f"{opp} worst pace {weights['low_pace_w']}")
        points_mean += weights['low_pace_w']
    elif opp in TOP_PACE:
        # print(f"{opp} top pace {weights['high_pace_w']}")
        points_mean += weights['high_pace_w']

    if three_point_shooter:
        if opp in TOP_3PT_D:
            # print(f'3PT shooter agasint 3PT Top D {weights["top_3pt_def_w"]}')
            points_mean += weights["top_3pt_def_w"]
        if opp in WORST_3PT_D:
            # print(
            #     f'3PT Shooter agasint 3PT Worst D {weights["worst_3pt_def_w"]}'
            # )
            points_mean += weights["worst_3pt_def_w"]
    elif two_point_shooter:
        if opp in TOP_2PT_D:
            # print(f'2PT Shooter agasint 2PT Top D {weights["top_2pt_def"]}')
            points_mean += weights["top_2pt_def"]
        if opp in WORST_2PT_D:
            # print(
            # f'2PT Shooter agasint 2PT Worst D {weights["worst_2pt_def"]}')
            points_mean += weights["worst_2pt_def"]

    # Big lead probably sitting..
    if prop_dict.get("team_spread") <= -10:
        # print(
        #     f"Big fav {prop_dict.get('team_spread')} {weights['big_fav_weight']}"
        # )
        points_mean += weights['big_fav_weight']

    if prop_dict.get('game_total') > 228:
        # print(f"High scoring game {weights['high_total_weight']}")
        points_mean += weights['high_total_weight']

    if prop_dict.get('game_total') < 216:
        # print(f"Low scoring game {weights['low_total_weight']}")
        points_mean += weights['low_total_weight']

    if opp in WORST_DEF_RB_PER:
        # print(f'Worst Def rb percentage {weights["worst_def_rb_perr_weight"]}')
        points_mean += weights["worst_def_rb_perr_weight"]

    if opp in TOP_DEF_RB_PER:
        # print(f'Top Def rb percentage {weights["top_def_rb_perr_weight"]}')
        points_mean += weights["top_def_rb_perr_weight"]

    # print(f"Mean after modifyer: {points_mean}")

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
