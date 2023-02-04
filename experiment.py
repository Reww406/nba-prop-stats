from datetime import date
import re

from matplotlib import pyplot as plt
import numpy as np

from player_stats import stats
from player_stats import sqllite_utils
from player_stats import constants

DB_CONN = sqllite_utils.get_conn()
NAME_LINK_REGEX = re.compile(r"^.*?/name/(\w+)/(.*?)$", re.IGNORECASE)

PACE_RATINGS = sqllite_utils.get_team_name_and_stat(DB_CONN, 'pace',
                                                    'nba_adv_stats')
TOP_2PT_D = sqllite_utils.get_team_name_and_stat(DB_CONN, 'two_pt_made',
                                                 'opp_scoring')
TOP_3PT_D = sqllite_utils.get_team_name_and_stat(DB_CONN, 'three_pt_made',
                                                 'opp_scoring')
TOP_DEF_RTG = sqllite_utils.get_team_name_and_stat(DB_CONN, 'def_rtg',
                                                   'nba_adv_stats')
TOP_DEF_RB_PER = sqllite_utils.get_team_name_and_stat(DB_CONN,
                                                      'def_rebound_per',
                                                      'nba_adv_stats')
TOP_OFF_RB_PER = sqllite_utils.get_n_team_stats(30, True, 'nba_adv_stats',
                                                'off_rebound_per', DB_CONN)

OPP_REGEX = re.compile(r"^(@|vs)(\w+)$")
RESULT_REGEX = re.compile(r"^(W|L)(\d{2,3})-(\d{2,3}).*?$")


def _get_pace_diff(opp, players_team):
    # print(f"{opp} : {players_team}")
    return PACE_RATINGS.get(opp) - PACE_RATINGS.get(players_team)


def convert_team_name(team_name):
    """
        Fixes the clippers name
    """
    if constants.ESPN_TEAM_NAME_TO_FD.get(team_name) is None:
        return team_name
    return constants.ESPN_TEAM_NAME_TO_FD.get(team_name)


def _corr(y, x, y_name, x_name, player_name):
    plt.scatter(x, y, c="blue")
    plt.title(player_name)
    plt.xlabel(x_name)
    plt.ylabel(y_name)
    # plt.show()
    # To show the plot
    return np.corrcoef(x, y)


GL_DATE_REGEX = re.compile(r"^.*?(\d{1,2})/(\d{1,2})$")


def days_since_this_game(this_game, gls, player_name):
    #12-19-2022
    this_game_match = GL_DATE_REGEX.match(this_game.get('game_date'))
    this_game_year = 2022
    if this_game_match.group(1) == '1':
        this_game_year = 2023
    this_game_date = date(this_game_year, int(this_game_match.group(1)),
                          int(this_game_match.group(2)))

    # print(f"This games date: {this_game_date}")
    #Fri 12/16
    days = 4
    g_date = None
    for gl in gls:
        game_date_match = GL_DATE_REGEX.match(gl.get('game_date'))
        this_game_year = 2022
        if game_date_match.group(1) == '1':
            this_game_year = 2023
        game_date = date(this_game_year, int(game_date_match.group(1)),
                         int(game_date_match.group(2)))
        delta = this_game_date - game_date
        if int(delta.days) < days and this_game_date != game_date and int(
                delta.days) > 0:
            days = int(delta.days)
            g_date = game_date
    # print(f"Game data: {g_date}")
    # print(f'Its been {days} since {player_name} the last game')
    return days


