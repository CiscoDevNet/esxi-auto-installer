# VMware Auto-Installer functions
from platform import system_alias
from imcsdk.imchandle import ImcHandle
from imcsdk.apis.server.vmedia import *
from imcsdk.apis.server.boot import *
from imcsdk.apis.server.serveractions import (
    server_power_state_get,
    server_power_up,
    server_power_cycle,
)

from generic_functions import *
from helper_functions import *
from config import *

from os import system, path, listdir, WEXITSTATUS
from jinja2 import Template
import re
from ipaddress import ip_network
from multiprocessing import Process
from shutil import which

## Libraries to support enable SSH ##
import requests
import xml.etree.ElementTree as ET
import datetime


def get_form_data(mainlog, form_result):
    """
    Takes FlaskForm result as an input and returns dictionary with kickstart configuration and network details
    for ESXi server(s) and CIMC(s)

    :param mainlog: application main logger handler
    :param form_result: (werkzeug.datastructures.ImmutableMultiDict)
    :return: form_data: (dict) dictionary with IP address(es) and task(s) as list items
    """

    mainlog.info(f"Reading data from web form:")

    form_data = {}
    form_data["iso_image"] = form_result["iso_image"]
    form_data["root_pwd"] = form_result["root_pwd"]
    form_data["vmnic"] = form_result["vmnic"]
    form_data["vlan"] = form_result["vlan"]
    form_data["firstdisk"] = form_result["firstdisk"]
    form_data["firstdisktype"] = form_result["firstdisktype"]
    form_data["diskpath"] = form_result["diskpath"]
    form_data["enablessh"] = form_result.get("enablessh")
    form_data["clearpart"] = form_result.get("clearpart")

    # get static routes (if provided)
    form_data["static_routes"] = []
    if form_result["static_routes_set"] == "True":
        for key, value in form_result.items():
            if "subnet_ip" in key:
                seq = key.replace("subnet_ip", "")
                form_data["static_routes"].append(
                    {
                        "subnet_ip": form_result[key],
                        "cidr": form_result["cidr" + seq],
                        "gateway": form_result["gateway" + seq],
                    }
                )

    # get common settings - CIMC credentials and subnet/gateway
    form_data["installmethod"] = form_result["installmethod"]
    if form_data["installmethod"] != "pxeboot":
        form_data["cimc_usr"] = form_result["cimc_usr"]
        form_data["cimc_pwd"] = form_result["cimc_pwd"]
    form_data["host_prefix"] = form_result["host_prefix"]
    form_data["host_suffix"] = form_result["host_suffix"]
    # calculate subnet based on gateway IP address and netmask (needed for PXE booted installation)
    form_data["host_subnet"] = ip_network(
        form_result["host_gateway"] + "/" + form_result["host_netmask"], strict=False
    ).network_address
    form_data["host_netmask"] = form_result["host_netmask"]
    form_data["host_gateway"] = form_result["host_gateway"]
    form_data["dns1"] = form_result["dns1"]
    form_data["dns2"] = form_result["dns2"]

    # get ESXi host and CIMC IP address(es)
    form_data["hosts"] = []
    if form_data["installmethod"] == "pxeboot":
        for key, value in form_result.items():
            if "hostname" in key:
                seq = key.replace("hostname", "")
                hostname = (
                    form_result["host_prefix"]
                    + form_result[key]
                    + form_result["host_suffix"]
                )
                macaddr = (
                    form_result["macaddr" + seq]
                    .replace(":", "")
                    .replace(".", "")
                    .replace("-", "")
                    .lower()
                )
                macaddr = ":".join([macaddr[i : i + 2] for i in range(0, 12, 2)])
                form_data["hosts"].append(
                    {
                        "hostname": hostname,
                        "host_ip": form_result["host_ip" + seq],
                        "macaddr": macaddr,
                    }
                )
    else:
        for key, value in form_result.items():
            if "hostname" in key:
                seq = key.replace("hostname", "")
                hostname = (
                    form_result["host_prefix"]
                    + form_result[key]
                    + form_result["host_suffix"]
                )
                form_data["hosts"].append(
                    {
                        "hostname": hostname,
                        "host_ip": form_result["host_ip" + seq],
                        "cimc_ip": form_result["cimc_ip" + seq],
                    }
                )
    # print(form_data)
    mainlog.debug(form_data)
    return form_data


def generate_kickstart(
    jobid,
    form_data,
    index,
    logger,
    mainlog,
    eai_host_ip=EAIHOST_IP,
    dryrun=DRYRUN,
    ksjinja=KSTEMPLATE,
    ksdir=KSDIR,
):
    logger.info(f"Generating kickstart file for server")

    # set installation disk
    if form_data["firstdisk"] == "firstdiskfound":
        # first disk found
        firstdisk_install = "firstdisk"
        cleardisk = "firstdisk"
    elif form_data["firstdisk"] == "firstdisk":
        # first disk: local, remote or usb
        firstdisk_install = "firstdisk=" + form_data["firstdisktype"]
        cleardisk = "firstdisk=" + form_data["firstdisktype"]
    elif form_data["firstdisk"] == "diskpath":
        firstdisk_install = "disk=" + form_data["diskpath"]
        cleardisk = "drives=" + form_data["diskpath"]

    # customize install and (optionally) clearpart lines
    install = f"install --{firstdisk_install} --overwritevmfs --ignoreprereqwarnings --ignoreprereqerrors --forceunsupportedinstall"
    if form_data["clearpart"]:
        clearline = "clearpart --" + cleardisk + " --overwritevmfs\n"
    else:
        clearline = ""

    # generate pre-section if static routes have been provided
    # i.e. 'localcli network ip route ipv4 add -n NET_CIDR -g GATEWAY'
    static_routes = ""
    # if form_data['static_routes_set'] == 'True':
    if form_data["static_routes"]:
        for route in form_data["static_routes"]:
            net_cidr = route["subnet_ip"] + "/" + str(route["cidr"])
            static_routes += f"localcli network ip route ipv4 add -n {net_cidr} -g {route['gateway']}\n"
        static_routes = "# Set static routes\n" + static_routes

    # additional default route set when static route has been selected in %pre section
    if static_routes:
        set_def_gw = (
            "# Set Default Gateway\n"
            + f"esxcli network ip route ipv4 add --gateway {form_data['host_gateway']} --network 0.0.0.0\n"
        )
    else:
        set_def_gw = ""

    # Add IP addressing during the pre stage if this is an ISO boot.
    # This allows non-DHCP boots to get an address so they can update
    # the installer status.
    if form_data["installmethod"] != "pxeboot":
        pre_network = True
    else:
        pre_network = False

    # enable ssh
    if form_data["enablessh"]:
        enable_ssh = True
    else:
        enable_ssh = False

    # process DNS
    if form_data["dns1"] != "":
        if form_data["dns2"] != "":
            dnsservers = form_data["dns1"] + "," + form_data["dns2"]
        else:
            dnsservers = form_data["dns1"]
    else:
        dnsservers = ""

    # remaining host data
    import crypt

    rootpw_hash = crypt.crypt(form_data["root_pwd"], crypt.mksalt(crypt.METHOD_SHA512))

    vmnicid = form_data["vmnic"]
    vlan = form_data["vlan"]
    netmask = form_data["host_netmask"]
    gateway = form_data["host_gateway"]
    hostname = form_data["hosts"][index]["hostname"]
    ipaddr = form_data["hosts"][index]["host_ip"]

    # read jinja template from file and render using read variables
    with open(ksjinja, "r") as kstemplate_file:
        kstemplate = Template(kstemplate_file.read())
    kickstart = kstemplate.render(
        clearpart=clearline,
        install=install,
        rootpw_hash=rootpw_hash,
        vmnicid="vmnic" + vmnicid,
        vlan=vlan,
        ipaddr=ipaddr,
        netmask=netmask,
        gateway=gateway,
        hostname=hostname,
        dnsservers=dnsservers,
        pre_network=pre_network,
        static_routes=static_routes,
        set_def_gw=set_def_gw,
        enable_ssh=enable_ssh,
        eai_host_ip=eai_host_ip,
        jobid=jobid,
    )
    # remove password before saving kickstart to log file
    logger.info(
        f"Generated kickstart configuration:\n{re.sub(r'rootpw.*', 'rootpw --iscrypted ***********', kickstart)}\n"
    )
    if not dryrun:
        kspath = path.join(ksdir, jobid + "_ks.cfg")
        with open(kspath, "w+") as ksfile:
            ksfile.write(kickstart)
            mainlog.debug(
                f"{jobid} Generated kickstart config for host: {hostname} saved to {kspath}"
            )
            logger.info(f"Kickstart config for host: {hostname} saved to {kspath}\n")
        return kspath
    else:
        mainlog.debug(
            f"{jobid} [DRYRUN] Generated kickstart config for host: {hostname}"
        )
        return "not a real kscfg path"


