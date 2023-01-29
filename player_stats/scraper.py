"""
    Scrapes info from ESPN NBA and Fanduel
"""

from datetime import datetime
import re
import random
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry
from requests import HTTPError, ConnectTimeout, ReadTimeout

import requests
from requests_futures.sessions import FuturesSession
from seleniumwire import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from lxml import etree

#from player_stats
from player_stats import sqllite_utils
from player_stats import constants

OPP_SCORING = "https://www.nba.com/stats/teams/opponent-shots-general"
NBA_ADV = "https://www.nba.com/stats/teams/advanced"

# Used to sploof http requests device originator
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36(KHTML, "
    + "like Gecko) Chrome/104.0.5112.79 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:101.0) Gecko/20100101 Firefox/101.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.75.14 (KHTML, "
    + "like Gecko) Version/7.0.3 Safari/7046A194A",
]

PLAYER_ID_REGEX = re.compile(r"^.*?/id/(\d+)/.*?$")
GL_FORMAT_STR = "https://www.espn.com/nba/player/gamelog/_/id/{player_id}/type/nba/year/{year}"

PROXY_FILE = open("proxy_pass.txt", "r", encoding="UTF-8")
USERNAME = PROXY_FILE.readline().strip()
PASSWORD = PROXY_FILE.readline().strip()
PROXY_FILE.close()

PROXY_URL = "http://customer-" + USERNAME + "-cc-US:" + PASSWORD + "@pr.oxylabs.io:7777"
PROXIES = {"http": PROXY_URL, "https": PROXY_URL}

CHROME_OPTIONS = webdriver.ChromeOptions()
CAPS = DesiredCapabilities().CHROME
CAPS["pageLoadStrategy"] = "normal"
PREFS = {
    'profile.default_content_setting_values': {
        'images': 2,
    }
}

retries = Retry(total=5,
                backoff_factor=0.1,
                status_forcelist=[500, 502, 503, 504])

session = FuturesSession(executor=ThreadPoolExecutor(max_workers=16))
session.mount("http://", HTTPAdapter(max_retries=retries))
CHROM_DRIVER_PATH = "/usr/bin/chromedriver"
CHROME_OPTIONS.add_experimental_option("prefs", PREFS)
CHROME_OPTIONS.add_argument("--window-size=800,1200")
OPTIONS = {'proxy': {'http': PROXY_URL, 'https': PROXY_URL}}

CAPABILITIES = webdriver.DesiredCapabilities.CHROME

MAX_RETRIES = 3
NBA_CURR_SEASON = '2022-23'
# months the season is played
NBA_MONTH = [
    "april", "march", "february", "january", "december", "november", "october"
]
FANDUEL_LINK = "https://sportsbook.fanduel.com"

DB_CUR = sqllite_utils.get_conn()

# These change depending on the size of the window
# Title of bets section so Player Points
PROP_TITLE_XPATH = "/html/body/div[1]/div/div/div[1]/main/div/div[1]/div/div[2]/div[4]/ul/li[2]/div/div/div[1]/div/div[1]/span"
# div of individual bet rows, changing when you shrink the window
PLAYER_DIV_XPATH = "/html/body/div[1]/div/div/div[1]/main/div/div[1]/div/div[2]/div[4]/ul/li[2]/div/div/div[3]/div[1]/div"
SHOW_XPATH = '/html/body/div[1]/div/div/div[1]/main/div/div[1]/div/div[2]/div[4]/ul/li[2]/div/div/div[4]/div/div/div/span'
# Section on the front page containing the game info
GAME_LINES_XPATH = "/html/body/div[1]/div/div/div[1]/main/div/div[1]/div/div[2]/div[4]/ul/li[2]/div/div/div[3]/div/div"
# The live page above game time, used to skipping live bets
LIVE_XPATH = "/html/body/div[1]/div/div/div[2]/div[2]/main/div/div[1]/div/div[2]/div[2]/div/div[3]/div[1]/svg"


