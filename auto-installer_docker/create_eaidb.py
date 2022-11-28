from sys import path
path.append('auto-installer_flask')
from config import *

from os import system, path, listdir
from shutil import which
import sqlite3 as sl

EAISTATUS_COLUMNS = {
    'jobid': {'type': 'TEXT'}, 
    'hostname': {'type': 'TEXT'}, 
    'ipaddr': {'type': 'TEXT'}, 
    'cimcip': {'type': 'TEXT'}, 
    'start_time': {'type': 'DATETIME'}, 
    'finish_time': {'type': 'DATETIME'}, 
    'status': {'type': 'TEXT'}, 
    'cimcusr': {'type': 'TEXT'}, 
    'cimcpwd': {'type': 'TEXT'}, 
    'macaddr': {'type': 'TEXT'}, 
    'netmask': {'type': 'TEXT'}, 
    'gateway': {'type': 'TEXT'}
    }

def eaidb_create_db(eaidb=EAIDB, required_columns=EAISTATUS_COLUMNS):
    # check EAISTATUS table format
    if path.isfile(eaidb):
        print(f'[INFO] Found EAIDB ({eaidb}), verifying schema...')
        con = sl.connect(eaidb) 
        with con:
            c = con.cursor()
            result = c.execute("PRAGMA table_info(EAISTATUS)").fetchall()
            columns = {}
            for column in result:
                columns[column[1]] = {'type': column[2]}
            # compare EAISTATUS schema with expected schema
            if columns == required_columns:
                print('[INFO] EAISTATUS table OK.')
                return
            else:
                print('[WARNING] EAISTATUS table schema different from expected.')
                eaidb_bak = f'{eaidb}_bak'
                print(f'[INFO] Moving {eaidb} file to {eaidb_bak}')
                mv_cmd = which('mv')
                system(f'{mv_cmd} {eaidb} {eaidb_bak}')

    if not path.isfile(eaidb):
        print(f'[INFO] EAIDB file ({eaidb}) not found - creating.')

        con = sl.connect(eaidb) 
        with con:
            c = con.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS EAISTATUS (
                            jobid TEXT NOT NULL PRIMARY KEY,
                            hostname TEXT NOT NULL,
                            ipaddr TEXT NOT NULL,
                            cimcip TEXT,
                            start_time DATETIME,
                            finish_time DATETIME,
                            status TEXT,
                            cimcusr TEXT,
                            cimcpwd TEXT,
                            macaddr TEXT,
                            netmask TEXT,
                            gateway TEXT
                        );''')
        con.commit()
        print(f'[INFO] EAIDB ({eaidb}) created.')


if __name__ == "__main__":
    eaidb_create_db()