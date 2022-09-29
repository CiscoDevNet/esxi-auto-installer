# VMware Auto-Installer functions
from imcsdk.imchandle import ImcHandle
from imcsdk.apis.server.vmedia import *
from imcsdk.apis.server.boot import *
from imcsdk.apis.server.serveractions import server_power_cycle, server_power_state_get

from generic_functions import *
from helper_functions import *
from config import *

from os import system, path, listdir
from jinja2 import Template
import re
import time
from ipaddress import ip_network
from multiprocessing import Process

def get_form_data(mainlog, form_result):
    """
    Takes FlaskForm result as an input and returns dictionary with kickstart configuration and network details
    for ESXi server(s) and CIMC(s)

    :param mainlog: application main logger handler
    :param form_result: (werkzeug.datastructures.ImmutableMultiDict)
    :return: form_data: (dict) dictionary with IP address(es) and task(s) as list items
    """

    mainlog.info(f'Reading data from web form:')

    form_data = {}
    form_data['iso_image'] = form_result['iso_image']
    form_data['root_pwd'] = form_result['root_pwd']
    form_data['vmnic'] = form_result['vmnic']
    form_data['vlan'] = form_result['vlan']
    form_data['firstdisk'] = form_result['firstdisk']
    form_data['firstdisktype'] = form_result['firstdisktype']
    form_data['diskpath'] = form_result['diskpath']
    form_data['enablessh'] = form_result.get('enablessh')
    form_data['clearpart'] = form_result.get('clearpart')

    # get static routes (if provided)
    form_data['static_routes'] = []
    if form_result['static_routes_set'] == 'True':
        for key, value in form_result.items():
            if 'subnet_ip' in key:
                seq = key.replace('subnet_ip', '')
                form_data['static_routes'].append({'subnet_ip': form_result[key],
                                                   'cidr': form_result['cidr' + seq],
                                                   'gateway': form_result['gateway' + seq]})

    # get common settings - CIMC credentials and subnet/gateway
    # TODO: skip cimc credentials if installmethod is pxeboot
    form_data['cimc_usr'] = form_result['cimc_usr']
    form_data['cimc_pwd'] = form_result['cimc_pwd']
    form_data['host_prefix'] = form_result['host_prefix']
    form_data['host_suffix'] = form_result['host_suffix']
    # calculate subnet based on gateway IP address and netmask (needed for PXE booted installation)
    form_data['host_subnet'] = ip_network(form_result['host_gateway'] + '/' + form_result['host_netmask'], strict=False).network_address
    form_data['host_netmask'] = form_result['host_netmask']
    form_data['host_gateway'] = form_result['host_gateway']
    form_data['dns1'] = form_result['dns1']
    form_data['dns2'] = form_result['dns2']

    # get ESXi host and CIMC IP address(es)
    form_data['hosts'] = []
    for key, value in form_result.items():
        if 'hostname' in key:
            seq = key.replace('hostname', '')
            hostname = form_result['host_prefix'] + form_result[key] + form_result['host_suffix']
            form_data['hosts'].append({'hostname': hostname,
                                       'host_ip': form_result['host_ip' + seq],
                                       'cimc_ip': form_result['cimc_ip' + seq]})
                                       # TODO: set/save cimc_ip/macaddr based on installmethod
    mainlog.debug(form_data)
    return form_data


