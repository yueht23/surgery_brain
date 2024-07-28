# -*- coding: utf-8 -*-
from django.http import HttpResponse
import json
from . import schedule2 as schedule
from .Codes.doImportSurgery import do_import_surgery
from .Codes.doRefreshSurgery import do_refresh_surgery

from common.logger import Logger


def get_first_schedule(request):
    logger = Logger(__name__).get_logger()
    if request.method == 'POST':
        result = []
        query_condition = json.loads(request.body)
        case_date = query_condition['date']

        logger.info("import the surgery and  case_date: " + case_date)
        do_import_surgery(date=case_date)
        do_refresh_surgery(fresh_date=case_date)
        logger.info("import the surgery is done")

        logger.info("first schedule and  case_date: " + case_date)
        my_schedule = schedule.Schedule(schedule_date=case_date)

        # logger.info("pre first schedule")
        # my_schedule.pre_first_schedule()
        #
        # logger.info("do first schedule")
        # result.append(my_schedule.do_first_schedule())

        my_schedule.run()


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
