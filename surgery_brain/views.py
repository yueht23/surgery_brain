# -*- coding: utf-8 -*-
from django.http import HttpResponse
import json
from .schedule2 import Schedule

from common.logger import Logger


def get_first_schedule(request):
    logger = Logger(__name__).get_logger()
    if request.method == 'POST':
        result = []
        query_condition = json.loads(request.body)
        case_date = query_condition['date']

        logger.info("first schedule and  case_date: " + case_date)
        my_schedule = Schedule(schedule_date=case_date)

        my_schedule.schedule_first()

        logger.info("first schedule is done")
        return HttpResponse(json.dumps(result))
    return HttpResponse("请求错误")


def get_sec_schedule(request):
    logger = Logger(__name__).get_logger()
    if request.method == 'POST':
        result = []
        query_condition = json.loads(request.body)
        case_date = query_condition['date']

        logger.info("sec schedule and  case_date: " + case_date)

        logger.info("init schedule object")
        my_schedule = Schedule(schedule_date=case_date)

        my_schedule.schedule_sec()
        logger.info("sec schedule is done")
        return HttpResponse(json.dumps(result))
    return HttpResponse("请求错误")


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
