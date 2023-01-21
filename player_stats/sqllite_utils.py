"""
    Module to make interacting with Sqlite3 
    easier
"""

import sqlite3


# returns row as dictionary
def _dict_factory(cursor, row):
    dict_fact = {}
    for idx, col in enumerate(cursor.description):
        dict_fact[col[0]] = row[idx]
    return dict_fact


def get_db_in_mem():
    """
        Loads SQLlite3 DB into memory only good for reading
    """
    source = sqlite3.connect('nba_stats.db', check_same_thread=False)
    dest = sqlite3.connect(':memory:', check_same_thread=False)
    source.backup(dest)
    source.close()
    dest.row_factory = _dict_factory
    return dest.cursor()


def get_conn():
    """
        Opens SQLite3 file.
    """
    connection = sqlite3.connect('nba_stats.db', check_same_thread=False)
    connection.row_factory = _dict_factory
    return connection.cursor()


def insert_player_gamelogs(gamelog, cur):
    """
        Inserts gamelog into player db.
    """
    cur.execute(
        """INSERT INTO player_gl
           (player_name, season, game_date, team_name, result, opp, minutes_played,
            fg_att, fg_made, fg_per, three_pt_att, three_pt_made, three_pt_per, ft_att, ft_made, 
            ft_per, rebounds, assists, blocks, steals, fouls, turn_overs, points)
           VALUES (?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?, ?, ?, ?)""",
        (gamelog['player_name'], gamelog['season'], gamelog['game_date'],
         gamelog['team_name'], gamelog['result'], gamelog['opp'],
         gamelog['minutes_played'], gamelog['fg_att'], gamelog['fg_made'],
         gamelog['fg_per'], gamelog['three_pt_att'], gamelog['three_pt_made'],
         gamelog['three_pt_per'], gamelog['ft_att'], gamelog['ft_made'],
         gamelog['ft_per'], gamelog['rebounds'], gamelog['assists'],
         gamelog['blocks'], gamelog['steals'], gamelog['fouls'],
         gamelog['turn_overs'], gamelog['points']))
    cur.connection.commit()


def insert_correlations(corrs, cur):
    """
        Inserts gamelog into player db.
    """
    cur.execute(
        """INSERT INTO player_stat_correlation 
           (player_name, team_name, pace_corr, two_pt_corr, three_pt_corr, 
           total_corr, opp_deff_rtg_corr, opp_def_rb_per_corr, opp_off_rb_per_corr, rest_corr)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (corrs.get('player_name'), corrs.get('team_name'),
         corrs.get('pace_corr'), corrs.get('two_pt_corr'),
         corrs.get('three_pt_corr'), corrs.get('total_corr'),
         corrs.get('opp_deff_rtg_corr'), corrs.get('opp_def_rb_per_corr'),
         corrs.get('opp_off_rb_per_corr'), corrs.get('rest_corr')))
    cur.connection.commit()


def insert_opp_scoring_stats(gamelog, cur):
    """
        Inserts gamelog into player db.
    """
    cur.execute(
        """INSERT INTO opp_scoring
           (team_name, season, games_played, fg_freq, fg_made, fg_att, fg_per, fg_eff_per,
            two_pt_freq, two_pt_made, two_pt_att, two_pt_per, three_pt_freq, three_pt_made,
            three_pt_att, three_pt_per)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?, ?, ?, ?, ?)""",
        (gamelog['team_name'], gamelog['season'], gamelog['games_played'],
         gamelog['fg_freq'], gamelog['fg_made'], gamelog['fg_att'],
         gamelog['fg_per'], gamelog['fg_eff_per'], gamelog['two_pt_freq'],
         gamelog['two_pt_made'], gamelog['two_pt_att'], gamelog['two_pt_per'],
         gamelog['three_pt_freq'], gamelog['three_pt_made'],
         gamelog['three_pt_att'], gamelog['three_pt_per']))
    cur.connection.commit()


def insert_adv_team_stats(gamelog, cur):
    """
        Inserts gamelog into player db.
    """
    cur.execute(
        """INSERT INTO nba_adv_stats
           (team_name, season, games_played, wins, losses, minutes_played, off_rtg,
            def_rtg, net_rtg, ast_per, ast_to_ratio, ast_ratio, off_rebound_per, def_rebound_per,
            reb_per, to_ratio, eff_fg_per, true_shotting_per, pace, player_impact_est,
            possions)
           VALUES (?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   ?, ?, ?, ?, ?)""",
        (gamelog['team_name'], gamelog['season'], gamelog['games_played'],
         gamelog['wins'], gamelog['losses'], gamelog['minutes_played'],
         gamelog['off_rtg'], gamelog['def_rtg'], gamelog['net_rtg'],
         gamelog['ast_per'], gamelog['ast_to_ratio'], gamelog['ast_ratio'],
         gamelog['off_rebound_per'], gamelog['def_rebound_per'],
         gamelog['reb_per'], gamelog['to_ratio'], gamelog['eff_fg_per'],
         gamelog['true_shotting_per'], gamelog['pace'],
         gamelog['player_impact_est'], gamelog['possions']))
    cur.connection.commit()


def insert_props(props, cur):
    """
        Inserts gamelog into player db.
    """
    for prop in props:
        cur.execute(
            """INSERT INTO props 
            (season, prop_name, player_name, over_num, team_spread, game_total, under_num,
                over_odds, under_odds, prop_scraped, team_name, opp_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (prop['season'], prop['prop_name'], prop['player_name'],
             prop['over_num'], prop['team_spread'], prop['game_total'],
             prop['under_num'], prop['over_odds'], prop['under_odds'],
             prop['prop_scraped'], prop['team_name'], prop['opp_name']))
        cur.connection.commit()


