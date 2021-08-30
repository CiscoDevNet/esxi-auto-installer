# VMware Auto-Installer functions
from config import *

from os import system, path, listdir
import time
import logging
import sqlite3 as sl



def generate_jobid(cimcip='no_ip_address_provided'):
    """
    Return jobid in format cimcp_timestamp, eg. 192.168.1.111_1617701465.718063

    :param cimcip: (str)
    :return: jobid (str)
    """
    return cimcip + '_' + str(time.time())


def check_service_status(service_name):
    return_code = system('/usr/bin/systemctl status ' + service_name + '>/dev/null')
    if return_code == 0:
        service_status = 'Running.'
    else:
        service_status = 'Stopped. Check details.'
    return service_status


def format_message_for_web(message):
    # remove '<' and '>' from string as it renders issues when displayed in web browser
    return str(message).replace('<', '"').replace('>', '"')


def get_jobid_logger(jobid=generate_jobid(), logdir=LOGDIR):
    """
    Create logger per jobid.

    :param jobid: (str) should be generated based on CIMC IP, otherwise 'no_ip_address_provided' string is used
    :param logdir: (str) dafault LOGDIR configured in config.py
    :return: logger handle
    """

    # Get/create a logger
    logger = logging.getLogger(jobid.replace('.','_'))
    # TODO: remove debugging code
    # print(f'[DEBUG] Configuring job logger: {logger}, PID: {os.getpid()}')

    if not logger.hasHandlers():
        # set log level
        logger.setLevel(logging.DEBUG)
        # define file handler and set formatter
        log_file = os.path.join(logdir, jobid)
        file_handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S %Z')
        file_handler.setFormatter(formatter)
        # add file handler to logger
        logger.addHandler(file_handler)
    return logger


def get_main_logger(log_file=EAILOG):
    """
    Create logger per jobid.

    :param logdir: (str) dafault LOGDIR configured in config.py
    :return: logger handle
    """

    # Get/create main application logger
    main_logger = logging.getLogger('main')
    # TODO: remove debugging code
    # print(f'[DEBUG] Configuring main logger: {main_logger}, PID: {os.getpid()}')
    # set log level
    main_logger.setLevel(logging.DEBUG)
    # define formatter
    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(funcName)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S %Z')

    if not main_logger.hasHandlers():
        # configure logging to log file (define file handler and set formatter)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        # add file handler to logger
        main_logger.addHandler(file_handler)

        # configure logging to stderr (define handler and set formatter)
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        main_logger.addHandler(console)

    # return logger handler
    return main_logger


def eaidb_create_job_entry(jobid, timestamp, hostname, ipaddr, cimcip, cimcusr, cimcpwd, eaidb=EAIDB):
    """
    Create new entry in EAIDB database EAISTATUS table.

    :param jobid: (str) jobid
    :param timestamp: (str) current time
    :param hostname: (str) ESXi server hostname
    :param eaidb: (str) sqlite3 DB filename
    :return: n/a
    """

    con = sl.connect(eaidb)

    # set values
    start_time = timestamp
    finish_time = ''
    status = 'Ready to deploy'

    # create new DB record
    with con:
        sql = 'INSERT INTO EAISTATUS (jobid, hostname, ipaddr, cimcip, start_time, finish_time, status, cimcusr, cimcpwd) ' \
              'values(?, ?, ?, ?, ?, ?, ?, ?, ?)'
        data = (jobid, hostname, ipaddr, cimcip, start_time, finish_time, status, cimcusr, cimcpwd)
        con.execute(sql, data)


def eaidb_update_job_status(jobid, status, finish_time, eaidb=EAIDB):
    """
    Update 'status' and 'finish_time' columns in EAISTATUS table for 'jobid'.

    :param jobid: (str) job ID
    :param status:
    :param finish_time:
    :param eaidb:
    :return:
    """
    con = sl.connect(eaidb)

    # write changes to database
    sql = 'UPDATE EAISTATUS SET finish_time=?, status = ? WHERE jobid=?'
    data = (finish_time, status, jobid)
    with con:
        con.execute(sql, data)

def eaidb_get_status(eaidb=EAIDB):
    """
    Get all entries from EAISTATUS table.

    :param eaidb: sqlite3 database filename
    :return: dict of table rows with columns as fields:
        jobid (str) {
        hostname (str),
        ipaddr (str),
        cimcip (str),
        start_time (str),
        finish_time (str),
        status (str) }
    """
    con = sl.connect(eaidb)
    eaidb_dict = {}
    with con:
        for row in con.execute("SELECT * FROM EAISTATUS"):
            eaidb_dict[row[0]] = {}
            eaidb_dict[row[0]]['hostname'] = row[1]
            eaidb_dict[row[0]]['ipaddr'] = row[2]
            eaidb_dict[row[0]]['cimcip'] = row[3]
            eaidb_dict[row[0]]['start_time'] = row[4]
            eaidb_dict[row[0]]['finish_time'] = row[5]
            eaidb_dict[row[0]]['status'] = row[6]
    return eaidb_dict


def eaidb_get_cimc_credentials(jobid, eaidb=EAIDB):
    """
    Get CIMC IP address and credentials for given jobid.

    :param jobid: (str) job ID
    :param eaidb: sqlite3 database filename
    :return: (tuple of str) cimcip, cimcusr, cimcpwd
    """
    con = sl.connect(eaidb)
    with con:
        for cimc_data in con.execute(f"SELECT cimcip, cimcusr, cimcpwd FROM EAISTATUS WHERE jobid is '{jobid}';"):
            cimcip = cimc_data[0]
            cimcusr = cimc_data[1]
            cimcpwd = cimc_data[2]
    return cimcip, cimcusr, cimcpwd


def eaidb_check_jobid_exists(jobid, eaidb=EAIDB):
    con = sl.connect(eaidb)
    with con:
        if con.execute(f"SELECT * FROM EAISTATUS WHERE jobid='{jobid}';").fetchone() is not None:
            return True
        else:
            return False