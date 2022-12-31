import re
import json
import shutil
import time
import matplotlib
from matplotlib import pyplot as plt
import numpy as np
import pandas as pd
import matplotlib.backends.backend_pdf
from pygam import GAM, LinearGAM, s, f, te, l
from sklearn.model_selection import train_test_split

from player_stats import stats
from player_stats import sqllite_utils
from player_stats import scraper

DB_CONN = sqllite_utils.get_conn()
NBA_SEASON_KEY = '2022-23'
NAME_LINK_REGEX = re.compile(r"^.*?/name/(\w+)/(.*?)$", re.IGNORECASE)

PACE_RATINGS = sqllite_utils.get_team_name_and_pace(DB_CONN)
TOP_2PT_D = sqllite_utils.get_team_name_and_2pt_made(DB_CONN)
TOP_3PT_D = sqllite_utils.get_team_name_and_3pt_made(DB_CONN)
TOP_DEF_RTG = sqllite_utils.get_team_name_and_def_rating(DB_CONN)
TOP_DEF_RB_PER = sqllite_utils.get_n_deff_rb(30, True, DB_CONN)
TOP_OFF_RB_PER = sqllite_utils.get_n_off_rb(30, True, DB_CONN)

OPP_REGEX = re.compile(r"^(@|vs)(\w+)$")

RESULT_REGEX = re.compile(r"^(W|L)(\d{2,3})-(\d{2,3}).*?$")


def _get_pace_diff(opp, players_team):
    return PACE_RATINGS.get(opp) - PACE_RATINGS.get(players_team)


# def create_general_gam():
#     """
#         Return [over, under] percentages
#     """
#     all_gls = []
#     for player in sqllite_utils.get_unique_player_names(DB_CON):
#         all_gls.extend(
#             _remove_outliers_mod(
#                 sqllite_utils.get_player_gls(player.get('player_name'),
#                                              NBA_SEASON_KEY,
#                                              player.get('team_name'), DB_CON),
#                 'minutes_played', -2.6, 3, False))
#     print(f"All game logs: {len(all_gls)}")
#     spread_bounds = get_spread_bounds()
#     total_bounds = get_total_bounds()

#     int_to_team_name = create_int_to_team_name(scraper.TEAMS)
#     data = []
#     for gl in all_gls:
#         opp = int_to_team_name.get(OPP_REGEX.match(gl.get('opp')).group(2))
#         player_name = gl.get('player_name')
#         team_name = gl.get('team_name')
#         result_match = RESULT_REGEX.match(gl.get('result'))
#         scores = [int(result_match.group(2)), int(result_match.group(3))]
#         total = normalize(scores[0] + scores[1], total_bounds)
#         pace_diff = TEAM_NAME_PACE.get(team_name) - TEAM_NAME_PACE.get(opp)
#         spread = abs(scores[0] - scores[1])
#         if gl.get('result').find("L") != -1:
#             spread = spread * -1
#         spread = normalize(spread, spread_bounds)
#         input_data = {
#             'points':
#             gl.get('points'),
#             'points_mean':
#             get_stat_mean_for_player(player_name, team_name, 'points'),
#             'pace':
#             pace_diff,
#             'deff_rating':
#             DEF_RTG.get(opp),
#         }
#         data.append(input_data)
#     df = pd.DataFrame(data)
#     print(df.describe())
#     x = df.loc[:, df.columns != 'points']
#     y = df['points']
#     X_train, X_test, y_train, y_test = train_test_split(x,
#                                                         y,
#                                                         random_state=104,
#                                                         test_size=0.01)
#     lams = np.random.rand(250, 3)
#     lams = lams * 3
#     lams = np.exp(lams)

#     gam = LinearGAM(s(0, n_splines=5) + s(1, n_splines=7) + s(2, n_splines=7),
#                     max_iter=200)
#     gam.gridsearch(X_train.values,
#                    y_train.values,
#                    keep_best=True,
#                    return_scores=True,
#                    lam=lams)
#     gam.summary()
#     for i, term in enumerate(gam.terms):
#         if term.isintercept:
#             continue

#         XX = gam.generate_X_grid(term=i)
#         pdep, confi = gam.partial_dependence(term=i, X=XX, width=0.95)

#         plt.figure()
#         plt.plot(XX[:, term.feature], pdep)
#         plt.plot(XX[:, term.feature], confi, c='r', ls='--')
#         plt.title(repr(term))
#         plt.show()

#     # for i in range(1, len(X_test)):
#     #     print(
#     #         f"{gam.predict(X_test.iloc[i].to_numpy().reshape(1,4))} -> {y_test.iloc[i]}"
#     #     )
#     return gam

# def create_2pt_gam():
#     """
#         Return [over, under] percentages
#     """
#     all_gls = []
#     for player in sqllite_utils.get_unique_player_names(DB_CON):
#         all_gls.extend(
#             _remove_outliers_mod(
#                 sqllite_utils.get_player_gls(player.get('player_name'),
#                                              NBA_SEASON_KEY,
#                                              player.get('team_name'), DB_CON),
#                 'minutes_played', -2.6, 3, False))
#     print(f"All game logs: {len(all_gls)}")
#     two_pt_gls = []
#     for gl in all_gls:
#         if get_2_pt_freq([gl]) > 65:
#             two_pt_gls.append(gl)
#     spread_bounds = get_spread_bounds()
#     total_bounds = get_total_bounds()
#     print(f"Two point game logs: {len(two_pt_gls)}")

