# -*- coding: utf-8 -*-
import datetime
from common.logger import Logger
from surgery_brain.scheduleIO import ScheduleIO


class Schedule():
    def __init__(self, schedule_date):
        self.logger = Logger(__name__).get_logger()
        self.logger.info("Schedule initializing...")

        self.schedule_date = datetime.datetime.strptime(schedule_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        self.sio = ScheduleIO(self.schedule_date)

        """
        定义排程的一些参数
        """
        self.MAX_DOCTOR_WORKLOAD = 13.0  # 医生当日最大工作量
        self.MAX_ROOM_WORKLOAD = 13.0  # 手术室当日最大工作量
        self.TURNOVER_INTERVAL = 0.5  # 手术室换台间隔
        self.BEGIN_TIME = 8.0  # 手术室开始工作时间

        """
        定义一轮手术日确定性排程的所需数据结构
        """
        self.doctor_workload = {}
        self.rooms = {}

        """
        定义二轮抢单排程的所需数据结构
        """
        # TODO:

        self.logger.info("Schedule initialized")

    def __check_doctor_overwork(self, doctor, max_workload=13.0):
        """
        Get the doctor workload of the current day.
        :return:
        """

        if doctor not in self.doctor_workload:
            self.doctor_workload[doctor] = 0.0
        return self.doctor_workload[doctor] > max_workload

    def __get_room_workload(self, room_id, interval=0.5):
        """
        Get the room workload of the current day.
        :return:
        """
        total_duration = 0.0
        for application in self.rooms[room_id]:
            total_duration += application['duration'] + interval
        return total_duration

    def __check_room_overwork(self, room_id, max_workload=13.0, interval=0.5):
        """
        Get the room workload of the current day, noted the last application must end before 8:00 + 13:00 = 21:00
        :return:
        """
        return self.__get_room_workload(room_id, interval) - interval > max_workload

    def schedule_first(self):
        """
        一期的手术日确定性排程
        :return: None
        """

        self.logger.info("开始确定性排程...")
        self.logger.info("获取waiting list...")
        waiting_list = self.sio.get_unarranged_applications()
        self.logger.info("waiting list获取成功")
        self.logger.info("waiting list长度为{}".format(len(waiting_list)))

        for application in waiting_list:
            self.logger.info("#" * 40)
            self.logger.info("#" * 40)
            self.logger.info("#" * 40)

            self.logger.info("当前申请{}".format(application))

            if self.__check_doctor_overwork(application['doctor']):
                self.logger.info("医生{}已经超过工作量".format(application['doctor']))
                self.logger.info("跳过当前申请")
                continue

            room_id, init_weight = self.sio.get_room_id_and_weight(application['dept'], application['seq_alphabet'])
            if not room_id:
                self.logger.info("当前申请没有对应的手术室")
                self.logger.info("跳过当前申请")
                continue

            weight = init_weight + 100 * (ord(application['seq_alphabet']) - ord('A')) + application['seq_number']

            operating_department, real_name = self.sio.get_room_info_from_id(room_id)  # 手术部, 真实名称

            self.logger.info("当前申请对应的手术室为{}({},{})".format(room_id, operating_department, real_name))
            self.logger.info("当前申请的权重为{}".format(weight))
            application["weight"] = weight

            self.logger.info("加入到手术室中")
            if room_id not in self.rooms:
                self.rooms[room_id] = []
            self.rooms[room_id].append(application)

            self.logger.info("更新医生工作量")
            self.doctor_workload[application['doctor']] += application['duration']
            self.logger.info("当前医生{}的工作量为{}".format(application['doctor'],
                                                             self.doctor_workload[application['doctor']]))

            self.logger.info("基于权重排序")
            self.rooms[room_id].sort(key=lambda x: x['weight'])

            self.logger.info("当前手术室的申请列表长度为{}".format(len(self.rooms[room_id])))
            self.logger.info("当前手术室的占用时长为{}".format(self.__get_room_workload(room_id)))

            while self.__check_room_overwork(room_id):
                self.logger.info("手术室{}已经超过工作量".format(room_id))
                self.logger.info("删除最后一个申请")
                dropped_application = self.rooms[room_id].pop()
                self.logger.info("删除的申请为{}".format(dropped_application))
                self.logger.info("更新医生工作量")
                self.doctor_workload[dropped_application['doctor']] -= dropped_application['duration']
                self.logger.info("当前医生{}的工作量为{}".format(dropped_application['doctor'],
                                                                 self.doctor_workload[dropped_application['doctor']]))

        self.logger.info("排好结果汇总")
        res = []
        for room_id, applications in self.rooms.items():
            operating_department, real_name = self.sio.get_room_info_from_id(room_id)
            clock = self.BEGIN_TIME
            for idx, application in enumerate(applications):
                res.append({
                    "id": application["id"],
                    "arranged": "是",
                    "arranged_room_id": room_id,  # e.g. 2586
                    "arranged_room_dept": operating_department,  # e.g. 第一手术部
                    "arranged_room_name": real_name,  # e.g. 01
                    "arranged_start_time": clock,
                    "arranged_end_time": clock + application["duration"],
                })
                clock += application["duration"] + self.TURNOVER_INTERVAL
        self.logger.info(f"排好结果汇总完成，申请数为{len(waiting_list)}，一阶段完成数为{len(res)}")

        self.logger.info("回写数据库")
        self.sio.write_result_to_db(res)
        self.logger.info("数据库回写成功")
        self.logger.info("Schedule runned")
