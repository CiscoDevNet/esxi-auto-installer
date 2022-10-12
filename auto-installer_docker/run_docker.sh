echo Killing old docker processes
docker-compose rm -fs

echo Exporting host network settings

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

echo Building docker containers
docker-compose up --build -d
