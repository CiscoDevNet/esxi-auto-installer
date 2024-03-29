# from flask import Flask
from email.policy import default
from flask_restful import Resource, reqparse
from flask import request
from autoinstaller_functions import *

import ipaddress


class EAIJobs(Resource):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument(
            "installmethod",
            type=str,
            required=True,
            help="No installation method provided",
            location="json",
        )
        self.reqparse.add_argument(
            "iso_image",
            type=str,
            required=True,
            help="No ISO name provided",
            location="json",
        )
        self.reqparse.add_argument(
            "root_pwd",
            type=str,
            required=True,
            help="No root password provided",
            location="json",
        )
        self.reqparse.add_argument(
            "cimc_pwd", type=str, help="No CIMC password provided", location="json"
        )
        self.reqparse.add_argument(
            "host_netmask",
            type=str,
            required=True,
            help="No Netmask provided",
            location="json",
        )
        self.reqparse.add_argument(
            "host_gateway",
            type=str,
            required=True,
            help="No Gateway provided",
            location="json",
        )
        self.reqparse.add_argument(
            "hosts",
            type=list,
            required=True,
            help="No host list provided",
            location="json",
        )
        # hosts data validation (hostname, host_ip, cimc_ip, MAC address) handled in post() method
        self.reqparse.add_argument(
            "vlan", type=str, default="0", help="No VLAN ID provided", location="json"
        )
        self.reqparse.add_argument(
            "vmnic", type=str, default="0", help="No VMNIC provided", location="json"
        )
        self.reqparse.add_argument(
            "cimc_usr",
            type=str,
            default="admin",
            help="No CIMC account provided",
            location="json",
        )
        self.reqparse.add_argument(
            "firstdisk",
            type=str,
            default="firstdiskfound",
            help="No Install Disk provided",
            location="json",
        )
        self.reqparse.add_argument(
            "firstdisktype",
            type=str,
            default="local",
            help="No Disk Type provided",
            location="json",
        )
        # TODO: if firstdisk == diskpath: diskpath required
        self.reqparse.add_argument(
            "enablessh", type=bool, default=True, location="json"
        )
        self.reqparse.add_argument(
            "clearpart", type=bool, default=False, location="json"
        )
        self.reqparse.add_argument("dns1", type=str, default="", location="json")
        self.reqparse.add_argument("dns2", type=str, default="", location="json")
        # self.reqparse.add_argument('static_routes_set', type = bool, default=False, location = 'json')
        self.reqparse.add_argument(
            "static_routes", type=list, default=[], location="json"
        )
        # static_routes data validation (subnet_ip, cidr, gateway) handled in post() method
        super(EAIJobs, self).__init__()

    def get(self):
        # api endpoint for getting details for all jobs
        return eaidb_get_status(), 200

    def post(self):
        mainlog = get_main_logger()
        try:
            jobid_list = []
            install_data = {}
            args = self.reqparse.parse_args()
            mainlog.debug(f"API /jobs endpoint called with args: {args}")

            # Verify fields that are common to all install types.
            if args["installmethod"] not in ("pxeboot", "cimc"):
                mainlog.error(
                    f"API POST /jobs error - Unknown installation method. Request aborted."
                )
                return {
                    "status": "error",
                    "message": "Unknown installation method",
                }, 400
            try:
                ipaddress.ip_address(args["host_gateway"])
            except ValueError:
                return {
                    "status": "error",
                    "message": "Required field is not valid: host_gateway",
                }, 400
            try:
                ipaddress.ip_address(args["host_netmask"])
            except ValueError:
                return {
                    "status": "error",
                    "message": "Required field is not valid: host_netmask",
                }, 400
            try:
                # Cached for later use in the host address checkcheck.
                ipsubnetobj = ipaddress.ip_network(f'{args["host_gateway"]}/{args["host_netmask"]}', strict=False)
            except ValueError:
                return {
                    "status": "error",
                    "message": "Field is not a valid netmask: host_netmask",
                }, 400
            p = re.compile("^[A-Za-z\d\-_]{1,63}$")
            for host_data in args["hosts"]:
                print(f"[DEBUG] Host data: {host_data}")
                if "hostname" in host_data:
                    if not re.search(p, host_data["hostname"]):
                        return {
                            "status": "error",
                            "message": "Required hosts field is not valid: hostname",
                        }, 400
                else:
                    return {
                        "status": "error",
                        "message": "Required hosts field not provided: hostname",
                    }, 400
                if "host_ip" in host_data:
                    try:
                        ipaddress.ip_address(host_data["host_ip"])
                    except ValueError:
                        return {
                            "status": "error",
                            "message": "Required hosts field is not valid: host_ip",
                        }, 400
                    if args["host_gateway"]:
                        if not (ipaddress.ip_address(host_data["host_ip"]) in ipsubnetobj):
                            return {
                                "status": "error",
                                "message": f'Host IP {host_data["host_ip"]} and Host Gateway {args["host_gateway"]} are not in the same Host Netmask {args["host_netmask"]}'
                            }, 400
                else:
                    mainlog.error(
                        f"API POST /jobs error - missing host data. Request aborted."
                    )
                    return {
                        "status": "error",
                        "message": "Required hosts field not provided: host_ip",
                    }, 400

            # Installation method: PXE boot
            if args["installmethod"] == "pxeboot":
                # Setup regex before the loop. This is a simplified mac address check because it will be run after the mac has been cleaned up.
                p = re.compile("^([a-f0-9]){12}$")
                # get current entries from EAIDB
                eaidb_dict = eaidb_get_status()

                # Set required keys. host_ip is omitted because we tested it earlier.
                for host_data in args["hosts"]:
                    # do not create new entry with same hostname and 'Ready to deploy' state
                    for jobid, job_data in eaidb_dict.items():
                        if (
                            host_data["hostname"] == job_data["hostname"]
                            and job_data["status"] == "Ready to deploy"
                        ):
                            return {
                                "status": "error",
                                "message": f"Conflicting job entry. Run the following API call to cancel conflicting job.",
                                "cancel_url": f"http://{EAIHOST_IP}/api/v1/jobs/{jobid}?state=25",
                                "http_method": "PUT",
                            }, 409

                    if not "macaddr" in host_data:
                        mainlog.error(
                            f"API POST /jobs error - missing host data. Request aborted."
                        )
                        return {
                            "status": "error",
                            "message": "Required hosts field not provided: macaddr",
                        }, 400
                    # Remove symbols from MAC address.
                    host_data["macaddr"] = (
                        host_data["macaddr"]
                        .replace(":", "")
                        .replace(".", "")
                        .replace("-", "")
                        .lower()
                    )
                    # Verify mac address is a valid.
                    if not re.search(p, host_data["macaddr"]):
                        return {
                            "status": "error",
                            "message": "Required hosts field is not valid: macaddr",
                        }, 400
                    # Put MAC addres in required format
                    host_data["macaddr"] = ":".join(
                        [host_data["macaddr"][i : i + 2] for i in range(0, 12, 2)]
                    )
            else:  # any OOBM installation method.
                # Installation method: mount installation ISO with OOBM
                # check if CIMC IP and credentials have been provided
                if not args["cimc_pwd"] or not args["cimc_usr"]:
                    mainlog.error(
                        f"API POST /jobs error - missing CIMC credentials. Request aborted."
                    )
                    return {
                        "status": "error",
                        "message": "Missing CIMC credentials",
                    }, 400
                for host_data in args["hosts"]:
                    print(f"[DEBUG] Host data: {host_data}")
                    if "cimc_ip" not in host_data:
                        # if not host_data['hostname'] or not host_data['host_ip'] or not host_data['cimc_ip']:
                        # in case some data is missing KeyError is thrown and corresponding error returned
                        mainlog.error(
                            f"API POST /jobs error - missing host data. Request aborted."
                        )
                        return {
                            "status": "error",
                            "message": "Required hosts field not provided. cimc_ip",
                        }, 400
                    # Verify OOBM IP Address
                    try:
                        if host_data["cimc_ip"].count(".") == 3:
                            # It's an IPv4 address.
                            port_separator = host_data["cimc_ip"].rfind(":")
                            address_string = (
                                host_data["cimc_ip"]
                                if port_separator == -1
                                else host_data["cimc_ip"][0:port_separator]
                            )
                        else:
                            # Could be IPv6 address.
                            port_separator = host_data["cimc_ip"].rfind("]:")
                            address_string = (
                                host_data["cimc_ip"]
                                if port_separator == -1
                                else host_data["cimc_ip"][0 : port_separator + 1]
                            )

                        ipaddress.ip_address(address_string)
                    except ValueError:
                        return {
                            "status": "error",
                            "message": "Required hosts field is not valid: cimc_ip.",
                        }, 400

            # check if static_routes are valid.
            if len(args["static_routes"]) > 0:
                for item in args["static_routes"]:
                    # Test the ip address.
                    try:
                        ipaddress.ip_network(f"{item['subnet_ip']}/{item['cidr']}")
                    except ValueError:
                        mainlog.error(
                            f"Static route subnet '{item['subnet_ip']}/{item['cidr']}' is invalid"
                        )
                        return {
                            "status": "error",
                            "message": "static_route field combination is not valid: subnet_ip and cidr",
                        }, 400

                    # Test the gateway.
                    try:
                        ipaddress.ip_address(item["gateway"])
                    except ValueError:
                        return {
                            "status": "error",
                            "message": "static_route field is not valid: gateway",
                        }, 400

            # host data validation passed for all entries - let's skip arguments with None value and calculate host_subnet
            for k, v in args.items():
                if v != None:
                    install_data[k] = v

            install_data["host_subnet"] = str(
                ip_network(
                    install_data["host_gateway"] + "/" + install_data["host_netmask"],
                    strict=False,
                ).network_address
            )

            # if requested ISO is not valid - return an error
            if not install_data["iso_image"] in get_available_isos():
                mainlog.error(f"Requested ISO {install_data['iso_image']} not found")
                return {"status": "error", "message": "Requested ISO not found"}, 404

            # All data validated, print debug log
            mainlog.debug(f"API POST /jobs install data: {install_data}")

            # interate over the list of ESXi hosts and run corresponding actions for each host
            jobid_list = create_jobs(install_data, args["installmethod"], mainlog)
            return jobid_list
        except KeyError as e:
            return {
                "status": "error",
                "message": f"Incorrect or missing key when trying to create a new job. Expected key: {str(e)}",
            }, 400


