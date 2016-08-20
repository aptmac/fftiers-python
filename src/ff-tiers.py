__author__ = 'joelwhitney'
'''
A clustering program that uses FantasyPros data inspired by Boris Chen (http://www.borischen.co/)
This program utilizes unsupervised machine learning by flat clustering with KMeans -- a simple way
to uncover like tiers within the player data mined from FantasyPros (http://www.fantasypros.com/)

To Do's
-Comment/clean code
-Improve plot output
-Add logging and improved cmd line stuff
-Add sms alert when graph updated (pass/fail)

Big picture
-Make the script run continuously once a day from Raspberry Pi
  -Add local v Pi run option (save locations will differ)
  -Upload plots to site root folder
-Make this program work with NHL data for Fantasy Hockey
'''
import argparse
import traceback
import os
import logging
import logging.handlers
import datetime
import sys
import csv
import numpy as np
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt
from matplotlib.pyplot import cm
from matplotlib import style
style.use("ggplot")
import requests
from lxml import html


def initialize_logging(logFile):
    """
    setup the root logger to print to the console and log to file
    :param logFile: string log file to write to
    """
    formatter = logging.Formatter("[%(asctime)s] [%(filename)30s:%(lineno)4s - %(funcName)30s()]\
         [%(threadName)5s] [%(name)10.10s] [%(levelname)8s] %(message)s")  # The format for the logs
    logger = logging.getLogger()  # Grab the root logger
    logger.setLevel(logging.DEBUG)  # Set the root logger logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    # Create a handler to print to the console
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    sh.setLevel(logging.DEBUG)
    # Create a handler to log to the specified file
    rh = logging.handlers.RotatingFileHandler(logFile, mode='a', maxBytes=10485760)
    rh.setFormatter(formatter)
    rh.setLevel(logging.DEBUG)
    # Add the handlers to the root logger
    logger.addHandler(sh)
    logger.addHandler(rh)


def verify_file_path(filePath):
    """
    verify file exists
    :param filePath: the joined directory and file name
    :return: Boolean: True if file exists
    """
    logger = logging.getLogger()
    ospath = os.path.abspath(filePath)
    ospath = ospath.replace("\\","\\\\")
    logger.debug("Evaluating if {} exists...".format(ospath))
    if not os.path.isfile(str(ospath)):
        logging.getLogger().critical("File not found: {}".format(filePath))
        return False
    else:
        return True


def csv_from_excel(full_file_name):
    """
    converts old xls to csv using this roundabout method
    TODO's: comment
    :param full_file_name: downloaded xls file name
    """
    logger = logging.getLogger()
    with open(full_file_name, 'r') as xlsfile, open(full_file_name[:-4] + '.csv', 'w', newline="\n", encoding="utf-8") as csv_file:
        xls_reader = csv.reader(xlsfile, delimiter='\t')
        csv_writer = csv.writer(csv_file)
        for i in range(5):
            next(xls_reader, None)
        for row in xls_reader:
            csv_writer.writerow(row)


def get_nfl_week(start_week_date):
    """
    get the nfl_week
    TODO's: comment
    :param start_week_date: date object for Tuesday before 1st Thursday game
    :return: week: integer
    """
    logger = logging.getLogger()
    week = 0
    today_date = datetime.datetime.now().date()
    if today_date >= start_week_date:
        difference_days = today_date - start_week_date
        week = int((difference_days.days / 7) + 1)
        return week
    else:
        return week