#     int_to_team_name = create_int_to_team_name(scraper.TEAMS)
#     data = []
#     for gl in two_pt_gls:
#         opp = int_to_team_name.get(OPP_REGEX.match(gl.get('opp')).group(2))
#         player_name = gl.get('player_name')
#         team_name = gl.get('team_name')
#         result_match = RESULT_REGEX.match(gl.get('result'))
#         scores = [int(result_match.group(2)), int(result_match.group(3))]
#         total = normalize(scores[0] + scores[1], total_bounds)
#         pace_diff = TEAM_NAME_PACE.get(team_name) - TEAM_NAME_PACE.get(opp)
#         spread = abs(scores[0] - scores[1])
#         if gl.get('result').find("L") != -1:
#             spread = spread * -1
#         spread = normalize(spread, spread_bounds)
#         input_data = {
#             'points':
#             gl.get('points'),
#             'points_mean':
#             get_stat_mean_for_player(player_name, team_name, 'points'),
#             'pace':
#             pace_diff,
#             'opp_2pt_rank':
#             TEAM_NAME_2PT.get(opp),
#             # 'total':
#             # total
#             # 'spread':
#             # spread
#         }
#         data.append(input_data)
#     df = pd.DataFrame(data)
#     print(df.describe())
#     x = df.loc[:, df.columns != 'points']
#     y = df['points']
#     X_train, X_test, y_train, y_test = train_test_split(x,
#                                                         y,
#                                                         random_state=104,
#                                                         test_size=0.01)
#     lams = np.random.rand(250, 3)
#     lams = lams * 3
#     lams = np.exp(lams)

#     gam = LinearGAM(n_splines=10, max_iter=200)
#     gam.gridsearch(X_train.values,
#                    y_train.values,
#                    keep_best=True,
#                    return_scores=True,
#                    lam=lams)
#     gam.summary()
#     for i, term in enumerate(gam.terms):
#         if term.isintercept:
#             continue

#         XX = gam.generate_X_grid(term=i)
#         pdep, confi = gam.partial_dependence(term=i, X=XX, width=0.95)

#         plt.figure()
#         plt.plot(XX[:, term.feature], pdep)
#         plt.plot(XX[:, term.feature], confi, c='r', ls='--')
#         plt.title(repr(term))
#         plt.show()

#     for i in range(1, len(X_test)):
#         print(
#             f"{gam.predict(X_test.iloc[i].to_numpy().reshape(1,3))} -> {y_test.iloc[i]}"
#         )
#     return gam

# def create_3pt_gam():
#     """
#         Return [over, under] percentages
#     """
#     all_gls = []
#     for player in sqllite_utils.get_unique_player_names(DB_CON):
#         all_gls.extend(
#             _remove_outliers_mod(
#                 sqllite_utils.get_player_gls(player.get('player_name'),
#                                              NBA_SEASON_KEY,
#                                              player.get('team_name'), DB_CON),
#                 'minutes_played', -2.6, 3, False))
#     print(len(all_gls))

#     three_pt_gls = []
#     for gl in all_gls:
#         if get_3_pt_freq([gl]) > 42:
#             three_pt_gls.append(gl)
#     int_to_team_name = create_int_to_team_name(scraper.TEAMS)
#     spread_bounds = get_spread_bounds()
#     total_bounds = get_total_bounds()
#     print(f"three point game log length {len(three_pt_gls)}")
#     data = []
#     print(len(three_pt_gls))
#     for gl in three_pt_gls:
#         opp = int_to_team_name.get(OPP_REGEX.match(gl.get('opp')).group(2))
#         player_name = gl.get('player_name')
#         team_name = gl.get('team_name')
#         result_match = RESULT_REGEX.match(gl.get('result'))
#         scores = [int(result_match.group(2)), int(result_match.group(3))]
#         total = normalize(scores[0] + scores[1], total_bounds)
#         spread = abs(scores[0] - scores[1])
#         if gl.get('result').find("L") != -1:
#             spread = spread * -1
#         spread = normalize(spread, spread_bounds)
#         pace_diff = TEAM_NAME_PACE.get(team_name) - TEAM_NAME_PACE.get(opp)
#         input_data = {
#             'points':
#             gl.get('points'),
#             'points_mean':
#             get_stat_mean_for_player(player_name, team_name, 'points'),
#             'pace':
#             pace_diff,
#             'opp_3pt_rank':
#             TEAM_NAME_3PT.get(opp),
#             # 'total':
#             # total
#             # 'spread':
#             # spread
#         }
#         data.append(input_data)
#     df = pd.DataFrame(data)
#     print(df.describe())
#     x = df.loc[:, df.columns != 'points']
#     y = df['points']
#     X_train, X_test, y_train, y_test = train_test_split(x,
#                                                         y,
#                                                         random_state=104,
#                                                         test_size=0.001)
#     lams = np.random.rand(250, 3)
#     lams = lams * 3
#     lams = np.exp(lams)