def _scrape(url):
    r"""
        Rotates IP and user agent for request
    """
    for _ in range(3):
        try:
            headers = {"User-Agent": USER_AGENTS[random.randint(0, 2)]}
            resp = requests.get(url,
                                headers=headers,
                                timeout=20,
                                proxies=PROXIES)
            if resp.status_code == 200:
                return resp
            print("Retrying..")
        except (requests.exceptions.SSLError, requests.exceptions.ProxyError,
                ConnectionError, HTTPError, ConnectTimeout, ReadTimeout):
            print("Failed to get request.. retrying")
    raise Exception("Failed to get: " + url)


def _scrape_async(url):
    """
        Returns a future of resp instead of the response..
    """
    for _ in range(1):
        try:
            headers = {"User-Agent": USER_AGENTS[random.randint(0, 2)]}

            future = session.get(url,
                                 headers=headers,
                                 timeout=20,
                                 proxies=PROXIES)
            return future
        except (requests.exceptions.SSLError, requests.exceptions.ProxyError,
                ConnectionError, HTTPError, ConnectTimeout, ReadTimeout):
            print("Failed to get request.. retrying")
    raise Exception("Failed to get: " + url)


def _scrape_js_page(url):
    r"""
        Get page text using Selenium
    """
    for _ in range(5):
        print(f"attempting to get {url}")
        driver = webdriver.Chrome(CHROM_DRIVER_PATH,
                                  seleniumwire_options=OPTIONS,
                                  chrome_options=CHROME_OPTIONS,
                                  desired_capabilities=CAPABILITIES)

        driver.set_page_load_timeout(30)
        try:
            driver.get(url)
            if driver.page_source is None:
                print('access denied..')
                continue
            source = driver.page_source
            driver.close()
            return source
        except Exception as err:
            print(f"Retrying due to error: {err}")
    raise Exception("Failed to get: " + url)


# FIXME: not sure if this works
def _scrape_js_page_select_more(url):
    r"""
        Selects the more drop down on fanduel
    """
    for _ in range(5):
        print(f"attempting to get {url}")
        driver = webdriver.Chrome(CHROM_DRIVER_PATH,
                                  seleniumwire_options=OPTIONS,
                                  chrome_options=CHROME_OPTIONS,
                                  desired_capabilities=CAPABILITIES)

        driver.set_page_load_timeout(35)
        try:
            driver.get(url)
            if driver.page_source is None:
                print('access denied..')
                continue
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, SHOW_XPATH)))
                element = driver.find_element(By.XPATH, SHOW_XPATH)
                element.click()
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, SHOW_XPATH)))
            except WebDriverException:
                print("Trying to show more element is not clickable")
            source = driver.page_source
            driver.close()
            return source
        except Exception as err:
            print(f"Retrying due to error: {err}")
    raise Exception("Failed to get: " + url)


def _normalize_player_name(name: str):
    """
        Removes injured and out from names
    """
    remove = ['DD', 'O']
    name_split = name.strip().split()
    if name_split[len(name_split) - 1] in remove:
        del name_split[len(name_split) - 1]
    return "-".join(name_split).lower()


def _normalize_team_name(name: str):
    r"""
        Lower cases name replaces \s with -
    """
    return "-".join(name.strip().split()).lower()


def _get_season_year(season):
    season_splt = season.split('-')
    year = season_splt[0][0:2] + season_splt[1]
    return year


def _get_top_players_gl_links(team_url: str, season):
    """
        Get top players from the depth chart
        player_name and gl_link
    """
    gl_link_for_player = {}
    depth_link = team_url[:team_url.rindex('/_/')] + "/depth" + team_url[
        team_url.rindex('/_/'):]

    soup = BeautifulSoup(_scrape(depth_link).text, "html.parser")
    tbody = soup.find_all("tbody", {"class": ["Table", "Table__TBODY"]})[1]
    for row in tbody.find_all("tr"):
        tds = row.find_all('td')
        for i in range(0, 2):
            player_link = tds[i].find("a")['href']
            player_id = PLAYER_ID_REGEX.match(player_link).group(1)
            year = _get_season_year(season)

            gl_link_for_player[_normalize_player_name(
                tds[i].find("a").text)] = GL_FORMAT_STR.format(
                    player_id=player_id, year=year)

    return gl_link_for_player


