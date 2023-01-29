r"""
  Caclulate projections based on player stats..
"""

import re
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
from datetime import date

from player_stats import sqllite_utils
from player_stats import constants

SCORE_REGEX = re.compile(r"^[WLT]{1}(\d+)[\-]{1}(\d+).*?$")
OPP_REGEX = re.compile(r"^(@|vs)(\w+)$")
DB_CON = sqllite_utils.get_db_in_mem()
NAME_LINK_REGEX = re.compile(r"^.*?/name/(\w+)/(.*?)$", re.IGNORECASE)
RESULT_REGEX = re.compile(r"^(W|L)(\d{2,3})-(\d{2,3}).*?$")
GL_DATE_REGEX = re.compile(r"^.*?(\d{1,2})/(\d{1,2})$")

TOP_3PT_D = sqllite_utils.get_n_team_stats(12, False, 'opp_scoring',
                                           'three_pt_made', DB_CON)
WORST_3PT_D = sqllite_utils.get_n_team_stats(12, True, 'opp_scoring',
                                             'three_pt_made', DB_CON)

TOP_2PT_D = sqllite_utils.get_n_team_stats(12, False, 'opp_scoring',
                                           'two_pt_made', DB_CON)
WORST_2PT_D = sqllite_utils.get_n_team_stats(12, True, 'opp_scoring',
                                             'two_pt_made', DB_CON)

TOP_DEF_RB_PER = sqllite_utils.get_n_team_stats(12, True, 'nba_adv_stats',
                                                'def_rebound_per', DB_CON)
WORST_DEF_RB_PER = sqllite_utils.get_n_team_stats(12, False, 'nba_adv_stats',
                                                  'def_rebound_per', DB_CON)

TEAM_NAME_PACE = sqllite_utils.get_team_name_and_stat(DB_CON, 'pace',
                                                      'nba_adv_stats')
TEAM_NAME_2PT = sqllite_utils.get_team_name_and_stat(DB_CON, 'two_pt_made',
                                                     'opp_scoring')
TEAM_NAME_3PT = sqllite_utils.get_team_name_and_stat(DB_CON, 'three_pt_made',
                                                     'opp_scoring')
DEF_RTG = sqllite_utils.get_team_name_and_stat(DB_CON, 'def_rtg',
                                               'nba_adv_stats')


def get_2_pt_freq(gls):
    """
        Calculates the averge 2pt frequency
        of a player using past games
    """
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
    """
        Calculates the averge 3pt frequency
        of a player based on past games
    """
    three_atts = 0
    total_atts = 0
    for gl in gls:
        three_atts += (gl.get('three_pt_att'))
        total_atts += (gl.get('fg_att'))
    if total_atts != 0:
        return (three_atts / total_atts) * 100
    return 0


def convert_team_name(team_name):
    """
        Fixes the clippers name
    """
    if constants.ESPN_TEAM_NAME_TO_FD.get(team_name) is None:
        return team_name
    return constants.ESPN_TEAM_NAME_TO_FD.get(team_name)


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
    player_gls = sqllite_utils.get_player_gls(player_name,
                                              constants.NBA_CURR_SEASON,
                                              team_name, DB_CON)
    player_gls.extend(
        sqllite_utils.get_player_gls(player_name, constants.NBA_LAST_SEASON,
                                     team_name, DB_CON))
    gls_no_outliers = remove_outliers_mod(player_gls, 'minutes_played', -2.6,
                                          3, False)

    stats = [x.get(stat_key) for x in gls_no_outliers]

    if len(stats) == 0:
        return None

    return float("{:.1f}".format(np.mean(stats)))


def points_histogram():
    """
        Create Histogram plot of player points
        grabs data from Sqlite3
    """
    all_gls = []
    for player in sqllite_utils.get_unique_player_names(DB_CON):
        all_gls.extend(
            remove_outliers_mod(
                sqllite_utils.get_player_gls(player.get('player_name'),
                                             constants.NBA_CURR_SEASON,
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


# FIXME: not sure if this works
def days_since_last_game(prop_date, gls):
    """
        Calculate the days since last played.
    """
    prop_date_arr = prop_date.split('-')
    prop_date = date(int(prop_date_arr[2]), int(prop_date_arr[0]),
                     int(prop_date_arr[1]))

    # Max days we take into account makes standarization
    # better if we don't allow huge numbers for hurt players
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
    return days


def get_pace_diff(opp, players_team):
    """
        Get the difference between team vs opp pace
    """
    return TEAM_NAME_PACE.get(convert_team_name(opp)) - TEAM_NAME_PACE.get(
        convert_team_name(players_team))
