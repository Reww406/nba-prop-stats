"""
  Main python file that kicks off script processes file and creates output.
"""

import re
import time
import matplotlib
from matplotlib import pyplot as plt
import matplotlib.backends.backend_pdf
import numpy as np
import pandas as pd
import sklearn.metrics as sm

from player_stats import stats
from player_stats import sqllite_utils
from player_stats import scraper

GAME_REGEX = re.compile(r"^\w+\s*@\s*\w+$", re.IGNORECASE)
SPREAD_REGEX = re.compile(r"^Spread[:]\s(.*?)$", re.IGNORECASE)
TOTAL_REGEX = re.compile(r"^Total[:]\s(.*?)$", re.IGNORECASE)
DATE_REGEX = re.compile(r"^Date[:]\s(.*?)$", re.IGNORECASE)
HURT_PLAYER_RE = re.compile(r"^(\w{2,3})\sstarting\s(\w{1,2}).*?$",
                            re.IGNORECASE)

OPP_REGEX = re.compile(r"^(@|vs)(\w+)$")

START_TIME = str(int(time.time()))

DB_CON = sqllite_utils.get_conn()


def build_graphic(data_f, game):
    """
        Takes Pandas data frame and builds a table from it
    """

    df_dict = data_f.to_dict(orient='records')
    rows = len(data_f.axes[0])
    cols = len(data_f.axes[1])
    fig, axis = plt.subplots(figsize=(12, 5))

    axis.set_ylim(-1, rows + 1)
    axis.set_xlim(0, cols + .5)
    for row in range(rows):
        d = df_dict[row]
        # Add data to graph
        axis.text(x=0.2, y=row, s=d['id'], va='center', ha='left', fontsize=10)
        axis.text(x=1.5,
                  y=row,
                  s=d['prop'][0:8],
                  va='center',
                  ha='left',
                  fontsize=10)
        axis.text(x=2.2,
                  y=row,
                  s=d['odds'],
                  va='center',
                  ha='left',
                  fontsize=10)
        axis.text(x=3.2,
                  y=row,
                  s=d['team'],
                  va='center',
                  ha='left',
                  fontsize=10)
        axis.text(x=4.5,
                  y=row,
                  s=d['over'],
                  va='center',
                  ha='left',
                  fontsize=10)
        axis.text(x=5.5,
                  y=row,
                  s=d['proj'],
                  va='center',
                  ha='left',
                  fontsize=10)

    # Column Title
    axis.text(0.2, rows, 'Player', weight='bold', ha='left')
    axis.text(1.5, rows, 'Prop', weight='bold', ha='left')
    axis.text(2.2, rows, 'Odds', weight='bold', ha='left')
    axis.text(3.2, rows, 'Team', weight='bold', ha='left')
    axis.text(4.5, rows, 'Over %', weight='bold', ha='left')
    axis.text(5.5, rows, 'Proj', weight='bold', ha='left')

    # Creates lines
    for row in range(rows):
        axis.plot([0, cols + .5], [row - .5, row - .5],
                  ls=':',
                  lw='.5',
                  c='grey')
    # rect = patches.Rectangle(
    #     (1.5, -.5),  # bottom left starting position (x,y)
    #     .65,  # width
    #     10,  # height
    #     ec='none',
    #     fc='grey',
    #     alpha=.2,
    #     zorder=-1)
    # line under title
    axis.plot([-.1, cols + 0.1], [row + 0.5, row + 0.5], lw='.5', c='black')

    axis.axis('off')
    axis.set_title(f"{beatuify_name(game)} - Points",
                   loc='left',
                   fontsize=18,
                   weight='bold')
    return fig


def get_unique_names(props):
    """
        Get unique team names
    """
    team_names = set()
    for prop in props:
        team_names.add(prop.get('team_name'))
    return team_names


def get_team_props(props, team):
    """
        Get all props for a certain team
    """
    team_props = []
    for prop in props:
        if prop.get('team_name') == team:
            team_props.append(prop)
    return team_props


def beatuify_name(name: str):
    """
        Upper case name and turn - back to space
    """
    name_split = name.split('-')
    name_split = [name.capitalize() for name in name_split]
    return " ".join(name_split)


def calculate_correct(prop_type):
    all_props = sqllite_utils.get_all_props_for_type(prop_type, DB_CON)
    total = 0
    correct = 0
    y_actual = []
    y_pred = []
    y_avg_pred = []
    y_custom_pred = []
    for prop in all_props:
        over = prop.get('over_num')
        name = prop.get('player_name')
        team_name = prop.get('team_name')
        date = prop.get('prop_scraped')
        game_date = date.split('-')[0] + '/' + date.split('-')[1]
        proj = float(stats.get_points_proj(prop))
        team_name = stats.convert_team_name(team_name)
        game_log = sqllite_utils.get_points_for_game(name, team_name,
                                                     game_date, DB_CON)
        game_logs = sqllite_utils.get_player_gls(name, '2022-23', team_name,
                                                 DB_CON)
        if game_log is not None:
            y_custom_pred.append(proj)
            y_avg_pred.append(
                stats.get_stat_mean_for_player(name, team_name, 'points'))
            y_actual.append(game_log.get('points'))
            total += 1
            game_log = game_log.get('points')

            if game_log >= over and proj >= over:
                correct += 1
            elif game_log <= over and proj <= over:
                correct += 1
            else:
                # print(
                #     f"Wrong over: {over} proj: {gam_proj} actual_points: {game_log}"
                # )
                pass
        else:
            print(
                f"Couldnt get actual points {name} {team_name} and {game_date}"
            )
    if total == 0:
        return 0
    print(f"{y_pred[0:10]}\n{y_avg_pred[0:10]}")
    print("Mean absolute error Just Avg =",
          round(sm.mean_absolute_error(y_actual, y_avg_pred), 2))
    print("Mean absolute error Custom Proj =",
          round(sm.mean_absolute_error(y_actual, y_custom_pred), 2))
    print(correct / total)


# Main function
def main(prop_date, calc_corr):
    """
        Starts parsing props
    """
    props = sqllite_utils.get_point_props(prop_date, DB_CON)
    figs = []
    corrects = []
    for team in get_unique_names(props):
        # Process Team Props..
        team_dict = {
            'id': [],
            'prop': [],
            'odds': [],
            'team': [],
            'over': [],
            'proj': [],
            'gam_proj': []
        }
        t_props = get_team_props(props, team)
        for t_prop in t_props:
            over_under = stats.get_points_ats(t_prop)
            team_dict.get('id').append(beatuify_name(
                t_prop.get('player_name')))
            team_dict.get('prop').append(beatuify_name(
                t_prop.get('prop_name')))
            team_dict.get('odds').append(
                f"o{t_prop.get('over_num')} {t_prop.get('over_odds')}")
            team_dict.get('team').append(beatuify_name(
                t_prop.get('team_name')))
            team_dict.get('over').append(over_under)
            team_dict.get('proj').append(stats.get_points_proj(t_prop))
            team_dict.get('gam_proj').append(stats.get_gam_pred(t_prop))
        figs.append(build_graphic(pd.DataFrame(team_dict), team))
    pdf = matplotlib.backends.backend_pdf.PdfPages("./reports/" + START_TIME +
                                                   '-report.pdf')
    for fig in figs:
        pdf.savefig(fig)
    pdf.close()


# scraper.update_nba_adv_stats()
# scraper.update_nba_opp_scoring()
# scraper.update_player_gamelogs()
# scraper.update_todays_player_props()

# main("12-30-2022", False)

calculate_correct('points')

# stats.create_3pt_gam()
# stats.create_2pt_gam()
