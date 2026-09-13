# Nettoyage préalable au cas où
sudo ip netns del nsA 2>/dev/null
sudo ip netns del nsB 2>/dev/null
sudo ip netns del nsC 2>/dev/null
sudo ip link del br1 2>/dev/null
sudo ip link del br2 2>/dev/null

# Création des 3 namespaces
sudo ip netns add nsA
sudo ip netns add nsB
sudo ip netns add nsC

# Création des 2 bridges
sudo ip link add br1 type bridge
sudo ip link add br2 type bridge
sudo ip link set br1 up
sudo ip link set br2 up

# Lien A <-> br1
sudo ip link add vethA type veth peer name vethAbr
sudo ip link set vethA netns nsA
sudo ip link set vethAbr master br1
sudo ip link set vethAbr up

# Liens de B (un vers br1, un vers br2)
sudo ip link add vethB1 type veth peer name vethB1br
sudo ip link set vethB1 netns nsB
sudo ip link set vethB1br master br1
sudo ip link set vethB1br up

sudo ip link add vethB2 type veth peer name vethB2br
sudo ip link set vethB2 netns nsB
sudo ip link set vethB2br master br2
sudo ip link set vethB2br up

# Lien C <-> br2
sudo ip link add vethC type veth peer name vethCbr
sudo ip link set vethC netns nsC
sudo ip link set vethCbr master br2
sudo ip link set vethCbr up

# Configuration de nsA
sudo ip netns exec nsA ip link set lo up
sudo ip netns exec nsA ip link set vethA up
sudo ip netns exec nsA ip addr add 10.0.1.1/24 dev vethA
sudo ip netns exec nsA ip route add default dev vethA

# Configuration de nsB
sudo ip netns exec nsB ip link set lo up
sudo ip netns exec nsB ip link set vethB1 up
sudo ip netns exec nsB ip addr add 10.0.1.2/24 dev vethB1
sudo ip netns exec nsB ip link set vethB2 up
sudo ip netns exec nsB ip addr add 10.0.2.2/24 dev vethB2
sudo ip netns exec nsB ip route add default dev vethB1

# Configuration de nsC
sudo ip netns exec nsC ip link set lo up
sudo ip netns exec nsC ip link set vethC up
sudo ip netns exec nsC ip addr add 10.0.2.3/24 dev vethC
sudo ip netns exec nsC ip route add default dev vethC