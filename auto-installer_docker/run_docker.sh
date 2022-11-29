echo "*** Checking pre-requisites ***"
# check pre-requisites: docker-compose
which docker-compose >/dev/null
if [ $? -ne 0 ]
then
    echo "[ERROR] Missing docker-compose binary - install the package and re-run this script. Aborting."
    exit 1
fi
# check pre-requisites: python3
which python3 >/dev/null
if [ $? -ne 0 ]
then
    echo "[ERROR] Missing Python binary - install the package and re-run this script. Aborting."
    exit 2
fi
# check pre-requisites: python3
pip3 show netifaces >/dev/null
if [ $? -ne 0 ]
then
    echo "[ERROR] Missing Python netifaces library - install and re-run this script. Aborting."
    exit 3
fi
# check pre-requisites: python3
pip3 show jinja2 >/dev/null
if [ $? -ne 0 ]
then
    echo "[ERROR] Missing Python jinja2 library - install and re-run this script. Aborting."
    exit 4
fi
echo "[INFO] All pre-requisites met."

# (re)building docker containers
echo
echo "*** Killing old docker processes ***"
docker-compose rm -fs

echo
echo "*** Exporting host network settings ***"

NETWORK_DATA=( `python3 get_host_network_settings.py` )
export EAI_HOST_IP=${NETWORK_DATA[0]}
export EAI_HOST_GW=${NETWORK_DATA[1]}
export EAI_HOST_SUBNET=${NETWORK_DATA[2]}
export EAI_HOST_NETMASK=${NETWORK_DATA[3]}

echo
echo EAI_HOST_IP: $EAI_HOST_IP
echo EAI_HOST_GW: $EAI_HOST_GW
echo EAI_HOST_SUBNET: $EAI_HOST_SUBNET
echo EAI_HOST_NETMASK: $EAI_HOST_NETMASK
echo

echo "*** Checking/creating EAIDB database ***"
python3 create_eaidb.py 
echo

echo "*** Building docker containers ***"
docker-compose up --build -d
