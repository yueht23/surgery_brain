# -*- coding: utf-8 -*-
from django.http import HttpResponse
import json
from .schedule2 import Schedule

from common.logger import Logger
import traceback
from django.conf import settings
from django.http import JsonResponse



def get_first_schedule(request):
    logger = Logger(__name__).get_logger()
    try:
        query_condition = json.loads(request.body)
        case_date = query_condition['date']
        logger.info("first schedule and  case_date: " + case_date)
        my_schedule = Schedule(schedule_date=case_date)
        my_schedule.schedule_first()
        logger.info("first schedule is done")
        return HttpResponse(json.dumps("手术日排程成功", ensure_ascii=False), status=200)
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(tb)
        return HttpResponse(json.dumps("手术日排程失败,原因如下：" + str(e), ensure_ascii=False), status=400)


def get_sec_schedule(request):
    logger = Logger(__name__).get_logger()
    try:
        query_condition = json.loads(request.body)
        case_date = query_condition['date']
        logger.info("sec schedule and  case_date: " + case_date)
        my_schedule = Schedule(schedule_date=case_date)


        if not "arranged_status" in query_condition:
            ARRANGE_STATUS = 2
        else:
            ARRANGE_STATUS = int(query_condition["arranged_status"])
        assert   ARRANGE_STATUS in [2,3], "抢单排程状态必须为2或3"
        my_schedule.schedule_sec(ARRANGED_STATUS=ARRANGE_STATUS)

        logger.info("sec schedule is done")
        return HttpResponse(json.dumps("抢单排程成功", ensure_ascii=False), status=200)
    except Exception as e:
        tb = traceback.format_exc()
        logger.error(tb)
        return HttpResponse(json.dumps("抢单排程失败,原因如下：" + str(e), ensure_ascii=False), status=400)


def reset_info_port(request):
    logger = Logger(__name__).get_logger()
    if request.method == 'POST':
        result = []
        query_condition = json.loads(request.body)
        case_date = query_condition['date']

        logger.info("reset info port and  case_date: " + case_date)

        my_schedule = Schedule(schedule_date=case_date)
        my_schedule.sio.reset_info_port()
        logger.info("reset info port is done")
        return HttpResponse(json.dumps(result))
    return HttpResponse("请求错误")


def sync_info_python_to_info(request):
    logger = Logger(__name__).get_logger()
    if request.method == 'POST':
        result = []
        query_condition = json.loads(request.body)
        case_date = query_condition['date']

        logger.info("sync info python to info and  case_date: " + case_date)

        my_schedule = Schedule(schedule_date=case_date)
        my_schedule.sio.sync_info_python_to_info(drop_ratio=0)
        logger.info("sync info python to info is done")
        return HttpResponse(json.dumps(result))
    return HttpResponse("请求错误")


def gantt_chart(request):
    logger = Logger(__name__).get_logger()
    if request.method == 'POST':
        result = []
        query_condition = json.loads(request.body)
        case_date = query_condition['date']

        logger.info("gantt chart and  case_date: " + case_date)

        my_schedule = Schedule(schedule_date=case_date)
        my_schedule.gantt_chart()
        logger.info("gantt chart is done")
        return HttpResponse(json.dumps(result))
    return HttpResponse("请求错误")


def hello_world(request):
    logger = Logger(__name__).get_logger()
    if request.method == 'POST':
        data = json.loads(request.body)
        logger.info("hello_world and  data: " + str(data))
        return HttpResponse(f"POST: hello world,{data}", status=200)
    elif request.method == 'GET':
        logger.info("hello_world and  GET")
        return HttpResponse("GET:hello world", status=200)

def get_db_settings(request):
    db_settings = {
        "DATABASES": settings.DATABASES
    }
    return JsonResponse(db_settings)