def generate_kickstart(jobid, form_data, index, logger, mainlog, eai_host_ip=EAIHOST_IP, dryrun=DRYRUN, ksjinja=KSTEMPLATE, ksdir=KSDIR):
    logger.info(f'Generating kickstart file for server')

    # set installation disk
    if form_data['firstdisk'] == 'firstdiskfound':
        # first disk found
        firstdisk_install = 'firstdisk'
        cleardisk = 'firstdisk'
    elif form_data['firstdisk'] == 'firstdisk':
        # first disk: local, remote or usb
        firstdisk_install = 'firstdisk=' + form_data['firstdisktype']
        cleardisk = 'firstdisk=' + form_data['firstdisktype']
    elif form_data['firstdisk'] == 'diskpath':
        firstdisk_install = 'disk=' + form_data['diskpath']
        cleardisk = 'drives=' + form_data['diskpath']

    # customize install and (optionally) clearpart lines
    install = 'install --' + firstdisk_install + ' --overwritevmfs'
    if form_data['clearpart']:
        clearline = 'clearpart --' + cleardisk + ' --overwritevmfs\n'
    else:
        clearline = ''

    # generate pre-section if static routes have been provided
    # i.e. 'localcli network ip route ipv4 add -n NET_CIDR -g GATEWAY'
    static_routes = ''
    # if form_data['static_routes_set'] == 'True':
    if form_data['static_routes']:
        for route in form_data['static_routes']:
            net_cidr = route['subnet_ip'] + '/' + str(route['cidr'])
            static_routes += 'localcli network ip route ipv4 add -n ' + net_cidr + ' -g ' + route['gateway'] + '\n'
        pre_section = '%pre --interpreter=busybox\n' + static_routes + '\n'
    else:
        pre_section = ''

    # additional default route set when static route has been selected in %pre section
    if pre_section:
        set_def_gw = '# Set Default Gateway\nesxcli network ip route ipv4 add --gateway ' + form_data['host_gateway'] + ' --network 0.0.0.0\n'
    else:
        set_def_gw = ''

    # enable ssh
    if form_data['enablessh']:
        enable_ssh = '# enable & start remote ESXi Shell (SSH)\nvim-cmd hostsvc/enable_ssh\nvim-cmd hostsvc/start_ssh\n'
    else:
        enable_ssh = ''

    # in this version we don't disable IPv6 (default is enabled) and no reboot after %firstboot is required
    disable_ipv6 = False
    # disableipv6 = False
    # if disableipv6:
    #     disable_ipv6 = '# disable IPv6\nesxcli network ip set --ipv6-enabled=false\n'
    # else:
    #     disable_ipv6 = ''

    # process DNS
    if form_data['dns1'] != '':
        if form_data['dns2'] != '':
            dnsservers = form_data['dns1'] + ',' + form_data['dns2']
        else:
            dnsservers = form_data['dns1']
    else:
        dnsservers = ''


    # remaining host data
    import crypt
    rootpw_hash = crypt.crypt(form_data['root_pwd'], crypt.mksalt(crypt.METHOD_SHA512))

    vmnicid = form_data['vmnic']
    vlan = form_data['vlan']
    netmask = form_data['host_netmask']
    gateway = form_data['host_gateway']
    hostname = form_data['hosts'][index]['hostname']
    ipaddr = form_data['hosts'][index]['host_ip']

    # read jinja template from file and render using read variables
    with open(ksjinja, 'r') as kstemplate_file:
        kstemplate = Template(kstemplate_file.read())
    kickstart = kstemplate.render(clearpart=clearline, install=install, rootpw_hash=rootpw_hash, vmnicid='vmnic' + vmnicid, vlan=vlan,
                                  ipaddr=ipaddr, netmask=netmask, gateway=gateway, hostname=hostname, pre_section=pre_section, dnsservers=dnsservers,
                                  set_def_gw=set_def_gw, enable_ssh=enable_ssh, disable_ipv6=disable_ipv6,
                                  eai_host_ip=eai_host_ip, jobid=jobid)
    # remove password before saving kickstart to log file
    logger.info(f"Generated kickstart configuration:\n{re.sub(r'rootpw.*', 'rootpw --iscrypted ***********', kickstart)}\n")
    if not dryrun:
        kspath = path.join(ksdir, jobid + '_ks.cfg')
        with open(kspath, 'w+') as ksfile:
            ksfile.write(kickstart)
            mainlog.debug(f'{jobid} Generated kickstart config for host: {hostname} saved to {kspath}')
            logger.info(f'Kickstart config for host: {hostname} saved to {kspath}\n')
        return kspath
    else:
        mainlog.debug(f'{jobid} [DRYRUN] Generated kickstart config for host: {hostname}')
        return 'not a real kscfg path'


def iso_extract(mainlog, uploaded_file, uploaddir=UPLOADDIR, tmpisodir=MNTISODIR, extracted_iso_dir=ESXISODIR):
    mainlog.info(f'Extracting uploaded ISO: {uploaded_file.filename}')

    # get system commands paths
    from shutil import which
    mkdir_cmd = which('mkdir')
    mount_cmd = which('mount')
    umount_cmd = which('umount')
    chmod_cmd = which('chmod')
    rmdir_cmd = which('rmdir')

    # STEP 1: save ISO to uploaddir (default: /opt/eai/upload/<iso_filename>)
    iso_save_path = path.join(uploaddir, uploaded_file.filename)
    uploaded_file.save(iso_save_path)

    # STEP 2: create mountpoint under tmpisodir (default: /opt/eai/upload/tmp/<iso_filebase>)
    filebase = path.splitext(uploaded_file.filename)[0]
    mountdir = path.join(tmpisodir, filebase)
    mainlog.debug(f'Create mountpoint: {mountdir}')
    system(f'{mkdir_cmd} -p {mountdir} 1>&2')

    # STEP 3: mount the ISO
    mainlog.debug(f'Mount the ISO: ')
    command = f'{mount_cmd} -r -o loop {iso_save_path} {mountdir} 1>&2'
    mainlog.debug(f'CMD: {command}')
    system(command)
    system(f'ls -la {mountdir} 1>&2')

    # STEP 4: copy mounted ISO content to extracted_iso_dir (default: /opt/eai/exsi-iso/<iso_filebase>)
    command = f'cp -R {mountdir} {extracted_iso_dir} 1>&2'
    mainlog.debug(f'CMD: {command}')
    system(command)
    # set boot.cfg to be writable, so that it can be modified per each installation job
    bootcfg_path = path.join(extracted_iso_dir, filebase, "boot.cfg")
    mainlog.debug(f'bootcfg_path: {bootcfg_path}')
    command = f'{chmod_cmd} 644 {path.join(extracted_iso_dir, filebase, "boot.cfg")} 1>&2'
    mainlog.debug(f'CMD: {command}')
    system(command)

    # STEP 5: cleanup - unmount and delete ISO and temporary mountpoint
    system(f'{umount_cmd} {mountdir} 1>&2')
    mainlog.debug(f'Cleanup - remove ISO: {iso_save_path} and mountdir: {mountdir}')
    system(f'rm -f {iso_save_path} 1>&2')
    system(f'{rmdir_cmd} {mountdir} 1>&2')

    # INFO: check content of tftpisodir directory (INFO only)
    mainlog.info(f'New ISO: {filebase}')
    mainlog.debug(f'Listing {extracted_iso_dir} content:')
    dirs = [f for f in listdir(extracted_iso_dir) if path.isdir(path.join(extracted_iso_dir, f))]
    mainlog.debug(dirs)
    system(f'ls -la {extracted_iso_dir} 1>&2')


