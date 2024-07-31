# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from common.logger import Logger
from surgery_brain.scheduleIO import ScheduleIO


class Schedule():
    def __init__(self, schedule_date):
        self.logger = Logger(__name__).get_logger()
        self.logger.info("Schedule initializing...")

        self.schedule_date = datetime.strptime(schedule_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        self.sio = ScheduleIO(self.schedule_date)

        """
        定义排程的一些参数
        """
        self.MAX_DOCTOR_WORKLOAD = 13.0  # 医生当日最大工作量
        self.MAX_ROOM_WORKLOAD = 12.0  # 手术室当日最大工作量
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

    def __check_doctor_overwork(self, doctor):
        """
        Get the doctor workload of the current day.
        :return:
        """

        if doctor not in self.doctor_workload:
            self.doctor_workload[doctor] = 0.0
        return self.doctor_workload[doctor] > self.MAX_DOCTOR_WORKLOAD

    def __get_room_workload(self, room_id):
        """
        Get the room workload of the current day.
        :return:
        """
        total_duration = 0.0
        for application in self.rooms[room_id]:
            total_duration += application['duration'] + self.TURNOVER_INTERVAL
        return total_duration

    def __check_room_overwork(self, room_id):
        """
        Get the room workload of the current day, noted the last application must end before 8:00 + 13:00 = 21:00
        :return:
        """
        return self.__get_room_workload(room_id) - self.TURNOVER_INTERVAL > self.MAX_ROOM_WORKLOAD

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
        # TODO: 一阶段排程还没有考虑HIV等感染性疾病的传播问题
        self.logger.warning("当前一阶段排程还没有考虑HIV等感染性疾病的传播问题")

        for application in waiting_list:
            self.logger.info("#" * 40)
            self.logger.info("#" * 40)
            self.logger.info("#" * 40)

            self.logger.info("当前申请{}".format(application))

            if self.__check_doctor_overwork(application['surgeon_code']):
                self.logger.info("医生{}已经超过工作量".format(application['surgeon_code']))
                self.logger.info("跳过当前申请")
                continue

            room_id, init_weight = self.sio.get_room_id_and_weight(application['apply_dept'],
                                                                   application['seq_alphabet'])
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
            self.doctor_workload[application['surgeon_code']] += application['duration']
            self.logger.info("当前医生{}的工作量为{}".format(application['surgeon_code'],
                                                             self.doctor_workload[application['surgeon_code']]))

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
                self.doctor_workload[dropped_application['surgeon_code']] -= dropped_application['duration']
                self.logger.info("当前医生{}的工作量为{}".format(dropped_application['surgeon_code'],
                                                                 self.doctor_workload[
                                                                     dropped_application['surgeon_code']]))

        self.logger.info("排好结果汇总")
        res = []
        for room_id, applications in self.rooms.items():
            # 每个手术室从8:00开始,转换为datetime.time
            clock = datetime.strptime(self.schedule_date + " 08:00:00", "%Y-%m-%d %H:%M:%S")

            for idx, application in enumerate(applications):
                res.append({
                    "id": application["id"],
                    "is_arranged": 1,
                    "arranged_room_id": room_id,  # e.g. 2586
                    "arranged_start_time": clock,
                    "arranged_end_time": clock + timedelta(hours=application["duration"])
                })
                clock += timedelta(hours=(application["duration"] + self.TURNOVER_INTERVAL))
        self.logger.info(f"排好结果汇总完成，申请数为{len(waiting_list)}，一阶段完成数为{len(res)}")

        self.logger.info("回写数据库")
        self.sio.write_result_to_db(res)
        self.logger.info("数据库回写成功")
        self.logger.info("Schedule first finished")

    def schedule_sec(self):
        """
        二期的手术日抢单排程
        :return: None
        """
        arranged_applications = self.sio.get_arranged_applications()
        unarranged_applications = self.sio.get_unarranged_applications()
        self.logger.info("已排程的申请长度为{}".format(len(arranged_applications)))
        self.logger.info("未排程的申请长度为{}".format(len(unarranged_applications)))

        # TODO: 二期的手术日抢单排程尚未实现
        raise NotImplementedError("二期的手术日抢单排程尚未实现")

        res = []  # 二阶拍好的结果

        # self.logger.info("排好结果汇总")
        for application in res:
            assert isinstance(application, dict), "二阶段排程结果中有非字典类型的申请"
            assert application["id"] in [x["id"] for x in unarranged_applications], "二阶段排程结果中有未排程的申请"
            assert application["id"] not in [x["id"] for x in arranged_applications], "二阶段排程结果中有已排程的申请"
            assert application["is_arranged"] == 1, "二阶段排程结果中有未排程的申请"
            assert application["arranged_start_time"] < application["arranged_end_time"], "二阶段排程结果中有时间错误的申请"
            assert application["arranged_start_time"].hour >= 8, "二阶段排程结果中有时间错误的申请"
            assert application["arranged_room_id"] is not None, "二阶段排程结果中有未分配手术室的申请"
            # TODO: 其余的检查

        # self.logger.info("回写数据库")
        # self.sio.write_result_to_db(res)

    def gantt_chart(self):
        """
        利用甘特图，可视化已经排好的手术日
        :return:
        """
        try:
            import plotly.express as px
            import pandas as pd

            self.logger.info("开始绘制甘特图...")
            self.logger.info("获取已排程的申请...")
            arranged_applications = self.sio.get_arranged_applications()
            self.logger.info("已排程的申请获取成功")
            self.logger.info("已排程的申请长度为{}".format(len(arranged_applications)))

            df = pd.DataFrame(arranged_applications)
            df['arranged_start_time'] = df['arranged_start_time'].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S"))
            df['arranged_end_time'] = df['arranged_end_time'].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S"))

            df["room"] = df["arranged_room_dept"] + df["arranged_room_name"] + "(" + df["arranged_room_id"] + ")"
            df = df.sort_values(by="room")

            fig = px.timeline(df,
                              x_start="arranged_start_time",
                              x_end="arranged_end_time",
                              y="room",
                              title="手术日排程甘特图",
                              hover_data=["id", "apply_dept", "patient_name", "surgeon_name", "duration", "t_seq"],
                              )
            fig.show()
            self.logger.info("甘特图绘制成功")

        except Exception as e:
            self.logger.error("oops!绘制甘特图失败：" + str(e))
