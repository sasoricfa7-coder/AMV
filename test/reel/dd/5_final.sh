set -e

echo "=== 1. Création des 3 namespaces ==="
sudo ip netns add nsA
sudo ip netns add nsB
sudo ip netns add nsC

echo "=== 2. Création du bridge br0 ==="
sudo ip link add br0 type bridge
sudo ip link set br0 up

echo "=== 3. Lien A <-> br0 ==="
sudo ip link add vethA type veth peer name vethAbr
sudo ip link set vethA netns nsA
sudo ip link set vethAbr master br0
sudo ip link set vethAbr up

echo "=== 4. Lien B <-> br0 ==="
sudo ip link add vethB type veth peer name vethBbr
sudo ip link set vethB netns nsB
sudo ip link set vethBbr master br0
sudo ip link set vethBbr up

echo "=== 5. Lien C <-> br0 ==="
sudo ip link add vethC type veth peer name vethCbr
sudo ip link set vethC netns nsC
sudo ip link set vethCbr master br0
sudo ip link set vethCbr up

echo "=== 6. Config IP dans nsA ==="
sudo ip netns exec nsA ip link set lo up
sudo ip netns exec nsA ip link set vethA up
sudo ip netns exec nsA ip addr add 10.0.1.1/24 dev vethA

echo "=== 7. Config IP dans nsB ==="
sudo ip netns exec nsB ip link set lo up
sudo ip netns exec nsB ip link set vethB up
sudo ip netns exec nsB ip addr add 10.0.1.2/24 dev vethB

echo "=== 8. Config IP dans nsC ==="
sudo ip netns exec nsC ip link set lo up
sudo ip netns exec nsC ip link set vethC up
sudo ip netns exec nsC ip addr add 10.0.1.3/24 dev vethC

echo "=== 9. Isolation A <-> C ==="
sudo ebtables -A FORWARD -i vethAbr -o vethCbr -j DROP
sudo ebtables -A FORWARD -i vethCbr -o vethAbr -j DROP

echo "=== 10. Vérification finale ==="
echo "--- Interfaces bridge/veth ---"
ip -br link | grep -E "br0|veth"
echo "--- nsA ---"
sudo ip netns exec nsA ip -br addr
echo "--- nsB ---"
sudo ip netns exec nsB ip -br addr
echo "--- nsC ---"
sudo ip netns exec nsC ip -br addr

echo "=== TERMINÉ SANS ERREUR ==="