def iso_prepare_tftp(mainlog, uploaded_file, extracted_iso_dir=ESXISODIR, tftpisodir=TFTPISODIR):
    filebase = path.splitext(uploaded_file.filename)[0]
    mainlog.info(f'tftpboot: copy and prepare {filebase} installation media.')
    source_iso_dir = path.join(extracted_iso_dir, filebase)

    # copy files from 'vanilla' ISO directory to target subdirectory under TFTPISODIR
    mainlog.info(f'Copy ISO files to target subdirectory: {path.join(tftpisodir, filebase)}')
    system(f'cp -R {source_iso_dir} {tftpisodir} 1>&2')

    bootcfg_path = path.join(tftpisodir, filebase, 'boot.cfg')
    mainlog.info(f'Modify {bootcfg_path} for PXE boot')
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
    system(f'chmod +w {bootcfg_path}')
    with open(bootcfg_path, 'w+') as bootcfg_file:
        bootcfg_file.write(bootcfg)
    mainlog.info(f'tftpboot: installation media for {filebase} ready.')


def generate_custom_iso(jobid, logger, mainlog, hostname, iso_image, kscfg_path, dryrun=DRYRUN, isodir=ESXISODIR, customisodir=CUSTOMISODIR):
    if not dryrun:
        mainlog.info(f'{jobid} Generating custom installation ISO for host: {hostname} using ESXi ISO {iso_image}')
        logger.info(f'Generating custom installation ISO for host: {hostname} using ESXi ISO {iso_image}')

        # copy mounted ISO content to customisodir (i.e. /opt/esxi-iso/<iso_filebase>)
        tmpisodir = path.join(customisodir, jobid)
        command = f'cp -R {path.join(isodir, iso_image)} {tmpisodir} 1>&2'
        mainlog.debug(f'{jobid} {command}')
        system(command)

        system(f'chmod -R +w {tmpisodir} 1>&2')
        command = f'cp {kscfg_path} {path.join(tmpisodir, "ks.cfg")} 1>&2'
        mainlog.debug(f'{jobid} {command}')
        system(command)

        # prepare boot.cfg
        # read original boot.cfg
        bootcfg_path = path.join(tmpisodir, 'boot.cfg')
        with open(bootcfg_path, 'r') as bootcfg_file:
            bootcfg = bootcfg_file.read()

        # customize boot.cfg file - title and kernelopt lines
        title = 'title=Loading ESXi ' + iso_image + ' installer for server: ' + hostname
        bootcfg = re.sub(r"title.*", title, bootcfg)
        kernelopt = 'kernelopt=ks=cdrom:/KS.CFG'
        bootcfg = re.sub(r"kernelopt.*", kernelopt, bootcfg)

        # save customized boot.cfg
        with open(bootcfg_path, 'w+') as bootcfg_file:
            bootcfg_file.write(bootcfg)

        # copy boot.cfg for EFI boot
        bootcfg_efi_path = path.join(tmpisodir, 'efi/boot/boot.cfg')
        system(f'cp -f {bootcfg_path} {bootcfg_efi_path}')

        # generate custom iso
        system(f'genisoimage -relaxed-filenames -J -R -o {path.join(tmpisodir + ".iso")} -b isolinux.bin -c boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table -eltorito-alt-boot -e efiboot.img -no-emul-boot {tmpisodir}')

        mainlog.debug(f'rm -rf {tmpisodir} 1>&2')
        system(f'rm -rf {tmpisodir} 1>&2')

        mainlog.info(f'{jobid} Custom installation ISO for host {hostname} saved to: {path.join(tmpisodir + ".iso")}')
        logger.info(f'Custom installation ISO for host {hostname} saved to: {path.join(tmpisodir + ".iso")}\n')
    else:
        mainlog.info(f'[DRYRUN] Running generate_custom_iso({jobid}, {logger}, {mainlog}, {hostname}, {iso_image})')


def cimc_login(logger, cimcaddr, cimcusr, cimcpwd, dryrun=DRYRUN):
    logger.info(f'Connecting to CIMC IP: {cimcaddr} using account: {cimcusr}')
    if not dryrun:
        # check if custom port has been provided
        if ':' in cimcaddr:
            cimcip = cimcaddr.split(':')[0]
            cimcport = int(cimcaddr.split(':')[1])
        else:
            cimcip = cimcaddr
            cimcport = 443
        if cimcport == 80:
            # ImcSeccion in imcsdk does not seem to handle non-secure port 80 correctly - let's workaround it here
            cimcsecure = False
        else:
            cimcsecure = True
        # Create a connection handle
        cimchandle = ImcHandle(cimcip, cimcusr, cimcpwd, cimcport, cimcsecure)
        # Login to CIMC
        cimchandle.login()
        logger.info(f'Connected to CIMC: {cimcaddr}')
        return cimchandle
    else:
        return 'dummy_handle'


