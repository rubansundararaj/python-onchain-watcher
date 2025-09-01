
#Step 1: Get UTXOs from an Address
curl -u ruban:InsaneElonTrump --data-binary '{"jsonrpc": "2.0", "id": 1, "method": "getaddressunspent", "params": ["bc1qqysw3y94w3mq8huqxq4ggtzm8w4v5h0w8ypdet"]}' http://127.0.0.1:7777
{"id": 1, "jsonrpc": "2.0", "result": [{"height": 912229, "tx_hash": "bee52c6957e3276702ad2a9290b26fd5844821b216156d9c1608a82cb0c7ad0e", "tx_pos": 1, "value": 5000}]}

curl -u ruban:InsaneElonTrump --data-binary '{"jsonrpc": "2.0", "id": 1, "method": "blockchain.scripthash.listunspent", "params": ["scripthash_here"]}' http://127.0.0.1:7777

curl -u ruban:InsaneElonTrump --data-binary '{"jsonrpc": "2.0", "id": 1, "method": "getpubkeys", "params": ["bc1qqysw3y94w3mq8huqxq4ggtzm8w4v5h0w8ypdet"]}' http://127.0.0.1:7777
{"id": 1, "jsonrpc": "2.0", "result": ["032b064a42f57925e0938e54d14abd4558c4a1ad8ab541f5a1ed78782c6b99a107"]}




curl -u ruban:InsaneElonTrump --data-binary '{"jsonrpc": "2.0", "id": 1, "method": "serialize", "params": [{"inputs": [{"prevout_hash": "bee52c6957e3276702ad2a9290b26fd5844821b216156d9c1608a82cb0c7ad0e", "prevout_n": 1, "redeemPubkey": "032b064a42f57925e0938e54d14abd4558c4a1ad8ab541f5a1ed78782c6b99a107", "value_sats": 5000}], "outputs": [["bc1qaysw3y9w4w3m9q8huaxq4qggtzm8w4v5h0w8ypdet", 0.00003], ["bc1qgapvnn6vpyr37adaekxphyhrquqn386nzf2r6z", 0.000015]]}]}' http://127.0.0.1:7777




curl -u ruban:InsaneElonTrump --data-binary '{"jsonrpc": "2.0", "id": 1, "method": "serialize", "params": [{"inputs": [{"prevout_hash": "bee52c6957e3276702ad2a9290b26fd5844821b216156d9c1608a82cb0c7ad0e", "prevout_n": 1, "redeemPubkey": "032b064a42f57925e0938e54d14abd4558c4a1ad8ab541f5a1ed78782c6b99a107", "value_sats": 5000}], "outputs": [["bc1qaysw3y9w4w3m9q8huaxq4qggtzm8w4v5h0w8ypdet", 0.00003], ["bc1qgapvnn6vpyr37adaekxphyhrquqn386nzfr6z", 0.000015]]}]}' http://127.0.0.1:7777