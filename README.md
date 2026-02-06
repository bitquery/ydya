# Your Data - Your AI

Materials for the master class "Your Data - Your AI"

Content is grouped by the projects:

* Amazon Killer
* Analytics on LLM
* AI my API
* AI my Crypto


## Pre Requisites

* [Python 3](https://www.python.org/downloads/)
* [Claude Desktop](https://claude.com/download)
* [Docker](https://docs.docker.com/get-started/get-docker/)
* 
## Amazon Killer

Goal is to create e-shop where you can select and buy products using LLM chat

### Step 1 Setting up Database

Checkout the project locally: 

```
git clone https://github.com/bitquery/ydya.git
```

1. Run MySQL server under docker
```
 docker run -d \
  --name mysql-amazon \
  -e MYSQL_ROOT_PASSWORD='mysql' \
  -e MYSQL_DATABASE='my_store' \
  -e MYSQL_USER='user' \
  -e MYSQL_PASSWORD='pwd' \
  -p 3306:3306 \
  -v /tmp/mysql:/var/lib/mysql \
  -v /tmp/import:/var/lib/import \
  -v /tmp/mysql-logs:/var/log/mysql \
  --health-cmd='mysqladmin ping -h localhost' \
  --health-interval=10s \
  mysql:8.0-oracle \
  --local-infile=1 \
  --general_log=1 \
  --general_log_file=/var/log/mysql/queries.log \
  --log_output=FILE
```

Make sure it is started

```
docker ps
CONTAINER ID   IMAGE              COMMAND                  CREATED         STATUS                   PORTS                               NAMES
a8ffcfa8f2c6   mysql:8.0-oracle   "docker-entrypoint.s…"   3 minutes ago   Up 3 minutes (healthy)   0.0.0.0:3306->3306/tcp, 33060/tcp   mysql-amazon
```

2. Download and unzip full dataset of products  from https://www.kaggle.com/datasets/asaniczka/amazon-products-dataset-2023-1-4m-products

```
curl -L -o data/amazon-products-dataset-2023-1-4m-products.zip\
  https://www.kaggle.com/api/v1/datasets/download/asaniczka/amazon-products-dataset-2023-1-4m-products

unzip data/amazon-products-dataset-2023-1-4m-products.zip -d /tmp/import
```

3. Import schema, data into MySQL

go to client of MySQL:

```
docker exec -it mysql-amazon mysql --user user --local-infile=1 -p    
Enter password: pwd
```

copy/paste/execute files from data dir:

1. schema.sql
2. import.sql ( can take some time to execute )
3. create_account.sql ( you can replace name and email with your own )

Now you can open file to see queries in other window

```
tail -f  /tmp/mysql-logs/queries.log
```

and execute queries in client:

```
SELECT * FROM my_store.products LIMIT 10;
```