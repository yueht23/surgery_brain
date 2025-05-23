-- 有没有都一样，如果没有zhihuishoshudanao，会直接报错，等不到执行到下面
-- CREATE DATABASE IF NOT EXISTS zhihuishoshudanao; 
ALTER DATABASE zhihuishoshudanao CHARACTER SET 'utf8mb4' COLLATE 'utf8mb4_general_ci';
USE zhihuishoshudanao;

-- DROP ALL TABLES IN ZHIHUISHOSHUDANAO
SET FOREIGN_KEY_CHECKS = 0;
SET GROUP_CONCAT_MAX_LEN=32768;
SET @tables = NULL;
SELECT GROUP_CONCAT('`', table_name, '`') INTO @tables
  FROM information_schema.tables
  WHERE table_schema = (SELECT DATABASE());
SELECT IFNULL(@tables,'dummy') INTO @tables;

SET @tables = CONCAT('DROP TABLE IF EXISTS ', @tables);
PREPARE stmt FROM @tables;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
SET FOREIGN_KEY_CHECKS = 1;