class EAIJob(Resource):
    def get(self, jobid):
        try:
            eaidb_dict = eaidb_get_status()
            return eaidb_dict[jobid], 200
        except KeyError:
            return {"status": "error", "message": f"Job ID not found"}, 404

    def put(self, jobid, mainlog=get_main_logger(), status_dict=STATUS_CODES):
        try:
            if eaidb_check_jobid_exists(jobid):
                # only run cleanup tasks for existing job ID
                query_parameters = request.args
                status_code = int(query_parameters.get("state"))
                mainlog.debug(
                    f"{jobid} API endpoint called with args: {query_parameters.to_dict()}"
                )

                if status_code not in status_dict:
                    # ignore invalid status codes
                    mainlog.error(f"State not valid: {status_code}")
                    return {"status": "error", "message": f"State not valid"}, 400
                else:
                    status = status_dict[status_code]
                    logger = get_jobid_logger(jobid)
                    logger.info(f"API received status code {status_code}: {status}")

                    # if status_code == 0:
                    #     # this state should be only set when creating DB entry - not doing anything here
                    #     pass
                    if status_code in range(10, 19):
                        # status codes for installation phases
                        Finished = False
                        if status_code == 17:
                            Process(
                                target=final_reboot,
                                args=(
                                    jobid,
                                    (
                                        True
                                        if query_parameters.get("enable_ssh") == "1"
                                        else False
                                    ),
                                    logger,
                                    mainlog,
                                ),
                            ).start()

                    elif status_code in range(20, 39):
                        # TODO:
                        #### Under new 'api-ssh' update, this section will never be called.
                        #### Need to ensure it's functionality is covered.

                        # status codes for finished or errors
                        Finished = True
                        # for status codes from range Finished/Error - run cleanup and log status in job log
                        # get job logger
                        # run cleanup
                        if status_code == 31:
                            # do not try to unmount the ISO if login to CIMC failed
                            job_cleanup(jobid, logger, mainlog, unmount_iso=False)
                        else:
                            job_cleanup(jobid, logger, mainlog, unmount_iso=True)

                    if status_code != 17:
                        # update status in EAIDB
                        # Do not want to set status for code 17 because it will set it's own status. Do not want a race condition by setting it multiple times.
                        update_job_status(jobid, status, logger, Finished)

                eaidb_dict = eaidb_get(
                    jobid,
                    (
                        "hostname",
                        "ipaddr",
                        "cimcip",
                        "start_time",
                        "finish_time",
                        "status",
                        "macaddr",
                        "netmask",
                        "gateway",
                    ),
                )
                return eaidb_dict
            else:
                return {"status": "error", "message": f"Job ID not found"}, 404
        except Exception:
            mainlog.error("Unable to process PUT jobs request.")
            return {"status": "error", "message": f"Job ID not found"}, 404


class EAILogs(Resource):
    def get(self, jobid):
        return get_logs(jobid)


class EAIISOs(Resource):
    def get(self):
        # return the list of available ISO images
        return get_available_isos()
