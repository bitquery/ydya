USE my_store;

-- Enable local infile if needed (run this in MySQL client first):
SET GLOBAL local_infile = 1;

-- Import categories
LOAD DATA LOCAL INFILE '/var/lib/import/amazon_categories.csv'
INTO TABLE categories
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(id, category_name);

-- Import products
LOAD DATA LOCAL INFILE '/var/lib/import/amazon_products.csv'
INTO TABLE products
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(asin, title, img_url, product_url, stars, reviews, price, list_price, @cat_id, is_best_seller, bought_in_last_month)
SET
    category_id = NULLIF(@cat_id, ''),
    description = NULL;  -- Set to NULL initially; populate later if needed