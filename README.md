# Your Data - Your AI

Materials for the master class "Your Data - Your AI"

Content is grouped by the projects:

* Amazon Killer
* Vibe Analytics
* AI my API
* AI my Crypto


## Pre Requisites

* [Python 3](https://www.python.org/downloads/)
* [Claude Desktop](https://claude.com/download)
* [Docker](https://docs.docker.com/get-started/get-docker/)

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

### Step 2 Create code for MCP server

1. Open Claude Desktop, switch to Code tab and connect it to local ydya project

2. Enter the prompt 
```
I have a database created in data/schema.sql for e-commerce. 
Generate MCP server in Python that will allow AI chat to interactwith this database, 
provide recommendations on products and generate orders for them in interactive chat.
Add there methods for full text search of products by words.
```

3. make sure it created files requirements.txt and server.py

### Step 3 Connect LLM to MCP server

1. Open Claude Desktop, go to Settings > Extensions
   Press button Advanced Settings
   Press button Install Unpacked Extention

    Select folder of ydya project and install it.

    In case you got an error, check the logs.

    One of the problem can be that it should have a path to correct executable of python.

    To fix it, change "python3" to the correct path of python, for which you already install all required packages

2. Make sure it is started. Extentions now should show ecommerce-mcp extentions with a number of tools

    Press Configure to see the tools.

3. Go to Claude Desktop in Chat folder and try to buy goods, for example by chat:

```
I go to Mexico by plane want to buy some goods for this trip
```

4. Ask it to sell the selected goods for you, provide address and make an order.

5. Check MySQL log and  order creation

```
SELECT * FROM my_store.orders;
```


## Vibe Analytics

Create application to make analytics of user recommendations using our analytical database on Clickhouse.

### Step 1 Create analytical database on Clickhouse

1. Install clickhouse

```
docker pull clickhouse/clickhouse-server

docker run -d --name clickhouse-server -e CLICKHOUSE_DB=amazon -e CLICKHOUSE_USER=username -e CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1 -e CLICKHOUSE_PASSWORD=password -p 8123:8123 -p 9000:9000 clickhouse/clickhouse-server
```

2. Import product reviews

```
docker exec -it clickhouse-server clickhouse-client --user username --password password
```

copy / paste / execute files

* analytics/schema.sql
* analytics/import.sql


3. Install https://github.com/ClickHouse/mcp-clickhouse

```
python3 -m pip install mcp-clickhouse
```