def download_nfl_data(args, week, position_list):
    """
    download xls file from fantasy pros to the data_directory specified above
    TODO's: comment, clean up code
    :param args: list of parameters can be used to get data directories
    :param week: integer week to be used when building file names
    :param position_list: list of positions to download, also used to build file names
    """
    logger = logging.getLogger()
    download_data = args.download_data
    username, password, token = args.username, args.password, args.token
    if download_data == "True":
        data_directory = args.data_directory
        if week == 0:
            preseason_rankings = ['https://www.fantasypros.com/nfl/rankings/consensus-cheatsheets.php?export=xls',
                                  'https://www.fantasypros.com/nfl/rankings/qb-cheatsheets.php?export=xls',
                                  'https://www.fantasypros.com/nfl/rankings/rb-cheatsheets.php?export=xls',
                                  'https://www.fantasypros.com/nfl/rankings/wr-cheatsheets.php?export=xls',
                                  'https://www.fantasypros.com/nfl/rankings/te-cheatsheets.php?export=xls',
                                  'https://www.fantasypros.com/nfl/rankings/k-cheatsheets.php?export=xls',
                                  'https://www.fantasypros.com/nfl/rankings/dst-cheatsheets.php?export=xls']
            preseason_rankings_names = ['week-0-preseason-overall-raw.xls',
                                        'week-0-preseason-qb-raw.xls', 'week-0-preseason-rb-raw.xls',
                                        'week-0-preseason-wr-raw.xls', 'week-0-preseason-te-raw.xls',
                                        'week-0-preseason-k-raw.xls', 'week-0-preseason-dst-raw.xls']
            for item_position in range(len(preseason_rankings)):
                full_file_name = os.path.join(data_directory, preseason_rankings_names[item_position])
                url = preseason_rankings[item_position]
                payload = {
                    "username": username,
                    "password": password,
                    "csrfmiddlewaretoken": token
                }
                session_requests = requests.session()
                login_url = "https://secure.fantasypros.com/accounts/login/?"
                result = session_requests.get(login_url)
                tree = html.fromstring(result.text)
                authenticity_token = list(set(tree.xpath("//input[@name='csrfmiddlewaretoken']/@value")))[0]
                payload["csrfmiddlewaretoken"] = authenticity_token
                session_requests.post(
                    login_url,
                    data=payload,
                    headers=dict(referer=login_url)
                )
                with open(full_file_name, 'wb') as handle:
                    response = session_requests.get(url)
                    if not response.ok:
                        # Something went wrong
                        pass
                    for block in response.iter_content(1024):
                        handle.write(block)

                csv_from_excel(full_file_name)
        else:
            for position in position_list:
                filename = 'week-' + str(week) + '-' + position + '-raw.xls'
                full_file_name = os.path.join(data_directory, filename)

                url = 'http://www.fantasypros.com/nfl/rankings/' + position + '.php?export=xls'
                payload = {
                    "username": "whitneyjb5",
                    "password": "999jbw",
                    "csrfmiddlewaretoken": "reiHrx0n5o7YstOIFsZ5Gj29UVuuC80z"
                }
                session_requests = requests.session()
                login_url = "https://secure.fantasypros.com/accounts/login/?next=http://www.fantasypros.com/index.php?"
                result = session_requests.get(login_url)
                tree = html.fromstring(result.text)
                authenticity_token = list(set(tree.xpath("//input[@name='csrfmiddlewaretoken']/@value")))[0]
                payload["csrfmiddlewaretoken"] = authenticity_token
                session_requests.post(
                    login_url,
                    data=payload,
                    headers=dict(referer=login_url)
                )
                with open(full_file_name, 'wb') as handle:
                    response = session_requests.get(url)
                    if not response.ok:
                        # Something went wrong
                        pass
                    for block in response.iter_content(1024):
                        handle.write(block)
                if verify_file_path(full_file_name):
                    csv_from_excel(full_file_name)
                else:
                    logger.info("XLS file not found for: {} - Week {}. Skipping position...".format(position, week))


def get_position_setting(position, settings):
    """
    returns the max number of players to show and the k-value for clusters
    TODO's: comment, build in preseason stuff here (see plot() TODO)
    :param position: string position of setting you want
    :param settings: list of dictionaries of settings
    :return: max_num, k_val: positional settings for plotting
    """
    logger = logging.getLogger()
    for dict in settings:
        if str(dict.get('pos')).lower() == str(position).lower():
            max_num = dict.get('max_num')
            k_val = dict.get('k_val')
    return max_num, k_val