#     gam = LinearGAM(n_splines=10, max_iter=200)
#     gam.gridsearch(X_train.values,
#                    y_train.values,
#                    keep_best=True,
#                    return_scores=True,
#                    lam=lams)
#     gam.summary()
#     # for i, term in enumerate(gam.terms):
#     #     if term.isintercept:
#     #         continue

#     #     XX = gam.generate_X_grid(term=i)
#     #     pdep, confi = gam.partial_dependence(term=i, X=XX, width=0.95)

#     #     plt.figure()
#     #     plt.plot(XX[:, term.feature], pdep)
#     #     plt.plot(XX[:, term.feature], confi, c='r', ls='--')
#     #     plt.title(repr(term))
#     #     plt.show()

#     # for i in range(1, len(X_test)):
#     #     print(
#     #         f"{gam.predict(X_test.iloc[i].to_numpy().reshape(1,5))} -> {y_test.iloc[i]}"
#     #     )
#     return gam

# def normalize(x, bounds):
#     return float("{:.1f}".format(
#         bounds['desired']['lower'] + (x - bounds['actual']['lower']) *
#         (bounds['desired']['upper'] - bounds['desired']['lower']) /
#         (bounds['actual']['upper'] - bounds['actual']['lower'])))

# def get_spread_bounds():
#     all_gls = sqllite_utils.get_unqiue_games_results(DB_CON)
#     spreads = []
#     for gl in all_gls:
#         result_match = RESULT_REGEX.match(gl.get('result'))
#         scores = [int(result_match.group(2)), int(result_match.group(3))]
#         spread = abs(scores[0] - scores[1])
#         if gl.get('result').find("L") != -1:
#             spread = spread * -1
#         spreads.append(spread)

#     bounds = {
#         'actual': {
#             'lower': np.min(spreads),
#             'upper': np.max(spreads)
#         },
#         'desired': {
#             'lower': -13,
#             'upper': 13
#         }
#     }

#     return bounds


def create_int_to_team_name(team_urls):
    r"""
        Creates dict with team_name : initial
    """
    team_name_to_int = {}
    for url in team_urls:
        match = NAME_LINK_REGEX.match(url.strip())
        team_name_to_int[match.group(1).upper()] = match.group(2)
    return team_name_to_int


def store_correlations():
    """_summary_
    """
    unqiue_players = sqllite_utils.get_unique_player_names(DB_CONN)
    int_to_team_name = create_int_to_team_name(scraper.TEAMS)
    for player in unqiue_players:
        player_gls = sqllite_utils.get_player_gls(player.get('player_name'),
                                                  NBA_SEASON_KEY,
                                                  player.get('team_name'),
                                                  DB_CONN)
        points = [gl.get('points') for gl in player_gls]
        opps = [
            int_to_team_name.get(OPP_REGEX.match(gl.get('opp')).group(2))
            for gl in player_gls
        ]
        pace_corr = np.corrcoef(points,
                                [WORST_PACE.index(opp) for opp in opps])
        two_pt_corr = np.corrcoef(points,
                                  [TOP_2PT_D.index(opp) for opp in opps])
        three_pt_corr = np.corrcoef(points,
                                    [TOP_3PT_D.index(opp) for opp in opps])
        def_rtg_corr = np.corrcoef(points,
                                   [TOP_DEF_RTG.index(opp) for opp in opps])
        def_rb_corr = np.corrcoef(points,
                                  [TOP_DEF_RB_PER.index(opp) for opp in opps])
        off_rb_corr = np.corrcoef(points,
                                  [TOP_OFF_RB_PER.index(opp) for opp in opps])
        totals = []
        for gl in player_gls:
            result_match = RESULT_REGEX.match(gl.get('result'))
            scores = [int(result_match.group(2)), int(result_match.group(3))]
            totals.append(scores[0] + scores[1])

        totals_corr = np.corrcoef(points, totals)

        correlations = {
            'player_name': player.get('player_name'),
            'team_name': player.get('team_name'),
            'pace_corr': float("{:.3f}".format(pace_corr[0][1])),
            'two_pt_corr': float("{:.3f}".format(two_pt_corr[0][1])),
            'three_pt_corr': float("{:.3f}".format(three_pt_corr[0][1])),
            'opp_deff_rtg_corr': float("{:.3f}".format(def_rtg_corr[0][1])),
            'opp_def_rb_per_corr': float("{:.3f}".format(def_rb_corr[0][1])),
            'opp_off_rb_per_corr': float("{:.3f}".format(off_rb_corr[0][1])),
            'total_corr': float("{:.3f}".format(totals_corr[0][1]))
        }
        sqllite_utils.insert_correlations(correlations, DB_CONN)


def three_point_freq():
    unqiue_players = sqllite_utils.get_unique_player_names(DB_CONN)
    freqs = []
    for player in unqiue_players:
        player_gls = sqllite_utils.get_player_gls(player.get('player_name'),
                                                  NBA_SEASON_KEY,
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