def iso_extract(
    mainlog,
    uploaded_file,
    uploaddir=UPLOADDIR,
    tmpisodir=MNTISODIR,
    extracted_iso_dir=ESXISODIR,
):
    """
    Saves uploaded ISO file, mounts it and extracts files to subdirectory in ESXISODIR.

    :param mainlog: application main logger handler
    :param uploaded_file: (str) ISO file name
    :param uploaddir: (str) path to directory where uploaded ISO file is saved
    :param tmpisodir: (str) path to directory where uploaded ISO gets mounted
    :param extracted_iso_dir: (str) path to directory with extracted ESXi ISOs
    :return: (str) status message (OK or errore message in case of failure)
    """

    try:

        # get system commands paths
        mkdir_cmd = which("mkdir")
        mount_cmd = which("mount")
        umount_cmd = which("umount")
        chmod_cmd = which("chmod")
        rmdir_cmd = which("rmdir")
        cp_cmd = which("cp")
        rm_cmd = which("rm")
        ls_cmd = which("ls")

        # pre-check if this ISO is not already available in ESXISODIR
        filebase = path.splitext(uploaded_file.filename)[0]
        if path.isdir(path.join(extracted_iso_dir, filebase)):
            mainlog.error(
                f"ISO {filebase} already available for installation - upload aborted"
            )
            return f"ISO {filebase} already available for installation"

        # STEP 1: save ISO to uploaddir (default: /opt/eai/upload/<iso_filename>)
        mainlog.info(f"Saving ISO: {uploaded_file.filename}")
        iso_save_path = path.join(uploaddir, uploaded_file.filename)
        uploaded_file.save(iso_save_path)

        mainlog.info(f"Extracting uploaded ISO: {uploaded_file.filename}")

        # STEP 2: create mountpoint under tmpisodir (default: /opt/eai/upload/tmp/<iso_filebase>)
        mountdir = path.join(tmpisodir, filebase)
        mainlog.info(f"Create mountpoint: {mountdir}")
        system(f"{mkdir_cmd} -p {mountdir} 1>&2")

        # STEP 3: mount the ISO
        mainlog.info(f"Mount the ISO: ")
        command = f"{mount_cmd} -r -o loop {iso_save_path} {mountdir} 1>&2"
        mainlog.debug(f"CMD: {command}")
        if WEXITSTATUS(system(command)):
            raise Exception("Failed to mount ISO")
        system(f"{ls_cmd} -la {mountdir} 1>&2")

        # STEP 4: copy mounted ISO content to extracted_iso_dir (default: /opt/eai/exsi-iso/<iso_filebase>)
        command = f"{cp_cmd} -R {mountdir} {extracted_iso_dir} 1>&2"
        mainlog.debug(f"CMD: {command}")
        if WEXITSTATUS(system(command)):
            raise Exception("Failed to copy ISO files to target directory")

        # set boot.cfg to be writable, so that it can be modified per each installation job
        bootcfg_path = path.join(extracted_iso_dir, filebase, "boot.cfg")
        mainlog.info(f"Checking for boot.cfg file: {bootcfg_path}")
        if not path.isfile(bootcfg_path):
            mainlog.error(f"{bootcfg_path} file does not exist - aborting")
            err_msg = "Missing boot.cfg file"
            raise Exception("Missing boot.cfg file")
        command = (
            f'{chmod_cmd} 644 {path.join(extracted_iso_dir, filebase, "boot.cfg")} 1>&2'
        )
        mainlog.debug(f"CMD: {command}")
        if WEXITSTATUS(system(command)):
            raise Exception("Failed to change boot.cfg file permissions")

        # STEP 5: cleanup - unmount and delete ISO and temporary mountpoint
        system(f"{umount_cmd} {mountdir} 1>&2")
        mainlog.info(f"Cleanup - remove ISO: {iso_save_path} and mountdir: {mountdir}")
        system(f"{rm_cmd} -f {iso_save_path} 1>&2")
        system(f"{rmdir_cmd} {mountdir} 1>&2")

        # INFO: check content of ESXISODIR directory (INFO only)
        mainlog.info(f"New ISO: {filebase}")
        mainlog.debug(f"Listing {extracted_iso_dir} content:")
        dirs = [
            f
            for f in listdir(extracted_iso_dir)
            if path.isdir(path.join(extracted_iso_dir, f))
        ]
        mainlog.debug(dirs)
        system(f"{ls_cmd} -la {extracted_iso_dir} 1>&2")
        return "OK"

    except Exception as err_msg:
        mainlog.error(f"Errors during extracting ISO: {str(err_msg)}")
        iso_cleanup_on_failed_extract(mainlog, uploaded_file)
        return str(err_msg)


def iso_prepare_tftp(
    mainlog,
    uploaded_file,
    extracted_iso_dir=ESXISODIR,
    tftpisodir=TFTPISODIR,
    tftpdir=TFTPBOOT,
    pxedir=PXEDIR,
):
    """
    Copy files extracted from uploaded ESXi ISO to TFTPBOOT directory and prepare PXE boot structure.

    :param mainlog: application main logger handler
    :param uploaded_file: (str) ISO file name
    :param extracted_iso_dir: (str) path to directory with extracted ESXi ISOs (default: /opt/eai/esxi-iso)
    :param tftpisodir: (str) path to iso subdirectory in tftpboot directory (default: /opt/eai/tftpboot/iso)
    :param tftpdir: (str) path to tftpboot directory (default: /opt/eai/tftpboot)
    :param pxedir: (str) path to directory where PXE boot configuration files are saved (default: /opt/eai/tftpboot/pxelinux.cfg)
    """

    try:
        cp_cmd = which("cp")
        rm_cmd = which("rm")
        mkdir_cmd = which("mkdir")
        chmod_cmd = which("chmod")

        filebase = path.splitext(uploaded_file.filename)[0]
        target_iso_dir = path.join(tftpisodir, filebase)

        # initial check for PXE boot files
        if not path.isfile(path.join(tftpdir, "pxelinux.0")):
            raise Exception(f"Missing PXE boot files in {tftpdir} directory")

        # prepare tftpboot directory structure on first run
        if not path.isdir(tftpisodir):
            mainlog.info(f"tftpboot: creating {tftpisodir} directory")
            if WEXITSTATUS(system(f"{mkdir_cmd} {tftpisodir}")):
                raise Exception(f"Failed to create {tftpisodir} directory")

        if not path.isdir(pxedir):
            mainlog.info(f"tftpboot: creating {pxedir} directory")
            if WEXITSTATUS(system(f"{mkdir_cmd} {pxedir}")):
                raise Exception(f"Failed to create {pxedir} directory")

        # prepare uploaded ISO for PXE boot
        mainlog.info(f"tftpboot: copy and prepare {filebase} installation media.")
        source_iso_dir = path.join(extracted_iso_dir, filebase)

        # copy files from 'vanilla' ISO directory to target subdirectory under TFTPISODIR
        mainlog.info(f"Copy ISO files to target subdirectory: {target_iso_dir}")
        if WEXITSTATUS(system(f"{cp_cmd} -R {source_iso_dir} {tftpisodir} 1>&2")):
            raise Exception(f"Failed to copy ISO files to {tftpisodir} directory")

        bootcfg_path = path.join(target_iso_dir, "boot.cfg")
        mainlog.info(f"Modify {bootcfg_path} for PXE boot")
        # read original boot.cfg
        with open(bootcfg_path, "r") as bootcfg_file:
            bootcfg = bootcfg_file.read()
        # customize boot.cfg file
        title = f"title=Loading ESXi installer - {filebase}"
        prefix = f"prefix=iso/{filebase}"
        # customize 'title' and 'prefix'
        bootcfg = re.sub(r"title.*", title, bootcfg)
        if "prefix" in bootcfg:
            bootcfg = re.sub(r"prefix.*", prefix, bootcfg)
        else:
            # if there is no 'prefix=' line - add it just before 'kernel=' line
            bootcfg = re.sub(r"kernel=", prefix + "\nkernel=", bootcfg)
        # remove '/' from 'kernel=' and 'modules=' paths
        bootcfg = re.sub(r"kernel=/", "kernel=", bootcfg)
        # findall returns a list - extract string in position [0] to run replace() function
        modules = re.findall("^modules=.*", bootcfg, re.MULTILINE)[0].replace("/", "")
        bootcfg = re.sub(r"modules=.*", modules, bootcfg)

        # save customized boot.cfg
        if WEXITSTATUS(system(f"chmod +w {bootcfg_path}")):
            raise Exception(f"Failed to make {bootcfg_path} file writeable")
        with open(bootcfg_path, "w+") as bootcfg_file:
            bootcfg_file.write(bootcfg)
        mainlog.info(f"tftpboot: installation media for {filebase} ready.")

        # prepare mboot EFI file on first run
        mbootefi = path.join(tftpdir, "mboot.efi")
        if not path.isfile(mbootefi):
            mainlog.info(f"tftpboot: creating {mbootefi} file")
            command = f"{cp_cmd} {path.join(target_iso_dir, 'efi', 'boot', 'bootx64.efi')} {mbootefi}"
            if WEXITSTATUS(system(command)):
                raise Exception(f"Failed to create {mbootefi} file")
        return "OK"

    except Exception as err_msg:
        mainlog.error(f"Errors during preparing tftpboot: {str(err_msg)}")
        iso_cleanup_on_failed_extract(mainlog, uploaded_file)
        return str(err_msg)


