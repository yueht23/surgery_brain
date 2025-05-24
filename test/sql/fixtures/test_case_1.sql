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



-- 如下的表结构只有后序抢单用得到，一阶段手术日排程不用
-- administrative_office
CREATE TABLE administrative_office LIKE zhihuishoshudanao_0417.administrative_office;
INSERT INTO administrative_office SELECT * FROM zhihuishoshudanao_0417.administrative_office;


-- interoperative_constraint
CREATE TABLE interoperative_constraint LIKE zhihuishoshudanao_0417.interoperative_constraint;
INSERT INTO interoperative_constraint SELECT * FROM zhihuishoshudanao_0417.interoperative_constraint;


-- special_surgical_info
CREATE TABLE special_surgical_info LIKE zhihuishoshudanao_0417.special_surgical_info;
INSERT INTO special_surgical_info SELECT * FROM zhihuishoshudanao_0417.special_surgical_info;


-- special_surgical_restraint
CREATE TABLE special_surgical_restraint LIKE zhihuishoshudanao_0417.special_surgical_restraint;
INSERT INTO special_surgical_restraint SELECT * FROM zhihuishoshudanao_0417.special_surgical_restraint;

