
docker build -t rubansundararaj/go-onchain --no-cache .
docker push rubansundararaj/go-onchain

docker stop go-onchain
docker rm go-onchain
docker container prune -f 
docker image prune -a -f
docker pull rubansundararaj/go-onchain
docker run -d -p 8383:8383 --name go-onchain --restart unless-stopped rubansundararaj/go-onchain
docker ps