def iso_cleanup_on_failed_extract(
    mainlog,
    uploaded_file,
    uploaddir=UPLOADDIR,
    tmpisodir=MNTISODIR,
    extracted_iso_dir=ESXISODIR,
    tftpisodir=TFTPISODIR,
):
    """
    Clean up files and directories in case on an error during iso_extract() or iso_prepare_tftp() execution.

    :param mainlog: application main logger handler
    :param uploaded_file: (str) ISO file name
    :param uploaddir: (str) path to directory where uploaded ISO file is saved (default: /opt/eai/upload)
    :param tmpisodir: (str) path to directory where uploaded ISO gets mounted (default: /opt/eai/upload/mnt)
    :param extracted_iso_dir: (str) path to directory with extracted ESXi ISOs (default: /opt/eai/esxi-iso)
    :param tftpisodir: (str) path to iso subdirectory in tftpboot directory (default: /opt/eai/tftpboot/iso)
    """

    # get system commands paths
    umount_cmd = which("umount")
    chmod_cmd = which("chmod")
    rmdir_cmd = which("rmdir")
    rm_cmd = which("rm")

    # target paths
    iso_save_path = path.join(uploaddir, uploaded_file.filename)
    filebase = path.splitext(uploaded_file.filename)[0]
    mountdir = path.join(tmpisodir, filebase)
    target_iso_dir = path.join(tftpisodir, filebase)
    target_iso_subdirectory = path.join(extracted_iso_dir, filebase)

    mainlog.info(f"Running cleanup")
    if path.isdir(target_iso_dir):
        mainlog.info(f"Cleanup: removing target TFTP ISO subdirectory {target_iso_dir}")
        system(f"{chmod_cmd} -R 777 {target_iso_dir} 1>&2")
        system(f"{rm_cmd} -rf {target_iso_dir} 1>&2")
    if path.isdir(target_iso_subdirectory):
        mainlog.info(f"Cleanup: removing ISO directory {target_iso_subdirectory}")
        system(f"{chmod_cmd} -R 777 {target_iso_subdirectory} 1>&2")
        system(f"{rm_cmd} -rf {target_iso_subdirectory} 1>&2")
    mainlog.info(f"Cleanup: unmounting ISO from {mountdir}")
    system(f"{umount_cmd} {mountdir} 1>&2")
    mainlog.info(f"Cleanup: removing ISO: {iso_save_path} and mountdir: {mountdir}")
    system(f"{rm_cmd} -f {iso_save_path} 1>&2")
    system(f"{rmdir_cmd} {mountdir} 1>&2")
    mainlog.info(f"Cleanup: finished.")


def generate_custom_iso(
    jobid,
    logger,
    mainlog,
    hostname,
    iso_image,
    kscfg_path,
    dryrun=DRYRUN,
    isodir=ESXISODIR,
    customisodir=CUSTOMISODIR,
):
    if not dryrun:
        mainlog.info(
            f"{jobid} Generating custom installation ISO for host: {hostname} using ESXi ISO {iso_image}"
        )
        logger.info(
            f"Generating custom installation ISO for host: {hostname} using ESXi ISO {iso_image}"
        )

        # copy mounted ISO content to customisodir (i.e. /opt/esxi-iso/<iso_filebase>)
        tmpisodir = path.join(customisodir, jobid)
        command = f"cp -R {path.join(isodir, iso_image)} {tmpisodir} 1>&2"
        mainlog.debug(f"{jobid} {command}")
        system(command)

        system(f"chmod -R +w {tmpisodir} 1>&2")
        command = f'cp {kscfg_path} {path.join(tmpisodir, "ks.cfg")} 1>&2'
        mainlog.debug(f"{jobid} {command}")
        system(command)

        # prepare boot.cfg
        # read original boot.cfg
        bootcfg_path = path.join(tmpisodir, "boot.cfg")
        with open(bootcfg_path, "r") as bootcfg_file:
            bootcfg = bootcfg_file.read()

        # customize boot.cfg file - title and kernelopt lines
        title = "title=Loading ESXi " + iso_image + " installer for server: " + hostname
        bootcfg = re.sub(r"title.*", title, bootcfg)
        kernelopt = "kernelopt=ks=cdrom:/KS.CFG"
        bootcfg = re.sub(r"kernelopt.*", kernelopt, bootcfg)

        # save customized boot.cfg
        with open(bootcfg_path, "w+") as bootcfg_file:
            bootcfg_file.write(bootcfg)

        # copy boot.cfg for EFI boot
        bootcfg_efi_path = path.join(tmpisodir, "efi/boot/boot.cfg")
        system(f"cp -f {bootcfg_path} {bootcfg_efi_path}")

        # generate custom iso
        system(
            f'genisoimage -relaxed-filenames -J -R -o {path.join(tmpisodir + ".iso")} -b isolinux.bin -c boot.cat -no-emul-boot -boot-load-size 4 -boot-info-table -eltorito-alt-boot -e efiboot.img -no-emul-boot {tmpisodir}'
        )

        mainlog.debug(f"rm -rf {tmpisodir} 1>&2")
        system(f"rm -rf {tmpisodir} 1>&2")

        mainlog.info(
            f'{jobid} Custom installation ISO for host {hostname} saved to: {path.join(tmpisodir + ".iso")}'
        )
        logger.info(
            f'Custom installation ISO for host {hostname} saved to: {path.join(tmpisodir + ".iso")}\n'
        )
    else:
        mainlog.info(
            f"[DRYRUN] Running generate_custom_iso({jobid}, {logger}, {mainlog}, {hostname}, {iso_image})"
        )


def cimc_login(logger, cimcaddr, cimcusr, cimcpwd, dryrun=DRYRUN):
    logger.info(f"Connecting to CIMC IP: {cimcaddr} using account: {cimcusr}")
    if not dryrun:
        # check if custom port has been provided
        if ":" in cimcaddr:
            cimcip = cimcaddr.split(":")[0]
            cimcport = int(cimcaddr.split(":")[1])
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
        logger.info(f"Connected to CIMC: {cimcaddr}")
        return cimchandle
    else:
        return "dummy_handle"


def cimc_logout(logger, cimchandle, cimcip, dryrun=DRYRUN):
    if not dryrun:
        # Logout from the server
        cimchandle.logout()
    logger.info(f"Disconnected from CIMC: {cimcip}")


def install_esxi(
    jobid,
    logger,
    mainlog,
    cimcip,
    cimcusr,
    cimcpwd,
    iso_image,
    eai_ip=EAIHOST_IP,
    dryrun=DRYRUN,
    status_dict=STATUS_CODES,
):
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

    isourl = f"http://{eai_ip}/custom-iso/{iso_image}"
    mainlog.debug(
        f"{jobid} Starting ESXi hypervisor installation using custom ISO URL: {isourl}"
    )
    logger.info(f"Starting ESXi hypervisor installation using custom ISO URL: {isourl}")

    if not dryrun:
        # login to CIMC
        try:
            update_job_status(jobid, "Connecting to CIMC", logger)
            cimchandle = cimc_login(logger, cimcip, cimcusr, cimcpwd)
        except Exception as e:
            mainlog.error(f"{jobid} Error when trying to login to CIMC: {str(e)}")
            logger.error(
                f"Error when trying to login to CIMC: {format_message_for_web(e)}\n"
            )
            # if cimc_login failed - run cleanup tasks (with unmount_iso=False), update EAIDB with error message and abort
            job_cleanup(jobid, logger, mainlog, unmount_iso=False)
            update_job_status(jobid, "Error: Failed to login to CIMC", logger, True)
            return 1

        # set VMEDIA on Boot Order
        try:
            if cimc_vmedia_set(cimchandle, logger) == 33:
                job_cleanup(jobid, logger, mainlog, unmount_iso=False)
                cimc_logout(logger, cimchandle, cimcip)
                update_job_status(
                    jobid, "Error: UEFI Secure Boot Mode enabled", logger, True
                )
                return 33
        except Exception as e:
            mainlog.error(f"{jobid} : {str(e)}")
            logger.error("Failed to set VMEDIA on Boot Order")
            logger.error(format_message_for_web(e))

        # mount custom ISO and reboot the server to start the installation
        try:
            # update status in EAIDB to 'Mounting installation ISO'
            update_job_status(jobid, "Mounting installation ISO", logger)

            logger.info("")
            logger.info(f"Mount custom installation ISO on CIMC")
            mainlog.info(f"{jobid} Attempting ISO mount with URL: {isourl}")

            try:
                vmedia_mount_iso_uri(cimchandle, isourl)
                mainlog.info(
                    f"{jobid} vmedia_mount_iso_uri call completed without exception"
                )
            except Exception as mount_ex:
                # Log the exception but don't fail immediately - check if mount actually succeeded
                mainlog.warning(
                    f"{jobid} vmedia_mount_iso_uri raised exception: {str(mount_ex)}"
                )
                mainlog.info(
                    f"{jobid} Continuing to check if mount actually succeeded despite exception..."
                )

            # Verify mount by checking existing URI
            existing_uri = vmedia_get_existing_uri(cimchandle)
            existing_status = vmedia_get_existing_status(cimchandle)
            mainlog.info(f"{jobid} vmedia_get_existing_uri: {existing_uri}")
            mainlog.info(f"{jobid} vmedia_get_existing_status: {existing_status}")

            # Check if mount actually succeeded
            if existing_uri and (
                isourl in existing_uri
                or isourl.replace("/custom-iso/", "/custom-iso") in existing_uri
            ):
                mainlog.info(f"{jobid} Mount verification successful - URI matches")
            # elif existing_status and existing_status.lower() in ['ok', 'in-progress']:
            #     mainlog.info(f"{jobid} Mount verification successful - Status: {existing_status}")
            else:
                mainlog.error(
                    f"{jobid} Mount verification failed - URI: {existing_uri}, Status: {existing_status}"
                )
                raise Exception(f"Mount verification failed - no valid mount found")

            logger.info(f"Installation ISO mounted")

            # query CIMC CommVMediaMap Managed Object - useful for debugging
            # cimc_query_classid(cimchandle, 'CommVMediaMap')

            mainlog.info(f"{jobid} Boot the machine...")
            pwrstate = server_power_state_get(cimchandle)
            if pwrstate == "off":
                logger.info(f"Powering on the server to start the installation")
                server_power_up(cimchandle)
            else:
                logger.info(f"Rebooting the server to start the installation")
                server_power_cycle(cimchandle)
            pwrstate = server_power_state_get(cimchandle)
            mainlog.info(f"{jobid} Server power state: {pwrstate}")
            logger.info(f"Server power state: {pwrstate}")
            logger.info(
                f"Open KVM console to follow the installation process or wait for the job status update to [Finished].\n"
            )

            # update status in EAIDB to 'Server is booting'
            update_job_status(jobid, status_dict[15], logger)

        except Exception as e:
            mainlog.error(f"{jobid} : {str(e)}")
            logger.error("Failed to mount installation ISO")
            logger.error(format_message_for_web(e))
            # if mounting ISO failed - run cleanup tasks, update EAIDB with error message and abort
            job_cleanup(jobid, logger, mainlog)
            cimc_logout(logger, cimchandle, cimcip)
            update_job_status(
                jobid, "Error: Failed to mount installation ISO", logger, True
            )
            return 2

        # logout from CIMC
        cimc_logout(logger, cimchandle, cimcip)
    else:
        mainlog.debug(
            f"{jobid} [DRYRUN] Running install_esxi({jobid}, {cimcip}, {cimcusr}, {cimcpwd}, {isourl})"
        )


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