def _is_game_line(text):
    """
        ESPN likes to throw random lines in there data
        so we add those lines to this list to filter out
    """
    no_no_words = [
        'All-Star', 'Mexico', 'Paris', 'Makeup', 'Round', 'Semifinals',
        'Finals'
    ]
    for word in no_no_words:
        if text.find(word) != -1:
            return False
    return True


def _parse_gamelog_tbody(tbody):
    r"""
    :param tbody is beatiful soup object of table body
    Each sub-list (row) in the list is a game log
    [['10', '12', '12'], ['13','13','43]]
    """
    stats = []
    for row in tbody.findChildren("tr"):
        row_data = []
        for t_data in row.findChildren("td"):
            if t_data.text.find('Previously') != -1:
                print('Player switched teams, stop scraping')
                return stats
            if _is_game_line(t_data.text):
                row_data.append(t_data.text)
        if len(row_data) >= 1:
            stats.append(row_data)
    return stats


# FIXME: will become more complicated after Feb 9th 2023
def _month_contains_team_switch(tbody):
    r"""
    :param tbody is beatiful soup object of table body
    Each sub-list (row) in the list is a game log
    [['10', '12', '12'], ['13','13','43]]
    """
    for row in tbody.findChildren("tr"):
        for t_data in row.findChildren("td"):
            if t_data.text.find('Previously') != -1:
                return True
    return False


# FG, 3PT, FT made and attempt shown in same field
def _insert_gl_into_db(player_name, team_name, col_names, game_log, season):
    db_entry = {
        'player_name': player_name,
        'season': season,
        'team_name': team_name
    }
    for col_name, stat in zip(col_names, game_log):
        # FG, 3PT, and FT are captured as 8-10 so we need to
        # split to get attempted and made.
        if col_name == 'FG':
            db_entry['fg_made'] = stat.split('-')[0]
            db_entry['fg_att'] = stat.split('-')[1]
        elif col_name == '3PT':
            db_entry['three_pt_made'] = stat.split('-')[0]
            db_entry['three_pt_att'] = stat.split('-')[1]
        elif col_name == 'FT':
            db_entry['ft_made'] = stat.split('-')[0]
            db_entry['ft_att'] = stat.split('-')[1]
        else:
            if constants.GL_TO_SQL_COL_NAMES.get(col_name) is None:
                raise Exception(
                    f"Missing header in conversion dict {col_name}")
            db_entry[constants.GL_TO_SQL_COL_NAMES.get(col_name)] = stat
    sqllite_utils.insert_player_gamelogs(db_entry, DB_CUR)


def _add_gamelogs_to_db(resp_future_for_name, team_name, season):
    """
        This function is ran on a teams starting 8-10 players
        the function will iterate over a dictionary with the players
        name and a future holding the resp of querying his
        game logs page

        The resp will be parsed and stored into a the SQLite Database
    """
    for name, future in resp_future_for_name.items():
        print(f"Working on {name}")
        resp = ""
        try:
            resp = future.result()
        except requests.exceptions.ConnectionError:
            print(f"Failed to get: {name}")
            return
        soup = BeautifulSoup(resp.text, "html.parser")
        # Table per month on Game log page

        switched_teams = False
        for table in soup.find_all("table",
                                   {"class": ["Table", "Table--align-right"]}):
            if switched_teams:
                print(f"{name}: switched teams last month, stopping scrape")
                break
            thead = table.find('thead')
            tbody = table.find('tbody')

            # Filter out tables where last row is not a month
            # FIXME: This will skip over the post season
            last_row = tbody.find_all('tr')[len(tbody.find_all('tr')) -
                                            1].find_all('td')[0].text.strip()
            if last_row not in NBA_MONTH:
                continue

            col_names = [x.text for x in thead.find("tr").findChildren("th")]
            # Stop scraping after feb deadline
            switched_teams = _month_contains_team_switch(tbody)
            stats = _parse_gamelog_tbody(tbody)

            for game_log in stats:
                if game_log[0] in NBA_MONTH:
                    continue
                _insert_gl_into_db(name, team_name, col_names, game_log,
                                   season)


