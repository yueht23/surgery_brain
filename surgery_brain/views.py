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
        # query_condition = json.loads(request.body)
        # case_date = query_condition['date']
        #
        # logger.info("sec schedule and  case_date: " + case_date)
        # do_import_surgery(date=case_date)
        #
        # logger.info("init schedule object")
        # my_schedule = schedule.Schedule(shedule_date=case_date)
        #
        # logger.info("pre sec schedule")
        # my_schedule.pre_sec_schedule()
        #
        # logger.info("do sec schedule")
        # result.append(my_schedule.do_sec_schedule())
        #
        # logger.info("sec schedule is done")
        return HttpResponse(json.dumps(result))
    return HttpResponse("请求错误")
