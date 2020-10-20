# VMware Auto-Installer functions
#from config_local import *
from config import *
from os import system, path
import re, json

def generate_kickstart(rootpw, hostname, ipaddr, subnet, netmask, gateway, vmnicid, kscfg, enablessh=False, clearpart=False):
    # uses KSTEMPLATE to build custom kickstart config based on provided parameters
    # customkickstart is saved to KSDIR
    kstemplate_file = open(KSTEMPLATE)

    kstemplate = kstemplate_file.read()
    # check if "Erase existing partition" has been set
    if clearpart:
        kstemplate = kstemplate.replace('accepteula', 'accepteula\nclearpart --firstdisk --overwritevmfs')
    kstemplate = kstemplate.replace('ROOTPW', rootpw)
    kstemplate = kstemplate.replace('HOSTNAME', hostname)
    kstemplate = kstemplate.replace('IPADDR', ipaddr)
    kstemplate = kstemplate.replace('SUBNET', subnet)
    kstemplate = kstemplate.replace('NETMASK', netmask)
    kstemplate = kstemplate.replace('GATEWAY', gateway)
    kstemplate = kstemplate.replace('VMNIC', 'vmnic' + vmnicid)

    with open(KSDIR + kscfg, 'w+') as ksfile:
        ksfile.write(kstemplate)
        # check if "Enable SSH" has been set
        if enablessh:
            ksfile.write(SSHTXT)
        else:
            ksfile.write(NOSSHTXT)
    ksfile.close()
    kstemplate_file.close()

def generate_pxe(ksurl, isofile, macaddr):
    # uses PXETEMPLATE to build custom PXE config based on provided parameters
    pxetemplate_file = open(PXETEMPLATE)
    pxetemplate = pxetemplate_file.read()

    # need to decide where to keep these - keep here or in config? generate dynamically?
    if '6.7.0_U3_Installer-14320388' in isofile:
        ISOVER = 'esxi67u3'
    elif '6.5.0_U3_Installer-13932383' in isofile:
        ISOVER = 'esxi65u3'
    elif '6.5.0_U2_Installer-9298722' in isofile:
        ISOVER = 'esxi65u2'

    pxetemplate = pxetemplate.replace('ISOVER', ISOVER)
    pxetemplate = pxetemplate.replace('KSURL', ksurl)
    # generate PXE config file name based on MAC address (add prefix + replace ':' with '-')
    pxecfg = PXEDIR + '01-' + macaddr.replace(':', '-')

    with open(pxecfg, 'w+') as pxefile:
        pxefile.write(pxetemplate)
    pxefile.close()
    pxetemplate_file.close()
    return ISOVER

def generate_dhcp(hostname, subnet, netmask, ipaddr, gateway, macaddr):
    dhcptemplate_file = open(DHCPTEMPLATE)
    dhcptemplate = dhcptemplate_file.read()
    dhcptemplate = dhcptemplate.replace('HOSTNAME', hostname)
    dhcptemplate = dhcptemplate.replace('SUBNET', subnet)
    dhcptemplate = dhcptemplate.replace('NETMASK', netmask)
    dhcptemplate = dhcptemplate.replace('IPADDR', ipaddr)
    dhcptemplate = dhcptemplate.replace('GATEWAY', gateway)
    dhcptemplate = dhcptemplate.replace('MAC', macaddr)

    # backup dhcp.conf - need to add unique suffix
    system('cp ' + DHCPCFG + ' ' + DHCPCFG + '_bak')

    # open /etc/dhcp/dhcpd.conf and append configuration
    with open(DHCPCFG, 'a+') as dhcpfile:
        dhcpfile.write(dhcptemplate)
    dhcpfile.close()

def generate_efi(ksurl, macaddr):
    # create /tftboot/01-aa:bb:cc:dd:ee:ff directory
    efidir = TFTPBOOT + '01-' + macaddr.replace(':', '-')
    system('mkdir ' + efidir)
    bootcfg_custom = efidir + '/boot.cfg'
    # read default boot.cfg
    bootcfg_file = open(TFTPBOOT + 'boot.cfg')
    bootcfg = bootcfg_file.read()
    # search for kernelopt line and replace parameters with ksurl
    kerneloptline = 'kernelopt=ks=' + ksurl
    bootcfg = re.sub(r"kernelopt.*", kerneloptline, bootcfg)
    with open(bootcfg_custom, 'w+') as bootcfg_custom_file:
        bootcfg_custom_file.write(bootcfg)