def get_player_team(player_name, cur):
    """
      get's players team
    """
    select_statement = """
      SELECT team_name FROM player_gl WHERE player_name LIKE ?
    """
    return cur.execute(select_statement, (player_name + '%', )).fetchone()


def get_point_props(date, cur):
    """
        Gets props for date
    """
    select_statement = """
      SELECT * FROM props WHERE prop_scraped = ? and prop_name = 'points';
    """
    return cur.execute(select_statement, (date, )).fetchall()

def get_player_gls(player_name, season, team_name, cur):
    """
      Get's all game logs for player and section
    """
    select_statement = """
      SELECT * FROM player_gl WHERE player_name LIKE ? and team_name = ? and season = ?
    """
    return cur.execute(select_statement,
                       (player_name + '%', team_name, season)).fetchall()


def get_player_games_vs_opp(player_name, season, team_name, opp, cur):
    """
      Get's all game logs for player and section
    """
    select_statement = """
      SELECT * FROM player_gl WHERE player_name LIKE ? and team_name = ? and season = ? and opp LIKE ?
    """
    return cur.execute(
        select_statement,
        (player_name + '%', team_name, season, '%' + opp)).fetchall()


def get_team_name_and_stat(cur, stat_key, stat_table):
    """
        Get a dictionary with team name and corresponding stat
    """
    top_select = f"""
      SELECT team_name, {stat_key} FROM {stat_table}
    """
    results = cur.execute(top_select).fetchall()
    team_name_and_stat = {}
    for result in results:
        team_name_and_stat[result.get('team_name')] = result.get(stat_key)
    return team_name_and_stat


def get_unqiue_games_results(cur):
    """
        Get pace numbers
    """
    top_select = """
      SELECT DISTINCT team_name, opp, game_date, result FROM player_gl
    """

    return cur.execute(top_select).fetchall()


def get_points_for_game(name, team_name, game_date, cur):
    top_select = """
      SELECT points, minutes_played FROM player_gl WHERE player_name LIKE ? AND 
        team_name = ? AND game_date LIKE ?
    """
    # print(f"{name} {team_name} %{game_date}")
    return cur.execute(top_select,
                       (name + '%', team_name, '%' + game_date)).fetchone()


def get_team_name_and_def_rating(cur):
    """
        Get pace numbers
    """
    top_select = """
      SELECT team_name, def_rtg FROM nba_adv_stats ORDER BY def_rtg DESC
    """

    results = cur.execute(top_select).fetchall()
    team_name_pace = {}
    for result in results:
        team_name_pace[result.get('team_name')] = result.get('def_rtg')
    return team_name_pace


# top pace
def get_n_pace(num, get_top, cur):
    """
        Get top/bottom 5 defenses based on interceptions.
    """

    top_select = f"""
      SELECT team_name FROM nba_adv_stats ORDER BY pace DESC LIMIT {num}
    """

    bottom_select = f"""
      SELECT team_name FROM nba_adv_stats ORDER BY pace ASC LIMIT {num}
    """

    if get_top:
        return [d.get('team_name') for d in cur.execute(top_select).fetchall()]
    return [d.get('team_name') for d in cur.execute(bottom_select).fetchall()]