def cimc_logout(logger, cimchandle, cimcip, dryrun=DRYRUN):
    if not dryrun:
        # Logout from the server
        cimchandle.logout()
    logger.info(f'Disconnected from CIMC: {cimcip}')


def install_esxi(jobid, logger, mainlog, cimcip, cimcusr, cimcpwd, iso_image, eai_ip=EAIHOST_IP, dryrun=DRYRUN):
    """
    Install ESXi hypervisor using custom installation ISO (iso_image):
    - login to CIMC
    - set VMEDIA (installation ISO) on Boot Order
    - mount installation ISO on CIMC
    - reboot the server
    - logout from CIMC

    :param jobid: (str) job ID
    :param logger: (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :param customisodir: (str) path to custom ISO directory
    :return: n/a
    """

    isourl = f'http://{eai_ip}/custom-iso/{iso_image}'
    mainlog.debug(f'{jobid} Starting ESXi hypervisor installation using custom ISO URL: {isourl}')
    logger.info(f'Starting ESXi hypervisor installation using custom ISO URL: {isourl}')

    if not dryrun:
        # login to CIMC
        try:
            eaidb_update_job_status(jobid, 'Connecting to CIMC', '')
            cimchandle = cimc_login(logger, cimcip, cimcusr, cimcpwd)
        except Exception as e:
            mainlog.error(f'{jobid} Error when trying to login to CIMC: {str(e)}')
            logger.error(f'Error when trying to login to CIMC: {format_message_for_web(e)}\n')
            # if cimc_login failed - run cleanup tasks (with unmount_iso=False), update EAIDB with error message and abort
            job_cleanup(jobid, logger, mainlog, unmount_iso=False)
            eaidb_update_job_status(jobid, 'Error: Failed to login to CIMC', time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime()))
            return 1

        # set VMEDIA on Boot Order
        try:
            if cimc_vmedia_set(cimchandle, logger) == 33:
                job_cleanup(jobid, logger, mainlog, unmount_iso=False)
                cimc_logout(logger, cimchandle, cimcip)
                eaidb_update_job_status(jobid, 'Error: UEFI Secure Boot Mode enabled', time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime()))
                return 33
        except Exception as e:
            mainlog.error(f'{jobid} : {str(e)}')
            logger.error('Failed to set VMEDIA on Boot Order')
            logger.error(format_message_for_web(e))

        # mount custom ISO and reboot the server to start the installation
        try:
            # update status in EAIDB to 'Mounting installation ISO'
            eaidb_update_job_status(jobid, 'Mounting installation ISO', '')

            logger.info('')
            logger.info(f'Mount custom installation ISO on CIMC')
            vmedia_mount_iso_uri(cimchandle, isourl)

            mainlog.debug(f'{jobid} vmedia_get_existing_uri: {vmedia_get_existing_uri(cimchandle)}')
            mainlog.debug(f'{jobid} vmedia_get_existing_status: {vmedia_get_existing_status(cimchandle)}')

            logger.info(f'Installation ISO mounted')

            # query CIMC CommVMediaMap Managed Object - useful for debugging
            # cimc_query_classid(cimchandle, 'CommVMediaMap')

            mainlog.info(f'{jobid} Reboot the machine...')
            logger.info(f'Rebooting the server to start the installation')
            server_power_cycle(cimchandle)
            pwrstate = server_power_state_get(cimchandle)
            mainlog.info(f'{jobid} Server power state: {pwrstate}')
            logger.info(f'Server power state: {pwrstate}')
            logger.info(f'Open KVM console to follow the installation process or wait for the job status update to [Finished].\n')

            # update status in EAIDB to 'Installation in progress'
            eaidb_update_job_status(jobid, 'Installation in progress', '')

        except Exception as e:
            mainlog.error(f'{jobid} : {str(e)}')
            logger.error('Failed to mount installation ISO')
            logger.error(format_message_for_web(e))
            # if mounting ISO failed - run cleanup tasks, update EAIDB with error message and abort
            job_cleanup(jobid, logger, mainlog)
            cimc_logout(logger, cimchandle, cimcip)
            eaidb_update_job_status(jobid, 'Error: Failed to mount installation ISO', time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime()))
            return 2

        # logout from CIMC
        cimc_logout(logger, cimchandle, cimcip)
    else:
        mainlog.debug(f'{jobid} [DRYRUN] Running install_esxi({jobid}, {cimcip}, {cimcusr}, {cimcpwd}, {isourl})')


def cimc_query_classid(cimchandle, mo_class):
    """
    Generic function for querying and printing CIMC Managed Object.

    :param cimchandle: (ImcHandle) CIMC connection handle
    :param mo_class: (str) CIMC Managed Object class name
    :return: n/a
    """
    mo = cimchandle.query_classid(mo_class)
    for MO in mo:
        print(MO)


def get_available_isos(isodir=ESXISODIR):
    """
    Get directories from ESXISODIR to build 'Select your ISO Image' dropdown menu on main page.

    :param isodir: (str) path to ESXi ISO directory
    :return: (list) list of available ISO files in ESXISODIR
    """
    dirs = [f for f in listdir(isodir) if path.isdir(path.join(isodir, f))]
    dirs.sort()
    return dirs


