from flask import Flask, render_template, request, send_from_directory, redirect, url_for, session, jsonify
from flask_wtf import FlaskForm
from os import system, path, listdir
from multiprocessing import Process
from generic_functions import *
from autoinstaller_functions import *
from config import *

# from wtforms.validators import (DataRequired, Email, EqualTo, Length, URL)
# from forms import GatherInput
# import logging
import sys

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cll-vmware-auto-installer'
app.config['UPLOAD_EXTENSIONS'] = ['.iso']
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
# app.config['UPLOAD_PATH'] = UPLOADDIR


@app.route("/", methods=['GET', 'POST'])
def autoinstaller_gui():
    dirs = get_available_isos()
    form = FlaskForm()
    # get data entered on main page
    result = request.form

    # if request.method == 'POST' and form.validate_on_submit():
    # TODO: server side data validation

    if request.method == 'POST' and form.is_submitted():
        mainlog = get_main_logger()
        mainlog.debug(result)
        form_data = get_form_data(mainlog, result)

        # interate over the list of ESXi hosts and run corresponding actions for each host
        for index in range(len(form_data['hosts'])):
            hostname = form_data['hosts'][index]['hostname']
            ipaddr = form_data['hosts'][index]['ipaddr']
            cimcip = form_data['hosts'][index]['cimcip']

            # generate jobid based on CIMC IP and current timestamp
            jobid = generate_jobid(form_data['hosts'][index]['cimcip'])

            # create logger handler
            logger = get_jobid_logger(jobid)
            logger.info(f'Processing job ID: {jobid}, server {hostname}\n')
            mainlog.info(f'{jobid} - processing job ID, server {hostname}')

            # create entry in Auto-Installer DB
            mainlog.info(f'{jobid} Saving installation data for server {hostname}')
            eaidb_create_job_entry(jobid, time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime()), hostname, ipaddr,
                                   cimcip, form_data['cimc_usr'], form_data['cimc_pwd'])

            # customize kickstart config
            mainlog.info(f'{jobid} Generating kickstart file for server {hostname}')
            kscfg = generate_kickstart(jobid, form_data, index, logger, mainlog)

            # generate custom installation ISO
            mainlog.info(f'{jobid} Generating custom installation ISO for server {hostname}')
            generate_custom_iso(jobid, logger, mainlog, hostname, form_data['iso_image'], kscfg)

            # start ESXi hypervisor installation
            Process(target=install_esxi, args=(jobid, logger, mainlog, cimcip, form_data['cimc_usr'],
                                               form_data['cimc_pwd'], jobid + '.iso')).start()

        return redirect(url_for('show'))
    return render_template('index.html', form=form, isodirs=dirs)


# route for serving kickstart files from KSDIR directory
@app.route('/ks/<path:filename>')
def send_ks(filename):
    return send_from_directory(KSDIR, filename)


# route for serving files from CUSTOMISODIR directory
@app.route('/custom-iso/<path:filename>')
def send_customiso(filename):
    return send_from_directory(CUSTOMISODIR, filename)


# route for files in ESXISODIR directory
@app.route('/esxi-iso/<path:filename>')
def send_esxi_iso(filename):
    return send_from_directory(ESXISODIR, filename)


# show EAIDB page
@app.route('/show')
def show():
    # get all jobs details from EAIDB using GET /jobs endpoint function
    eaidb_dict = api_jobs_get()
    # convert dictionary result to list with selected jobs' fields and sort by start_date
    eaidb_list = []
    for job_entry in eaidb_dict.items():
        list_entry = [job_entry[1]['hostname'], job_entry[1]['cimcip'], job_entry[1]['start_time'],
                   job_entry[1]['finish_time'], job_entry[1]['status'], job_entry[0]]
        eaidb_list.append(list_entry)
    # TODO: fix sort to actually sort by date, not by string (?)
    sorteddb = sorted(eaidb_list, key=lambda x: x[2], reverse=True)
    return render_template('show-status.jinja', eaidb=sorteddb)


@app.route('/logs/<jobid>')
def logs(jobid):
    # get job log using GET /logs endpoint function and display on web page
    return render_template('display_file.jinja', log_file_text=api_logs_get(jobid)[0])


# upload and extract ISO
@app.route('/upload', methods=['GET', 'POST'])
def upload_iso(mainlog=get_main_logger()):
    if request.method == 'POST':
        # read file name
        uploaded_iso = request.files['file']
        mainlog.info(f'Request to upload ISO: {uploaded_iso.filename}')
        if uploaded_iso.filename != '':
            file_ext = path.splitext(uploaded_iso.filename)[1]
            if file_ext not in app.config['UPLOAD_EXTENSIONS']:
                # return an error if file is not an ISO
                mainlog.error(f'Incorrect file extension - not an ISO: {uploaded_iso.filename}')
                return f'ERROR: Incorrect file extension - not an ISO: {uploaded_iso.filename}'
            else:
                mainlog.info(f'Starting ISO upload')
                # extract ISO to ESXISODIR
                iso_extract(mainlog, uploaded_iso)
                # copy extracted ISO and prepare it for tftpboot
                # iso_prepare_tftp(mainlog, uploaded_iso)
        return redirect(url_for('autoinstaller_gui'))
    return render_template('upload.html')


# api swagger document
@app.route('/api', methods=['GET'])
def api_swagger():
    return render_template('api_swagger.html')

# API endpoints #
# api endpoint for getting details for all jobs
@app.route('/api/v1/jobs', methods=['GET'])
def api_jobs_get():
    return eaidb_get_status()


# api endpoint for getting details for specific job
@app.route('/api/v1/jobs/<jobid>', methods=['GET'])
def api_jobs_get_jobid(jobid):
    try:
        eaidb_dict = eaidb_get_status()
        return eaidb_dict[jobid]
    except KeyError:
        return f'Job ID {jobid} not found.', 404


# api endpoint for starting new job(s)
@app.route('/api/v1/jobs', methods=['POST'])
def api_jobs_post(mainlog=get_main_logger()):
    query_parameters = request.args
    jobid = generate_jobid()
    mainlog.debug(f'{jobid} API endpoint called with args: {query_parameters}')
    return 'API jobs POST endpoint placeholder'


# api endpoint for updating job status
@app.route('/api/v1/jobs/<jobid>', methods=['PUT'])
def api_jobs_put(jobid, mainlog=get_main_logger(), status_dict=STATUS_CODES):
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
                    job_cleanup(jobid, logger, mainlog)
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


# api endpoint for updating job status
@app.route('/api/v1/logs/<jobid>', methods=['GET'])
def api_logs_get(jobid, basedir=LOGDIR):
    # Joining the base and the requested path
    abs_path = os.path.join(basedir, jobid)

    # Return 404 if path doesn't exist
    if not os.path.exists(abs_path):
        return 'File does not exist!', 404

    # Check if path is a file and serve
    if os.path.isfile(abs_path):
        with open(abs_path, 'r') as log_file:
            return log_file.read(), 200, {'Content-Type': 'text/plain; charset=utf-8'}


# api endpoint for uploading installation ISO
@app.route('/api/v1/upload', methods=['POST'])
def api_upload_iso():
    return '/api/v1/upload endpoint placeholder'


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True)