def lists_from_csv(position, week, data_directory):
    """
    builds lists from the csv to be used in the graphing
    TODO's: comment
    :param position: string position used for building csv name
    :param week: integer week used for building csv name
    :param data_directory: string data directory used for building csv name
    :return: rank_list, name_list, position_list, average_rank_list, standard_deviation_list: lists of data
    """
    logger = logging.getLogger()
    rank_list = []
    name_list = []
    position_list = []
    average_rank_list = []
    standard_deviation_list = []
    filename = 'week-' + str(week) + '-' + position + '-raw.csv'
    full_file_name = os.path.join(data_directory, filename)
    print(full_file_name)
    if verify_file_path(full_file_name):
        with open(full_file_name, 'r') as csv_file:
            csv_reader = csv.reader(csv_file)
            for row in csv_reader:
                logger.info(row)
                rank_list.append(int(row[0]))
                name_list.append(str(row[1]))
                if position == 'preseason-overall':
                    position_list.append(str(row[2]))
                    average_rank_list.append(float(row[7]))
                    standard_deviation_list.append(float(row[8]))
                else:
                    position_list.append(str(position))
                    average_rank_list.append(float(row[6]))
                    standard_deviation_list.append(float(row[7]))
        return rank_list, name_list, position_list, average_rank_list, standard_deviation_list
    else:
        logger.info("CSV file not found for: {} - Week {}. Skipping position...".format(position, week))


def get_cluster_settings(week):
    """
    helper function for geting the parameters needed for plotting
    TODO's: comment, rethink this piece (maybe just return based on position instead of whole list
    :param week: int week used for getting right settings
    :return: type_cluster_settings and ros_settings: list of dictionaries with the appropiate settings
    """
    logger = logging.getLogger()
    # preseason clustering settings
    preseason_cluster_settings = [{'pos': 'preseason-overall', 'plot1': 70, 'k_val_1': 10, 'plot2': 70, 'k_val_2': 8, 'plot3': 70, 'k_val_3': 8},
                                  {'pos': 'preseason-qb', 'max_num': 24, 'k_val': 8},
                                  {'pos': 'preseason-rb', 'max_num': 40, 'k_val': 9},
                                  {'pos': 'preseason-wr', 'max_num': 60, 'k_val': 12},
                                  {'pos': 'preseason-te', 'max_num': 24, 'k_val': 8},
                                  {'pos': 'preseason-flex', 'max_num': 80, 'k_val': 14},
                                  {'pos': 'preseason-k', 'max_num': 24, 'k_val': 5},
                                  {'pos': 'preseason-dst', 'max_num': 24, 'k_val': 6}]

    # positional clustering settings
    weekly_pos_cluster_settings = [{'pos': 'qb', 'max_num': 24, 'k_val': 8},
                                   {'pos': 'rb', 'max_num': 40, 'k_val': 9},
                                   {'pos': 'wr', 'max_num': 60, 'k_val': 12},
                                   {'pos': 'te', 'max_num': 24, 'k_val': 8},
                                   {'pos': 'flex', 'max_num': 80, 'k_val': 14},
                                   {'pos': 'k', 'max_num': 24, 'k_val': 5},
                                   {'pos': 'dst', 'max_num': 24, 'k_val': 6}]
    # rest of season clustering settings
    ros_pos_cluster_settings = [{'pos': 'ros-qb', 'max_num': 32, 'k_val': 7},
                                {'pos': 'ros-rb', 'max_num': 50, 'k_val': 12},
                                {'pos': 'ros-wr', 'max_num': 64, 'k_val': 65/5},
                                {'pos': 'ros-te', 'max_num': 30, 'k_val': 7},
                                {'pos': 'ros-k', 'max_num': 20, 'k_val': 5},
                                {'pos': 'ros-dst', 'max_num': 25, 'k_val': 5}]
    # get cluster settings
    if week == 0:
        type_cluster_settings = preseason_cluster_settings
        ros_settings = ros_pos_cluster_settings
    elif week > 0:
        type_cluster_settings = weekly_pos_cluster_settings
        ros_settings = ros_pos_cluster_settings
    return type_cluster_settings, ros_settings


