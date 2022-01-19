# from flask import Flask
from email.policy import default
from flask_restful import Resource, reqparse
from flask import request
from autoinstaller_functions import *


class EAIJobs(Resource):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('iso_image', type = str, required = True, help = 'No ISO name provided', location = 'json')
        self.reqparse.add_argument('root_pwd', type = str, required = True, help = 'No root password provided', location = 'json')
        self.reqparse.add_argument('cimc_pwd', type = str, required = True, help = 'No CIMC password provided', location = 'json')
        self.reqparse.add_argument('host_netmask', type = str, required = True, help = 'No Netmask provided', location = 'json')
        self.reqparse.add_argument('host_gateway', type = str, required = True, help = 'No Gateway provided', location = 'json')
        self.reqparse.add_argument('hosts', type = list, required = True, help = 'No host list provided', location = 'json')
        # TODO: add hosts list validation (hostname, host_ip, cimc_ip) ?
        self.reqparse.add_argument('vlan', type = str, default='0', help = 'No VLAN ID provided', location = 'json')
        self.reqparse.add_argument('vmnic', type = str, default='0', help = 'No VMNIC provided', location = 'json')
        self.reqparse.add_argument('cimc_usr', type = str, default='admin', help = 'No CIMC account provided', location = 'json')
        self.reqparse.add_argument('firstdisk', type = str, default='firstdiskfound', help = 'No Install Disk provided', location = 'json')
        self.reqparse.add_argument('firstdisktype', type = str, default='local', help = 'No Disk Type provided', location = 'json')
        # TODO: if firstdisk == diskpath: diskpath required
        self.reqparse.add_argument('enablessh', type = bool, default=True, location = 'json')
        self.reqparse.add_argument('clearpart', type = bool, default=False, location = 'json')
        self.reqparse.add_argument('dns1', type = str, default='', location = 'json')
        self.reqparse.add_argument('dns2', type = str, default='', location = 'json')
        # self.reqparse.add_argument('static_routes_set', type = bool, default=False, location = 'json')
        self.reqparse.add_argument('static_routes', type = list, default=[], location = 'json')
        # TODO: add static_routes list validation (subnet_ip, cidr, gateway) ?
        super(EAIJobs, self).__init__()

    def get(self):
        # api endpoint for getting details for all jobs
        return eaidb_get_status(), 200

    def post(self):
        mainlog=get_main_logger()
        try:
            jobid_list = []
            install_data = {}
            args = self.reqparse.parse_args()
            print(args)
            for k, v in args.items():
                if v != None:
                    install_data[k] = v

            install_data['host_subnet'] = str(ip_network(install_data['host_gateway'] + '/' + install_data['host_netmask'], strict=False).network_address)
            mainlog.debug(f'API /jobs endpoint called with args: {args}')

            # interate over the list of ESXi hosts and run corresponding actions for each host
            jobid_list = create_jobs(install_data, mainlog)
            return jobid_list
        except KeyError as e:
            return f'Incorrect key when trying to create a new job. Expected key: {str(e)}', 400


class EAIJob(Resource):
    def get(self, jobid):
        try:
            eaidb_dict = eaidb_get_status()
            return eaidb_dict[jobid], 200
        except KeyError:
            return f'Job ID {jobid} not found.', 404

    def put(self, jobid, mainlog=get_main_logger(), status_dict=STATUS_CODES):
        try:
            if eaidb_check_jobid_exists(jobid):
                # only run cleanup tasks for existing job ID
                query_parameters = request.args
                status_code = int(query_parameters.get('state'))
                mainlog.debug(f'{jobid} API endpoint called with args: {query_parameters}')

                # TODO: move status code validation/translation to separate function?
                if status_code not in status_dict:
                    # ignore invalid status codes
                    mainlog.error(f'State not valid: {status_code}')
                else:
                    if status_code == 0:
                        # this state should be only set when creating DB entry - not doing anything here
                        eaidb_dict = eaidb_get_status()
                        return eaidb_dict[jobid]
                    elif status_code in range(10,19):
                        # status codes for installation phases
                        status = status_dict[status_code]
                        finish_time = ''
                    elif status_code in range(20,39):
                        # status codes for finished or errors
                        status = status_dict[status_code]
                        finish_time = time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime())

                        # for status codes from range Finished/Error - run cleanup and log status in job log
                        # get job logger
                        logger = get_jobid_logger(jobid)
                        # run cleanup
                        if status_code == 31:
                            # do not tru to unmount the ISO if login to CIMC failed
                            job_cleanup(jobid, logger, mainlog, unmount_iso=False)
                        else:
                            job_cleanup(jobid, logger, mainlog, unmount_iso=True)
                        # update job log
                        logger.info(f'Installation job (ID: {jobid}) finished.')
                        logger.info(f'Final status code: {status_dict[status_code]}\n')

                    # update status in EAIDB
                    eaidb_update_job_status(jobid, status, finish_time)

                eaidb_dict = eaidb_get_status()
                return eaidb_dict[jobid]
            else:
                return f'Job ID {jobid} not found.', 404
        except Exception:
            return f'Job ID {jobid} not found.', 404


class EAILogs(Resource):
    def get(self, jobid):
        return get_logs(jobid)


class EAIISOs(Resource):
    def get(self):
        # return the list of available ISO images
        return get_available_isos()
