from vmai_functions import *
from config import *
# from config_local import *
from time import sleep

if __name__ == "__main__":
    print_vmai_db()
    while True:
        with open(VMAI_DB, 'r') as vmaidb_file:
            vmaidb = json.load(vmaidb_file)
            print("{:25} {:20} {:20} {:30}"
                  .format('Hostname', 'MAC address', 'IP Address', 'STATUS'))
            for host in vmaidb.items():
                # check current server status
                status = deployment_status(host[1]['IPADDR'], host[1]['MAC'])
                # check if deployment status has changed and update VMAI_DB accordingly
                if status not in host[1]['STATUS'] and host[1]['STATUS'] not in 'Finished':
                    host[1]['STATUS'] = status
                    vmaidb_file.close()
                    with open(VMAI_DB, 'w') as vmaidb_file:
                        json.dump(vmaidb, vmaidb_file, ensure_ascii=False, indent=2)
                print("{:25} {:20} {:20} {:30}"
                      .format(host[0], host[1]['MAC'], host[1]['IPADDR'], host[1]['STATUS']))
            vmaidb_file.close()
        print('')
        sleep(5)