def job_cleanup(jobid, logger, mainlog, unmount_iso=True, dryrun=DRYRUN):
    """
    Run post-installation cleanup tasks:
    - remove kickstart file
    - remove custom installation ISO
    - remove CIMC password from database

    :param jobid: (str) job ID
    :param logger: (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :param customisodir: (str) path to custom ISO directory
    :return: n/a
    """
    if not dryrun:
        eaidb_update_job_status(jobid, 'Running cleanup tasks', '')

        mainlog.info(f'{jobid} Starting cleanup')
        logger.info('')
        logger.info(f'Starting cleanup:')

        logger.info(f'* kickstart file')
        remove_kickstart(jobid, logger, mainlog)

        logger.info(f'* custom installation ISO')
        if unmount_iso:
            cimc_unmount_iso(jobid, logger, mainlog)
        remove_custom_iso(jobid, logger, mainlog)

        logger.info(f'* remove CIMC password from database')
        eaidb_remove_cimc_password(jobid)

        # TODO: add PXE cleanup when method is implemented
        mainlog.info(f'{jobid} Cleanup finished.')
        logger.info(f'Cleanup finished.\n')
    else:
        mainlog.debug(f'{jobid} [DRYRUN] Running job cleanup tasks)')


def remove_kickstart(jobid, logger, mainlog, ksdir=KSDIR):
    """
    Remove kickstart jobid file from KSDIR.

    :param jobid: (str) job ID
    :param logger: (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :param ksdir:  (str) path to kickstart directory
    :return: n/a
    """
    kspath = path.join(ksdir, jobid + '_ks.cfg')
    mainlog.info(f'{jobid} Removing kickstart file: {kspath}')
    logger.info(f'Removing kickstart file: {kspath}')
    try:
        system(f'rm -f {kspath} 1>&2')
    except Exception as e:
        mainlog.error(f'{jobid} : Failed to remove {kspath}: {str(e)}')
        logger.error(f'Failed to remove {kspath}: {format_message_for_web(e)}')


def cimc_unmount_iso(jobid, logger, mainlog):
    """
    Unmount installation ISO on target CIMC.

    :param jobid: (str) job ID
    :param logger: (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :return: (int) Error code
    """
    mainlog.info(f'{jobid} Unmounting installation ISO from CIMC')
    logger.info(f'Unmounting installation ISO from CIMC:')
    try:
        # get CIMC IP and credentials from DB
        mainlog.info(f'{jobid} Get CIMC credentials for job ID')
        cimcip, cimcusr, cimcpwd = eaidb_get_cimc_credentials(jobid)
    except Exception as e:
        # cimcdata = False
        mainlog.error(f'{jobid} Failed to get CIMC credentials for job ID: {str(e)}')
        logger.error(f'Failed to get CIMC credentials for job ID: {format_message_for_web(e)}')
        logger.error(f'Unmount installation ISO aborted.\n')
        return 1

    try:
        # login to CIMC
        mainlog.info(f'{jobid} Login to CIMC')
        cimchandle = cimc_login(logger, cimcip, cimcusr, cimcpwd)
    except Exception as e:
        mainlog.error(f'{jobid} Failed to login to CIMC: {str(e)}')
        logger.error(f'Failed to login to CIMC: {format_message_for_web(e)}')
        logger.error(f'Unmount installation ISO aborted.\n')
        return 2

    try:
        mainlog.info(f'{jobid} Unmounting installation ISO (vmedia_mount_delete, {jobid}.iso) on CIMC {cimcip}')
        logger.info(f'Unmounting installation ISO ({jobid}.iso) on CIMC {cimcip}')
        vmedia_mount_delete(cimchandle, f'{jobid}.iso')
        cimc_logout(logger, cimchandle, cimcip)
    except Exception as e:
        mainlog.error(f'{jobid} Failed to unmount vmedia: {str(e)}')
        logger.error(f'Failed to unmount installation ISO: {format_message_for_web(e)}\n')
        return 3

    return 0


def remove_custom_iso(jobid, logger, mainlog, customisodir=CUSTOMISODIR):
    """
    Remove custom installation ISO file from CUSTOMISODIR.

    :param jobid: (str) job ID
    :param logger: (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :param customisodir: (str) path to custom ISO directory
    :return: n/a
    """
    iso_path = path.join(customisodir, jobid + '.iso')
    mainlog.info(f'{jobid} Removing custom installation ISO: {iso_path}')
    logger.info(f'Removing custom installation ISO: {iso_path}')
    try:
        system(f'rm -f {iso_path} 1>&2')
    except Exception as e:
        mainlog.error(f'{jobid} : Failed to remove {iso_path}: {str(e)}')
        logger.error(f'Failed to remove {iso_path}: {format_message_for_web(e)}')


