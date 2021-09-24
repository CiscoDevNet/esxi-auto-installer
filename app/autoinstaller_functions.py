# VMware Auto-Installer functions
from imcsdk.imchandle import ImcHandle
from imcsdk.apis.server.vmedia import *
from imcsdk.apis.server.serveractions import server_power_cycle, server_power_state_get

from generic_functions import *
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
    form_data['iso_image'] = form_result['ISOFile']
    form_data['rootpw'] = form_result['ROOTPW']
    form_data['vmnic'] = form_result['VMNIC']
    form_data['vlan'] = form_result['VLAN']
    form_data['firstdisk'] = form_result['FirstDisk']
    form_data['firstdisktype'] = form_result['FirstDiskType']
    form_data['enable_ssh'] = form_result.get('SSH')
    form_data['clearpart'] = form_result.get('clearpart')

    # get static routes (if provided)
    form_data['static_routes_set'] = form_result['StaticRoute']
    form_data['static_routes'] = []
    if form_data['static_routes_set']:
        for key, value in form_result.items():
            if 'StaticSubnet' in key:
                seq = key.replace('StaticSubnet', '')
                form_data['static_routes'].append({'subnet': form_result[key],
                                                   'mask': form_result['StaticMask' + seq],
                                                   'gateway': form_result['StaticGateway' + seq]})

    # get common settings - CIMC credentials and subnet/gateway
    form_data['cimc_usr'] = form_result['CIMCUSR']
    form_data['cimc_pwd'] = form_result['CIMCPWD']
    form_data['host_prefix'] = form_result['HOSTPREFIX']
    form_data['host_suffix'] = form_result['HOSTSUFFIX']
    # form_data['host_subnet'] = form_result['SUBNET']
    # calculate subnet based on gateway IP address and netmask (needed for PXE booted installation)
    form_data['host_subnet'] = ip_network(form_result['GATEWAY'] + '/' + form_result['NETMASK'], strict=False).network_address
    form_data['host_netmask'] = form_result['NETMASK']
    form_data['host_gateway'] = form_result['GATEWAY']
    form_data['dns1'] = form_result['DNS1']
    form_data['dns2'] = form_result['DNS2']

    # get ESXi host and CIMC IP address(es)
    form_data['hosts'] = []
    for key, value in form_result.items():
        if 'HOSTNAME' in key:
            seq = key.replace('HOSTNAME', '')
            hostname = form_result['HOSTPREFIX'] + form_result[key] + form_result['HOSTSUFFIX']
            form_data['hosts'].append({'hostname': hostname,
                                       'ipaddr': form_result['IPADDR' + seq],
                                       'cimcip': form_result['CIMCIP' + seq]})
    mainlog.debug(form_data)
    return form_data