def get_n_deff_rb(num, get_top, cur):
    """
        Get top/bottom 5 defenses based on interceptions.
    """

    top_select = f"""
      SELECT team_name FROM nba_adv_stats ORDER BY def_rebound_per DESC LIMIT {num}
    """

    bottom_select = f"""
      SELECT team_name FROM nba_adv_stats ORDER BY def_rebound_per ASC LIMIT {num}
    """

    if get_top:
        return [d.get('team_name') for d in cur.execute(top_select).fetchall()]
    return [d.get('team_name') for d in cur.execute(bottom_select).fetchall()]


def get_team_name_and_def_rb(cur):
    """
        Get pace numbers
    """
    top_select = """
      SELECT team_name, def_rebound_per FROM nba_adv_stats ORDER BY def_rebound_per DESC
    """

    results = cur.execute(top_select).fetchall()
    team_name_pace = {}
    for result in results:
        team_name_pace[result.get('team_name')] = result.get('def_rebound_per')
    return team_name_pace


def get_n_off_rb(num, get_top, cur):
    """
        Get top/bottom 5 defenses based on interceptions.
    """

    top_select = f"""
      SELECT team_name FROM nba_adv_stats ORDER BY off_rebound_per DESC LIMIT {num}
    """

    bottom_select = f"""
      SELECT team_name FROM nba_adv_stats ORDER BY off_rebound_per ASC LIMIT {num}
    """

    if get_top:
        return [d.get('team_name') for d in cur.execute(top_select).fetchall()]
    return [d.get('team_name') for d in cur.execute(bottom_select).fetchall()]


def get_n_def(num, get_top, cur):
    """
        Get top/bottom 5 defenses based on interceptions.
    """

    top_select = f"""
      SELECT team_name FROM nba_adv_stats ORDER BY def_rtg ASC LIMIT {num}
    """

    bottom_select = f"""
      SELECT team_name FROM nba_adv_stats ORDER BY def_rtg DESC LIMIT {num}
    """

    if get_top:
        return [d.get('team_name') for d in cur.execute(top_select).fetchall()]
    return [d.get('team_name') for d in cur.execute(bottom_select).fetchall()]


def get_n_two_d(num, get_top, cur):
    """
        Get top/bottom 5 defenses based on interceptions.
    """

    top_select = f"""
      SELECT team_name FROM opp_scoring ORDER BY two_pt_made ASC LIMIT {num}
    """

    bottom_select = f"""
      SELECT team_name FROM opp_scoring ORDER BY two_pt_made DESC LIMIT {num}
    """

    if get_top:
        return [d.get('team_name') for d in cur.execute(top_select).fetchall()]
    return [d.get('team_name') for d in cur.execute(bottom_select).fetchall()]


def get_n_three_d(num, get_top, cur):
    """
        Get top/bottom 5 defenses based on interceptions.
    """

    top_select = f"""
      SELECT team_name FROM opp_scoring ORDER BY three_pt_made ASC LIMIT {num}
    """

    bottom_select = f"""
      SELECT team_name FROM opp_scoring ORDER BY three_pt_made DESC LIMIT {num}
    """

    if get_top:
        return [d.get('team_name') for d in cur.execute(top_select).fetchall()]
    return [d.get('team_name') for d in cur.execute(bottom_select).fetchall()]


def get_all_gls(cur):
    """
      Get's all game logs for player and section
    """
    select_statement = """
      SELECT * FROM player_gl
    """
    return cur.execute(select_statement).fetchall()


def get_unique_player_names(cur):
    """
      Get's unqiue players
    """
    select_statement = """
      SELECT DISTINCT player_name, team_name FROM player_gl
    """
    return cur.execute(select_statement).fetchall()


def get_array_of_correlations(corr_name, cur):
    """
        Get top/bottom 5 defenses based on interceptions.
    """

    select = f"""
      SELECT {corr_name} FROM player_stat_correlation
    """

    return [d.get(corr_name) for d in cur.execute(select).fetchall()]


def get_player_correlations(player_name, team_name, cur):
    """
        Get top/bottom 5 defenses based on interceptions.
    """

    select = """
      SELECT * FROM player_stat_correlation WHERE player_name LIKE ? AND
        team_name = ?
    """
    return cur.execute(select, (player_name + '%', team_name)).fetchone()


def get_all_props_for_type(prop_type, cur):
    """
        Get top/bottom 5 defenses based on interceptions.
    """

    select = """
      SELECT * FROM props WHERE prop_name = ?
    """
    return cur.execute(select, (prop_type, )).fetchall()