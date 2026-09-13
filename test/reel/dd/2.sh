sudo ip netns exec nsA ping -c 2 10.0.1.2    # A doit joindre B ✅
sudo ip netns exec nsA ping -c 2 10.0.2.3    # A NE doit PAS joindre C ❌
sudo ip netns exec nsC ping -c 2 10.0.1.1    # C NE doit PAS joindre A ❌
sudo ip netns exec nsB ping -c 2 10.0.1.1    # B joint A ✅
sudo ip netns exec nsB ping -c 2 10.0.2.3    # B joint C ✅