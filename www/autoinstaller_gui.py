from flask import Flask, render_template, request, send_from_directory, redirect, url_for, session, jsonify
from flask_wtf import FlaskForm
# from wtforms.validators import (DataRequired, Email, EqualTo, Length, URL)
# from forms import GatherInput
from os import system
from vmai_functions import *
from config import *
# from config_local import *

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cll-vmware-auto-installer'


@app.route("/", methods=('GET', 'POST'))
def autoinstaller_gui():
    form = FlaskForm()
    #if form.validate_on_submit():
    if form.is_submitted():
        # get data entered on main page
        result = request.form
        # debug output
        print(result)

        for key in result.keys():
            if 'HOSTNAME' in key:
                hostname = result['HOSTPREFIX'] + result[key] + result['HOSTSUFFIX']
                print("Processing " + key + ": " + hostname)

                # generate seq number based on HOSTNAME#
                seq = key.replace('HOSTNAME', '')

                ### customize kickstart config ###
                kscfg = hostname + "_ks.cfg"
                enablessh = False
                clearpart = False

                # check if "Enable SSH" has been set
                try:
                    if result['SSH']:
                        enablessh = True
                except Exception:
                    pass

                # check if "Erase existing partition" has been set
                try:
                    if result['clearpart']:
                        clearpart = True
                except Exception:
                    pass

                # generate kickstart file and save to KSDIR
                generate_kickstart(result['ROOTPW'], hostname, result['IPADDR' + seq], result['SUBNET'],
                                   result['NETMASK'], result['GATEWAY'], result['VMNIC'], kscfg, enablessh, clearpart)

                ### customize PXE config ###
                srvip = request.host.split(':')[0]
                #srvip = '192.168.100.1'             # on dev VM we have separate installation NIC
                ksurl = 'http://' + srvip + '/ks/' + kscfg
                # generate PXE config file and save to PXEDIR
                isover = generate_pxe(ksurl, result['ISOFile'], result['MAC' + seq])

                # generate custom EFI boot.cfg and save to /tftpboot/01-'mac-addr-dir'
                generate_efi(ksurl, result['MAC' + seq])


                ### customize dhcp entries and update dhcp config ###
                # generate dhcp config add to DHCPCFG
                # add verification if IP address isn't already used in dhcp.conf
                # ping verification to check if IP address is actually free?
                generate_dhcp(hostname, result['SUBNET'], result['NETMASK'],
                              result['IPADDR' + seq], result['GATEWAY'], result['MAC' + seq])

                # reload dhcpd config - need to add error handling
                system('systemctl restart dhcpd')

                ### save installation data to local database (VMAI_DB)
                # save_install_data_to_db(hostname, result['MAC' + seq], result['IPADDR' + seq], result['SUBNET'],
                #                         result['NETMASK'], result['GATEWAY'], result['VLAN'], result['VMNIC'],
                #                         enablessh, clearpart, result['ROOTPW'], isover, 'Ready to deploy')
                ## setting VLAN disabled in web form - adjusting function call accordingly
                save_install_data_to_db(hostname, result['MAC' + seq], result['IPADDR' + seq], result['SUBNET'],
                                        result['NETMASK'], result['GATEWAY'], '0', result['VMNIC'],
                                        enablessh, clearpart, result['ROOTPW'], isover, 'Ready to deploy')
                print_vmai_db()

                ### tmp file for debugging ###
                with open('/tmp/autotuner.out', 'a+') as file:
                  for key, value in result.items():
                    file.write(key + ': ' + value + '\n')

        # display status page
        # return render_template('status.html', install_data=result)
        return redirect(url_for('show'))
    return render_template('index.html', form=form)

# allow listing kickstart files in 'ks' directory
@app.route('/ks/<path:filename>')
def send_ks(filename):
    return send_from_directory(directory='ks', filename=filename)

# allow listing kickstart files in 'ks' directory
@app.route('/show')
def show():
    with open(VMAI_DB, 'r') as vmaidb_file:
        vmaidb = json.load(vmaidb_file)
    return render_template('show-vmai-db.html', vmaidb=vmaidb)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=80, debug=True)