def _insert_team_stats(stat_row, col_names, conv_map, db_func):
    db_entry = {}
    db_entry['season'] = NBA_CURR_SEASON
    for col_name, stat in zip(col_names, stat_row):
        if conv_map.get(col_name) is None:
            raise Exception(f"Missing header in conversion dict {col_name}")
        # Normalize name..
        if conv_map.get(col_name) == "team_name":
            db_entry[conv_map.get(col_name)] = _normalize_team_name(stat)
        else:
            db_entry[conv_map.get(col_name)] = stat
    db_func(db_entry, DB_CUR)


def update_player_gamelogs(season):
    """
        Get top 5 players from each team,
        then get their game logs and append any new game
        to the sqllite database.
    """
    for team_url in constants.NBA_TEAMS:
        print(f"Working on {team_url}")
        future_for_player_name = {}
        for name, link in _get_top_players_gl_links(team_url, season).items():
            future_for_player_name[name] = _scrape_async(link)

        team_name = team_url[team_url.rfind("/") + 1:]

        _add_gamelogs_to_db(future_for_player_name, team_name, season)


def update_nba_adv_stats():
    """
        Get ADV stats per team on NBA's page
    """
    soup = BeautifulSoup(_scrape_js_page(NBA_ADV), "html.parser")
    # Table per month on Game log page
    for table in soup.find_all("table", {"class": "Crom_table__p1iZz"}):
        thead = table.find('thead')
        tbody = table.find('tbody')

        # Filter out tables where last row is not a month
        col_names = [x.text for x in thead.find("tr").findChildren("th")]
        col_names = [x for x in col_names if not "RANK" in x]
        # Remove blank value
        del col_names[0]

        stats = _parse_gamelog_tbody(tbody)
        for stat_row in stats:
            # remove col_num
            del stat_row[0]
            _insert_team_stats(stat_row, col_names,
                               constants.ADV_STATS_TO_SQL_COL_NAMES,
                               sqllite_utils.insert_adv_team_stats)


def update_nba_opp_scoring():
    """
        Get ADV stats per team on NBA's page
    """
    soup = BeautifulSoup(_scrape_js_page(OPP_SCORING), "html.parser")
    # Table per month on Game log page
    for table in soup.find_all("table", {"class": "Crom_table__p1iZz"}):
        thead = table.find('thead')
        tbody = table.find('tbody')

        # Filter out tables where last row is not a month
        col_names = [
            x.text for x in thead.find_all("tr")[1].findChildren("th")
        ]
        stats = _parse_gamelog_tbody(tbody)
        for stat_row in stats:
            _insert_team_stats(stat_row, col_names,
                               constants.OPP_SCORING_TO_SQL_COL_NAMES,
                               sqllite_utils.insert_opp_scoring_stats)


def _get_game_links(soup):
    game_links = set()
    divs = soup.find_all(
        'div', {
            'class': [
                "t", 'u', 'v', 'w', 'ch', 'ci', 'x', 'dg', 'h', 'fu', 'cz',
                'hr', 'av'
            ]
        })
    for div in divs:
        _ = [
            game_links.add(FANDUEL_LINK + x['href'])
            if '/basketball/nba/' in x['href'] else None
            for x in div.find_all("a", {
                "class":
                ["t", "u", "al", "w", "ch", "ci", "x", "ht", "h", "hh"]
            })
        ]
    return game_links


