from django.db import connection


def get_sqlalchemy_engine(database='default'):
    """
    获取defualt数据库的sqlalchemy engine
    :param database:
    :return: a sqlalchemy engine
    """
    from django.conf import settings
    from sqlalchemy import create_engine

    # Extract the database settings
    db_settings = settings.DATABASES['default']

    # Map Django engine to SQLAlchemy dialect
    DIALECT_MAP = {
        'django.db.backends.mysql': 'mysql',
    }

    # Get the corresponding SQLAlchemy dialect
    dialect = DIALECT_MAP.get(db_settings['ENGINE'])

    if dialect is None:
        raise ValueError(f"Unsupported Django database engine: {db_settings['ENGINE']}")

    # Construct the SQLAlchemy connection string
    if dialect == 'sqlite':
        connection_string = f"{dialect}:///{db_settings['NAME']}"
    else:
        connection_string = (
            f"{dialect}://"
            f"{db_settings.get('USER', '')}:{db_settings.get('PASSWORD', '')}@"
            f"{db_settings.get('HOST', 'localhost')}:{db_settings.get('PORT', '')}/"
            f"{db_settings['NAME']}?charset=utf8mb4"
        )

    # Create the SQLAlchemy engine
    engine = create_engine(connection_string)

    return engine


def query_all_dict(sql, params=None):
    '''
    查询所有结果返回字典类型数据
    :param sql:
    :param params:
    :return:
    '''
    with connection.cursor() as cursor:
        if params:
            cursor.execute(sql, params=params)
        else:
            cursor.execute(sql)
        col_names = [desc[0] for desc in cursor.description]
        row = cursor.fetchall()
        rowList = []
        for list in row:
            tMap = dict(zip(col_names, list))
            rowList.append(tMap)
        return rowList


def execute_sql(sql, params=None):
    '''
    执行sql语句
    :param sql:
    :param params:
    :return:
    '''
    with connection.cursor() as cursor:
        if params:
            cursor.execute(sql, params=params)
        else:
            cursor.execute(sql)
        connection.commit()
        return cursor.rowcount