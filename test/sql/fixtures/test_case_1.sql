-- DROP DATABASE IF EXISTS zhihuishoshudanao_0327_0417_simple;
-- CREATE DATABASE zhihuishoshudanao_0327_0417_simple;
-- USE zhihuishoshudanao_0327_0417_simple;




USE zhihuishoshudanao;
CREATE TABLE surgicalapplication_info_port LIKE zhihuishoshudanao_0417.surgicalapplication_info_port;
INSERT INTO surgicalapplication_info_port (SELECT * FROM zhihuishoshudanao_0417.surgicalapplication_info_port WHERE SURGERY_DATE > '2025-03-27');
UPDATE surgicalapplication_info_port t SET t.scheduling_state = 0 WHERE 1;


CREATE TABLE surgicalapplicationinfo_python LIKE zhihuishoshudanao_0417.surgicalapplicationinfo_python;
CREATE TABLE surgicalapplicationinfo LIKE zhihuishoshudanao_0417.surgicalapplicationinfo;

CREATE TABLE surgery_schedule LIKE zhihuishoshudanao_0417.surgery_schedule;
INSERT INTO surgery_schedule SELECT * FROM zhihuishoshudanao_0417.surgery_schedule;


CREATE TABLE operating_room_info LIKE zhihuishoshudanao_0417.operating_room_info;
INSERT INTO operating_room_info SELECT * FROM zhihuishoshudanao_0417.operating_room_info;

-- operation_room_whitelist
CREATE TABLE operation_room_whitelist LIKE zhihuishoshudanao_0417.operation_room_whitelist;
INSERT INTO operation_room_whitelist SELECT * FROM zhihuishoshudanao_0417.operation_room_whitelist;

-- department_whitelist
CREATE TABLE department_whitelist LIKE zhihuishoshudanao_0417.department_whitelist;
INSERT INTO department_whitelist SELECT * FROM zhihuishoshudanao_0417.department_whitelist;



-- doctor_info
CREATE TABLE doctor_info LIKE zhihuishoshudanao_0417.doctor_info;
INSERT INTO doctor_info SELECT * FROM zhihuishoshudanao_0417.doctor_info;



-- mapping_date
CREATE TABLE mapping_date LIKE zhihuishoshudanao_0417.mapping_date;
INSERT INTO mapping_date SELECT * FROM zhihuishoshudanao_0417.mapping_date;
