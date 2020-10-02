# VMware Auto-Installer functions
from config import *
from os import system
import re

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