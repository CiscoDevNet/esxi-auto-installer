#!/bin/bash
while true
do
    if [ -f /etc/dhcp/dhcpd.conf ]
    then
        if [ -f /etc/dhcp/dhcpd.conf_current ]
        then
            diff /etc/dhcp/dhcpd.conf /etc/dhcp/dhcpd.conf_current
            if [ $? -ne 0 ]
            then
                echo "[INFO] Current config different from reference config. Re-reading dhcpd.conf and restarting DHCP server."
                supervisorctl stop dhcpd
            else
                # just in case - start DHCP server if it isn't running, as we know it should
                supervisorctl status dhcpd
                if [ $? -ne 0 ]
                then
                    supervisorctl start dhcpd
                fi
            fi
        fi

        # create current config reference if it doesnt exist (first run)
        cp /etc/dhcp/dhcpd.conf /etc/dhcp/dhcpd.conf_current
        # start DHCP server if it isn't running
        supervisorctl status dhcpd
        if [ $? -ne 0 ]
        then
            supervisorctl start dhcpd
        fi

    else
        # echo "[DEBUG] No config file present"
        # no dhcpd.config - stop DHCP server it is running
        supervisorctl status dhcpd
        if [ $? -eq 0 ]
        then
            echo "[INFO] Stopping DHCP server..."
            supervisorctl stop dhcpd
        fi
    fi

    echo " Waiting 5 seconds..."
    sleep 5
done