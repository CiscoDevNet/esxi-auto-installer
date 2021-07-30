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

### OBSOLETE FUNCTIONS ###

# def eaidb_create_job_entry(jobid, timestamp, hostname, ipaddr, cimcip, eaidb=EAIDB):
#     """
#     Create new entry in EAIDB database EAISTATUS table.
#
#     :param jobid: (str) jobid
#     :param timestamp: (str) current time
#     :param hostname: (str) ESXi server hostname
#     :param eaidb: (str) sqlite3 DB filename
#     :return: n/a
#     """
#
#     con = sl.connect(eaidb)
#
#     # set values
#     start_time = timestamp
#     finish_time = ''
#     status = 'Ready to deploy'
#
#     # create new DB record
#     with con:
#         sql = 'INSERT INTO EAISTATUS (jobid, hostname, ipaddr, cimcip, start_time, finish_time, status) ' \
#               'values(?, ?, ?, ?, ?, ?, ?)'
#         data = (jobid, hostname, ipaddr, cimcip, start_time, finish_time, status)
#         con.execute(sql, data)

# def eaidb_update_job_status(jobid, state, eaidb=EAIDB):
#     status_dict = {
#         '0': 'Ready to deploy',
#         '1': 'Installation in progress',
#         '2': 'Finished',
#         '3': 'Error',
#         '4': 'Mounting installation ISO',
#         '5': 'Connecting to CIMC'
#     }
#     con = sl.connect(eaidb)
#     if str(state) == '0':
#         # this state should be only set when creating DB entry - not doing anything here
#         return
#     elif str(state) == '1':
#         status = status_dict['1']
#         finish_time = ''
#     elif str(state) == '2':
#         finish_time = time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime())
#         status = status_dict['2']
#     elif str(state) == '3':
#         status = status_dict['3']
#         finish_time = time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime())
#     elif str(state) == '4':
#         status = status_dict['4']
#         finish_time = ''
#     elif str(state) == '5':
#         status = status_dict['5']
#         finish_time = ''
#     else:
#         print(f'State not valid: {state}')
#         return f'State not valid: {state}'
#
#     # write changes to database
#     sql = 'UPDATE EAISTATUS SET finish_time=?, status = ? WHERE jobid=?'
#     data = (finish_time, status, jobid)
#     with con:
#         con.execute(sql, data)

# def eaidb_get_status_list(eaidb=EAIDB):
#     """
#     Get all entries from EAISTATUS table.
#
#     :param eaidb: sqlite3 database filename
#     :return: list of table rows with columns as fields in the following order:
#         jobid (str),
#         hostname (str),
#         ipaddr (str),
#         cimcip (str),
#         start_time (str),
#         finish_time (str),
#         status (str)
#     """
#     con = sl.connect(eaidb)
#     eaidb_list = []
#     with con:
#         for row in con.execute("SELECT * FROM EAISTATUS"):
#             eaidb_list.append(row)
#     return eaidb_list


# def eaidb_create_job_entry(jobid, timestamp, hostname, ipaddr, cimcip, state, eaidb=EAIDB):
#     """
#     Update EAIDB database EAISTATUS table, according to current_task. If 'Start' is passed - create new entry,
#     otherwise update existing entry.
#
#     :param jobid: (str) jobid
#     :param timestamp: (str) current time
#     :param hostname: (str) ESXi server hostname
#     :param state: (str) current job status
#     :param eaidb: (str) sqlite3 DB filename
#     :return: n/a
#     """
#
#     con = sl.connect(eaidb)
#
#     # create new record if 'Start' in status
#     if 'Start' in state:
#         # set values
#         start_time = timestamp
#         finish_time = ''
#         status = 'Ready to deploy'
#         with con:
#             sql = 'INSERT INTO EAISTATUS (jobid, hostname, ipaddr, cimcip, start_time, finish_time, status) ' \
#                          'values(?, ?, ?, ?, ?, ?, ?)'
#             data = (jobid, hostname, ipaddr, cimcip, start_time, finish_time, status)
#             con.execute(sql, data)
#     elif 'Installation in progress' in state:
#         status = 'Installation in progress'
#         with con:
#             sql = 'UPDATE EAISTATUS SET status = ? WHERE jobid=?'
#             data = (status, jobid)
#             con.execute(sql, data)
#     elif 'Finish' in state:
#         finish_time = state
#         status = 'Finished'
#         with con:
#             sql = 'UPDATE EAISTATUS SET finish_time=?, status = ? WHERE jobid=?'
#             data = (finish_time, status, jobid)
#             con.execute(sql, data)
#         # print(f'{jobid} Finished running tasks')
#     elif 'Error' in state:
#         status = state
#         with con:
#             sql = 'UPDATE EAISTATUS SET status = ? WHERE jobid=?'
#             data = (status, jobid)
#             con.execute(sql, data)
#
#
# def eaidb_update_job_status(jobid, state, eaidb=EAIDB):
#     con = sl.connect(eaidb)
#     if 'Installation in progress' in state:
#         status = 'Installation in progress'
#         with con:
#             sql = 'UPDATE EAISTATUS SET status = ? WHERE jobid=?'
#             data = (status, jobid)
#             con.execute(sql, data)
#     elif 'Finish' in state:
#         finish_time = state
#         status = 'Finished'
#         with con:
#             sql = 'UPDATE EAISTATUS SET finish_time=?, status = ? WHERE jobid=?'
#             data = (finish_time, status, jobid)
#             con.execute(sql, data)
#         # print(f'{jobid} Finished running tasks')
#     elif 'Error' in state:
#         status = state
#         with con:
#             sql = 'UPDATE EAISTATUS SET status = ? WHERE jobid=?'
#             data = (status, jobid)
#             con.execute(sql, data)
#     else:
#         print(f'State not valid: {state}')
#         return f'State not valid: {state}'