def job_cleanup(
    jobid,
    logger,
    mainlog,
    unmount_iso=True,
    cleanroot=True,
    dryrun=DRYRUN,
    tftpboot=TFTPBOOT,
    pxedir=PXEDIR,
):
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
        try:
            eaidb_dict = eaidb_get_status()

            # Only update status to "Running cleanup tasks" if not already in an error or finished state
            current_status = eaidb_dict[jobid]["status"]
            if not current_status.startswith("Error") and current_status != "Finished":
                update_job_status(jobid, "Running cleanup tasks", logger)

            mainlog.info(f"{jobid} Starting cleanup")
            logger.info("")
            logger.info(f"Starting cleanup:")

            logger.info(f"* kickstart file")
            remove_kickstart(jobid, logger, mainlog)

            # Remove Proxmox answer file and first-boot script if they exist
            logger.info(f"* answer file")
            remove_answerfile(jobid, logger, mainlog)

            logger.info(f"* first-boot script")
            remove_first_boot_script(jobid, logger, mainlog)

            if eaidb_dict[jobid]["cimcip"]:
                logger.info(f"* custom installation ISO")
                if unmount_iso:
                    cimc_unmount_iso(jobid, logger, mainlog)
                remove_custom_iso(jobid, logger, mainlog)

                if cleanroot:
                    logger.info(f"* remove server passwords from database")
                    eaidb_set(jobid, {"root_pwd": "", "cimcpwd": ""})
                else:
                    logger.info(f"* remove CIMC password from database")
                    eaidb_set(jobid, {"cimcpwd": ""})

            elif eaidb_dict[jobid]["macaddr"]:
                rm_cmd = which("rm")
                logger.info(f"* PXE boot config")
                pxepath = path.join(
                    pxedir, f"01-{eaidb_dict[jobid]['macaddr'].replace(':', '-')}"
                )
                system(f"{rm_cmd} {pxepath}")

                logger.info(f"* EFI boot config")
                efidir = path.join(
                    tftpboot, f"01-{eaidb_dict[jobid]['macaddr'].replace(':', '-')}"
                )
                system(f"{rm_cmd} -rf {efidir}")

                logger.info(f"* DHCP config")
                generate_dhcp_config(jobid, logger, mainlog)
                if cleanroot:
                    logger.info(f"* remove root password from database")
                    eaidb_set(jobid, {"root_pwd": ""})

            mainlog.info(f"{jobid} Cleanup finished.")
            logger.info(f"Cleanup finished.\n")
        except Exception as e:
            logger.error(f"Errors during job cleanup: {format_message_for_web(e)}")
            mainlog.error(f"{jobid} Errors during job cleanup: {str(e)}")
    else:
        mainlog.debug(f"{jobid} [DRYRUN] Running job cleanup tasks)")


def remove_kickstart(jobid, logger, mainlog, ksdir=KSDIR):
    """
    Remove kickstart jobid file from KSDIR.

    :param jobid: (str) job ID
    :param logger: (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :param ksdir:  (str) path to kickstart directory
    :return: n/a
    """
    kspath = path.join(ksdir, jobid + "_ks.cfg")
    mainlog.info(f"{jobid} Removing kickstart file: {kspath}")
    # logger.info(f'Removing kickstart file: {kspath}')
    try:
        system(f"rm -f {kspath} 1>&2")
    except Exception as e:
        mainlog.error(f"{jobid} : Failed to remove {kspath}: {str(e)}")
        logger.error(f"Failed to remove {kspath}: {format_message_for_web(e)}")


def remove_answerfile(jobid, logger, mainlog, answerfile_dir=ANSWERFILEDIR):
    """
    Remove Proxmox answer file from ANSWERFILEDIR.

    :param jobid: (str) job ID
    :param logger: (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :param answerfile_dir: (str) path to answer files directory
    :return: n/a
    """
    answer_path = path.join(answerfile_dir, jobid + "_answer.toml")
    if path.exists(answer_path):
        mainlog.info(f"{jobid} Removing answer file: {answer_path}")
        try:
            system(f"rm -f {answer_path} 1>&2")
        except Exception as e:
            mainlog.error(f"{jobid} : Failed to remove {answer_path}: {str(e)}")
            logger.error(f"Failed to remove {answer_path}: {format_message_for_web(e)}")


def remove_first_boot_script(jobid, logger, mainlog, answerfile_dir=ANSWERFILEDIR):
    """
    Remove first-boot script from ANSWERFILEDIR.

    :param jobid: (str) job ID
    :param logger: (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :param answerfile_dir: (str) path to answer files directory
    :return: n/a
    """
    script_path = path.join(answerfile_dir, jobid + ".sh")
    if path.exists(script_path):
        mainlog.info(f"{jobid} Removing first-boot script: {script_path}")
        try:
            system(f"rm -f {script_path} 1>&2")
        except Exception as e:
            mainlog.error(f"{jobid} : Failed to remove {script_path}: {str(e)}")
            logger.error(f"Failed to remove {script_path}: {format_message_for_web(e)}")


def cimc_unmount_iso(jobid, logger, mainlog):
    """
    Unmount installation ISO on target CIMC.

    :param jobid: (str) job ID
    :param logger: (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :return: (int) Error code
    """
    mainlog.info(f"{jobid} Unmounting installation ISO from CIMC")
    logger.info(f"Unmounting installation ISO from CIMC:")
    try:
        # get CIMC IP and credentials from DB
        mainlog.info(f"{jobid} Get CIMC credentials for job ID")
        cimcip, cimcusr, cimcpwd = eaidb_get_cimc_credentials(jobid)
    except Exception as e:
        # cimcdata = False
        mainlog.error(f"{jobid} Failed to get CIMC credentials for job ID: {str(e)}")
        logger.error(
            f"Failed to get CIMC credentials for job ID: {format_message_for_web(e)}"
        )
        logger.error(f"Unmount installation ISO aborted.\n")
        return 1

    try:
        # login to CIMC
        mainlog.info(f"{jobid} Login to CIMC")
        cimchandle = cimc_login(logger, cimcip, cimcusr, cimcpwd)
    except Exception as e:
        mainlog.error(f"{jobid} Failed to login to CIMC: {str(e)}")
        logger.error(f"Failed to login to CIMC: {format_message_for_web(e)}")
        logger.error(f"Unmount installation ISO aborted.\n")
        return 2

    try:
        mainlog.info(
            f"{jobid} Unmounting installation ISO (vmedia_mount_delete, {jobid}.iso) on CIMC {cimcip}"
        )
        logger.info(f"Unmounting installation ISO ({jobid}.iso) on CIMC {cimcip}")
        vmedia_mount_delete(cimchandle, f"{jobid}.iso")
        cimc_logout(logger, cimchandle, cimcip)
    except Exception as e:
        mainlog.error(f"{jobid} Failed to unmount vmedia: {str(e)}")
        logger.error(
            f"Failed to unmount installation ISO: {format_message_for_web(e)}\n"
        )
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
    iso_path = path.join(customisodir, jobid + ".iso")
    mainlog.info(f"{jobid} Removing custom installation ISO: {iso_path}")
    logger.info(f"Removing custom installation ISO: {iso_path}")
    try:
        system(f"rm -f {iso_path} 1>&2")
    except Exception as e:
        mainlog.error(f"{jobid} : Failed to remove {iso_path}: {str(e)}")
        logger.error(f"Failed to remove {iso_path}: {format_message_for_web(e)}")


