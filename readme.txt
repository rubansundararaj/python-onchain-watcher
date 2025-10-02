sudo systemctl daemon-reload  
sudo systemctl start onchain-watcher
sudo systemctl status onchain-watcher

sudo systemctl stop onchain-watcher

# Additional logging and monitoring commands
sudo journalctl -u onchain-watcher -f                    # Follow logs in real-time
sudo journalctl -u onchain-watcher --since "1 hour ago" # Show logs from last hour
sudo journalctl -u onchain-watcher -n 100                # Show last 100 log lines
sudo systemctl is-active onchain-watcher                 # Check if service is running
sudo systemctl is-enabled onchain-watcher                # Check if service starts on boot


sudo systemctl stop onchain-watcher

sudo journalctl -u electrumd -n 100  