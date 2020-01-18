import requests
from bs4 import BeautifulSoup
# import lxml.html as lh
import pandas as pd
import datetime
import numpy as np
import re
import time


def get_page_content(url, encoding='UTF-8', remove_linebreaks=True
                     , header={
            'User-Agent': r'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) '
                          r'Chrome/41.0.2227.1 Safari/537.36'}):
    session = requests.Session()
    base_url = url
    response = session.get(base_url, headers=header)
    response.encoding = encoding
    page_content = BeautifulSoup(response.content, "html.parser")
    page_content_str = str(page_content)
    if remove_linebreaks:
        page_content_str = re.sub('\n', '', page_content_str)
    return page_content_str


# ------------------------------------------------------------------------------------------------------------------------------
# All Games Collecting
# Get the schedule from http://cba.sports.sina.com.cn/cba/schedule/all/?qleagueid=205&qmonth=&qteamid=
# Get all the links
# Loop through all the game links and scrape detailed stats


def scrape_sina_schedule(output_path,base_url=r"http://cba.sports.sina.com.cn/cba/schedule/all/?qleagueid=205&qmonth=&qteamid="):
    page_content = get_page_content(url=base_url, remove_linebreaks=True)
    print('开始爬取所有赛程、数据统计链接.')
    # Get table division
    table_content = re.findall('<div class="blk_wrap"><table>(.*)</table></div>', str(page_content))
    # Get table headers
    table_headers = re.findall('<th>(.*?)</th>', str(table_content))
    # ### Get table rows (table body, 也就是赛程表)
    table_body = re.findall('<tbody>(.*?)</tbody>', str(table_content))
    # There are 2 tables. We only want the first table, second table is irrelevant.
    table_body_str = table_body[0]
    # get rid of invalid character
    table_body_str = table_body_str.replace(u'\xa0', ' ')
    # get all table cells
    table_cells = re.findall('<td>(.*?)</td>', table_body_str)
    # get rid of spaces
    table_cells = list(map(lambda x: x.strip(), table_cells))
    # get actual text
    table_cells_txt = list(map(lambda x: re.findall('<a.*?>(.*)</a>', x)[0].strip() if '<a' in x else x, table_cells))
    # get all the links
    table_cells_links = list(
        map(lambda x: re.findall('<a href="(.*?)" target="_blank">', x)[0].strip() if '<a' in x else None, table_cells))
    # Save data as schedule table
    table_cells_txt = np.reshape(table_cells_txt, [-1, 10]).tolist()
    table_cells_links = np.reshape(table_cells_links, [-1, 10]).tolist()
    df_schedule_text = pd.DataFrame(data=table_cells_txt, columns=table_headers)
    df_schedule_links = pd.DataFrame(data=table_cells_links, columns=[header + '_link' for header in table_headers])

    df_schedule_full = pd.merge(df_schedule_text, df_schedule_links, left_index=True, right_index=True)
    # remove columns that are all None
    df_schedule_full.dropna(axis=1, how='all', inplace=True)

    # (Later we'll use beitai's game ID) id consists of season and a 5-digit label of the game
    # e.g. 2019-2020 season, game No.1 = 2019202000001
    # Label is generated by unique http address of the game stats
    uid_column = ['20192020' + f'{item + 1:05d}' for item in pd.factorize(df_schedule_full['统计_link'])[0].tolist()]
    df_schedule_full['UID'] = uid_column
    # 从轮次中提取出数字
    df_schedule_full['轮次'] = df_schedule_full['轮次'].apply(lambda x: int(re.findall('(\d+)', x)[0]))
    print(f'所有赛程、数据统计链接将会存在 {output_path}.')
    df_schedule_full.to_csv(output_path, index=False)
    print(f'所有赛程、数据统计链接已保存在 {output_path}.')


# ------------------------------------------------------------------------------------------------------------------------------
# ## Details Page

# ###  主队统计数据

# ### Todo:
# * 从game_schedule表内加上队伍名称，比赛ID
# * save as json?? df_schedule_full[:3].to_json(force_ascii=False,orient='index')


def get_team_details(page_content_str, re_pattern):
    team_details = re.findall(re_pattern, page_content_str)[0]
    return team_details


def get_table_coach(team_details):
    coach = re.findall('主教练：(.*?)领队', team_details)[0].replace('\xa0', '')
    return coach


def get_table_lingdui(team_details):
    lingdui = re.findall('领队：(.*?)<', team_details)[0].replace('\xa0', '')
    return lingdui


def get_table_headers(team_details):
    team_table_str = re.findall('<table>(.*?)</table>', team_details)[0]
    team_table_header_str = re.findall('<thead>(.*?)</thead>', team_table_str)[0]
    team_table_header_lst = re.findall('<th>(.*?)</th>', team_table_header_str)
    return team_table_header_lst