def process_submission(jobid_list, logger_list, mainlog, form_data):
    """
    Generates installation data and starts install process.

    :param jobid_list: (list) List of (str) job ID
    :param logger: (list) List of (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :param form_data: (dict) dictionary with IP address(es) and task(s) as list items
    :return: n/a
    """

    for index in range(len(form_data["hosts"])):
        jobid = jobid_list[index]
        logger = logger_list[index]
        hostname = form_data["hosts"][index]["hostname"]

        # customize kickstart config
        mainlog.info(f"{jobid} Generating kickstart file for server {hostname}")
        kscfg = generate_kickstart(jobid, form_data, index, logger, mainlog)

        if form_data["installmethod"] == "pxeboot":
            mainlog.info(f"{jobid} Generating PXE Boot files for server {hostname}")
            generate_pxe_boot(
                jobid,
                logger,
                mainlog,
                form_data["iso_image"],
                form_data["hosts"][index]["macaddr"],
            )

            mainlog.info(f"{jobid} Generating EFI Boot files for server {hostname}")
            generate_efi_boot(
                jobid,
                logger,
                mainlog,
                form_data["iso_image"],
                form_data["hosts"][index]["macaddr"],
            )

            mainlog.info(f"{jobid} Generating DHCP configuration for server {hostname}")
            generate_dhcp_config(jobid, logger, mainlog)
            update_job_status(jobid, "Ready to deploy", logger)

            mainlog.info(
                f"{jobid} Ready to start PXE Boot installation for server {hostname}"
            )
            logger.info(
                f"Ready to start PXE Boot installation - power on or restart the server to initialize installation process.\n"
            )

        else:
            # generate custom installation ISO
            mainlog.info(
                f"{jobid} Generating custom installation ISO for server {hostname}"
            )
            generate_custom_iso(
                jobid, logger, mainlog, hostname, form_data["iso_image"], kscfg
            )

            # start ESXi hypervisor installation
            Process(
                target=install_esxi,
                args=(
                    jobid,
                    logger,
                    mainlog,
                    form_data["hosts"][index]["cimc_ip"],
                    form_data["cimc_usr"],
                    form_data["cimc_pwd"],
                    jobid + ".iso",
                ),
            ).start()


def create_jobs(form_data, installmethod, mainlog):
    """
    Create installation job for each server in form_data['hosts'] list.

    :param form_data: (dict) installatiomn data as returned by get_form_data() function
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :return: (list) list of job IDs
    """

    # interate over the list of ESXi hosts and run corresponding actions for each host
    jobid_list = []
    logger_list = []
    for index in range(len(form_data["hosts"])):
        hostname = form_data["hosts"][index]["hostname"]
        # if form_data['hosts'][index]['cimc_ip']:
        if installmethod == "pxeboot":
            # Installation method: PXE boot
            cimcusr = ""
            cimcip = ""
            cimcpwd = ""
            macaddr = form_data["hosts"][index]["macaddr"]
            jobid = generate_jobid(macaddr)
        else:
            # Installation method: mount installation ISO with CIMC API (Cisco UCS servers only)
            cimcusr = form_data["cimc_usr"]
            cimcip = form_data["hosts"][index]["cimc_ip"]
            cimcpwd = form_data["cimc_pwd"]
            macaddr = ""
            jobid = generate_jobid(cimcip)

        # cimcip = form_data['hosts'][index]['cimc_ip']

        # generate jobid based on CIMC IP and current timestamp
        # jobid = generate_jobid(cimcip_or_mac)

        # create logger handler
        logger = get_jobid_logger(jobid)
        logger.info(f"Processing job ID: {jobid}, server {hostname}\n")
        mainlog.info(f"{jobid} - processing job ID, server {hostname}")

        # create entry in Auto-Installer DB
        mainlog.info(f"{jobid} Saving installation data for server {hostname}")
        # print(form_data)
        eaidb_create_job_entry(
            jobid,
            hostname,
            form_data["hosts"][index]["host_ip"],
            form_data["root_pwd"],
            cimcip,
            cimcusr,
            cimcpwd,
            macaddr,
            form_data["host_netmask"],
            form_data["host_gateway"],
        )

        jobid_list.append(jobid)
        logger_list.append(logger)
    # Process data on seperate thread
    Process(
        target=process_submission, args=(jobid_list, logger_list, mainlog, form_data)
    ).start()
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
        return "File does not exist!", 404

    # Check if path is a file and serve
    if os.path.isfile(abs_path):
        with open(abs_path, "r") as log_file:
            return log_file.read(), 200, {"Content-Type": "text/plain; charset=utf-8"}


def update_job_status(jobid, status, logger, finished=False):
    """
    Update 'status' and 'finish_time' columns in EAISTATUS table for 'jobid'.

    :param jobid: (str) job ID
    :param status:
    :param logger:
    :param finished:
    :return:
    """

    if finished:
        data = {
            "status": status,
            "finish_time": time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime()),
            "root_pwd": "",
            "cimcpwd": "",
        }
    else:
        data = {"status": status, "finish_time": ""}

    eaidb_set(jobid, data)

    logger.info(f"Job Status has been updated to: {status}")
    if finished:
        logger.info(f"Installation job (ID: {jobid}) finished.")


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

        vmedia = "NULL"
        # check if vmedia on configured boot order list
        for boot_device in basic_boot_order:
            if boot_device["device-type"] == "cdrom":
                vmedia = boot_device["order"]
                logger.info(f"Discovered VMEDIA on position: {vmedia}")

        if vmedia == "NULL":
            logger.info("No valid VMEDIA on configured boot order list - adding...")
            from imcsdk.apis.server.boot import _add_boot_device

            _add_boot_device(
                cimchandle,
                "sys/rack-unit-1/boot-policy",
                {"order": "1", "device-type": "cdrom", "name": "cdrom-eai"},
            )
            logger.info(f"Boot Order set to: {boot_order_policy_get(cimchandle)}")
        elif vmedia != "1":
            logger.info(
                f"VMEDIA found on configured boot order list at position: {vmedia} - moving to 1st position..."
            )
            new_boot_order = []
            for boot_device in basic_boot_order:
                if boot_device["device-type"] != "cdrom" and int(
                    boot_device["order"]
                ) < int(vmedia):
                    # devices on higher position than VMEDIA - move 1 position down
                    boot_device["order"] = str(int(boot_device["order"]) + 1)
                    new_boot_order.append(boot_device)
                elif boot_device["device-type"] != "cdrom" and int(
                    boot_device["order"]
                ) > int(vmedia):
                    # devices on lower position than VMEDIA - move 1 position down
                    new_boot_order.append(boot_device)
                else:
                    # move VMEDIA to position 1
                    boot_device["order"] = "1"
                    new_boot_order.append(boot_device)
            # apply new boot order policy
            boot_order_policy_set(cimchandle, boot_devices=new_boot_order)
            logger.info(f"Boot Order set to: {boot_order_policy_get(cimchandle)}")
    except Exception as e:
        logger.error(f"Error when running vmedia check:")
        logger.error(format_message_for_web(e))


def cimc_vmedia_advanced_check(cimchandle):
    """
    Check for valid VMEDIA on Advanced Boot Order list.
    VMEDIA is valid when subtype is either 'cimc-mapped-dvd' or not specified.

    :param cimchandle: (ImcHandle) CIMC connection handle
    :return: (dict) NULL if no valid VMEDIA found,
                    VMEDIA name, dn and state if valid VMEDIA found,
             (str)  Error otherwise.

    """

    vmedia_dict = {"name": "NULL", "dn": "NULL", "state": "NULL"}
    try:
        vmedia_list = cimchandle.query_classid("LsbootVMedia")
        if len(vmedia_list) > 0:
            for vmedia in vmedia_list:
                if getattr(vmedia, "subtype") != "kvm-mapped-dvd":
                    vmedia_dict["name"] = getattr(vmedia, "name")
                    vmedia_dict["dn"] = getattr(vmedia, "dn")
                    vmedia_dict["state"] = getattr(vmedia, "state")
                    break  # fvoudn valid vmedia - we can break the loop here
        return vmedia_dict

    except Exception as e:
        return f"Error when running vmedia check: {str(e)}"


def cimc_vmedia_advanced_set(cimchandle, logger):
    """
    Set Boot Order Precision (Advanced Boot Order).

    :param cimchandle: (ImcHandle) CIMC connection handle
    :param logger: (logging.Handler) logger handler for jobid
    :return: n/a
    """
    try:
        logger.info("Checking for VMEDIA on Advanced Boot Order ...")
        vmedia = cimc_vmedia_advanced_check(cimchandle)
        if "Error" in str(vmedia):
            logger.error(f"{str(vmedia)}. Aborting.")
            return 33
        elif vmedia["name"] == "NULL":
            logger.info("No valid VMEDIA on configured boot order list - adding")
            # append vmedia to boot order list
            vmedia_order = str(len(boot_precision_configured_get(cimchandle)) + 1)
            from imcsdk.apis.server.boot import _add_boot_device

            vmedia["name"] = "vmedia-eai"
            _add_boot_device(
                cimchandle,
                "sys/rack-unit-1/boot-precision",
                {
                    "order": vmedia_order,
                    "device-type": "vmedia",
                    "name": vmedia["name"],
                },
            )
            logger.info(
                f"Boot Order set to: {boot_precision_configured_get(cimchandle)}"
            )
        else:
            logger.info(f"VMEDIA found - using: {vmedia['name']}")
            if vmedia["state"].casefold() != "enabled":
                logger.info(
                    f"VMEDIA {vmedia['name']} disabled: changing state to Enabled"
                )
                cimc_set_mo_property(cimchandle, vmedia["dn"], "state", "Enabled")

        # set vmedia as OneTimePrecisionBootDevice
        cimc_set_mo_property(
            cimchandle,
            "sys/rack-unit-1/one-time-precision-boot",
            "device",
            vmedia["name"],
        )
        logger.info(f"Configured One time boot device: {vmedia['name']}")
    except Exception as e:
        logger.error(f"Error when trying to set One time boot device:")
        logger.error(format_message_for_web(e))