def generate_kickstart(jobid, form_data, index, logger, mainlog, eai_host_ip=EAIHOST, dryrun=DRYRUN, ksjinja=KSTEMPLATE, ksdir=KSDIR):
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
    if form_data['static_routes_set'] == 'True':
        for route in form_data['static_routes']:
            net_cidr = route['subnet'] + '/' + route['mask']
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
    if form_data['enable_ssh']:
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
    rootpw = form_data['rootpw']
    vmnicid = form_data['vmnic']
    vlan = form_data['vlan']
    netmask = form_data['host_netmask']
    gateway = form_data['host_gateway']
    hostname = form_data['hosts'][index]['hostname']
    ipaddr = form_data['hosts'][index]['ipaddr']

    # read jinja template from file and render using read variables
    with open(ksjinja, 'r') as kstemplate_file:
        kstemplate = Template(kstemplate_file.read())
    kickstart = kstemplate.render(clearpart=clearline, install=install, rootpw=rootpw, vmnicid='vmnic' + vmnicid, vlan=vlan,
                                  ipaddr=ipaddr, netmask=netmask, gateway=gateway, hostname=hostname, pre_section=pre_section, dnsservers=dnsservers,
                                  set_def_gw=set_def_gw, enable_ssh=enable_ssh, disable_ipv6=disable_ipv6,
                                  eai_host_ip=eai_host_ip, jobid=jobid)
    # remove password before saving kickstart to log file
    logger.info(f"Generated kickstart configuration:\n{re.sub(r'rootpw.*', 'rootpw ***********', kickstart)}\n")
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

    # STEP 1: save ISO to uploaddir (default: /opt/eai/upload/<iso_filename>)
    iso_save_path = path.join(uploaddir, uploaded_file.filename)
    uploaded_file.save(iso_save_path)

    # STEP 2: create mountpoint under tmpisodir (default: /opt/eai/upload/tmp/<iso_filebase>)
    filebase = path.splitext(uploaded_file.filename)[0]
    mountdir = path.join(tmpisodir, filebase)
    mainlog.debug(f'Create mountpoint: {mountdir}')
    system('sudo /usr/bin/mkdir -p ' + mountdir + ' 1>&2')

    # STEP 3: mount the ISO
    mainlog.debug(f'Mount the ISO: ')
    mainlog.debug(f'CMD: sudo /usr/bin/mount -r -o loop ' + iso_save_path + ' ' + mountdir)
    system('sudo /usr/bin/mount -r -o loop ' + iso_save_path + ' ' + mountdir + ' 1>&2')
    system('ls -la ' + mountdir + ' 1>&2')

    # STEP 4: copy mounted ISO content to extracted_iso_dir (default: /opt/eai/exsi-iso/<iso_filebase>)
    mainlog.debug(f'CMD: cp -R {mountdir} {extracted_iso_dir}')
    system('cp -R ' + mountdir + ' ' + extracted_iso_dir + ' 1>&2')
    system('sudo /usr/bin/chown apache.apache ' + extracted_iso_dir + ' 1>&2')
    system('/usr/bin/chmod 644 ' + extracted_iso_dir + '/boot.cfg' + ' 1>&2')

    # STEP 5: cleanup - unmount and delete ISO and temporary mountpoint
    system(f'sudo /usr/bin/umount {mountdir} 1>&2')
    mainlog.debug(f'Cleanup - remove ISO: {iso_save_path} and mountdir: {mountdir}')
    system('rm -f ' + iso_save_path + ' 1>&2')
    system('sudo /usr/bin/rmdir ' + mountdir + ' 1>&2')

    # INFO: check content of tftpisodir directory (INFO only)
    mainlog.info(f'New ISO: {filebase}')
    mainlog.info(f'Listing {extracted_iso_dir} content:')
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
        mainlog.debug(f'{jobid} cp -R {path.join(isodir, iso_image)} {tmpisodir} 1>&2')
        system(f'cp -R {path.join(isodir, iso_image)} {tmpisodir} 1>&2')

        system(f'chmod -R +w {tmpisodir} 1>&2')
        mainlog.debug(f'{jobid} cp {kscfg_path} {path.join(tmpisodir, "ks.cfg")} 1>&2')
        system(f'cp {kscfg_path} {path.join(tmpisodir, "ks.cfg")} 1>&2')

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

        # Create a connection handle
        cimchandle = ImcHandle(cimcip, cimcusr, cimcpwd, cimcport)
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


def install_esxi(jobid, logger, mainlog, cimcip, cimcusr, cimcpwd, iso_image, eai_ip=EAIHOST, dryrun=DRYRUN):

    isourl = 'http://' + eai_ip + '/custom-iso/' + iso_image
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
            # if cimc_login failed - run cleanup tasks, update EAIDB with error message and abort
            job_cleanup(jobid, logger, mainlog)
            eaidb_update_job_status(jobid, 'Error: Failed to login to CIMC', time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime()))
            return 1

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


def job_cleanup(jobid, logger, mainlog, dryrun=DRYRUN):
    if not dryrun:
        eaidb_update_job_status(jobid, 'Running cleanup tasks', '')

        mainlog.info(f'{jobid} Starting cleanup')
        logger.info('')
        logger.info(f'Starting cleanup:')

        logger.info(f'* kickstart file')
        remove_kickstart(jobid, logger, mainlog)

        logger.info(f'* custom installation ISO')
        # TODO: skip cimc_unmount_iso if cleanup has been triggered due to CIMC login error
        cimc_unmount_iso(jobid, logger, mainlog)
        remove_custom_iso(jobid, logger, mainlog)

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
        mainlog.info(f'{jobid} Unmounting installation ISO (vmedia_mount_remove_image) on CIMC {cimcip}')
        logger.info(f'Unmounting installation ISO on CIMC {cimcip}')
        # TODO: consider removing specific image instead of 'iso' type - check method vmedia_mount_delete(handle, volume_name)
        vmedia_mount_remove_image(cimchandle, image_type='iso')
        cimc_logout(logger, cimchandle, cimcip)
    except Exception as e:
        mainlog.error(f'{jobid} Failed to unmount vmedia: {str(e)}')
        logger.error(f'Failed to unmount installation ISO: {format_message_for_web(e)}\n')
        return 3


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

        # generate custom installation ISO
        mainlog.info(f'{jobid} Generating custom installation ISO for server {hostname}')
        generate_custom_iso(jobid, logger, mainlog, hostname, form_data['iso_image'], kscfg)

        # start ESXi hypervisor installation
        Process(target=install_esxi, args=(jobid, logger, mainlog, form_data['hosts'][index]['cimcip'], form_data['cimc_usr'],
                                            form_data['cimc_pwd'], jobid + '.iso')).start()
