# VMware Auto-Installer functions
from config import *
from os import system, path, listdir
import re, json

def generate_kickstart(rootpw, hostname, ipaddr, subnet, netmask, gateway, vmnicid, kscfg, enablessh=False, clearpart=False):
    # uses KSTEMPLATE to build custom kickstart config based on provided parameters
    # custom kickstart is saved to KSDIR
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
    kstemplate_file.close()

def generate_pxe(ksurl, isover, macaddr):
    # uses PXETEMPLATE to build custom PXE config based on provided parameters
    with open(PXETEMPLATE, 'r') as pxetemplate_file:
        pxetemplate = pxetemplate_file.read()

    # customize ISO and kickstart URL locations
    isopath = 'iso/' + isover
    pxetemplate = pxetemplate.replace('ISOVER', isopath)
    pxetemplate = pxetemplate.replace('KSURL', ksurl)
    # generate PXE config file name based on MAC address (add prefix + replace ':' with '-')
    pxecfg = PXEDIR + '01-' + macaddr.replace(':', '-')

    with open(pxecfg, 'w+') as pxefile:
        pxefile.write(pxetemplate)
    # return ISOVER

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

def generate_efi(ksurl, isover, macaddr):
    # create /tftboot/01-aa:bb:cc:dd:ee:ff directory
    efidir = TFTPBOOT + '01-' + macaddr.replace(':', '-')
    system('mkdir ' + efidir)
    bootcfg_custom = efidir + '/boot.cfg'
    # read original boot.cfg
    bootcfg_orig_path = TFTPISODIR + isover + '/boot.cfg'
    with open(bootcfg_orig_path, 'r') as bootcfg_file:
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
    # TODO: change the logic so that we don't run wget if status is finished
    system('wget --timeout=3 -t 1 --no-check-certificate https://' + ipaddr + '/READY -O /tmp/READY-' + ipaddr + '>/dev/null 2>&1')
    if path.isfile('/tmp/READY-' + ipaddr) and path.getsize('/tmp/READY-' + ipaddr) > 0:
        deployment_status = 'Finished'
    else:
        deployment_status = 'Installation in progress'
    return deployment_status

def extract_iso_to_tftpboot(uploaded_file, uploaddir=UPLOADDIR, tmpisodir=TMPISODIR, tftpisodir=TFTPISODIR):
    print('[INFO] Extracting uploaded ISO: ' + uploaded_file.filename)
    # STEP 1: save ISO to uploaddir (eg. /var/www/demo/upload/<iso_filename>)
    iso_save_path = path.join(uploaddir, uploaded_file.filename)
    uploaded_file.save(iso_save_path)
    # STEP 2: create mountpoint under tmpisodir (default: /var/www/demo/upload/<iso_filebase>)
    filebase = path.splitext(uploaded_file.filename)[0]
    mountdir = tmpisodir + filebase
    print('[DEBUG] Create mountpoint: ' + mountdir)
    system('sudo /usr/bin/mkdir -p ' + mountdir + ' 1>&2')
    # STEP 3: mount the ISO
    print('[DEBUG] Mount the ISO: ')
    print('[DEBUG] CMD: sudo /usr/bin/mount -r -o loop ' + iso_save_path + ' ' + mountdir)
    system('sudo /usr/bin/mount -r -o loop ' + iso_save_path + ' ' + mountdir + ' 1>&2')
    system('ls -la ' + mountdir + ' 1>&2')

    # STEP 4: copy mounted ISO content to tftpisodir (i.e. /tftpboot/iso/<iso_filebase>)
    iso_tftp_dir = path.join(tftpisodir, filebase)
    print('[DEBUG] CMD: cp -R ' + mountdir + ' ' + iso_tftp_dir)
    system('cp -R ' + mountdir + ' ' + iso_tftp_dir + ' 1>&2')
    system('sudo /usr/bin/chown apache.apache ' + iso_tftp_dir + ' 1>&2')
    system('/usr/bin/chmod 644 ' + iso_tftp_dir + '/boot.cfg' + ' 1>&2')

    # STEP 5: prepare boot.cfg
    bootcfg_path = iso_tftp_dir + '/boot.cfg'
    # read original boot.cfg
    with open(bootcfg_path, 'r') as bootcfg_file:
        bootcfg = bootcfg_file.read()
    # customize boot.cfg file
    title = 'title=Loading ESXi installer - ' + filebase
    prefix = 'prefix=iso/' + filebase
    # customize 'title' and 'prefix'
    bootcfg = re.sub(r"title.*", title, bootcfg)
    if 'prefix' in bootcfg:
        bootcfg = re.sub(r"prefix.*", prefix, bootcfg)
    else:
        # if there is no 'prefix=' line - add it just before 'kernel=' line
        bootcfg = re.sub(r"kernel=", prefix + '\nkernel=', bootcfg)
    # remove '/' from 'kernel=' and 'modules=' paths
    bootcfg = re.sub(r"kernel=/", "kernel=", bootcfg)
    # findall returns a list - extract string in position [0] to run replace() function
    modules = re.findall("^modules=.*", bootcfg, re.MULTILINE)[0].replace('/', '')
    bootcfg = re.sub(r"modules=.*", modules, bootcfg)
    # save customized boot.cfg
    with open(bootcfg_path, 'w+') as bootcfg_file:
        bootcfg_file.write(bootcfg)

    # STEP 6: cleanup - unmount and delete ISO and temporary mountpoint
    system('sudo /usr/bin/umount ' + mountdir + ' 1>&2')
    # system('sudo umount ' + mountdir)
    print('[DEBUG] Cleanup - remove ISO: ' + iso_save_path + ' and mountdir: ' + mountdir)
    system('rm -f ' + iso_save_path + ' 1>&2')
    system('sudo /usr/bin/rmdir ' + mountdir + ' 1>&2')
    # INFO: check content of tftpisodir directory (INFO only)
    print('[INFO] New ISO: ' + filebase)
    print('[INFO] Listing ' + tftpisodir + ' content:')
    dirs = [f for f in listdir(tftpisodir) if path.isdir(path.join(tftpisodir, f))]
    print(dirs)
    system('ls -la ' + tftpisodir + ' 1>&2')
