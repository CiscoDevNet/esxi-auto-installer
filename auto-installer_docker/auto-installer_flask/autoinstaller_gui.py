from flask import Flask, render_template, request, send_from_directory, redirect, url_for, session, jsonify
from flask_wtf import FlaskForm
from os import system, path, listdir
from multiprocessing import Process
from flask_restful import Api
import sys
from generic_functions import *
from autoinstaller_functions import *
from autoinstaller_api import *
from config import *

# from wtforms.validators import (DataRequired, Email, EqualTo, Length, URL)
# from forms import GatherInput

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cll-vmware-auto-installer'
app.config['UPLOAD_EXTENSIONS'] = ['.iso']
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
app.config['BUNDLE_ERRORS'] = True
# app.config['UPLOAD_PATH'] = UPLOADDIR
api = Api(app)


@app.route("/", methods=['GET', 'POST'])
def autoinstaller_gui():
    dirs = get_available_isos()
    # print(f'{EAIHOST_IP} {EAIHOST_GW} {EAIHOST_SUBNET} {EAIHOST_NETMASK}')

    if len(dirs) == 0:
        # redirect to welcome page when no installation ISO is found
        return render_template('no_iso.html')

    form = FlaskForm()
    # get data entered on main page
    result = request.form

    # if request.method == 'POST' and form.validate_on_submit():
    # TODO: server side data validation

    if request.method == 'POST' and form.is_submitted():
        mainlog = get_main_logger()
        mainlog.debug(result)
        # interate over the list of ESXi hosts and run corresponding actions for each host
        create_jobs(get_form_data(mainlog, result), result['installmethod'], mainlog)
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
    eaidb_dict = eaidb_get_status()
    # convert dictionary result to list with selected jobs' fields and sort by start_date
    eaidb_list = []
    for job_entry in eaidb_dict.items():
        if job_entry[1]['cimcip']:
            cimcip_or_mac = job_entry[1]['cimcip']
        else:
            cimcip_or_mac = job_entry[1]['macaddr']
        list_entry = [job_entry[1]['hostname'], cimcip_or_mac, job_entry[1]['start_time'],
                   job_entry[1]['finish_time'], job_entry[1]['status'], job_entry[0]]
        eaidb_list.append(list_entry)
    # TODO: fix sort to actually sort by date, not by string (?)
    sorteddb = sorted(eaidb_list, key=lambda x: x[2], reverse=True)
    return render_template('show-status.jinja', eaidb=sorteddb)


@app.route('/logs/<jobid>')
def logs(jobid):
    # get job log and display on web page
    return render_template('display_file.jinja', log_file_text=get_logs(jobid)[0])


# upload and extract ISO
@app.route('/upload', methods=['GET', 'POST'])
def upload_iso():
    mainlog=get_main_logger()
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
api.add_resource(EAIJobs, '/api/v1/jobs', methods=['GET', 'POST'])
api.add_resource(EAIJob, '/api/v1/jobs/<jobid>', methods=['GET', 'PUT'])
api.add_resource(EAILogs, '/api/v1/logs/<jobid>', methods=['GET'])
api.add_resource(EAIISOs, '/api/v1/isos', methods=['GET'])


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000, debug=True)