def save_install_data_to_db(hostname, mac, ipaddr, subnet, netmask, gateway, vlan, vmnic,
                            enablessh, clearpart, rootpw, isover, status):
    if path.isfile(VMAI_DB):
        print('[INFO] ' + VMAI_DB + ' file exists - importing data and adding new entry:')
        with open(VMAI_DB, 'r') as vmaidb_file:
            vmaidb_dict = json.load(vmaidb_file)
            # need to add checking of 'hostname' already exists ion VMAI_DB
            vmaidb_dict[hostname] = {}
            vmaidb_dict[hostname]['MAC'] = mac
            vmaidb_dict[hostname]['IPADDR'] = ipaddr
            vmaidb_dict[hostname]['SUBNET'] = subnet
            vmaidb_dict[hostname]['NETMASK'] = netmask
            vmaidb_dict[hostname]['GATEWAY'] = gateway
            vmaidb_dict[hostname]['VLAN'] = vlan
            vmaidb_dict[hostname]['VMNIC'] = vmnic
            vmaidb_dict[hostname]['SSH'] = enablessh
            vmaidb_dict[hostname]['CLEARPART'] = clearpart
            vmaidb_dict[hostname]['ROOTPW'] = rootpw
            vmaidb_dict[hostname]['ISO'] = isover
            vmaidb_dict[hostname]['STATUS'] = status
            print(vmaidb_dict)
            vmaidb_file.close()
        with open(VMAI_DB, 'w+') as vmaidb_file:
            json.dump(vmaidb_dict, vmaidb_file, ensure_ascii=False, indent=2)
            vmaidb_file.close()
    else:
        print('[INFO] ' + VMAI_DB + ' file DOES NOT exist - creating file and adding new entry')
        vmaidb_dict = {}
        vmaidb_dict[hostname] = {}
        vmaidb_dict[hostname]['MAC'] = mac
        vmaidb_dict[hostname]['IPADDR'] = ipaddr
        vmaidb_dict[hostname]['SUBNET'] = subnet
        vmaidb_dict[hostname]['NETMASK'] = netmask
        vmaidb_dict[hostname]['GATEWAY'] = gateway
        vmaidb_dict[hostname]['VLAN'] = vlan
        vmaidb_dict[hostname]['VMNIC'] = vmnic
        vmaidb_dict[hostname]['SSH'] = enablessh
        vmaidb_dict[hostname]['CLEARPART'] = clearpart
        vmaidb_dict[hostname]['ROOTPW'] = rootpw
        vmaidb_dict[hostname]['ISO'] = isover
        vmaidb_dict[hostname]['STATUS'] = status
        print(vmaidb_dict)
        with open(VMAI_DB, 'w+') as vmaidb_file:
            json.dump(vmaidb_dict, vmaidb_file, ensure_ascii=False, indent=2)
            vmaidb_file.close()

def print_vmai_db():
    # print VMAI_DB summary to stdout for debugging purposes
    with open(VMAI_DB, 'r') as vmaidb_file:
        vmaidb = json.load(vmaidb_file)
        print("{:25} {:20} {:20} {:30}"
              .format('Hostname', 'MAC address', 'IP Address', 'STATUS'))
        for host in vmaidb.items():
            print("{:25} {:20} {:20} {:30}"
                  .format(host[0], host[1]['MAC'], host[1]['IPADDR'], host[1]['STATUS']))
    print('')
    return vmaidb

def deployment_status(ipaddr, mac):
    # Stage 0: 'Ready to deploy' - initial state after submitting 'Launch automation'

    # print('[INFO] Checking for Stage 1...')
    # # Stage 1: 'DHCP request'    DHCPDISCOVER from 3c:57:31:ea:89:d8 via ens224
    # for line in tail("-10f", "../TMP/messages", _iter=True):
    #     if all(x in line for x in ['DHCPDISCOVER', mac]):
    #         print('[INFO] Found correct line:')
    #         print(line)
    #         deployment_status = 'DHCP request'
    #         break
    #     else:
    #         print(line)
    #         print('[INFO] Waiting for DHCPDISCOVER...')
    #
    # print('[INFO] Checking for Stage 2...')
    # # Stage 2: 'Bootloader request'        Client ::ffff:192.168.100.2 finished /01-3c-57-31-ea-89-d8/boot.cfg
    # for line in tail("-10f", "../TMP/messages", _iter=True):
    #     if all(x in line for x in ['boot.cfg', mac.replace(':', '-')]):
    #         print('[INFO] Found correct line:')
    #         print(line)
    #         deployment_status = 'Bootloader request'
    #         break
    #     else:
    #         print(line)
    #         print('[INFO] Waiting for Bootloader request...')

    # print('[INFO] Checking for Stage 3...')
    system('wget --timeout=3 -t 1 --no-check-certificate https://' + ipaddr + '/READY -O /tmp/READY-' + ipaddr + '>/dev/null 2>&1')
    if path.isfile('/tmp/READY-' + ipaddr) and path.getsize('/tmp/READY-' + ipaddr) > 0:
        deployment_status = 'Finished'
    else:
        deployment_status = 'Installation in progress'

    return deployment_status