def process_submission(jobid_list, logger_list, mainlog, form_data):
    """
    Generates installation data and starts install process.

    :param jobid_list: (list) List of (str) job ID
    :param logger: (list) List of (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :param form_data: (dict) dictionary with IP address(es) and task(s) as list items
    :return: n/a
    """

    for index in range(len(form_data['hosts'])):
        jobid = jobid_list[index]
        logger = logger_list[index]
        hostname = form_data['hosts'][index]['hostname']

        # customize kickstart config
        mainlog.info(f'{jobid} Generating kickstart file for server {hostname}')
        kscfg = generate_kickstart(jobid, form_data, index, logger, mainlog)
        
        if form_data['installmethod'] == 'customiso':
            # generate custom installation ISO
            mainlog.info(f'{jobid} Generating custom installation ISO for server {hostname}')
            generate_custom_iso(jobid, logger, mainlog, hostname, form_data['iso_image'], kscfg)

            # start ESXi hypervisor installation
            Process(target=install_esxi, args=(jobid, logger, mainlog, form_data['hosts'][index]['cimc_ip'], form_data['cimc_usr'], form_data['cimc_pwd'], jobid + '.iso')).start()

        elif form_data['installmethod'] == 'pxeboot':
            mainlog.info(f'{jobid} Generating PXE Boot files for server {hostname}')
            generate_pxe_boot(jobid, logger, mainlog, form_data['iso_image'], form_data['hosts'][index]['macaddr'])

            mainlog.info(f'{jobid} Generating EFI Boot files for server {hostname}')
            generate_efi_boot(jobid, logger, mainlog, form_data['iso_image'], form_data['hosts'][index]['macaddr'])

            mainlog.info(f'{jobid} Generating DHCP configuration for server {hostname}')
            generate_dhcp_config(jobid, logger, mainlog)
            eaidb_update_job_status(jobid, 'Ready to deploy', '')

            mainlog.info(f'{jobid} Ready to start PXE Boot installation for server {hostname}')
            logger.info(f'Ready to start PXE Boot installation - power on the server to initialize installation process.\n')


def create_jobs(form_data, installmethod, mainlog):
    """
    Create installation job for each server in form_data['hosts'] list.

    :param form_data: (dict) installatiomn data as returned by get_form_data() function
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :return: (list) list of job IDs
    """

    # interate over the list of ESXi hosts and run corresponding actions for each host
    jobid_list  = []
    logger_list = []
    for index in range(len(form_data['hosts'])):
        hostname = form_data['hosts'][index]['hostname']
        # if form_data['hosts'][index]['cimc_ip']:
        if installmethod == 'cimc':
        # Installation method: mount installation ISO with CIMC API (Cisco UCS servers only)
            cimcip = form_data['hosts'][index]['cimc_ip']
            cimcpwd = form_data['cimc_pwd']
            macaddr = ''
            jobid = generate_jobid(cimcip)
        else:
        # Installation method: PXE boot
            cimcip = ''
            cimcpwd = ''
            macaddr = form_data['hosts'][index]['macaddr']
            jobid = generate_jobid(macaddr)
        # cimcip = form_data['hosts'][index]['cimc_ip']

        # generate jobid based on CIMC IP and current timestamp
        # jobid = generate_jobid(cimcip_or_mac)

        # create logger handler
        logger = get_jobid_logger(jobid)
        logger.info(f'Processing job ID: {jobid}, server {hostname}\n')
        mainlog.info(f'{jobid} - processing job ID, server {hostname}')

        # create entry in Auto-Installer DB
        mainlog.info(f'{jobid} Saving installation data for server {hostname}')
        eaidb_create_job_entry(jobid, time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime()), hostname, form_data['hosts'][index]['host_ip'],
                                cimcip, form_data['cimc_usr'], cimcpwd, macaddr, form_data['host_netmask'], form_data['host_gateway'])

        jobid_list.append(jobid)
        logger_list.append(logger)
    # Process data on seperate thread
    Process(target=process_submission, args=(jobid_list, logger_list, mainlog, form_data)).start()
    return jobid_list


def get_logs(jobid, basedir=LOGDIR):
    """
    Get log file from basedir for specific job ID

    :param jobid: (str) job ID
    :param basedir: (str) path to jobs logs directory
    :return: n/a
    """
    # Joining the base and the requested path
    abs_path = os.path.join(basedir, jobid)

    # Return 404 if path doesn't exist
    if not os.path.exists(abs_path):
        return 'File does not exist!', 404

    # Check if path is a file and serve
    if os.path.isfile(abs_path):
        with open(abs_path, 'r') as log_file:
            return log_file.read(), 200, {'Content-Type': 'text/plain; charset=utf-8'}


def cimc_get_mo_property(cimchandle, mo_dn, mo_property):
    """
    Get CIMC Managed Object property.

    :param cimchandle: (ImcHandle) CIMC connection handle
    :param mo_dn: (str) CIMC Managed Object Distinguished Name
    :return: MO Property value
    """
    mo = cimchandle.query_dn(mo_dn)
    return getattr(mo, mo_property)


def cimc_set_mo_property(cimchandle, mo_dn, mo_property, value):
    """
    Set CIMC Managed Object property.

    :param cimchandle: (ImcHandle) CIMC connection handle
    :param mo_dn: (str) CIMC Managed Object Distinguished Name
    :param mo_property: (str) CIMC Managed Object property
    :param value: (str) Managed Object property new value
    :return: n/a
    """    
    mo = cimchandle.query_dn(mo_dn)
    setattr(mo, mo_property, value)
    cimchandle.set_mo(mo)