def cimc_vmedia_set(cimchandle, logger):
    """
    Set VMEDIA on Boot Order.

    :param cimchandle: (ImcHandle) CIMC connection handle
    :param logger: (logging.Handler) logger handler for jobid
    :return: n/a
    """
    try:
        # check Basic vs Advanced Boot mode
        basic_boot_order = boot_order_policy_get(cimchandle)
        if len(basic_boot_order) > 0:
            # set VMEDIA as first device on Basic Boot Order list
            logger.info(
                f"Discovered Basic Boot Order: {len(basic_boot_order)} devices, {basic_boot_order}"
            )
            cimc_vmedia_basic_set(cimchandle, logger, basic_boot_order)
        else:
            # ad VMEDIA to Advanced Boot Order and set it as One Time Boot Device
            adv_boot_order = boot_precision_configured_get(cimchandle)
            logger.info(
                f"Discovered Advanced Boot Order: {len(adv_boot_order)} devices, {adv_boot_order}"
            )
            cimc_vmedia_advanced_set(cimchandle, logger)

    except Exception as e:
        logger.error(f"Error when setting VMedia:")
        logger.error(format_message_for_web(e))


def generate_pxe_boot(
    jobid,
    logger,
    mainlog,
    iso_image,
    macaddr,
    dryrun=DRYRUN,
    pxejinja=PXETEMPLATE,
    pxedir=PXEDIR,
    eai_ip=EAIHOST_IP,
):
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
            with open(pxejinja, "r") as pxetemplate_file:
                pxetemplate = Template(pxetemplate_file.read())

            # generate PXE config file name based on MAC address (add prefix + replace ':' with '-')
            pxecfg_path = path.join(pxedir, f"01-{macaddr.replace(':', '-')}")

            logger.info(f"Saving PXE boot file as: {pxecfg_path}")

            # read jinja template from file and render using read variables
            with open(pxecfg_path, "w+") as pxefile:
                pxefile.write(
                    pxetemplate.render(
                        iso_image=f"iso/{iso_image}",
                        ksurl=f"http://{eai_ip}/ks/{jobid}_ks.cfg",
                    )
                )

        except Exception as e:
            logger.error(f"Failed to save PXE boot file: {format_message_for_web(e)}")
            mainlog.error(f"{jobid} Failed to save PXE boot file: {str(e)}")
    else:
        logger.info(f"[DRYRUN] Generating PXE boot file")
        mainlog.info(f"{jobid} [DRYRUN] Generating PXE boot file")


def generate_efi_boot(
    jobid,
    logger,
    mainlog,
    iso_image,
    macaddr,
    dryrun=DRYRUN,
    tftpboot=TFTPBOOT,
    tftpisodir=TFTPISODIR,
    eai_ip=EAIHOST_IP,
):
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
            mkdir_cmd = which("mkdir")
            efidir = path.join(tftpboot, f"01-{macaddr.replace(':', '-')}")
            system(f"{mkdir_cmd} {efidir}")

            # read original boot.cfg
            bootcfg_orig_path = path.join(tftpisodir, iso_image, "boot.cfg")
            with open(bootcfg_orig_path, "r") as bootcfg_file:
                bootcfg = bootcfg_file.read()

            # search for kernelopt line and replace parameters with ksurl
            bootcfg = re.sub(
                r"kernelopt.*",
                f"kernelopt=ks=http://{eai_ip}/ks/{jobid}_ks.cfg",
                bootcfg,
            )

            bootcfg_path = path.join(efidir, "boot.cfg")
            logger.info(f"Saving EFI boot file as: {bootcfg_path}")

            with open(bootcfg_path, "w+") as bootcfg_custom_file:
                bootcfg_custom_file.write(bootcfg)

        except Exception as e:
            logger.error(
                f"Failed to save EFI boot.cfg file: {format_message_for_web(e)}"
            )
            mainlog.error(f"{jobid} Failed to save EFI boot.cfg file: {str(e)}")
    else:
        logger.info(f"[DRYRUN] Generating EFI boot file")
        mainlog.info(f"{jobid} [DRYRUN] Generating EFI boot file")


def final_reboot(
    jobid,
    ssh,
    logger,
    mainlog,
    sleeptimer=60,
    timeoutminutes=45,
    status_dict=STATUS_CODES,
):
    # Server is in final reboot, does not need files anymore. Also prevents PXE reboot loop.
    job_cleanup(jobid, logger, mainlog, cleanroot=False)

    ### Wait for host to boot
    update_job_status(jobid, status_dict[17], logger)
    # Collect required data
    eaidb_dict = eaidb_get(jobid, ("ipaddr", "root_pwd"))
    url = "https://" + eaidb_dict["ipaddr"] + "/sdk"
    # Create Session
    session = requests.Session()
    # Request SOAP API
    response = None
    timeout = datetime.datetime.now() + datetime.timedelta(minutes=timeoutminutes)
    logger.info("Waiting for ESXi to become responsive.")
    while getattr(response, "status_code", 0) != 200:
        try:
            time.sleep(sleeptimer)
            mainlog.debug(
                "Attempting to connect to ESXi API at " + eaidb_dict["ipaddr"]
            )
            response = session.get(f"{url}/vimServiceVersions.xml", verify=False)
            # mainlog.debug(response.text)
        except:
            if datetime.datetime.now() > timeout:
                logger.error(
                    "ESXi API Connection timeout. Unable to start SSH service."
                )
                mainlog.error(
                    "ESXi API Connection timeout. Unable to start SSH service."
                )
                update_job_status(jobid, status_dict[35], logger, True)
                return
            continue

    ## After system has booted up, enable SSH if set.
    try:
        if ssh:
            # TODO: Ideally whether or not to enable ssh should be saved to the database.

            # TODO: Need to see if we can prevent multiple instances of enable_ssh running for the same ESXi host. ###

            enable_ssh(
                eaidb_dict["ipaddr"],
                eaidb_dict["root_pwd"],
                mainlog,
                logger,
                session=session,
            )
        else:
            # Close session
            session.close()
    except:
        update_job_status(jobid, status_dict[34], logger, True)
    else:
        update_job_status(jobid, status_dict[20], logger, True)


def enable_ssh(ipaddr, esxipass, mainlog, logger, session=None, esxiuser="root"):
    # https://developer.vmware.com/apis/1355/vsphere

    url = "https://" + ipaddr + "/sdk"
    # Create Session
    if session == None:
        session = requests.Session()
    # Request SOAP API
    response = None

    logger.info("Requesting VMware API Namespace")
    try:
        response = session.get(f"{url}/vimServiceVersions.xml", verify=False)
        # mainlog.debug(response.text)
    except:
        logger.error("Could not connect to ESXi API. Unable to start SSH service.")
        mainlog.error("Could not connect to ESXi API. Unable to start SSH service.")
        raise Exception("Failed to retrieve vimServiceVersions.xml")

    # Create values used for the rest of the session
    try:
        xml = ET.fromstring(response.text)
        xmlns = xml[0][0].text
        session.headers.update(
            {
                "Content-Type": "application/xml",
                "SOAPAction": f'"{xmlns}/{xml[0][1].text}"',
            }
        )
    except:
        logger.error("Unable to parse ESXi API Response. Unable to start SSH service.")
        mainlog.error("Unable to parse ESXi API Response")
        raise Exception("Failed to parse vimServiceVersions.xml")

    # Request Authentication
    payload = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">\n<soapenv:Body><Login xmlns="'
        + xmlns
        + '"><_this type="SessionManager">ha-sessionmgr</_this><userName>'
        + esxiuser
        + "</userName><password>"
        + esxipass
        + "</password></Login></soapenv:Body>\n</soapenv:Envelope>"
    )
    try:
        response = session.post(url, data=payload, verify=False)
    except:
        raise Exception("Failed to log into the ESXi host.")
    # mainlog.debug(response.text)
    if response.text.count('xsi:type="InvalidLogin"'):
        # Throw an error because the username or password is incorrect.
        # This should never happen because we just installed ESXi and set the password.
        logger.error("Unable to log into ESXi API. Unable to start SSH service.")
        mainlog.error("Unable to log into ESXi API.")
        raise Exception("Username and password was rejected by ESXi host.")

    try:
        # Set SSH policy to "on"
        payload = (
            '<?xml version="1.0" encoding="UTF-8"?>\n<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">\n<soapenv:Body><UpdateServicePolicy xmlns="'
            + xmlns
            + '"><_this type="HostServiceSystem">serviceSystem</_this><id>TSM-SSH</id><policy>on</policy></UpdateServicePolicy></soapenv:Body>\n</soapenv:Envelope>'
        )
        response = session.post(url, data=payload, verify=False)
        logger.info("Set SSH policy to 'on'.")
        # mainlog.debug(response.text)

        # Start the SSH Service
        payload = (
            '<?xml version="1.0" encoding="UTF-8"?>\n<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">\n<soapenv:Body><StartService xmlns="'
            + xmlns
            + '"><_this type="HostServiceSystem">serviceSystem</_this><id>TSM-SSH</id></StartService></soapenv:Body>\n</soapenv:Envelope>'
        )
        response = session.post(url, data=payload, verify=False)
        logger.info("Started SSH service.")
        # mainlog.debug(response.text)
    except:
        raise Exception("Failed to start ssh service.")

    # Logout
    payload = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<soapenv:Envelope xmlns:soapenc="http://schemas.xmlsoap.org/soap/encoding/" xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">\n<soapenv:Body><Logout xmlns="'
        + xmlns
        + '"><_this type="SessionManager">ha-sessionmgr</_this></Logout></soapenv:Body>\n</soapenv:Envelope>'
    )
    try:
        response = session.post(url, data=payload, verify=False)
    except:
        raise Exception("Failed to logoff API.")
    # mainlog.debug(response.text)
    mainlog.info("SSH was enabled.")
    # Close session
    session.close()


##### Proxmox Installation Functions #####


