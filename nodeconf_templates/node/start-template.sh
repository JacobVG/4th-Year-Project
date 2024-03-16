ip -6 addr add $IP_ADDR dev $IF_NAME 
ip -6 route add default via $GW_ADDR dev $IF_NAME