def _convert_team_name(team_name):
    if constants.ESPN_TEAM_NAME_TO_FD.get(team_name) is None:
        return team_name
    return constants.ESPN_TEAM_NAME_TO_FD.get(team_name)


def _insert_prop(spreads: dict, total, link, prop_name):
    page_source = _scrape_js_page_select_more(link)
    soup = BeautifulSoup(page_source, "html.parser")
    # PyLint warning because C import
    dom = etree.HTML(str(soup))
    player_etree = dom.xpath(PLAYER_DIV_XPATH)
    if len(player_etree) == 0:
        print("First has no bets.")
        return
    player_class = player_etree[0].attrib['class']
    # So we can find out if on right page
    title_class = dom.xpath(PROP_TITLE_XPATH)[0].attrib['class']

    title = soup.find(
        "span", {
            "class": lambda value: value and value.startswith(title_class)
        },
        recursive=True).text

    if title.find(prop_name.capitalize()) == -1:
        print(f"Couldn't find title: {prop_name}")
        return

    player_divs = soup.find_all(
        "div",
        {"class": lambda value: value and value.startswith(player_class)},
        recursive=True)

    print(f"Player divs found {len(player_divs)}")
    if player_divs is None:
        print(f"No {prop_name} props..")
        return

    prop_dicts = []
    for div in player_divs:
        props = []
        props.extend([span.text for span in div.find_all('span')])
        sql_object = sqllite_utils.get_player_team(
            _normalize_player_name(props[0]), DB_CUR)
        if sql_object is None:
            print(f"Can't find team name for {props[0]}")
            continue
        team_name = _convert_team_name(sql_object.get('team_name'))
        if len(props) != 5:
            print('Skipping section of prop locked')
            continue
        teams = list(spreads.keys())
        # print(f"{team_name} and {teams}")
        teams.remove(team_name)
        opp = teams[0]
        prop_dicts.append({
            'season': NBA_CURR_SEASON,
            'player_name': _normalize_player_name(props[0]),
            'over_num': float(re.sub(r'O\s', '', props[1])),
            'team_spread': spreads.get(team_name),
            'prop_name': prop_name,
            'game_total': total,
            'under_num': float(re.sub(r'U\s', '', props[3])),
            'over_odds': props[2],
            'under_odds': props[4],
            'opp_name': opp,
            'prop_scraped': datetime.today().strftime('%m-%d-%Y'),
            'team_name': team_name
        })
    sqllite_utils.insert_props(prop_dicts, DB_CUR)


def update_todays_player_props():
    """
        Gets prop bets for fanduel
    """
    soup = BeautifulSoup(_scrape_js_page(FANDUEL_LINK + '/basketball'),
                         "html.parser")
    game_links = _get_game_links(soup)
    for link in game_links:
        spreads = {}
        soup = BeautifulSoup(_scrape_js_page(link), "html.parser")
        dom = etree.HTML(str(soup))

        live_path = dom.xpath(LIVE_XPATH)
        if len(live_path) > 0:
            print("Skipping live game ")
            continue

        div_path = dom.xpath(GAME_LINES_XPATH)
        div_class = div_path[0].attrib['class']

        div = soup.find('div', {'class': div_class}, recursive=True)
        game_spans = []
        for span in div.findChildren('span'):
            game_spans.append(span.text)

        if len(game_spans) != 12:
            spreads[_normalize_team_name(game_spans[0])] = 0
            spreads[_normalize_team_name(game_spans[1])] = 0
            total = 0
        else:
            spreads[_normalize_team_name(game_spans[0])] = game_spans[2]
            spreads[_normalize_team_name(game_spans[1])] = game_spans[7]
            total = float(re.sub(r'O\s', '', game_spans[5]))

        _insert_prop(spreads, total, link + "/" + "?tab=player-points",
                     'points')
        _insert_prop(spreads, total, link + "/" + "?tab=player-rebounds",
                     'rebounds')
        _insert_prop(spreads, total, link + "/" + "?tab=player-threes",
                     'threes')