def plot(position, week, args):
    """
    the first stage of the plotting that prepares the data to then be cluster_and_plot'ed
    TODO's: comment, utilize get_position_settings for preseason data
    :param position: string position used for getting data and position settings for the plotting
    :param week: integer week used for getting data
    :param args: list of parameters can be used to get data and plot directories
    """
    logger = logging.getLogger()
    filename = 'week-' + str(week) + '-' + position + '-raw.png'
    plots_directory = args.plots_directory
    plot_full_file_name = os.path.join(plots_directory, filename)
    data_directory = args.data_directory
    # get the cluster settings
    type_cluster_settings, ros_cluster_settings = get_cluster_settings(week)
    # get preseason settings
    if week == 0:
        rank_list, name_list, position_list, average_rank_list, standard_deviation_list = lists_from_csv(position, week=week, data_directory=data_directory)
        # split lists for pos == overall
        if position == 'preseason-overall':
            for dict in type_cluster_settings:
                if dict.get('pos') == 'preseason-overall':
                    start1, stop1 = 0, 0 + dict.get('plot1')
                    start2 = stop1 + 1
                    stop2 = start2 + dict.get('plot2')
                    start3 = stop2 + 1
                    stop3 = start3 + dict.get('plot3')
                    rank_list_1, name_list_1, position_list1, average_rank_list_1, standard_deviation_list_1 = rank_list[start1: stop1], \
                                                                                                               name_list[start1: stop1], \
                                                                                                               position_list[start1: stop1], \
                                                                                                               average_rank_list[start1: stop1], \
                                                                                                               standard_deviation_list[start1: stop1]
                    rank_list_2, name_list_2, position_list2, average_rank_list_2, standard_deviation_list_2 = rank_list[start2: stop2], \
                                                                                                               name_list[start2: stop2], \
                                                                                                               position_list[start2: stop2], \
                                                                                                               average_rank_list[start2: stop2], \
                                                                                                               standard_deviation_list[start2: stop2]
                    rank_list_3, name_list_3, position_list3, average_rank_list_3, standard_deviation_list_3 = rank_list[start3: stop3], \
                                                                                                               name_list[start3: stop3], \
                                                                                                               position_list[start3: stop3], \
                                                                                                               average_rank_list[start3: stop3], \
                                                                                                               standard_deviation_list[start3: stop3]
                    k_value_1, k_value_2, k_value_3 = dict.get('k_val_1'), \
                                                      dict.get('k_val_2'), \
                                                      dict.get('k_val_3')
                    list_of_lists1 = [[rank_list_1, name_list_1, position_list1, average_rank_list_1, standard_deviation_list_1, k_value_1],
                                     [rank_list_2, name_list_2, position_list2, average_rank_list_2, standard_deviation_list_2, k_value_2],
                                     [rank_list_3, name_list_3, position_list3, average_rank_list_3, standard_deviation_list_3, k_value_3]]
                    cluster_and_plot(list_of_lists1, plot_full_file_name)
        else:
            max_number, k_value = get_position_setting(position, type_cluster_settings)
            rank_list, name_list, position_list, average_rank_list, standard_deviation_list = rank_list[0:max_number], \
                                                                                              name_list[0:max_number], \
                                                                                              position_list[0:max_number], \
                                                                                              average_rank_list[0:max_number], \
                                                                                              standard_deviation_list[0:max_number]
            list_of_lists2 = [[rank_list, name_list, position_list, average_rank_list, standard_deviation_list, k_value]]
            cluster_and_plot(list_of_lists2, plot_full_file_name)
    else:
        # get settings for weekly plots
        max_number, k_value = get_position_setting(position, type_cluster_settings)
        rank_list, name_list, position_list, average_rank_list, standard_deviation_list = lists_from_csv(position, week=week, data_directory=data_directory)
        list_of_lists = [[rank_list, name_list, position_list, average_rank_list, standard_deviation_list, k_value]]
        cluster_and_plot(list_of_lists, plot_full_file_name)


