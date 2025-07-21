# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from common.logger import Logger
from surgery_brain.scheduleIO import ScheduleIO
import pandas as pd
from typing import Tuple,List,Dict
from collections import defaultdict

class Cluster:
    """
    二阶段排程的过程中的一些手术的集合，同一个集合的手术的有相同的（申请科室+台序字母）
    例如，泌尿外科-A就是一个Cluster
    """
    def __init__(self, sio:ScheduleIO,applications:List[Dict]) -> None:
        self.applications:List[Dict] = applications
        self.cluster_name:Tuple[str,str] = self.__init_cluster_name()
        self.weight2:float = self.__init_weight2()
        self.sio = sio

    def __init_cluster_name(self)->Tuple[str,str]:
        """
        获取当前手术簇的名称
        """
        assert len(self.applications) > 0, "手术簇不能为空"
        apply_dept = self.applications[0]['apply_dept']
        seq_alphabet = self.applications[0]['seq_alphabet']
        for app in self.applications:
            if app['apply_dept'] != apply_dept or app['seq_alphabet'] != seq_alphabet:
                raise ValueError(f"手术簇中的手术{app['id']}的申请科室或台序字母与第一个手术不同")
        return (apply_dept,seq_alphabet)

    def __init_weight2(self)->float:
        """
        获取当前手术簇的权重
        """
        weight2 = 0.0
        for app in self.applications:
            weight2 += app['weight2']
        return weight2

    def __lt__(self,other:'Cluster')->bool:
        return self.weight2 < other.weight2
    
    def __repr__(self) -> str:
        return f"手术簇：{self.cluster_name[0]}-{self.cluster_name[1]}，手术数：{len(self)}，权重：{self.weight2}"

    def __len__(self)->int:
        return len(self.applications)

    def get_available_room_ids(self)->List[int]:
        """
        获取当前手术簇的可行手术室
        """
        return [int(_) for _ in self.sio.get_available_rooms(self.applications[0])]

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
        self.rooms = {}  # 术间id -> applications的映射，抢单也用这个结构


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
        获取当前天房间工作量的功能，注意：换台间隔被考虑进入
        :return:
        """
        total_duration = 0.0
        for application in self.rooms[room_id]:
            total_duration += application['duration'] + self.TURNOVER_INTERVAL
        return total_duration

    def __check_room_overwork(self, room_id):
        """
        最后一台手术在MAX_ROOM_WORKLOAD（e.g. 12 hour, i.e. 8+12=20点）之前开台就不超时
        :return:
        """
        # 没有一台手术，直接返回False
        if len(self.rooms[room_id]) == 0:
            return False
        else:
            last_app_dur = self.rooms[room_id][-1]['duration']
            last_app_start_time = self.__get_room_workload(room_id) - self.TURNOVER_INTERVAL - last_app_dur
            return last_app_start_time >= self.MAX_ROOM_WORKLOAD
    
    def __generate_stage2_weights(self, unarranged_applications, total_applications):
        """
        生成二阶段排程的权重，包括日间手术和择期手术的百分比权重，并计算每个申请的总权重。
        :param unarranged_applications: 未排程的手术申请列表
        :param total_applications: 所有手术申请列表（已排程+未排程）
        :return: None，直接修改传入的application对象
        """
        # 用inpatient_serial序列号来表示手术申请的先后顺序
        # inpatient_serial越大，手术申请越靠后，其权重越小
        df_day_surgery = pd.DataFrame([app for app in unarranged_applications if app['is_day_surgery'] == 1])
        df_elective_surgery = pd.DataFrame([app for app in unarranged_applications if not app['is_day_surgery'] == 1])
        if not df_day_surgery.empty:
            df_day_surgery["day_percentage"] = df_day_surgery['inpatient_serial'].rank(method='average', ascending=False)
            df_day_surgery["day_percentage"] = df_day_surgery["day_percentage"] / len(df_day_surgery)
        if not df_elective_surgery.empty:
            df_elective_surgery["elective_percentage"] = df_elective_surgery['inpatient_serial'].rank(method='average', ascending=False)
            df_elective_surgery["elective_percentage"] = df_elective_surgery["elective_percentage"] / len(df_elective_surgery)
        # 只有对于已经排程的手术，才需要考虑day_percentage和elective_percentage两项权重
        for app in unarranged_applications:
            if app['is_day_surgery'] == 1:
                app["day_percentage"] = df_day_surgery[df_day_surgery["id"] == app["id"]]["day_percentage"].values[0]
            else:
                app["elective_percentage"] = df_elective_surgery[df_elective_surgery["id"] == app["id"]]["elective_percentage"].values[0]

        self.logger.info("二阶段权重构造")
        for application in total_applications:
            self.logger.info("")
            self.logger.info("当前待排申请{}".format(application))

            # 用于记录各项权重的构成
            # key:子项权重->val:该子项权重的权重
            weight2 = dict()

            # 特殊手术
            weight2["is_sp_robot"] = 10 if application["is_sp_robot"] else 0
            weight2["is_sp_intervention"] = 10 if application["is_sp_intervention"] else 0
            weight2["is_sp_perspective"] = 10 if application["is_sp_perspective"] else 0
            weight2["is_sp_holmium"] = 10 if application["is_sp_holmium"] else 0

            # 抢单失败次数
            weight2["attempt_times"] = 2 * application["attempt_times"]

            # 日间手术
            if application["is_day_surgery"]:
                weight2["is_day_surgery"] = 3
                weight2["day_percentage"] = application.get("day_percentage", 0)
            # 择期手术
            else:
                weight2["elective_percentage"] = application.get("elective_percentage", 0)

            # 国考四级手术
            weight2["surgery_level"] = 3 if application["surgery_level"] == "4" else 0

            # 手术优先操作
            weight2["is_operation"] = 3 if not application["is_operation"] else 0

            # 微创优先非微创
            weight2["is_mini_invasive"] = 3 if application["is_mini_invasive"] else 0

            application["weight2"] = sum(weight2.values())
            self.logger.info("当前申请的总权重为{}".format(application["weight2"]))
            self.logger.info("当前申请的权重的构成为{}".format(weight2))

    def schedule_first(self):
        """
        一期的手术日确定性排程
        :return: None
        """

        self.logger.info("开始确定性排程...")
        self.sio.import_surgeries()
        self.logger.info("获取waiting list...")
        waiting_list = self.sio.get_unarranged_applications()
        assert self.sio.get_arranged_applications() == [], "一阶段排程前数据库中已有排程"
        self.logger.info("waiting list获取成功")
        self.logger.info("waiting list长度为{}".format(len(waiting_list)))
        self.logger.warning("当前一阶段排程还没有考虑HIV等感染性疾病的传播问题")

        for application in waiting_list:
            self.logger.info("")
            self.logger.info("当前申请{}".format(application))

            if application['is_infected']:
                self.logger.info("当前申请为感染性疾病，不参与一轮排程")
                self.sio.update_unscheduled_reason(application['id'], "该手术为感染性疾病，无法一轮排程")
                continue

            if self.__check_doctor_overwork(application['surgeon_code']):
                self.logger.info("医生{}已经超过工作量,跳过当前申请".format(application['surgeon_code']))
                self.sio.update_unscheduled_reason(application['id'], "该手术术者工作量已经超上限，无法一轮排程")
                continue

            room_id, init_weight = self.sio.get_room_id_and_weight(application['apply_dept'],
                                                                   application['seq_alphabet'])
            if not room_id:
                self.logger.info("当前申请没有对应的手术室,跳过当前申请")
                self.sio.update_unscheduled_reason(application['id'], f"{application['apply_dept']}" +
                                                   f"{application['seq_alphabet']}" +
                                                   f"在{self.schedule_date}没有对应的手术日,无法一轮排程")
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
                self.sio.update_unscheduled_reason(dropped_application['id'],
                                                   f"{application['apply_dept']}{application['seq_alphabet']}" +
                                                   f"在{self.schedule_date}对应的手术间" +
                                                   f"{self.sio.get_room_info_from_id(room_id)[0]}" +
                                                   f"{self.sio.get_room_info_from_id(room_id)[1]}" +
                                                   "已满,且该手术权重较小，无法一轮排程")
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
                    "arranged_status": 1,
                    "arranged_room_id": room_id,  # e.g. 2586
                    "arranged_start_time": clock,
                    "arranged_end_time": clock + timedelta(hours=application["duration"])
                })
                clock += timedelta(hours=(application["duration"] + self.TURNOVER_INTERVAL))
        self.logger.info(f"排好结果汇总完成，申请数为{len(waiting_list)}，一阶段完成数为{len(res)}")

        self.sio.write_result_to_db(res)
        self.sio.validation_check()



    def schedule_sec(self, ARRANGED_STATUS=2):
        """
        抢单排程
        :param ARRANGED_STATUS: 抢单排程状态，2表示第一次抢单排程，3表示第二次抢单排程
        :return: None
        """
        assert ARRANGED_STATUS in [2, 3], "抢单排程状态必须为2(第一次抢单排程)或3(第二次抢单排程)"

        current_date = datetime.now().date()
        schedule_date = datetime.strptime(self.schedule_date, "%Y-%m-%d").date()
        days_diff = (schedule_date - current_date).days
        self.sio.logger.info(f"所排的手术日期为{self.schedule_date}，当前为{current_date}，相差{days_diff}天,ARRANGED_STATUS={ARRANGED_STATUS}")


        self.sio.import_surgeries()
        arranged_applications = self.sio.get_arranged_applications()

        assert max([_["arranged_status"] for _ in arranged_applications]) < ARRANGED_STATUS, "抢单排程状态必须大于已排程的手术状态"

        unarranged_applications = []
        if ARRANGED_STATUS == 2:
            unarranged_applications = self.sio.get_unarranged_applications()
        elif ARRANGED_STATUS == 3:
            for app in self.sio.get_unarranged_applications():
                if app["is_admitted"] == 1 or app["is_day_surgery"] == 1:
                    unarranged_applications.append(app)



        total_applications = arranged_applications + unarranged_applications
        self.logger.info("已排程的申请长度为{}".format(len(arranged_applications)))
        self.logger.info("未排程的申请长度为{}".format(len(unarranged_applications)))
        self.logger.info("总的申请长度为{}".format(len(total_applications)))
        self.__generate_stage2_weights(unarranged_applications, total_applications)


        # 初始化self.rooms
        for room_id, _ in self.sio.get_total_room_info().items():
            self.rooms[room_id] = []
        
        # 将arranged_applications中的手术加入到self.rooms中
        for app in arranged_applications:
            if int(app['arranged_room_id']) not in self.rooms:
                raise ValueError(f"手术{app['id']}的手术室{app['arranged_room_id']}不在白名单中")
            self.rooms[int(app['arranged_room_id'])].append(app)

        for room_id, applications in self.rooms.items():
            room_info = self.sio.get_room_info_from_id(room_id)
            self.logger.info(f"手术室{room_info}的手术数为{len(applications)}总时长为{self.__get_room_workload(room_id)}")
        
        # 区分特殊手术和非特殊手术
        spec_unarranged_applications = []
        non_spec_unarranged_applications = []
        for app in unarranged_applications:
            if app['is_sp_robot'] or app['is_sp_intervention'] or app['is_sp_perspective'] or app['is_sp_holmium'] or app['is_infected_air']:
                spec_unarranged_applications.append(app)
            else:
                non_spec_unarranged_applications.append(app)
        """
        安排特殊手术，找到其可行手术室，定义使用时长最小的手术室为最优手术室
        如果最优手术室已经超过工作量，则跳过当前手术
        如果最优手术室没有超过工作量，则将当前手术安排到最优手术室
        """
        self.logger.info("开始安排特殊手术")
        for app in spec_unarranged_applications:
            available_room_ids = [int(_) for _ in self.sio.get_available_rooms(app)]
            if len(available_room_ids) == 0:
                self.logger.warning(f"特殊手术{app['id']}没有可用的手术室")
                continue
            best_room_id = min(available_room_ids, key=lambda x: self.__get_room_workload(x))
            # 尝试将当前手术加入到最优手术室
            self.rooms[best_room_id].append(app)
            if self.__check_room_overwork(best_room_id):
                # 手术室已经超过工作量，弹出当前手术
                self.rooms[best_room_id].pop()
                self.logger.warning(f"特殊手术{app['id']}最为合适的手术室{best_room_id}已经超过工作量，跳过当前手术")
                self.sio.update_unscheduled_reason(app['id'], f"特殊手术{app['id']}最为合适的手术室{best_room_id}已经超过工作量，跳过当前手术",append=True)
                continue
            # 安排成功
            app['arranged_status'] = ARRANGED_STATUS
            app['arranged_room_id'] = best_room_id
            self.logger.info(f"特殊手术{app['id']}安排到手术室{best_room_id}，手术室{best_room_id}的手术数为{len(self.rooms[best_room_id])}")
        self.logger.info("特殊手术安排完成")
        """
        安排非特殊手术，找到其可行手术室
        首先将非特殊手术按照申请科室和台序字母进行分组，每个组为一个手术簇
        每个簇的权重为：所有手术的权重之和
        将这些cluster放到sorted_clusters中，按照标准是：
        - 骨科优先
        - 权重越大越优先

        每次从sorted_clusters中取出一个cluster，尝试将其安排到手术室
        如果cluster中所有手术的可行手术室都超过工作量，则跳过当前cluster
        如果cluster中所有手术的可行手术室都未超过工作量，则将当前cluster安排到可行手术室中使用时长最小的手术室
        """
        self.logger.info("开始安排非特殊手术")
        cluster_name_to_apps = defaultdict(list)
        for app in non_spec_unarranged_applications:
            cluster_name_to_apps[(app['apply_dept'],app['seq_alphabet'])].append(app)
        sorted_clusters = [Cluster(self.sio,apps) for apps in cluster_name_to_apps.values()] 
        sorted_clusters.sort(key=lambda x: ("骨科" in x.cluster_name[0] ,-x.weight2))
        for cluster in sorted_clusters:
            self.logger.info(f"当前手术簇{cluster}包含的手术为如下：")
            for app in cluster.applications:
                self.logger.info(f"\t{app['id']}")
        while sorted_clusters:
            cluster = sorted_clusters.pop()
            available_room_ids = cluster.get_available_room_ids()
            best_room_id = min(available_room_ids, key=lambda x: self.__get_room_workload(x))
            self.rooms[best_room_id].extend(cluster.applications)
            if self.__check_room_overwork(best_room_id):
                self.rooms[best_room_id] = self.rooms[best_room_id][:-len(cluster.applications)]
                for app in cluster.applications:
                    self.sio.update_unscheduled_reason(app['id'], f"{cluster}安排到手术室{best_room_id}后，手术室{best_room_id}已经超过工作量，跳过当前手术簇",append=True)
                self.logger.warning(f"{cluster}安排到手术室{best_room_id}后，手术室{best_room_id}已经超过工作量，跳过当前手术簇")
                continue
            for app in cluster.applications:
                app['arranged_status'] = ARRANGED_STATUS
                app['arranged_room_id'] = best_room_id
                self.logger.info(f"手术簇{cluster}安排到手术室{best_room_id}，手术室{best_room_id}的手术数为{len(self.rooms[best_room_id])}")
            self.logger.info(f"手术簇{cluster}安排完成")

        self.logger.info("非特殊手术安排完成")
        # 排序
        for room_id, applications in self.rooms.items():
            for app in applications:
                assert app["is_infected_hiv"] in [0, 1], "手术{}的感染状态非法".format(app)
                assert app["arranged_status"] in [0, 1, 2, 3], "未知手术排程状态{}".format(app["arranged_status"])

                if app["arranged_status"] == ARRANGED_STATUS:
                    app['arranged_start_time'] = datetime.max

                else:
                    assert isinstance(app['arranged_start_time'], datetime), "手术{}的开始时间非法".format(app)
                    assert isinstance(app['arranged_end_time'], datetime), "手术{}的结束时间非法".format(app)

            self.rooms[room_id].sort(key=lambda x: (
                x['arranged_start_time'],
                x.get('surgeon_code', ''),
                x.get('is_infected_hiv', 0),
                x.get('incision_size', float('inf'))
            ))


        # 二阶段排好的结果
        res_2 = []
        stage_1st_finished = []
        stage_2st_finished = []
        stage_3st_finished = []

        for room_id, applications in self.rooms.items():
            # 每个手术室从8:00开始,转换为datetime.time
            clock = datetime.strptime(self.schedule_date + " 08:00:00", "%Y-%m-%d %H:%M:%S")

            for idx, application in enumerate(applications):
                res_2.append({
                    "id": application["id"],
                    "arranged_status": application["arranged_status"],
                    "arranged_room_id": room_id,  # e.g. 2586
                    "arranged_start_time": clock,
                    "arranged_end_time": clock + timedelta(hours=application["duration"]),
                })
                clock += timedelta(hours=(application["duration"] + self.TURNOVER_INTERVAL))

                if application["arranged_status"] == 1:
                    stage_1st_finished.append(application)
                elif application["arranged_status"] == 2:
                    stage_2st_finished.append(application)
                elif application["arranged_status"] == 3:
                    stage_3st_finished.append(application)
                else:
                    raise ValueError("手术排程状态（arranged_status）异常，异常申请为{}".format(application))


        self.logger.info(f"排好结果汇总完成，申请数为{len(total_applications)}")
        self.logger.info(f"第一阶段完成数{len(stage_1st_finished)}")
        self.logger.info(f"第二阶段完成数{len(stage_2st_finished)}")
        self.logger.info(f"第三阶段完成数{len(stage_3st_finished)}")

        self.sio.write_result_to_db(res_2)
        self.sio.validation_check()

    def gantt_chart(self):
        """
        利用甘特图，可视化已经排好的手术日
        :return:
        """
        try:
            import plotly.express as px
            import plotly.io as pio
            import pandas as pd

            pio.renderers.default = "browser"

            self.logger.info("开始绘制甘特图...")
            self.logger.info("获取已排程的申请...")
            arranged_applications = self.sio.get_arranged_applications()
            self.logger.info("已排程的申请获取成功")
            self.logger.info("已排程的申请长度为{}".format(len(arranged_applications)))


            # 添加dummy行，用于显示所有的手术间
            for key, value in self.sio.get_total_room_info().items():
                arranged_room_id = key
                arranged_room_dept, arranged_room_name = value
                tmp = {
                    # 添加dummy行，用于显示所有的手术间,该dummy只有1s，所以不会影响甘特图的显示
                    "arranged_start_time": datetime.strptime(self.schedule_date + " 23:59:58", "%Y-%m-%d %H:%M:%S"),
                    "arranged_end_time": datetime.strptime(self.schedule_date + " 23:59:59", "%Y-%m-%d %H:%M:%S"),
                    "arranged_room_id": arranged_room_id,
                    "arranged_room_dept":arranged_room_dept,
                    "arranged_room_name":arranged_room_name,
                }
                for k, v in arranged_applications[0].items():
                    if k not in tmp:
                        tmp[k] = v
                arranged_applications.append(tmp)

            df = pd.DataFrame(arranged_applications)
            df['arranged_start_time'] = df['arranged_start_time'].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S"))
            df['arranged_end_time'] = df['arranged_end_time'].apply(lambda x: x.strftime("%Y-%m-%d %H:%M:%S"))
            df["room"] =  df["arranged_room_dept"]  +"|"+  df["arranged_room_name"]  + "|" +  df["arranged_room_id"].astype(str) 
            df = df.sort_values(by="room")
            df["排程阶段"] = df["arranged_status"].map({1: "手术日排程", 2: "第一次抢单排程", 3: "第二次抢单排程"})
            cm = {"手术日排程":"green", "第一次抢单排程":"blue", "第二次抢单排程":"orange"}


            def sort_fun(x):
                dept,name,_ = x.split("|")
                if dept == "第一手术部":
                    priority = 2
                elif dept == "第二手术部":
                    priority = 1
                elif dept == "日间手术室":
                    priority = 0
                return priority,-int(name)
            room_order = sorted(df["room"].unique(),key=sort_fun)

            fig = px.timeline(df,
                              x_start="arranged_start_time",
                              x_end="arranged_end_time",
                              y="room",
                              title="手术日排程甘特图",
                              hover_data=["id", "apply_dept","surgeon_name", "duration", "t_seq","is_infected_air"],
                              color="排程阶段",
                              color_discrete_map=cm,
                              category_orders={"room": room_order})  # 固定y轴顺序

            # 更新布局以固定y轴
            fig.update_layout(
                yaxis=dict(
                    categoryorder='array',
                    categoryarray=room_order
                )
            )
            
            fig.show()
            self.logger.info("甘特图绘制成功")

        except Exception as e:
            self.logger.error("oops!绘制甘特图失败：" + str(e))
