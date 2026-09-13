# Terminal 1
sudo ip netns exec nsA python3 etape1.py 55555
# entre "Alice" comme nom

# Terminal 2
sudo ip netns exec nsB python3 etape1.py 55556
# entre "Bob" comme nom

# Terminal 3
sudo ip netns exec nsC python3 etape1.py 55557
# entre "Charlie" comme nom