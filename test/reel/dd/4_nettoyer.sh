sudo ip netns exec nsA ping -c 2 10.0.1.2   # A → B : OK ✅
sudo ip netns exec nsA ping -c 2 10.0.1.3   # A → C : PAS OK ❌ (voulu)
sudo ip netns exec nsC ping -c 2 10.0.1.2   # C → B : OK ✅
sudo ip netns exec nsC ping -c 2 10.0.1.1   # C → A : PAS OK ❌ (voulu)
sudo ip netns exec nsB ping -c 2 10.0.1.1   # B → A : OK ✅
sudo ip netns exec nsB ping -c 2 10.0.1.3   # B → C : OK ✅