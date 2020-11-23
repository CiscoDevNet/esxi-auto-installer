if [ $# -eq 0 ]
then
  echo "Please provide IP address as 1st parameter. Exiting."
  exit 1
fi

SRV=$1

while [ 1 ]
do
  wget --no-check-certificate https://${SRV}/READY -O /tmp/${SRV}_status >/dev/null 2>&1
  [ $? -ne 0 ] && echo -e "\E[1;35mServer $SRV installation in progress...\E[0;39m" || echo -e "\E[0;32m`grep finished /tmp/${SRV}_status`\E[0;39m"
  sleep 10
done
