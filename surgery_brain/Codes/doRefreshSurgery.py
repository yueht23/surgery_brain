import sqlite3
import pymysql
import os

from c2matica_py_server.settings import MYSQL_HOST, MYSQL_USERNAME, MYSQL_PASSWORD, MYSQL_DATABASE


def do_refresh_surgery(fresh_date):
    sql = """
    update surgicalapplicationinfo_python
set whether_operating = '',
    has_arranged      = '',
    second_round_scheduling_weight = '',
    arrange_operating_room_number = '',
    arrange_operating_number = '',
    arrange_operating_room = ''
where pseudo_operation_data like '{}%'
                """.format(fresh_date)
    conn = pymysql.connect(host=MYSQL_HOST, user=MYSQL_USERNAME, password=MYSQL_PASSWORD, database=MYSQL_DATABASE, charset="utf8")
    cursor = conn.cursor()
    cursor.execute(sql)
    conn.commit()
    cursor.close()
    conn.close()

    #
    # connSurgery = sqlite3.connect(db_file)
    # connSurgery.execute("update 手术申请信息 set "
    #                     "是否有手术日 = '', "
    #                     "是否已安排 = '', "
    #                     "二轮排程权重 = '', "
    #                     "安排手术间编号 = '', "
    #                     "安排手术部 = '', "
    #                     "安排手术间 = '' "
    #                     "where 拟手术日期 = '%s'"
    #                     % (fresh_date))
    # connSurgery.commit()


if __name__ == '__main__':
    do_refresh_surgery(fresh_date='20220329', db_file='../Data/DataBase/Surgery.db')
