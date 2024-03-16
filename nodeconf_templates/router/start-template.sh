FRR_PATH=/usr/lib/frr

# add IPs for router interfaces

sysctl -w net.ipv6.conf.all.forwarding=1

echo "no service integrated-vtysh-config" >> /etc/frr/vtysh.conf
chown -R frr:frrvty $BASE_DIR$NODE_NAME
chmod 755 $BASE_DIR$NODE_NAME
$FRR_PATH/zebra -f $BASE_DIR$NODE_NAME/zebra.conf -d -z $BASE_DIR$NODE_NAME/zebra.sock -i $BASE_DIR$NODE_NAME/zebra.pid

sleep 1

$FRR_PATH/isisd -f $BASE_DIR$NODE_NAME/isisd.conf -d -z $BASE_DIR$NODE_NAME/zebra.sock -i $BASE_DIR$NODE_NAME/isisd.pid

# enable Segment Routing for IPv6
sysctl -w net.ipv6.conf.all.seg6_enabled=1
for dev in $(ip -o -6 a | awk '{ print $2 }' | grep -v "lo")
do
   sysctl -w net.ipv6.conf."$dev".seg6_enabled=1
done