def clean_cells(cell_data):
    if '<a' in cell_data:
        cell_data = re.findall('<a.*?>(.*?)</a>', cell_data)[0]
    if 'document.write' in cell_data:
        try:
            cell_data = re.findall('[(]"(\d*)"[)]', cell_data)[0]
        except IndexError:
            cell_data = re.findall('[(]"(\d*/\d)"[)]', cell_data)[0]
    cell_data = re.sub('\s', '', cell_data)
    cell_data = re.sub('是', '1', cell_data)
    cell_data = re.sub('否', '0', cell_data)
    return cell_data


def get_table_cells(team_details, headers_count):
    team_table_str = re.findall('<table>(.*?)</table>', team_details)[0]
    team_table_cells_str = re.findall('<tbody style="">(.*?)</tbody>', team_table_str)[0]
    team_table_cells_lst = re.findall('<td>(.*?)</td>', team_table_cells_str)
    team_table_cells_lst = list(map(clean_cells, team_table_cells_lst))
    team_table_cells_lst = np.reshape(team_table_cells_lst, (-1, headers_count)).tolist()
    return team_table_cells_lst


def get_hometeam_stats(page_content_str, re_pattern='<div class="part part01 blk">(.*?)<div class="part part02 blk">'):
    hometeam_details = get_team_details(page_content_str, re_pattern)

    hometeam_coach = get_table_coach(hometeam_details)
    hometeam_lingdui = get_table_lingdui(hometeam_details)

    hometeam_table_header_lst = get_table_headers(hometeam_details)
    hometeam_table_cells_lst = get_table_cells(hometeam_details, len(hometeam_table_header_lst))

    df_hometeam_details = pd.DataFrame(data=hometeam_table_cells_lst, columns=hometeam_table_header_lst)
    return df_hometeam_details


def get_awayteam_stats(page_content_str, re_pattern='<div class="part part02 blk">(.*?)<div class="part part03 blk">'):
    awayteam_details = get_team_details(page_content_str, re_pattern)

    awayteam_coach = get_table_coach(awayteam_details)
    awayteam_lingdui = get_table_lingdui(awayteam_details)

    awayteam_table_header_lst = get_table_headers(awayteam_details)
    awayteam_table_cells_lst = get_table_cells(awayteam_details, len(awayteam_table_header_lst))

    df_awayteam_details = pd.DataFrame(data=awayteam_table_cells_lst, columns=awayteam_table_header_lst)
    return df_awayteam_details


def split_made_attempt(df_orig):
    df = df_orig.copy()
    for col_name in list(filter(lambda x: '-' in x, df.columns.tolist())):
        orig_col = col_name
        col_made = re.findall('(.*)中-投', col_name)[0] + '中'
        col_attempt = re.findall('(.*)中-投', col_name)[0] + '投'
        df[[col_made, col_attempt]] = df[orig_col].str.split('-', expand=True)
        df[col_attempt] = df[col_attempt].apply(lambda x: re.sub('[(].*[)]', '', x))
        df.drop(columns=orig_col, inplace=True)
    return df


def scrape_game_details(input_file, output_file):
    # # Loop and Scrape
    print(f'从{input_file}读取所有赛程、数据统计链接')
    df_schedule = pd.read_csv(input_file)
    print('读取完毕')
    df_list = []
    for index, row in df_schedule.iterrows():
        game_UID = row['UID']
        game_hteam_name = row['主队']
        game_ateam_name = row['客队']
        base_url = row['统计_link']
        page_content_str = get_page_content(base_url, encoding='GB2312')

        # Get home team stats
        df_home = get_hometeam_stats(page_content_str=page_content_str)
        df_home['Game_ID'] = game_UID
        df_home['球队'] = game_hteam_name
        df_home['对手'] = game_ateam_name
        df_list.append(df_home)

        # Get away team stats
        df_away = get_awayteam_stats(page_content_str=page_content_str)
        df_away['Game_ID'] = game_UID
        df_away['球队'] = game_ateam_name
        df_away['对手'] = game_hteam_name  # use to get opponents stats
        df_list.append(df_away)
        print('抓取比赛 ', row['UID'], ' ', row['主队'], ' ', row['客队'], ' ', datetime.datetime.now())

        # pause for a few seconds to avoid getting banned
        time.sleep(np.random.rand() * 10)
    games_stats = pd.concat(df_list, ignore_index=True)
    # remove team stats
    if 2 * len(games_stats['Game_ID'].unique()) == len(games_stats.loc[games_stats['号码'] == '--']):
        games_stats.drop(games_stats.loc[games_stats['号码'] == '--'].index, inplace=True)

    games_stats = split_made_attempt(games_stats)
    print(f'各场比赛详细数据保存在output_file')
    games_stats.to_csv(output_file, encoding='UTF-8', index=False)
