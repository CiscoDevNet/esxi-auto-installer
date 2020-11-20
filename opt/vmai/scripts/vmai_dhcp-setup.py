import ipaddress
from os import path
from datetime import datetime

IFCFG = '/etc/sysconfig/network-scripts/ifcfg-ens192'
DHCPTPL = '/etc/dhcp/dhcpd.conf_template'
DHCPBASE = '/etc/dhcp/dhcpd.conf_base'

def generate_dhcpd_conf(ifcfg=IFCFG, dhcptpl=DHCPTPL, dhcpbase=DHCPBASE):
    # get current IP, netmask and gateway from ifcfg
    ifcfg_dict = {}
    with open(ifcfg, 'rt') as ifcfg_file:
        for line in ifcfg_file:
            (key, val) = line.strip('\n').split('=')
            ifcfg_dict[key] = val
    # get subnet based on IPADDR and NETMASK
    net = ipaddress.ip_network(ifcfg_dict['IPADDR'] + '/' + ifcfg_dict['NETMASK'], strict=False)
    subnet = net.network_address
    print('[INFO] ' + datetime.now().strftime("%Y-%m-%d %X") + ' - Discovered IP address: '
          + ifcfg_dict['IPADDR'] + '/' + str(net.prefixlen))
    # generate dhcpd.conf
    with open(dhcptpl) as dhcptpl_file:
        dhcptpl_dict = dhcptpl_file.read()
        dhcptpl_dict = dhcptpl_dict.replace('NEXTSERVER', ifcfg_dict['IPADDR'])
        dhcptpl_dict = dhcptpl_dict.replace('IPADDR', ifcfg_dict['IPADDR'])
        dhcptpl_dict = dhcptpl_dict.replace('SUBNET', str(subnet))
        dhcptpl_dict = dhcptpl_dict.replace('NETMASK', ifcfg_dict['NETMASK'])
        dhcptpl_dict = dhcptpl_dict.replace('GATEWAY', ifcfg_dict['GATEWAY'])
    # write new config to dhcpd.conf_base
    print('[INFO] ' + datetime.now().strftime("%Y-%m-%d %X") +
          ' - Updating next-server and subnet definition in dhcpd.conf_base')
    with open(dhcpbase, 'w+') as dhcpbase_file:
        dhcpbase_file.write(dhcptpl_dict)
    # print new settings for debugging purposes
    with open(dhcpbase, 'rt') as dhcpbase_file:
        for line in dhcpbase_file:
            if ('next-server' in line) or ('subnet' in line) or ('range' in line) or ('routers' in line):
                print(line.strip('\n'))

if __name__ == "__main__":
    print('[INFO] ' + datetime.now().strftime("%Y-%m-%d %X") + ' - Running ' + path.basename(__file__) + ' script')
    # generate_dhcpd_conf('../../TMP/ifcfg-ens192-NEW', '../../TMP/dhcpd.conf_template', '../../TMP/dhcpd.conf_base')
    generate_dhcpd_conf()