def generate_proxmox_answer(
    jobid,
    form_data,
    index,
    logger,
    mainlog,
    eai_host_ip=EAIHOST_IP,
    dryrun=DRYRUN,
    answer_template=PROXMOX_ANSWER_TEMPLATE,
    answerfile_dir=ANSWERFILEDIR,
):
    """
    Generate Proxmox answer file for automated installation.

    :param jobid: (str) job ID
    :param form_data: (dict) installation data
    :param index: (int) index of host in hosts list
    :param logger: (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :param eai_host_ip: (str) EAI host IP address
    :param dryrun: (bool) dry run flag
    :param answer_template: (str) path to answer file Jinja template
    :param answerfile_dir: (str) path to answer files directory
    :return: (str) path to generated answer file
    """
    logger.info(f"Generating Proxmox answer file for server")

    import crypt

    # Hash the root password
    root_password_hashed = crypt.crypt(
        form_data["root_pwd"], crypt.mksalt(crypt.METHOD_SHA512)
    )

    # Get host data
    hostname = form_data["hosts"][index]["hostname"]
    ipaddr = form_data["hosts"][index]["host_ip"]

    # Prepare template variables
    template_vars = {
        "keyboard": form_data.get("keyboard", "en-us"),
        "country": form_data.get("country", "us"),
        "fqdn": hostname,
        "timezone": form_data.get("timezone", "UTC"),
        "root_password_hashed": root_password_hashed,
        "mailto": form_data.get("mailto", "admin@example.com"),
        "ipaddr": ipaddr,
        "cidr": form_data.get("cidr", "24"),
        "gateway": form_data["host_gateway"],
        "dns": form_data.get("dns", "8.8.8.8"),
        "interface": form_data.get("interface", "eno1"),
        "net_filter": form_data.get("net_filter", "ID_NET_NAME_SLOT"),
        "filesystem": form_data.get("filesystem", "ext4"),
        "disk_list": form_data.get("disk_list", "/dev/sda"),
        "eai_host_ip": eai_host_ip,
        "jobid": jobid,
    }

    # Read jinja template from file and render using variables
    with open(answer_template, "r") as template_file:
        template = Template(template_file.read())
    answer_content = template.render(**template_vars)

    # Remove password before saving to log file
    logger.info(
        f"Generated answer file configuration:\n{re.sub(r'root-password-hashed.*', 'root-password-hashed = ***********', answer_content)}\n"
    )

    if not dryrun:
        answer_path = path.join(answerfile_dir, jobid + "_answer.toml")
        with open(answer_path, "w+") as answer_file:
            answer_file.write(answer_content)
            mainlog.debug(
                f"{jobid} Generated answer file for host: {hostname} saved to {answer_path}"
            )
            logger.info(f"Answer file for host: {hostname} saved to {answer_path}\n")
        return answer_path
    else:
        mainlog.debug(f"{jobid} [DRYRUN] Generated answer file for host: {hostname}")
        return "not a real answer file path"


def generate_first_boot_script(
    jobid,
    logger,
    mainlog,
    eai_host_ip=EAIHOST_IP,
    answerfile_dir=ANSWERFILEDIR,
    dryrun=DRYRUN,
    custom_script=None,
):
    """
    Generate first-boot script that will mark the job as finished.

    :param jobid: (str) job ID
    :param logger: (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :param eai_host_ip: (str) EAI host IP address
    :param answerfile_dir: (str) path to answer files directory
    :param dryrun: (bool) dry run flag
    :param custom_script: (str) optional custom script to run before network wait
    :return: (str) path to generated script file
    """
    logger.info(f"Generating first-boot script for job completion")

    # Build custom script section if provided
    custom_section = ""
    if custom_script and custom_script.strip():
        custom_section = f"""
# Custom user script
{custom_script.strip()}

"""
        logger.info(f"Including custom script in first-boot")
        mainlog.info(f"{jobid} Including custom script in first-boot")

    script_content = f"""#!/bin/bash
# Proxmox first-boot script to mark installation as complete
# Job ID: {jobid}
{custom_section}
# Wait for network to be available
sleep 10

# Update job status to Finished (status code 20)
curl -X PUT "http://{eai_host_ip}/api/v1/jobs/{jobid}?state=20" -v

# Log completion
logger "Proxmox installation completed - Job ID: {jobid}"
"""

    if not dryrun:
        script_path = path.join(answerfile_dir, f"{jobid}.sh")
        with open(script_path, "w+") as script_file:
            script_file.write(script_content)

        # Make the script executable
        system(f"chmod +x {script_path}")

        mainlog.debug(f"{jobid} Generated first-boot script saved to {script_path}")
        logger.info(f"First-boot script saved to {script_path}\n")
        return script_path
    else:
        mainlog.debug(f"{jobid} [DRYRUN] Generated first-boot script")
        return "not a real script path"


def validate_answer_file(jobid, answer_file_path, logger, mainlog):
    """
    Validate Proxmox answer file using proxmox-auto-install-assistant.

    :param jobid: (str) job ID
    :param answer_file_path: (str) path to answer file
    :param logger: (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :return: (bool) True if validation successful, False otherwise
    """
    logger.info(f"Validating answer file: {answer_file_path}")

    # Check if proxmox-auto-install-assistant is available
    assistant_cmd = which("proxmox-auto-install-assistant")
    if not assistant_cmd:
        logger.error("proxmox-auto-install-assistant command not found")
        mainlog.error(f"{jobid} proxmox-auto-install-assistant command not found")
        return False

    # Run validation command
    validate_cmd = f"{assistant_cmd} validate-answer {answer_file_path}"
    logger.info(f"Running validation command: {validate_cmd}")

    exit_code = system(f"{validate_cmd} >> {path.join(LOGDIR, jobid)} 2>&1")

    if WEXITSTATUS(exit_code) == 0:
        logger.info("Answer file validation successful\n")
        mainlog.info(f"{jobid} Answer file validation successful")
        return True
    else:
        logger.error(
            f"Answer file validation failed with exit code: {WEXITSTATUS(exit_code)}"
        )
        mainlog.error(f"{jobid} Answer file validation failed")
        return False


def prepare_proxmox_iso(
    jobid,
    logger,
    mainlog,
    iso_image,
    answer_file_path,
    first_boot_script_path=None,
    custom_iso_dir=CUSTOMISODIR,
    proxmox_iso_dir=PROXMOXISODIR,
):
    """
    Prepare Proxmox ISO with answer file and first-boot script using proxmox-auto-install-assistant.

    :param jobid: (str) job ID
    :param logger: (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :param iso_image: (str) name of the base ISO image
    :param answer_file_path: (str) path to answer file
    :param first_boot_script_path: (str) path to first-boot script (optional)
    :param custom_iso_dir: (str) path to custom ISO directory
    :param proxmox_iso_dir: (str) path to Proxmox ISO directory
    :return: (str) path to prepared ISO file or None on failure
    """
    logger.info(f"Preparing Proxmox ISO with answer file")

    # Check if proxmox-auto-install-assistant is available
    assistant_cmd = which("proxmox-auto-install-assistant")
    if not assistant_cmd:
        logger.error("proxmox-auto-install-assistant command not found")
        mainlog.error(f"{jobid} proxmox-auto-install-assistant command not found")
        return None

    # Build paths
    source_iso_path = path.join(proxmox_iso_dir, iso_image)
    output_iso_path = path.join(custom_iso_dir, f"{jobid}.iso")

    # Check if source ISO exists
    if not path.exists(source_iso_path):
        logger.error(f"Source ISO not found: {source_iso_path}")
        mainlog.error(f"{jobid} Source ISO not found: {source_iso_path}")
        return None

    # Prepare ISO command with first-boot script if provided
    prepare_cmd = f"{assistant_cmd} prepare-iso {source_iso_path} --fetch-from iso --answer-file {answer_file_path}"

    if first_boot_script_path and path.exists(first_boot_script_path):
        prepare_cmd += f" --on-first-boot {first_boot_script_path}"
        logger.info(f"Including first-boot script: {first_boot_script_path}")
        mainlog.info(f"{jobid} Including first-boot script in ISO")

    prepare_cmd += f" --output {output_iso_path}"

    logger.info(f"Running prepare-iso command")
    mainlog.info(f"{jobid} Preparing ISO: {prepare_cmd}")

    # Execute command
    exit_code = system(f"{prepare_cmd} >> {path.join(LOGDIR, jobid)} 2>&1")

    if WEXITSTATUS(exit_code) == 0:
        logger.info(f"ISO preparation successful: {output_iso_path}\n")
        mainlog.info(f"{jobid} ISO preparation successful")
        return output_iso_path
    else:
        logger.error(f"ISO preparation failed with exit code: {WEXITSTATUS(exit_code)}")
        mainlog.error(f"{jobid} ISO preparation failed")
        return None