def cimc_vmedia_basic_set(cimchandle, logger, basic_boot_order):
    """
    Set Boot Order Policy (Basic Boot Order).

    :param cimchandle: (ImcHandle) CIMC connection handle
    :param logger: (logging.Handler) logger handler for jobid
    :param basic_boot_order: (list of dict) format
        [{"order":'1', "device-type":"cdrom", "name":"cdrom0"},
        {"order":'2', "device-type":"lan", "name":"lan"}]
        as returned by boot_order_policy_get() IMC SDK function
    :return: n/a    
    """
    try:

        vmedia = 'NULL'
        # check if vmedia on configured boot order list
        for boot_device in basic_boot_order:
            if boot_device['device-type'] == 'cdrom':
                vmedia = boot_device['order']
                logger.info(f"Discovered VMEDIA on position: {vmedia}")

        if vmedia == 'NULL':
            logger.info('No valid VMEDIA on configured boot order list - adding...')
            from imcsdk.apis.server.boot import _add_boot_device
            _add_boot_device(cimchandle, 'sys/rack-unit-1/boot-policy', {"order": "1", "device-type": "cdrom", "name": "cdrom-eai"})
            logger.info(f'Boot Order set to: {boot_order_policy_get(cimchandle)}')
        elif vmedia != '1':
            logger.info(f'VMEDIA found on configured boot order list at position: {vmedia} - moving to 1st position...')
            new_boot_order = []
            for boot_device in basic_boot_order:
                if boot_device['device-type'] != 'cdrom' and int(boot_device['order']) < int(vmedia):
                    # devices on higher position than VMEDIA - move 1 position down
                    boot_device['order'] = str(int(boot_device['order']) + 1)
                    new_boot_order.append(boot_device)
                elif boot_device['device-type'] != 'cdrom' and int(boot_device['order']) > int(vmedia):
                    # devices on lower position than VMEDIA - move 1 position down
                    new_boot_order.append(boot_device)
                else:
                    # move VMEDIA to position 1
                    boot_device['order'] = '1'
                    new_boot_order.append(boot_device)
            # apply new boot order policy
            boot_order_policy_set(cimchandle, boot_devices=new_boot_order)
            logger.info(f'Boot Order set to: {boot_order_policy_get(cimchandle)}')
    except Exception as e:
        logger.error(f'Error when running vmedia check:')
        logger.error(format_message_for_web(e))


def cimc_vmedia_advanced_check(cimchandle):
    """
    Check for valid VMEDIA on Advanced Boot Order list.
    VMEDIA is valid when state is enabled and subtype is either 'cimc-mapped-dvd' or not specified.

    :param cimchandle: (ImcHandle) CIMC connection handle
    :return: (str)  NULL if no valid VMEDIA found,
                    VMEDIA name if valid VMEDIA found,
                    Error otherwise.
    """
    vmedia_name = 'NULL'
    try:
        vmedia_list = cimchandle.query_classid('LsbootVMedia')
        if len(vmedia_list) > 0:
            for vmedia in vmedia_list:
                if getattr(vmedia, 'state').casefold() == 'enabled' and getattr(vmedia, 'subtype') != 'kvm-mapped-dvd':
                    vmedia_name = getattr(vmedia, "name")
        return vmedia_name

    except Exception as e:
        return f'Error when running vmedia check: {str(e)}'


def cimc_vmedia_advanced_set(cimchandle, logger):
    """
    Set Boot Order Precision (Advanced Boot Order).

    :param cimchandle: (ImcHandle) CIMC connection handle
    :param logger: (logging.Handler) logger handler for jobid
    :return: n/a    
    """
    try:
        logger.info('Checking for VMEDIA on Advanced Boot Order ...')
        vmedia = cimc_vmedia_advanced_check(cimchandle)
        if 'Error' in vmedia:
            logger.error(f'{vmedia}. Aborting.')
            return 33
        elif vmedia == 'NULL':
            logger.info('No valid VMEDIA on configured boot order list - adding')
            # append vmedia to boot order list
            vmedia_order = str(len(boot_precision_configured_get(cimchandle)) + 1)
            from imcsdk.apis.server.boot import _add_boot_device
            vmedia = "vmedia-eai"
            _add_boot_device(cimchandle, 'sys/rack-unit-1/boot-precision', {"order": vmedia_order, "device-type": "vmedia", "name": vmedia})
            logger.info(f'Boot Order set to: {boot_precision_configured_get(cimchandle)}')
        else:
            logger.info(f'VMEDIA found - using: {vmedia}')

        # set vmedia as OneTimePrecisionBootDevice
        cimc_set_mo_property(cimchandle, 'sys/rack-unit-1/one-time-precision-boot', 'device', vmedia)
        logger.info(f'Configured One time boot device: {vmedia}')
    except Exception as e:
        logger.error(f'Error when trying to set One time boot device:')
        logger.error(format_message_for_web(e))

    
