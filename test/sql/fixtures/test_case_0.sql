-- 该测试用例用于测试数据库连接
-- 主要测试 execute_sql_file 函数

CREATE TABLE IF NOT EXISTS test_table (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(50),
    value INT
);


INSERT INTO test_table (name, value) VALUES ('测试1', 100);
INSERT INTO test_table (name, value) VALUES ('测试2', 200);
INSERT INTO test_table (name, value) VALUES ('测试3', 300);





