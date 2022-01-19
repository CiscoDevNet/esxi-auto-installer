echo killing old docker processes
docker-compose rm -fs

echo export host IP address
export EAI_HOST_IP=`python3 /opt/eai/get_host_ip.py`
echo $EAI_HOST_IP

echo building docker containers
docker-compose up --build -d