def cimc_vmedia_set(cimchandle, logger):
    """
    Set VMEDIA on Boot Order.

    :param cimchandle: (ImcHandle) CIMC connection handle
    :param logger: (logging.Handler) logger handler for jobid
    :return: n/a    
    """
    try:
        # check Secure Boot
        logger.info('Checking UEFI Secure Boot')
        secure_boot = cimc_get_mo_property(cimchandle, 'sys/rack-unit-1/boot-policy/boot-security', 'secure_boot')
        if not secure_boot.casefold() == 'disabled':
            logger.error('UEFI Secure Boot enabled - it has to be disabled for the installation to proceed. Aborting.')
            return 33
        else:
            logger.info('UEFI Secure Boot disabled - OK to proceed.')

        # check Basic vs Advanced Boot mode
        basic_boot_order = boot_order_policy_get(cimchandle)
        if len(basic_boot_order) > 0:
            # set VMEDIA as first device on Basic Boot Order list
            logger.info(f'Discovered Basic Boot Order: {len(basic_boot_order)} devices, {basic_boot_order}')
            cimc_vmedia_basic_set(cimchandle, logger, basic_boot_order)
        else:
            # ad VMEDIA to Advanced Boot Order and set it as One Time Boot Device
            adv_boot_order = boot_precision_configured_get(cimchandle)
            logger.info(f'Discovered Advanced Boot Order: {len(adv_boot_order)} devices, {adv_boot_order}')
            cimc_vmedia_advanced_set(cimchandle, logger)

    except Exception as e:
        logger.error(f'Error when setting VMedia:')
        logger.error(format_message_for_web(e))


def generate_pxe_boot(jobid, logger, mainlog, iso_image, macaddr, dryrun=DRYRUN, pxejinja=PXETEMPLATE, pxedir=PXEDIR, eai_ip=EAIHOST_IP):
    """
    Build custom PXE config based on provided parameters and PXETEMPLATE.

    :param jobid: (str) job ID
    :param logger: (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :param iso_image: (str) installation ISO name
    :param dryrun: (bool) Toggle Auto-Installer "dry-run" mode
    :param pxejinja: (str) PXE boot jinja template file name
    :param pxedir: (str) Destination directory to save XPE boot file 
    :param eai_ip: (str) Auto-Installer host system IP address
    :return n/a
    """
    if not dryrun:
        try:
            with open(pxejinja, 'r') as pxetemplate_file:
                pxetemplate = Template(pxetemplate_file.read())

            # generate PXE config file name based on MAC address (add prefix + replace ':' with '-')
            pxecfg_path = path.join(pxedir, f"01-{macaddr.replace(':', '-')}")

            logger.info(f'Saving PXE boot file as: {pxecfg_path}')

            # read jinja template from file and render using read variables
            with open(pxecfg_path, 'w+') as pxefile:
                pxefile.write(pxetemplate.render(iso_image=f'iso/{iso_image}', ksurl=f'http://{eai_ip}/ks/{jobid}_ks.cfg'))

        except Exception as e:
            logger.error(f'Failed to save PXE boot file: {format_message_for_web(e)}')
            mainlog.error(f'{jobid} Failed to save PXE boot file: {str(e)}')
    else:
        logger.info(f'[DRYRUN] Generating PXE boot file')
        mainlog.info(f'{jobid} [DRYRUN] Generating PXE boot file')


def generate_efi_boot(jobid, logger, mainlog, iso_image, macaddr, dryrun=DRYRUN, tftpboot=TFTPBOOT, tftpisodir=TFTPISODIR, eai_ip=EAIHOST_IP):
    """
    Generate EFI boot structure:
    - subdirectory in tftpboot directory (example: /tftboot/01-aa-bb-cc-dd-ee-ff)
    - custom boot.cfg file based on boot.cfg from selected ISO

    :param jobid: (str) job ID
    :param logger: (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :param iso_image: (str) installation ISO name
    :param macaddr: (str) MAC address (example: aa:bb:cc:dd:ee:ff)
    :param dryrun: (bool) Toggle Auto-Installer "dry-run" mode
    :param tftpboot: (str) TFTPBOOT directory path (default: /tftpboot/)
    :param tftpisodir: (str) ISO subdirectory in TFTPBOOT directory (default: /tftpboot/iso)
    :param eai_ip: (str) Auto-Installer host system IP address
    :return n/a     
    """
    if not dryrun:
        try:
            from shutil import which
            mkdir_cmd = which('mkdir')
            efidir = path.join(tftpboot, f"01-{macaddr.replace(':', '-')}")
            system(f'{mkdir_cmd} {efidir}')

            # read original boot.cfg
            bootcfg_orig_path = path.join(tftpisodir, iso_image, 'boot.cfg')
            with open(bootcfg_orig_path, 'r') as bootcfg_file:
                bootcfg = bootcfg_file.read()

            # search for kernelopt line and replace parameters with ksurl
            bootcfg = re.sub(r"kernelopt.*", f'kernelopt=ks=http://{eai_ip}/ks/{jobid}_ks.cfg', bootcfg)

            bootcfg_path = path.join(efidir, 'boot.cfg')
            logger.info(f'Saving EFI boot file as: {bootcfg_path}')

            with open(bootcfg_path, 'w+') as bootcfg_custom_file:
                bootcfg_custom_file.write(bootcfg)

        except Exception as e:
            logger.error(f'Failed to save EFI boot.cfg file: {format_message_for_web(e)}')
            mainlog.error(f'{jobid} Failed to save EFI boot.cfg file: {str(e)}')
    else:
        logger.info(f'[DRYRUN] Generating EFI boot file')
        mainlog.info(f'{jobid} [DRYRUN] Generating EFI boot file')            