# VMware Auto-Installer config
import os
from helper_functions import get_host_ip_address

DRYRUN=False
WORKDIR = '/opt/eai'
ESXISODIR = os.path.join(WORKDIR, 'esxi-iso')
CUSTOMISODIR = os.path.join(WORKDIR, 'custom-iso')
LOGDIR = os.path.join(WORKDIR, 'logs/jobs')
EAILOG = os.path.join(WORKDIR, 'logs/eai.log')
EAIDB = os.path.join(WORKDIR, 'eaidb.sqlite3')

EAIHOST = os.environ.get('EAI_HOST_IP')

UPLOADDIR = os.path.join(WORKDIR, 'upload')
MNTISODIR = os.path.join(UPLOADDIR, 'mnt')
KSDIR = os.path.join(WORKDIR, 'ks')
PXEDIR = os.path.join(WORKDIR, 'pxelinux.cfg')
KSTEMPLATE = os.path.join(WORKDIR, 'templates/kickstart.jinja')
PXETEMPLATE = os.path.join(WORKDIR, 'templates/pxecfg_template')

TFTPISODIR = '/tftpboot/iso'

STATUS_CODES = {
    0: 'Ready to deploy',
    10: 'Connecting to CIMC',
    11: 'Mounting installation ISO',
    15: 'Installation in progress',
    16: 'Running First Boot',
    18: 'Running cleanup tasks',
    20: 'Finished',
    30: 'Error',
    31: 'Error: Failed to login to CIMC',
    32: 'Error: Failed to mount installation ISO',
    33: 'Error: UEFI Secure Boot Mode enabled'
}