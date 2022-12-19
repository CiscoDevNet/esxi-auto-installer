# VMware Auto-Installer functions
from config import *

from os import system, path, listdir
import time
import logging
import sqlite3 as sl

def generate_jobid(cimcip='no_ip_address_provided'):
    """
    Return jobid in format cimcip_timestamp, eg. 192.168.1.111_1617701465.718063

    :param cimcip: (str) CIMC IP or MAC address
    :return: jobid (str)
    """
    return cimcip.replace(':','-') + '_' + str(time.time())


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


def eaidb_create_job_entry(jobid, hostname, ipaddr, root_pwd, cimcip, cimcusr, cimcpwd, macaddr, netmask, gateway, eaidb=EAIDB):
    """
    Create new entry in EAIDB database EAISTATUS table.

    :param jobid: (str) jobid
    :param hostname: (str) ESXi server hostname
    :param eaidb: (str) sqlite3 DB filename
    :return: n/a
    """

    con = sl.connect(eaidb)

    # set values
    start_time = time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime())
    finish_time = ''
    status = 'Ready to deploy'

    # create new DB record
    with con:
        sql = 'INSERT INTO EAISTATUS (jobid, hostname, ipaddr, root_pwd, cimcip, start_time, finish_time, status, cimcusr, cimcpwd, macaddr, netmask, gateway) ' \
              'values(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
        data = (jobid, hostname, ipaddr, root_pwd, cimcip, start_time, finish_time, status, cimcusr, cimcpwd, macaddr, netmask, gateway)
        con.execute(sql, data)


def eaidb_update_job_status(jobid, status, logger, finished=False, eaidb=EAIDB):
    """
    Update 'status' and 'finish_time' columns in EAISTATUS table for 'jobid'.

    :param jobid: (str) job ID
    :param status:
    :param logger:
    :param finished:
    :param eaidb:
    :return:
    """

    # Setup DB Query
    sql = 'UPDATE EAISTATUS SET'
    if finished:
        sql += ' status=?, finish_time=?, root_pwd=?, cimcpwd=?'
        data = (status, time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime()), '', '', jobid)
    else:
        sql += ' status=?, finish_time=?'
        data = (status, '', jobid)

    sql += ' WHERE jobid=?'

    global dbcon
    # Verify DB is connected.
    try:
        dbcon.cursor()
    except:
        print('Creating new connection to DB.')
        dbcon = sl.connect(eaidb)

    # write changes to database
    with dbcon:
        dbcon.execute(sql, data)

    logger.info(f"Job Status has been updated to: {status}")
    if finished:
        logger.info(f'Installation job (ID: {jobid}) finished.')


def eaidb_get_status(eaidb=EAIDB):
    """
    Get all entries from EAISTATUS table, without cimcusr and cimcpwd

    :param eaidb: sqlite3 database filename
    :return: dict of table rows with columns as fields:
        jobid (str) {
        hostname (str),
        ipaddr (str),
        cimcip (str),
        start_time (str),
        finish_time (str),
        status (str),
        macaddr (str),
        netmask (str),
        gateway (str)
        }
    """
    con = sl.connect(eaidb)
    eaidb_dict = {}
    with con:
        for columns in con.execute("SELECT jobid, hostname, ipaddr, cimcip, start_time, finish_time, status, macaddr, netmask, gateway FROM EAISTATUS"):
            eaidb_dict[columns[0]] = {}
            eaidb_dict[columns[0]]['hostname'] = columns[1]
            eaidb_dict[columns[0]]['ipaddr'] = columns[2]
            eaidb_dict[columns[0]]['cimcip'] = columns[3]
            eaidb_dict[columns[0]]['start_time'] = columns[4]
            eaidb_dict[columns[0]]['finish_time'] = columns[5]
            eaidb_dict[columns[0]]['status'] = columns[6]
            eaidb_dict[columns[0]]['macaddr'] = columns[7]
            eaidb_dict[columns[0]]['netmask'] = columns[8]
            eaidb_dict[columns[0]]['gateway'] = columns[9]
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
        for cimc_data in con.execute(f"SELECT cimcip, cimcusr, cimcpwd FROM EAISTATUS WHERE jobid is ?;", (jobid,)):
            cimcip = cimc_data[0]
            cimcusr = cimc_data[1]
            cimcpwd = cimc_data[2]
    return cimcip, cimcusr, cimcpwd

def eaidb_check_jobid_exists(jobid, eaidb=EAIDB):
    """
    Check if job ID exists in EAIDB.

    :param jobid: (str) job ID
    :param eaidb: sqlite3 database filename
    :return: (bool) True if job ID found in EAIDB
    """
    con = sl.connect(eaidb)
    with con:
        if con.execute(f"SELECT jobid FROM EAISTATUS WHERE jobid=?;", (jobid,)).fetchone() is not None:
            return True
        else:
            return False

def eaidb_get(jobid, fields):
    global dbcon
    global allowed_fields
    # Verify DB is connected.
    try:
        dbcon.cursor()
    except:
        print('Creating new connection to DB.')
        dbcon = sl.connect(EAIDB)

    if 'allowed_fields' not in globals():
        allowed_fields = [columns[1] for columns in dbcon.execute("PRAGMA table_info(EAISTATUS)")]
    # check fields
    if type(fields) is not tuple:
        raise Exception("Fields must be an array of type tuple.")
    for field in fields:
        if field not in allowed_fields:
            raise Exception("field supplied was not a valid table column.")
    eaidb_dict = {}
    for columns in dbcon.execute(f"SELECT {', '.join(fields)} FROM EAISTATUS WHERE jobid=?", (jobid,)):
        i = 0
        for field in fields:
            eaidb_dict[field] = columns[i]
            i+=1
    # Decrypt encrypted fields here.
    return eaidb_dict

def eaidb_set(jobid, fieldsdict, eaidb=EAIDB):
    """
    Remove (i.e. replace with empty string) ESXi password from EAIDB for specific job ID.

    :param jobid: (str) job ID
    :param eaidb: sqlite3 database filename
    :return: n/a
    """
    if type(fieldsdict) is not dict:
        raise Exception("fieldsdict must be a dictionary object.")
    global dbcon
    try:
        dbcon.cursor()
    except:
        print('Creating new connection to DB.')
        dbcon = sl.connect(eaidb)

    fields = [item for item in fieldsdict.keys()]
    data = tuple([item for item in fieldsdict.values()])
    with dbcon:
        sql = f'UPDATE EAISTATUS SET {"=?, ".join(fields)}=? WHERE jobid=?'
        dbcon.execute(sql, data + (jobid,))

# eaidb_get('00-50-56-ad-f3-ee_1666105104.5060387', ('ipaddr', 'root_pwd', 'hostname'))
