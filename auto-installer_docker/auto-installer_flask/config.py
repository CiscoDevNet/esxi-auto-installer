# ESXi Auto-Installer config
import os

DRYRUN=False
WORKDIR = '/opt/eai'
ESXISODIR = os.path.join(WORKDIR, 'esxi-iso')
CUSTOMISODIR = os.path.join(WORKDIR, 'custom-iso')
LOGDIR = os.path.join(WORKDIR, 'logs/jobs')
EAILOG = os.path.join(WORKDIR, 'logs/eai.log')
EAIDB = os.path.join(WORKDIR, 'eaidb.sqlite3')

# host network settings are set through environment variables, set in run_docker.sh
EAIHOST_IP = os.environ.get('EAI_HOST_IP')
EAIHOST_GW = os.environ.get('EAI_HOST_GW')
EAIHOST_SUBNET = os.environ.get('EAI_HOST_SUBNET')
EAIHOST_NETMASK = os.environ.get('EAI_HOST_NETMASK')

UPLOADDIR = os.path.join(WORKDIR, 'upload')
MNTISODIR = os.path.join(UPLOADDIR, 'mnt')

TFTPBOOT = os.path.join(WORKDIR, 'tftpboot')
TFTPISODIR = os.path.join(TFTPBOOT, 'iso')
PXEDIR = os.path.join(TFTPBOOT, 'pxelinux.cfg')
KSDIR = os.path.join(WORKDIR, 'ks')
TEMPLATESDIR = os.path.join(WORKDIR, 'templates')
KSTEMPLATE = os.path.join(TEMPLATESDIR, 'kickstart.jinja')
PXETEMPLATE = os.path.join(TEMPLATESDIR, 'pxecfg.jinja')

DHCPD_CONF_TPL = os.path.join(TEMPLATESDIR, 'dhcpd_conf_template.jinja')
DHCP_SUBNET_TPL = os.path.join(TEMPLATESDIR, 'dhcp_subnet.jinja')
DHCP_HOST_TPL = os.path.join(TEMPLATESDIR, 'dhcp_template.jinja')
# path to DHCP server config file
DHCPD_CONF = os.path.join(WORKDIR, 'etc_dhcp', 'dhcpd.conf')


STATUS_CODES = {
    0: 'Ready to deploy',
    10: 'Connecting to CIMC',
    11: 'Mounting installation ISO',
    15: 'Server is booting',
    16: 'Installer is running',
    17: 'Running final reboot',
    18: 'Running cleanup tasks',
    20: 'Finished',
    25: 'Cancelled',
    30: 'Error',
    31: 'Error: Failed to login to CIMC',
    32: 'Error: Failed to mount installation ISO',
    34: 'Error: ESXi Installed but SSH was not enabled',
    35: 'Error: No response after final reboot'
}

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
    'root_pwd': {'type': 'TEXT'},
    'macaddr': {'type': 'TEXT'}, 
    'netmask': {'type': 'TEXT'}, 
    'gateway': {'type': 'TEXT'}
}
