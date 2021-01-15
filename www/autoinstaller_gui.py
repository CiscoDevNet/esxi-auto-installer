from flask import Flask, render_template, request, send_from_directory, redirect, url_for, session, jsonify
from flask_wtf import FlaskForm
# from wtforms.validators import (DataRequired, Email, EqualTo, Length, URL)
# from forms import GatherInput
from os import system, path, listdir
import sys
from vmai_functions import *
from config import *
# import logging

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cll-vmware-auto-installer'
app.config['UPLOAD_EXTENSIONS'] = ['.iso']
# app.config['UPLOAD_PATH'] = UPLOADDIR


@app.route("/", methods=('GET', 'POST'))
def autoinstaller_gui():
    # get directories from TFTPISODIR to build 'Select your ISO Image' dropdown menu
    print('[DEBUG] Listing ' + TFTPISODIR + ' content:')
    dirs = [f for f in listdir(TFTPISODIR) if path.isdir(path.join(TFTPISODIR, f))]
    dirs.sort()
    print(dirs)
    system('ls -la ' + TFTPISODIR + ' 1>&2')

    # pring page URL
    print('[DEBUG] ' + request.url)

    form = FlaskForm()
    #if form.validate_on_submit():
    if form.is_submitted():
        # get data entered on main page
        result = request.form
        # debug output
        print('[DEBUG] ' + str(result))

        for key in result.keys():
            if 'HOSTNAME' in key:
                hostname = result['HOSTPREFIX'] + result[key] + result['HOSTSUFFIX']
                print("[INFO] Processing " + key + ": " + hostname)

                # generate seq number based on HOSTNAME#
                seq = key.replace('HOSTNAME', '')

                # basic validation / error handling - abort in case mandatory data is missing
                if not (result['ROOTPW'] and result['HOSTPREFIX'] and result['MAC' + seq]
                        and result['IPADDR' + seq] and result['SUBNET'] and result['NETMASK'] and result['GATEWAY']):
                    print('[ERROR] Some manadatory data is missing!')
                    return render_template('error.html', install_data=result)

                ### customize kickstart config ###
                kscfg = hostname + "_ks.cfg"
                pre_section = ''
                # generate %pre section with static routes
                if result['StaticRoute'] in 'True':
                    pre_section = generate_ks_pre_section(result)

                ### generate kickstart file and save to KSDIR ###
                generate_kickstart(result['ROOTPW'], hostname, result['IPADDR' + seq],
                                   result['NETMASK'], result['GATEWAY'], result['VMNIC'], kscfg,
                                   result['FirstDisk'], result['FirstDiskType'], result['DiskPath'], pre_section,
                                   result.get('SSH'), result.get('clearpart'))

                ### customize PXE config ###
                srvip = request.host.split(':')[0]
                ksurl = 'http://' + srvip + '/ks/' + kscfg
                mac = str(result['MAC' + seq]).lower()
                # generate PXE config file and save to PXEDIR
                generate_pxe(ksurl, result['ISOFile'], mac)

                # generate custom EFI boot.cfg and save to /tftpboot/01-'mac-addr-dir'
                generate_efi(ksurl, result['ISOFile'], mac)


                ### customize dhcp entries and update dhcp config ###
                # generate dhcp config add to DHCPCFG
                # TODO: add verification if IP address isn't already used in dhcp.conf
                # TODO: ping verification to check if IP address is actually free?
                generate_dhcp(hostname, result['SUBNET'], result['NETMASK'],
                              result['IPADDR' + seq], result['GATEWAY'], mac)

                # reload dhcpd config - need to add error handling
                system('sudo /usr/bin/systemctl restart dhcpd')

                ### save installation data to local database (VMAI_DB)
                save_install_data_to_db(hostname, mac, result['IPADDR' + seq], result['SUBNET'],
                                        result['NETMASK'], result['GATEWAY'], '0', result['VMNIC'],
                                        result.get('SSH'), result.get('clearpart'), result['ROOTPW'],
                                        result['ISOFile'], 'Ready to deploy')
        return redirect(url_for('show'))
    return render_template('index.html', form=form, isodirs=dirs)

# allow listing kickstart files in 'ks' directory
@app.route('/ks/<path:filename>')
def send_ks(filename):
    return send_from_directory(directory='ks', filename=filename)

# show VMAI_DB page
@app.route('/show')
def show():
    with open(VMAI_DB, 'r') as vmaidb_file:
        vmaidb = json.load(vmaidb_file)
    return render_template('show-vmai-db.html', vmaidb=vmaidb)

# upload and extract ISO
@app.route('/upload', methods=['GET', 'POST'])
def upload_iso():
    print('[DEBUG] Listing ' + TFTPISODIR + ' content:')
    dirs = [f for f in listdir(TFTPISODIR) if path.isdir(path.join(TFTPISODIR, f))]
    print(dirs)
    system('ls -la ' + TFTPISODIR + ' 1>&2')

    if request.method == 'POST':
        # read file name
        uploaded_iso = request.files['file']
        if uploaded_iso.filename != '':
            file_ext = path.splitext(uploaded_iso.filename)[1]
            if file_ext not in app.config['UPLOAD_EXTENSIONS']:
                # return an error if file is not an ISO
                print('[ERROR] Incorrect file extension - not an ISO: ' + uploaded_iso.filename)
                return '[ERROR] Incorrect file extension - not an ISO: ' + uploaded_iso.filename
            else:
                # extract ISO to TFTPISODIR (default: /tftpboot/iso)
                extract_iso_to_tftpboot(uploaded_iso)
        return redirect(url_for('autoinstaller_gui'))
    return render_template('upload.html')

# show system services
@app.route('/services')
def services():
    services_dict = {}
    for service in 'dhcpd', 'crond', 'tftp':
        if 'tftp' in service:
            # tftp-server get's activatrd through socket
            services_dict[service] = check_service_status('tftp-server.socket')
        else:
            services_dict[service] = check_service_status(service)
    return render_template('show-services.html', services=services_dict)

# show service detailed status
@app.route('/service-details/<service_name>', methods=['GET'])
def service_details(service_name):
    if 'tftp' in service_name:
        service_name = 'tftp-server.socket'
    status_file = DOCROOT + 'tmp/' + service_name
    system('/usr/bin/systemctl status ' + service_name + ' >' + status_file)

    with open(status_file, 'r') as output_file:
        output = output_file.read()
    return render_template('service-detailed-status.html', service=service_name, details=output)

# admin panel
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    output = ''
    if request.method == 'POST':
        print('posted!')
        if request.form['submit_button'] == 'reset configuration':
            print('[DEBUG] Running /opt/vmai/scripts/vmai_cleanup.sh - reset to initial state.')
            system('sudo /opt/vmai/scripts/vmai_cleanup.sh')
        elif request.form['submit_button'] == 'restart dhcpd':
            print('[DEBUG] Restarting dhcpd service')
            system('sudo /usr/bin/systemctl restart dhcpd')
        # capture current auto-installer status
        print('[DEBUG] Check current Auto-installer status')
        system('sudo /opt/vmai/scripts/vmai_status_bw.sh >/tmp/vmai_status.out')
    elif request.method == 'GET':
        # on GET only display admin page with details on current status
        print('[DEBUG] Check current Auto-installer status')
        system('sudo /opt/vmai/scripts/vmai_status_bw.sh >/tmp/vmai_status.out')
    with open('/tmp/vmai_status.out', 'r') as output_file:
        output = output_file.read()
    return render_template('admin.html', details=output)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True)

