"""
  Main python file that kicks off script processes file and creates output.
"""

import re
import time
import matplotlib
from matplotlib import pyplot as plt
import matplotlib.backends.backend_pdf
import pandas as pd

from player_stats import stats
from player_stats import scraper
from player_stats import sqllite_utils
from player_stats import constants

import logreg

GAME_REGEX = re.compile(r"^\w+\s*@\s*\w+$", re.IGNORECASE)
SPREAD_REGEX = re.compile(r"^Spread[:]\s(.*?)$", re.IGNORECASE)
TOTAL_REGEX = re.compile(r"^Total[:]\s(.*?)$", re.IGNORECASE)
DATE_REGEX = re.compile(r"^Date[:]\s(.*?)$", re.IGNORECASE)
HURT_PLAYER_RE = re.compile(r"^(\w{2,3})\sstarting\s(\w{1,2}).*?$",
                            re.IGNORECASE)

OPP_REGEX = re.compile(r"^(@|vs)(\w+)$")

START_TIME = str(int(time.time()))

DB_CON = sqllite_utils.get_conn()

log_reg = logreg.create_logistic_regression_pipe()


def build_graphic(data_f, game, spread):
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
        axis.text(x=0.2, y=row, s=d['id'], va='center', ha='left', fontsize=10)
        axis.text(x=1.5,
                  y=row,
                  s=d['prop'][0:8],
                  va='center',
                  ha='left',
                  fontsize=10)
        axis.text(x=2.5,
                  y=row,
                  s=d['odds'],
                  va='center',
                  ha='left',
                  fontsize=10)
        axis.text(x=3.5,
                  y=row,
                  s=d['edge'],
                  va='center',
                  ha='left',
                  fontsize=10)
        axis.text(x=4.5,
                  y=row,
                  s=d['over_proba'],
                  va='center',
                  ha='left',
                  fontsize=10)
        axis.text(x=5.5,
                  y=row,
                  s=d['over_class'],
                  va='center',
                  ha='left',
                  fontsize=10)

    # Column Title
    axis.text(0.2, rows, 'Player', weight='bold', ha='left')
    axis.text(1.5, rows, 'Prop', weight='bold', ha='left')
    axis.text(2.5, rows, 'Odds', weight='bold', ha='left')
    axis.text(3.5, rows, 'Edge', weight='bold', ha='left')
    axis.text(4.5, rows, 'Probability', weight='bold', ha='left')
    axis.text(5.5, rows, 'Class', weight='bold', ha='left')

    # Creates lines
    for row in range(rows):
        axis.plot([0, cols + .5], [row - .5, row - .5],
                  ls=':',
                  lw='.5',
                  c='grey')
    axis.plot([-.1, cols + 0.1], [row + 0.5, row + 0.5], lw='.5', c='black')

    axis.axis('off')
    axis.set_title(f"{beatuify_name(game)}, Spread: {spread}",
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


def _calculate_edge(odds, proba):
    implied_proba = 0
    if odds > 0:
        # poss
        implied_proba = (100 / (odds + 100))
    else:
        # neg
        implied_proba = (-1 * (odds)) / (-1 * (odds) + 100)
    edge = '{:.2f}'.format((proba - implied_proba) * 100) + "%"
    return edge


# Main function
def main(prop_date):
    """
        Starts parsing props
    """
    props = sqllite_utils.get_point_props(prop_date, DB_CON)
    figs = []
    for team in get_unique_names(props):
        # Process Team Props..
        team_dict = {
            'id': [],
            'prop': [],
            'odds': [],
            'edge': [],
            'over_proba': [],
            'over_class': []
        }
        t_props = get_team_props(props, team)
        spread = t_props[0].get('team_spread')
        for t_prop in t_props:
            class_and_proba = logreg.get_class_and_proba(t_prop, log_reg)

            odds_num = 'Nan'
            odds = 'Nan'
            if class_and_proba is None:
                continue

            proba_class = class_and_proba[0]
            proba = class_and_proba[1]
            if class_and_proba[0] == "Pick Over":
                odds_num = f"o{t_prop.get('over_num')}"
                odds = t_prop.get('over_odds')
            else:
                odds_num = f"u{t_prop.get('under_num')}"
                odds = t_prop.get('under_odds')

            edge = _calculate_edge(odds, float(class_and_proba[1]))

            team_dict.get('id').append(beatuify_name(
                t_prop.get('player_name')))
            team_dict.get('prop').append(beatuify_name(
                t_prop.get('prop_name')))
            team_dict.get('odds').append(f"{odds_num} {odds}")
            team_dict.get('edge').append(edge)
            team_dict.get('over_proba').append(proba)
            team_dict.get('over_class').append(proba_class)
        figs.append(build_graphic(pd.DataFrame(team_dict), team, spread))
    pdf = matplotlib.backends.backend_pdf.PdfPages("./reports/" + START_TIME +
                                                   '-report.pdf')
    for fig in figs:
        pdf.savefig(fig)
    pdf.close()


def check_star_players_list():
    for team, players in constants.TEAM_TO_STAR_PLAYERS.items():
        for player in players:
            gls = sqllite_utils.get_player_gls(player,
                                               constants.NBA_CURR_SEASON, team,
                                               DB_CON)
            if len(gls) == 0:
                print(f"couldn't find {team} {player}")


# scraper.update_nba_adv_stats()
# scraper.update_nba_opp_scoring()
# scraper.update_player_gamelogs('2022-23')
# scraper.update_todays_player_props()

# check_star_players_list()

main("01-28-2023")