def install_proxmox(
    jobid,
    logger,
    mainlog,
    cimcip,
    cimcusr,
    cimcpwd,
    isoname,
):
    """
    Install Proxmox on server via CIMC ISO mount and reboot.

    :param jobid: (str) job ID
    :param logger: (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :param cimcip: (str) CIMC IP address
    :param cimcusr: (str) CIMC username
    :param cimcpwd: (str) CIMC password
    :param isoname: (str) ISO filename to mount
    :return: n/a
    """
    logger.info(f"Starting Proxmox installation process")
    mainlog.info(
        f"{jobid} Starting Proxmox installation on server with CIMC IP: {cimcip}"
    )

    # Update job status
    update_job_status(jobid, "Connecting to CIMC", logger)

    # Login to CIMC
    try:
        logger.info(f"Logging in to CIMC at {cimcip}")
        cimchandle = ImcHandle(cimcip, cimcusr, cimcpwd)
        cimchandle.login()
        logger.info(f"Successfully logged in to CIMC\n")
    except Exception as e:
        logger.error(f"Failed to login to CIMC:")
        logger.error(format_message_for_web(e))
        job_cleanup(jobid, logger, mainlog, unmount_iso=False)
        update_job_status(jobid, "Error: Failed to login to CIMC", logger, True)
        return

    # Set VMEDIA on boot order
    cimc_vmedia_set(cimchandle, logger)

    # Update job status
    update_job_status(jobid, "Mounting installation ISO", logger)

    # Mount ISO
    try:
        logger.info(f"Mounting ISO: {isoname}")
        iso_url = f"http://{EAIHOST_IP}/custom-iso/{isoname}"

        # Use vmedia_mount_create instead of vmedia_mount_iso_uri
        # vmedia_mount_iso_uri waits for status='OK' which can timeout even when mount succeeds
        mainlog.info(f"{jobid} Mounting ISO via vmedia_mount_create")

        # For map="www", split URL into remote_share (base URL) and remote_file (filename)
        remote_share = f"http://{EAIHOST_IP}/custom-iso"
        remote_file = isoname

        vmedia_mount_create(
            cimchandle,
            volume_name=jobid,
            remote_share=remote_share,
            remote_file=remote_file,
            map="www",
            mount_options="noauto",
            username="",
            password="",
        )

        # Give CIMC a moment to process the mount
        import time

        time.sleep(2)

        # Check if mount exists (optional - doesn't verify status, just existence)
        if vmedia_mount_exists(cimchandle, jobid):
            mainlog.info(f"{jobid} vmedia_mount_exists: True")
            existing_uri = vmedia_get_existing_uri(cimchandle)
            mainlog.info(f"{jobid} vmedia_get_existing_uri: {existing_uri}")
            existing_status = vmedia_get_existing_status(cimchandle)
            mainlog.info(f"{jobid} vmedia_get_existing_status: {existing_status}")

        logger.info(f"ISO mount command sent successfully: {iso_url}")
        logger.info(f"Note: CIMC may take a few moments to complete the mapping\n")
    except Exception as e:
        logger.error(f"Failed to mount ISO:")
        logger.error(format_message_for_web(e))
        cimchandle.logout()
        job_cleanup(jobid, logger, mainlog, unmount_iso=False)
        update_job_status(
            jobid, "Error: Failed to mount installation ISO", logger, True
        )
        return

    # Power cycle server
    update_job_status(jobid, "Server is booting", logger)
    try:
        logger.info(f"Power cycling server")
        power_state = server_power_state_get(cimchandle)
        logger.info(f"Current power state: {power_state}")

        if power_state == "off":
            server_power_up(cimchandle)
            logger.info(f"Server powered on")
        else:
            server_power_cycle(cimchandle)
            logger.info(f"Server power cycled")

        logger.info(f"Server is rebooting. Installation will begin automatically.\n")
    except Exception as e:
        logger.error(f"Failed to power cycle server:")
        logger.error(format_message_for_web(e))

    # Logout from CIMC
    cimchandle.logout()
    logger.info(f"Logged out from CIMC")

    # Update status
    update_job_status(jobid, "Installer is running", logger)
    logger.info(
        f"Proxmox installation in progress. Waiting for installation completion webhook...\n"
    )
    mainlog.info(f"{jobid} Proxmox installation in progress")


def process_proxmox_submission(jobid_list, logger_list, mainlog, form_data):
    """
    Generates installation data and starts Proxmox install process.

    :param jobid_list: (list) List of (str) job ID
    :param logger_list: (list) List of (logging.Handler) logger handler for jobid
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :param form_data: (dict) dictionary with installation data
    :return: n/a
    """

    for index in range(len(form_data["hosts"])):
        jobid = jobid_list[index]
        logger = logger_list[index]
        hostname = form_data["hosts"][index]["hostname"]

        # Generate answer file
        mainlog.info(f"{jobid} Generating answer file for server {hostname}")
        answer_file_path = generate_proxmox_answer(
            jobid, form_data, index, logger, mainlog
        )

        # Validate answer file
        mainlog.info(f"{jobid} Validating answer file for server {hostname}")
        if not validate_answer_file(jobid, answer_file_path, logger, mainlog):
            logger.error("Answer file validation failed. Aborting installation.")
            job_cleanup(jobid, logger, mainlog, unmount_iso=False)
            update_job_status(
                jobid, "Error: Answer file validation failed", logger, True
            )
            continue

        # Generate first-boot script
        mainlog.info(f"{jobid} Generating first-boot script for server {hostname}")
        custom_script = form_data.get("custom_script", None)
        first_boot_script_path = generate_first_boot_script(
            jobid, logger, mainlog, custom_script=custom_script
        )

        # Prepare ISO with answer file and first-boot script
        mainlog.info(f"{jobid} Preparing Proxmox ISO for server {hostname}")
        prepared_iso = prepare_proxmox_iso(
            jobid,
            logger,
            mainlog,
            form_data["iso_image"],
            answer_file_path,
            first_boot_script_path,
        )

        if not prepared_iso:
            logger.error("ISO preparation failed. Aborting installation.")
            job_cleanup(jobid, logger, mainlog, unmount_iso=False)
            update_job_status(jobid, "Error: ISO preparation failed", logger, True)
            continue

        # Start Proxmox installation via CIMC
        Process(
            target=install_proxmox,
            args=(
                jobid,
                logger,
                mainlog,
                form_data["hosts"][index]["cimc_ip"],
                form_data["cimc_usr"],
                form_data["cimc_pwd"],
                jobid + ".iso",
            ),
        ).start()


def create_proxmox_jobs(form_data, installmethod, mainlog):
    """
    Create Proxmox installation job for each server in form_data['hosts'] list.

    :param form_data: (dict) installation data
    :param installmethod: (str) installation method
    :param mainlog: (logging.Handler) main Auto-Installer logger handler
    :return: (list) list of job IDs
    """

    jobid_list = []
    logger_list = []

    for index in range(len(form_data["hosts"])):
        hostname = form_data["hosts"][index]["hostname"]
        cimcusr = form_data["cimc_usr"]
        cimcip = form_data["hosts"][index]["cimc_ip"]
        cimcpwd = form_data["cimc_pwd"]
        macaddr = ""
        jobid = generate_jobid(cimcip)

        # Create logger handler
        logger = get_jobid_logger(jobid)
        logger.info(f"Processing Proxmox job ID: {jobid}, server {hostname}\n")
        mainlog.info(f"{jobid} - processing Proxmox job ID, server {hostname}")

        # Create entry in Auto-Installer DB
        mainlog.info(f"{jobid} Saving installation data for server {hostname}")
        eaidb_create_job_entry(
            jobid,
            hostname,
            form_data["hosts"][index]["host_ip"],
            form_data["root_pwd"],
            cimcip,
            cimcusr,
            cimcpwd,
            macaddr,
            f"{form_data.get('cidr', '24')}",  # Store CIDR in netmask field
            form_data["host_gateway"],
        )

        jobid_list.append(jobid)
        logger_list.append(logger)

    # Process data on separate thread
    Process(
        target=process_proxmox_submission,
        args=(jobid_list, logger_list, mainlog, form_data),
    ).start()

    return jobid_list


def get_proxmox_isos(proxmox_iso_dir=PROXMOXISODIR):
    """
    Get list of available Proxmox ISO files.

    :param proxmox_iso_dir: (str) path to Proxmox ISO directory
    :return: (list) list of ISO filenames
    """
    if path.exists(proxmox_iso_dir):
        iso_files = [f for f in listdir(proxmox_iso_dir) if f.endswith(".iso")]
        return sorted(iso_files)
    return []


def is_proxmox_iso(filename):
    """
    Detect if uploaded ISO is a Proxmox ISO based on filename pattern.

    :param filename: (str) ISO filename
    :return: (bool) True if Proxmox ISO, False otherwise
    """
    filename_lower = filename.lower()
    # Check for proxmox patterns in filename
    return "proxmox" in filename_lower or filename_lower.startswith("pve-")


def save_proxmox_iso(mainlog, uploaded_file, proxmox_iso_dir=PROXMOXISODIR):
    """
    Save uploaded Proxmox ISO directly to PROXMOXISODIR without extraction.

    :param mainlog: application main logger handler
    :param uploaded_file: uploaded file object
    :param proxmox_iso_dir: (str) path to Proxmox ISO directory
    :return: (str) status message (OK or error message)
    """
    try:
        from os import makedirs

        # Ensure proxmox-iso directory exists
        if not path.exists(proxmox_iso_dir):
            mainlog.info(f"Creating Proxmox ISO directory: {proxmox_iso_dir}")
            makedirs(proxmox_iso_dir, exist_ok=True)

        # Check if ISO already exists
        iso_path = path.join(proxmox_iso_dir, uploaded_file.filename)
        if path.exists(iso_path):
            mainlog.error(
                f"Proxmox ISO {uploaded_file.filename} already exists - upload aborted"
            )
            return f"ISO {uploaded_file.filename} already exists"

        # Save the ISO file
        mainlog.info(f"Saving Proxmox ISO to: {iso_path}")
        uploaded_file.save(iso_path)
        mainlog.info(f"Proxmox ISO saved successfully: {uploaded_file.filename}")

        return "OK"

    except Exception as e:
        mainlog.error(f"Failed to save Proxmox ISO: {str(e)}")
        return f"Failed to save Proxmox ISO: {str(e)}"