# def save_install_data_to_db(hostname, mac, ipaddr, subnet, netmask, gateway, vlan, vmnic,
#                             enablessh, clearpart, rootpw, isover, status):
#     if path.isfile(VMAI_DB):
#         print('[INFO] ' + VMAI_DB + ' file exists - importing data and adding new entry:')
#         with open(VMAI_DB, 'r') as vmaidb_file:
#             vmaidb_dict = json.load(vmaidb_file)
#     else:
#         # this should not ever happen, but covering this 'just in case'
#         print('[INFO] ' + VMAI_DB + ' file DOES NOT exist - creating file and adding new entry')
#         vmaidb_dict = {}
#
#     # need to add checking of 'hostname' already exists ion VMAI_DB
#     vmaidb_dict[hostname] = {}
#     vmaidb_dict[hostname]['MAC'] = mac
#     vmaidb_dict[hostname]['IPADDR'] = ipaddr
#     vmaidb_dict[hostname]['SUBNET'] = subnet
#     vmaidb_dict[hostname]['NETMASK'] = netmask
#     vmaidb_dict[hostname]['GATEWAY'] = gateway
#     vmaidb_dict[hostname]['VLAN'] = vlan
#     vmaidb_dict[hostname]['VMNIC'] = vmnic
#     vmaidb_dict[hostname]['SSH'] = enablessh
#     vmaidb_dict[hostname]['CLEARPART'] = clearpart
#     vmaidb_dict[hostname]['ROOTPW'] = rootpw
#     vmaidb_dict[hostname]['ISO'] = isover
#     vmaidb_dict[hostname]['STATUS'] = status
#     print(vmaidb_dict)
#
#     with open(VMAI_DB, 'w+') as vmaidb_file:
#         json.dump(vmaidb_dict, vmaidb_file, ensure_ascii=False, indent=2)

# def print_vmai_db():
#     # print VMAI_DB summary to stdout for debugging purposes
#     with open(VMAI_DB, 'r') as vmaidb_file:
#         vmaidb = json.load(vmaidb_file)
#         print("{:25} {:20} {:20} {:30}"
#               .format('Hostname', 'MAC address', 'IP Address', 'STATUS'))
#         for host in vmaidb.items():
#             print("{:25} {:20} {:20} {:30}"
#                   .format(host[0], host[1]['MAC'], host[1]['IPADDR'], host[1]['STATUS']))
#     print('')
#     return vmaidb

# def deployment_status(ipaddr, mac):
#     # Stage 0: 'Ready to deploy' - initial state after submitting 'Launch automation'
#
#     # print('[INFO] Checking for Stage 1...')
#     # # Stage 1: 'DHCP request'    DHCPDISCOVER from 3c:57:31:ea:89:d8 via ens224
#     # for line in tail("-10f", "../TMP/messages", _iter=True):
#     #     if all(x in line for x in ['DHCPDISCOVER', mac]):
#     #         print('[INFO] Found correct line:')
#     #         print(line)
#     #         deployment_status = 'DHCP request'
#     #         break
#     #     else:
#     #         print(line)
#     #         print('[INFO] Waiting for DHCPDISCOVER...')
#     #
#     # print('[INFO] Checking for Stage 2...')
#     # # Stage 2: 'Bootloader request'        Client ::ffff:192.168.100.2 finished /01-3c-57-31-ea-89-d8/boot.cfg
#     # for line in tail("-10f", "../TMP/messages", _iter=True):
#     #     if all(x in line for x in ['boot.cfg', mac.replace(':', '-')]):
#     #         print('[INFO] Found correct line:')
#     #         print(line)
#     #         deployment_status = 'Bootloader request'
#     #         break
#     #     else:
#     #         print(line)
#     #         print('[INFO] Waiting for Bootloader request...')
#
#     # print('[INFO] Checking for Stage 3...')
#     system('wget --timeout=3 -t 1 --no-check-certificate https://' + ipaddr + '/READY -O /tmp/READY-' + ipaddr + '>/dev/null 2>&1')
#     if path.isfile('/tmp/READY-' + ipaddr) and path.getsize('/tmp/READY-' + ipaddr) > 0:
#         deployment_status = 'Finished'
#     else:
#         deployment_status = 'Installation in progress'
#     return deployment_status

