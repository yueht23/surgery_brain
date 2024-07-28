from django.db import connection as django_connection


def do_refresh_surgery(fresh_date):
    sql = """
    update 
        surgicalapplicationinfo_python
    set whether_operating = '',
        has_arranged      = '',
        second_round_scheduling_weight = '',
        arrange_operating_room_number = '',
        arrange_operating_number = '',
        arrange_operating_room = ''
    where pseudo_operation_data like '{}%'
                    """.format(fresh_date)
    conn = django_connection
    cursor = conn.cursor()
    cursor.execute(sql)
    conn.commit()
    cursor.close()
    conn.close()