def cluster_and_plot(list_of_lists, plot_full_file_name):
    """
    the second stage of the plotting that clusters and plots the data
    TODO's: comment, format graph
    :param list_of_lists: list of lists that has the pertinent plotting data
    :param plot_full_file_name: the file name of the plot to be saved
    """
    list_count = 1
    plot_file_name = plot_full_file_name[:-4]
    for list in list_of_lists:
        plot_full_file_name = plot_file_name + '-{}.png'.format(list_count)
        init_list_array = []
        rank_list, name_list, position_list, average_rank_list, standard_deviation_list, k_value = list[0], list[1], list[2], list[3], list[4], list[5]
        for n in range(len(average_rank_list)):
            item_list = [average_rank_list[n]]
            init_list_array.append(item_list)
        X = np.array(init_list_array)
        kmeans = KMeans(n_clusters=k_value)
        kmeans.fit(X)
        # find the centroids and label each cluster
        centroids = kmeans.cluster_centers_
        labels = kmeans.labels_
        # set up color list that will automatically cycle through
        colors = []
        color_cycle = iter(cm.rainbow(np.linspace(0, 5, len(labels))))
        for i in range(len(labels)):
            c = next(color_cycle)
            colors.append(c)
        for i in range(len(X)):
            plt.errorbar(X[i][0], rank_list[i], xerr=standard_deviation_list[i], marker='.', markersize=4, color=colors[labels[i]], ecolor=colors[labels[i]])
            position = position_list[i][10:].upper() if len(position_list[i]) > 10 else position_list[i].upper()
            plt.text(X[i][0] + standard_deviation_list[i] + 1, rank_list[i], "{} {} ({})".format(name_list[i], position, rank_list[i]), size=6, color=colors[labels[i]],
                     ha="left", va="center")
        plt.gca().invert_yaxis()
        # plt.show()
        plt.savefig(plot_full_file_name, bbox_inches='tight')
        plt.clf()
        list_count += 1


def main(args):
    logger = logging.getLogger()
    # downloading settings
    position_list = ['qb', 'rb', 'wr', 'te', 'flex', 'k', 'dst']
    start_week_date = datetime.date(2016, 9, 6)
    injured_player_list = []
    # get week and download the data
    week = get_nfl_week(start_week_date)
    print(week)
    if week == 0:
        position_list.remove('flex')
        position_list.insert(0, 'overall')
        download_nfl_data(args, week, position_list)
        for pos in position_list:
            preseason_pos = 'preseason-{}'.format(pos)
            plot(preseason_pos, week, args)
    else:
        download_nfl_data(args, week, position_list)
        for pos in position_list:
            plot(pos, week, args)


if __name__ == "__main__":    # get all of the commandline arguments
    parser = argparse.ArgumentParser("FantasyPros clustering program")
    # required parameters
    parser.add_argument('-u', dest='username', help="FantasyPros username", required=True)
    parser.add_argument('-p', dest='password', help="FantasyPros password", required=True)
    parser.add_argument('-t', dest='token', help="FantasyPros token", required=True)
    # optional parameters
    parser.add_argument('-down', dest='download_data', help="Boolean for if script should download data", default="True")
    parser.add_argument('-dat', dest='data_directory', help="The directory where the data is downloaded", default="data/fftiers/2016/")
    parser.add_argument('-plot', dest='plots_directory', help="The directory where the plots are saved", default="plots/fftiers/2016/")
    # required for logging
    parser.add_argument('-logFile', dest='logFile', help='The log file to use', default="log.txt")
    args = parser.parse_args()
    initialize_logging(args.logFile)
    try:
        main(args)
    except Exception as e:
        logging.getLogger().critical("Exception detected, script exiting")
        print(e)
        logging.getLogger().critical(e)
        logging.getLogger().critical(traceback.format_exc().replace("\n"," | "))