def store_correlations():
    """_summary_
    """
    unqiue_players = sqllite_utils.get_unique_player_and_team(DB_CONN)
    for player in unqiue_players:
        player_gls = sqllite_utils.get_player_gls(player.get('player_name'),
                                                  constants.NBA_CURR_SEASON,
                                                  player.get('team_name'),
                                                  DB_CONN)

        # player_gls = stats._remove_outliers_mod(player_gls, 'minutes_played',
        #                                         -2.5, 3, False)

        if len(player_gls) == 1:
            continue

        points = [gl.get('points') for gl in player_gls]

        player_name = player.get('player_name')
        opps = [
            constants.INT_TO_TEAM_NAME.get(
                OPP_REGEX.match(gl.get('opp')).group(2)) for gl in player_gls
        ]
        pace_corr = _corr(points, [
            _get_pace_diff(opp, convert_team_name(player.get('team_name')))
            for opp in opps
        ], 'points', 'pace', player_name)

        rest_corr = _corr(points, [
            days_since_this_game(gl, player_gls, player_name)
            for gl in player_gls
        ], 'points', 'rest_corr', player_name)

        two_pt_corr = _corr(points, [TOP_2PT_D.get(opp) for opp in opps],
                            'points', 'top_2pt', player_name)
        three_pt_corr = _corr(points, [TOP_3PT_D.get(opp) for opp in opps],
                              'points', 'top_3pt', player_name)
        def_rtg_corr = _corr(points, [TOP_DEF_RTG.get(opp) for opp in opps],
                             'points', 'def_rtg', player_name)
        def_rb_corr = _corr(points, [TOP_DEF_RB_PER.get(opp) for opp in opps],
                            'points', 'def_rb', player_name)
        off_rb_corr = _corr(points,
                            [TOP_OFF_RB_PER.index(opp) for opp in opps],
                            'points', 'off_rb', player_name)
        totals = []
        for gl in player_gls:
            result_match = RESULT_REGEX.match(gl.get('result'))
            scores = [int(result_match.group(2)), int(result_match.group(3))]
            totals.append(scores[0] + scores[1])

        totals_corr = _corr(points, totals, 'points', 'totals', player_name)

        if len(points) <= 4:
            correlations = {
                'player_name': player.get('player_name'),
                'team_name': player.get('team_name'),
                'pace_corr': 0,
                'two_pt_corr': 0,
                'three_pt_corr': 0,
                'opp_deff_rtg_corr': 0,
                'opp_def_rb_per_corr': 0,
                'opp_off_rb_per_corr': 0,
                'total_corr': 0,
                'rest_corr': 0
            }
        else:
            correlations = {
                'player_name': player.get('player_name'),
                'team_name': player.get('team_name'),
                'pace_corr': float("{:.3f}".format(pace_corr[0][1])),
                'two_pt_corr': float("{:.3f}".format(two_pt_corr[0][1])),
                'three_pt_corr': float("{:.3f}".format(three_pt_corr[0][1])),
                'opp_deff_rtg_corr':
                float("{:.3f}".format(def_rtg_corr[0][1])),
                'opp_def_rb_per_corr':
                float("{:.3f}".format(def_rb_corr[0][1])),
                'opp_off_rb_per_corr':
                float("{:.3f}".format(off_rb_corr[0][1])),
                'total_corr': float("{:.3f}".format(totals_corr[0][1])),
                "rest_corr": float("{:.3f}".format(rest_corr[0][1]))
            }

        sqllite_utils.insert_correlations(correlations, DB_CONN)


def three_point_freq():
    """
        Three point freq
    """
    unqiue_players = sqllite_utils.get_unique_player_and_team(DB_CONN)
    freqs = []
    for player in unqiue_players:
        player_gls = sqllite_utils.get_player_gls(player.get('player_name'),
                                                  constants.NBA_CURR_SEASON,
                                                  player.get('team_name'),
                                                  DB_CONN)
        freqs.append(stats.get_3_pt_freq(player_gls))

    print(freqs)
    print(np.mean(freqs))


# create_3pt_gam()

store_correlations()
print(
    f"Pace: {np.mean(sqllite_utils.get_array_of_correlations('pace_corr', DB_CONN))}"
)
print(
    f"two_pt_corr: {np.mean(sqllite_utils.get_array_of_correlations('two_pt_corr', DB_CONN))}"
)
print(
    f"three_pt_corr: {np.mean(sqllite_utils.get_array_of_correlations('three_pt_corr', DB_CONN))}"
)
print(
    f"opp_deff_rtg_corr: {np.mean(sqllite_utils.get_array_of_correlations('opp_deff_rtg_corr', DB_CONN))}"
)
print(
    f"opp_def_rb_per_corr: {np.mean(sqllite_utils.get_array_of_correlations('opp_def_rb_per_corr', DB_CONN))}"
)
print(
    f"opp_off_rb_per_corr: {np.mean(sqllite_utils.get_array_of_correlations('opp_off_rb_per_corr', DB_CONN))}"
)
print(
    f"total_corr: {np.mean(sqllite_utils.get_array_of_correlations('total_corr', DB_CONN))}"
)
print(
    f"rest_corr: {np.mean(sqllite_utils.get_array_of_correlations('rest_corr', DB_CONN))}"
)
