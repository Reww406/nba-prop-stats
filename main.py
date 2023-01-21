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
from player_stats import sqllite_utils
from player_stats import scraper
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
                  s=d['over'],
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
    axis.text(3.5, rows, 'ATO %', weight='bold', ha='left')
    axis.text(4.5, rows, 'Class Proba', weight='bold', ha='left')
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
            'over': [],
            'over_proba': [],
            'over_class': []
        }
        t_props = get_team_props(props, team)
        spread = t_props[0].get('team_spread')
        for t_prop in t_props:
            over_under = stats.get_points_ats(t_prop)
            team_dict.get('id').append(beatuify_name(
                t_prop.get('player_name')))
            team_dict.get('prop').append(beatuify_name(
                t_prop.get('prop_name')))
            team_dict.get('odds').append(
                f"o{t_prop.get('over_num')} {t_prop.get('over_odds')}")
            team_dict.get('over').append(over_under)
            team_dict.get('over_proba').append(
                logreg.get_class_proba(t_prop, log_reg))
            team_dict.get('over_class').append(
                logreg.get_over_class(t_prop, log_reg))
        figs.append(build_graphic(pd.DataFrame(team_dict), team, spread))
    pdf = matplotlib.backends.backend_pdf.PdfPages("./reports/" + START_TIME +
                                                   '-report.pdf')
    for fig in figs:
        pdf.savefig(fig)
    pdf.close()


# scraper.update_nba_adv_stats()
# scraper.update_nba_opp_scoring()
scraper.update_player_gamelogs('2021-22')
# scraper.update_todays_player_props()

# main("01-20-2023", False)