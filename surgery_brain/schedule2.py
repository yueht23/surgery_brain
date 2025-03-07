# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from common.logger import Logger
from surgery_brain.scheduleIO import ScheduleIO
import pandas as pd
import pulp


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
        self.rooms = {}  # 术间

        """
        定义二轮抢单排程的所需数据结构
        """
        self.room_surgery = {}  # 术间的手术信息

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
                continue

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
                    "arranged_status": 1,
                    "arranged_room_id": room_id,  # e.g. 2586
                    "arranged_start_time": clock,
                    "arranged_end_time": clock + timedelta(hours=application["duration"])
                })
                clock += timedelta(hours=(application["duration"] + self.TURNOVER_INTERVAL))
        self.logger.info(f"排好结果汇总完成，申请数为{len(waiting_list)}，一阶段完成数为{len(res)}")

        self.sio.write_result_to_db(res)
        self.sio.validation_check()

    def schedule_sec(self):
        """
        二期的手术日抢单排程
        :return: None
        """
        self.sio.import_surgeries()
        arranged_applications = self.sio.get_arranged_applications()
        unarranged_applications = self.sio.get_unarranged_applications()
        total_applications = arranged_applications + unarranged_applications
        total_room_info = self.sio.get_total_room_info()
        self.logger.info("已排程的申请长度为{}".format(len(arranged_applications)))
        self.logger.info("未排程的申请长度为{}".format(len(unarranged_applications)))
        self.logger.info("总的申请长度为{}".format(len(total_applications)))

        # 待排手术权重重新赋值 TODO: 需要考虑为空的情况
        day_surgery = [app for app in unarranged_applications if app['is_day_surgery']]
        elective_surgery = [app for app in unarranged_applications if not app['is_day_surgery']]
        # df_unarranged_applications = pd.DataFrame(unarranged_applications)
        df_day_surgery = pd.DataFrame(day_surgery)
        df_elective_surgery = pd.DataFrame(elective_surgery)
        df_day_surgery["day_percentage"] = df_day_surgery['inpatient_serial'].rank(method='average',
                                                                                   ascending=False) / len(
            df_day_surgery)
        df_elective_surgery["elective_percentage"] = df_elective_surgery['inpatient_serial'].rank(
            method='average') / len(df_elective_surgery)

        self.logger.info("二阶段权重构造")
        for application in total_applications:
            self.logger.info("")
            self.logger.info("当前待排申请{}".format(application))

            weight2 = 0.0

            # 特殊手术
            weight2 += 10 if application["is_sp_robot"] else 0
            weight2 += 10 if application["is_sp_intervention"] else 0
            weight2 += 10 if application["is_sp_perspective"] else 0
            weight2 += 10 if application["is_sp_holmium"] else 0

            # weight2 +=   # 先申请先使用,暂不考虑申请提交时间

            # 抢单失败次数
            weight2 += 2 * application["attempt_times"]

            # 日间手术
            if application["is_day_surgery"]:
                weight2 += 3
                for _, row_day_app in df_day_surgery.iterrows():
                    if row_day_app["id"] == application["id"]:
                        weight2 += row_day_app['day_percentage']
            # 择期手术
            else:
                for _, row_elective_app in df_elective_surgery.iterrows():
                    if row_elective_app["id"] == application["id"]:
                        weight2 += row_elective_app['elective_percentage']

            # 国考四级手术
            weight2 += 3 if application["surgery_level"] == "4" else 0

            # 手术优先操作
            weight2 += 3 if not application["is_operation"] else 0

            # 微创优先非微创
            weight2 += 3 if application["is_mini_invasive"] else 0

            application["weight2"] = weight2
            self.logger.info("当前申请的权重为{}".format(weight2))
        self.logger.info("二阶段权重构造完成")
        """
         变量/参数：
         set_i：向量：医生的集合
         set_j：向量：手术（申请号）的集合
         set_k：向量：手术间的集合
         set_m：向量：科室的集合
         set_n: 向量：手术部的集合
         weight_j：向量：手术的权重
         time_j：向量：手术的时长
         var_jk：变量：手术j是否排在手术间k
         var_ik：变量：手术间k是否排了医生i的手术
         var_in：变量：医生i的手术是否排在手术部n
         var_ik_2：变量：医生i在二轮是否在手术间k排了手术
         var_mk：变量：手术间k是否排了科室m的手术
         arranged_room_depts_k：字典：手术间k安排了几个科室的手术,{k:[dept]}
         arranged_dept_rooms_m：字典：科室m的手术被安排在几个术间,{m:[room_id]}
         arranged_doc_roomDepts_i：字典：医生i的手术被安排在几个手术部,{i:[room_dept]}
         para_ij：矩阵：手术j是否是i医生的=1/0
         para_mj：矩阵：手术j是否是m科室的=1/0
         list_nk: 字典：手术部n的手术间列表{n:[room_id]}
         startTime_k：向量：第k个手术间里（一轮）已经排好的手术的总时长（包括最后一次接台）
         finalTime_k：向量：第k个手术间里最后排好的手术的总时长（包括最后一次接台）
         var_i：变量：医生i在二轮排上的手术是否可以分到2个及以上的手术间里=1/0
        """
        # 变量集合
        set_i = []  # 医生
        set_j = []  # 手术申请
        set_m = []  # 科室
        set_k = list(total_room_info.keys())  # 术间
        set_k = list(map(str, set_k))
        set_n = []  # 手术部
        set_weight = {}  # 权重
        list_nk = {}  # 手术部n的手术间列表
        startTime_k = {}  # 术间k可用于抢单的时间段的开始
        for k in set_k:
            startTime_k[k] = 0.0
        time_j = {}  # 手术j的预计时长
        whether_arranged_s1 = {}  # 手术j是否在第一阶段被安排
        for application in total_applications:
            if application in arranged_applications:
                whether_arranged_s1[application['id']] = 1
            else:
                whether_arranged_s1[application['id']] = 0
            if application['surgeon_code'] not in set_i:
                set_i.append(application['surgeon_code'])
            if application['id'] not in set_j:
                set_j.append(application['id'])
                set_weight[application['id']] = application['weight2']
            if application['apply_dept'] not in set_m:
                set_m.append(application['apply_dept'])
            time_j[application['id']] = application['duration']

        for room in total_room_info.keys():
            if total_room_info[room][0] not in set_n:
                set_n.append(total_room_info[room][0])

        for n in set_n:
            list_nk[n] = []

        for room in total_room_info.keys():
            if room not in list_nk[total_room_info[room][0]]:
                list_nk[total_room_info[room][0]].append(str(room))

        # 定义变量和约束条件
        model = pulp.LpProblem("Stage2", pulp.LpMaximize)

        var_jk = {}
        for j in set_j:
            var_jk[j] = {}
            for k in set_k:
                var_jk[j][k] = 0
        var_ik = {}
        for i in set_i:
            var_ik[i] = {}
            for k in set_k:
                var_ik[i][k] = 0
        var_ik_2 = {}
        for i in set_i:
            var_ik_2[i] = {}
            for k in set_k:
                var_ik_2[i][k] = 0
        var_mk = {}
        for m in set_m:
            var_mk[m] = {}
            for k in set_k:
                var_mk[m][k] = 0
        var_in = {}
        for i in set_i:
            var_in[i] = {}
            for n in set_n:
                var_in[i][n] = 0
        var_i = {}
        for i in set_i:
            var_i[i] = 0
        para_ij = {}
        for i in set_i:
            para_ij[i] = {}
            for j in set_j:
                para_ij[i][j] = 0
        para_mj = {}
        for m in set_m:
            para_mj[m] = {}
            for j in set_j:
                para_mj[m][j] = 0
        arranged_room_depts = {}
        for k in set_k:
            arranged_room_depts[k] = []
        arranged_dept_rooms = {}
        for m in set_m:
            arranged_dept_rooms[m] = []
        arranged_doc_roomDepts = {}
        for i in set_i:
            arranged_doc_roomDepts[i] = []
        for k in set_k:
            for j in set_j:
                # 添加【变量】：var_jk
                var_jk[j][k] = pulp.LpVariable(
                    cat=pulp.LpBinary, name='VariableOf' + 'Surgery' + str(j) + 'Room' + str(k))
            for i in set_i:
                # 添加【变量】：var_ik
                var_ik[i][k] = pulp.LpVariable(
                    cat=pulp.LpBinary, name='DummyVariableOf' + 'Doctor' + str(i) + 'Room' + str(k))
                # 添加【变量】：var_ik_2
                var_ik_2[i][k] = pulp.LpVariable(
                    cat=pulp.LpBinary, name='DummyVariable222Of' + 'Doctor' + str(i) + 'Room' + str(k))
            for m in set_m:
                # 添加【变量】：var_mk
                var_mk[m][k] = pulp.LpVariable(
                    cat=pulp.LpBinary, name='DummyVariableOf' + 'Dept' + str(m) + 'Room' + str(k))
        for i in set_i:
            for n in set_n:
                # 添加【变量】：var_in
                var_in[i][n] = pulp.LpVariable(
                    cat=pulp.LpBinary, name='DummyVariableOf' + 'Doctor' + str(i) + 'Room_Dept' + str(n))

        # 添加【约束】：手术间条件约束
        unavailable_rooms = {}  # 不可进行手术的术间
        for application in total_applications:
            unavailable_rooms[application['id']] = list(set(set_k) - set(self.sio.get_available_rooms(application)))
            # self.logger.info("手术编号", application['id'], "可行术间", self.sio.get_available_rooms(application), "是否在第一阶段固定", whether_arranged_s1[j])
            para_ij[application['surgeon_code']][application['id']] = 1
            para_mj[application['apply_dept']][application['id']] = 1

        for j in set_j:
            # self.logger.info("手术编号", j, "不可行术间", unavailable_rooms[j], "是否在第一阶段固定", whether_arranged_s1[j])
            if whether_arranged_s1[j] == 0:
                model += (pulp.lpSum([var_jk[j][k] for k in unavailable_rooms[j]]) == 0,
                          'ConditionOf' + 'Surgery' + str(j))

        # 添加【约束】：手术至多安排在一个手术间里
        for j in set_j:
            model += (pulp.lpSum([var_jk[j][k] for k in set_k]) <= 1,
                      'AtMostOneRoomFor' + 'Surgery' + str(j))

        # 添加【约束】：第一阶段的手术固定在之前的术间
        for application in arranged_applications:
            room_id = application['arranged_room_id']
            startTime_k[str(room_id)] += application["duration"] + 0.5
            arranged_room_depts[str(room_id)].append(application['apply_dept'])
            arranged_dept_rooms[application['apply_dept']].append(str(room_id))
            arranged_doc_roomDepts[application['surgeon_code']].append(total_room_info[int(room_id)][0])

            model += (var_jk[application['id']][str(room_id)] == 1,
                      'Arranged' + 'Surgery' + str(application['id']))

        # 添加【约束】：每个手术间的用时不超过12小时（如果已经超了，就不超过当前值）
        for k in set_k:
            model += (pulp.lpSum([var_jk[j][k] * (time_j[j] + 0.5) for j in set_j]) <=
                      max(12.5, startTime_k[k]), 'TotalTimeOf' + 'Room' + str(k))

        for m in set_m:
            # 添加【约束】：定义var_mk（表示：手术间k是否排了科室m的手术）
            for k in set_k:
                model += pulp.lpSum([var_jk[j][k] * para_mj[m][j] for j in set_j]) \
                         <= 100 * var_mk[m][k], 'DefineVarOf' + 'Dept' + str(m) + 'Room' + str(k) + '1'
                model += pulp.lpSum([var_jk[j][k] * para_mj[m][j] for j in set_j]) \
                         >= var_mk[m][k], 'DefineVarOf' + 'Dept' + str(m) + 'Room' + str(k) + '2'

        for k in set_k:
            # 添加【约束】：一个手术间里的手术不能来自超过【3】个科室（如果已经超了，就不超过当前值）
            model += pulp.lpSum([var_mk[m][k] for m in set_m]) \
                     <= max(3, len(set(arranged_room_depts[k]))), 'ConstrOfDeptFor' + 'Room' + str(k)

        for m in set_m:
            # 添加【约束】：一个科室的手术不能分到超过【3】个手术间（如果已经超了，就不超过当前值）
            model += pulp.lpSum([var_mk[m][k] for k in set_k]) \
                     <= max(3, len(set(arranged_dept_rooms[m]))), 'ConstrOfRoomFor' + 'Dept' + str(m)

        for i in set_i:
            # 添加【变量】：var_i
            var_i[i] = pulp.LpVariable(
                cat=pulp.LpBinary, name='VariableFor' + 'Doctor' + str(i))
            for k in set_k:
                # 添加【约束】：定义var_ik（表示：手术间k是否排了医生i的手术）
                model += pulp.lpSum([var_jk[j][k] * para_ij[i][j] for j in set_j]) \
                         <= 100 * var_ik[i][k], 'DefineVarOf' + 'Doctor' + str(i) + 'Room' + str(k) + '1'
                model += pulp.lpSum([var_jk[j][k] * para_ij[i][j] for j in set_j]) \
                         >= var_ik[i][k], 'DefineVarOf' + 'Doctor' + str(i) + 'Room' + str(k) + '2'

                # 添加【约束】：定义var_ik_2（表示：医生i在二轮是否在手术间k排了手术）
                model += pulp.lpSum([var_jk[j][k] * para_ij[i][j] * (1 - whether_arranged_s1[j]) for j in set_j]) \
                         <= 100 * var_ik_2[i][k], \
                         'DefineVar222Of' + 'Doctor' + str(i) + 'Room' + str(k) + '1'
                model += pulp.lpSum([var_jk[j][k] * para_ij[i][j] * (1 - whether_arranged_s1[j]) for j in set_j]) \
                         >= var_ik_2[i][k], \
                         'DefineVar222Of' + 'Doctor' + str(i) + 'Room' + str(k) + '2'

            # 添加【约束】：医生i的排上的手术的总时长如果不超过4小时，
            # 那么var_i[i] == 0，否则var_i[i] == 1
            # 那么医生i的手术就至多只能排到1个手术间里
            model += (pulp.lpSum([para_ij[i][j] * var_jk[j][k] * time_j[j] for j in set_j
                                  for k in set_k]) <= 4 + 100 * (1 - var_i[i]))
            model += (pulp.lpSum([para_ij[i][j] * var_jk[j][k] * time_j[j]
                                  for j in set_j
                                  for k in set_k]) - 4 >= -100 * (1 - var_i[i]),
                      'Constr111DefineVar_iForDoctor' + str(i) + '2')
            # 添加【约束】：医生i的排上的手术的数量如果不超过3个，
            # 那么医生i的手术就至多只能排到1个手术间里
            # 那么var_i[i] == 0, 否则var_i[i] == 1
            model += (pulp.lpSum([para_ij[i][j] * var_jk[j][k]
                                  for j in set_j
                                  for k in set_k]) <= 3 + 100 * (1 - var_i[i]),
                      'Constr222DefineVar_iForDoctor' + str(i) + '1')
            model += (pulp.lpSum([para_ij[i][j] * var_jk[j][k]
                                  for j in set_j
                                  for k in set_k]) - 3 >= -100 * (1 - var_i[i]),
                      'Constr222DefineVar_iForDoctor' + str(i) + '2')

            # 添加【约束】：如果var_i[i]为0，那么医生i在二轮排上的手术不能排在2个及以上的手术间里
            model += pulp.lpSum([var_ik_2[i][k] for k in set_k]) <= 1 + 100 * var_i[i]

        # 添加【约束】：定义var_in（表示：医生i的手术是否安排在手术部n）
        for i in set_i:
            for n in set_n:
                model += pulp.lpSum([var_ik[i][k] for k in list_nk[n]]) \
                         <= 100 * var_in[i][n], 'DefineVarOf' + 'Doctor' + str(i) + 'Room_Dept' + str(n) + '1'
                model += pulp.lpSum([var_ik[i][k] for k in list_nk[n]]) \
                         >= var_in[i][n], 'DefineVarOf' + 'Doctor' + str(i) + 'Room_Dept' + str(n) + '2'

        # 添加【约束】，同一医生的手术不超过1个手术部（如果已经超了，就不超过当前值）
        for i in set_i:
            model += pulp.lpSum([var_in[i][n] for n in set_n]) \
                     <= max(1, len(set(arranged_doc_roomDepts[i]))), 'ConstrOfRoom_DeptFor' + 'Doctor' + str(i)

        # 【目标】最大化排上手术的总权重
        model += pulp.lpSum([var_jk[j][k] * set_weight[j] * (1 - whether_arranged_s1[j]) for k in set_k
                             for j in set_j]), 'Obj'

        solver = pulp.PULP_CBC_CMD(timeLimit=100)  # 算法运行时间不超过100秒
        model.solve(solver)
        # 确保模型已经成功求解
        if pulp.LpStatus[model.status] == 'Optimal':
            for j in set_j:
                for k in set_k:
                    if var_jk[j][k].varValue is not None and int(var_jk[j][k].varValue) == 1:
                        # self.logger.info(f"var_jk[{j}][{k}] = {var_jk[j][k].varValue}")
                        # self.logger.info(j, set_weight[j], self.sio.get_available_rooms(j))
                        # self.logger.info("是否在第一阶段已固定", whether_arranged_s1[j])
                        pass
            for k in set_k:
                # self.logger.info("术间", k, "总用时", sum(int(var_jk[j][k].varValue) * (time_j[j] + 0.5) for j in set_j), "小时")
                pass
        else:
            self.logger.info("Model did not solve to optimality.")
        for k in set_k:
            self.room_surgery[k] = []
            for app in total_applications:
                if int(var_jk[app['id']][k].varValue) == 1:
                    app["arranged_status"] = 2 if app["arranged_status"] == 0 else app["arranged_status"]
                    self.room_surgery[k].append(app)

        # 排序
        for k in set_k:
            for app in self.room_surgery[k]:
                if not isinstance(app['arranged_start_time'], datetime):
                    try:
                        app['arranged_start_time'] = datetime.strptime(app['arranged_start_time'], "%Y-%m-%d %H:%M:%S")
                    except Exception as e:
                        # TODO: 需要排查，时间无法转换为datetime的原因
                        self.logger.error(f"手术申请{app['id']}的arranged_start_time格式错误，错误信息为{e}")
                        app['arranged_start_time'] = datetime.max

            self.room_surgery[k].sort(key=lambda x: (
                x['arranged_start_time'] if x['arranged_start_time'] is not None else datetime.max,
                x.get('surgeon_code', ''),
                (x.get('is_infected', 1) != 0, x.get('is_infected', 1)),
                x.get('incision_size', float('inf'))
            ))
        # 二阶段排好的结果
        res_2 = []
        for room_id, applications in self.room_surgery.items():
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
        self.logger.info(f"排好结果汇总完成，申请数为{len(total_applications)}，二阶段总完成数为{len(res_2)}")

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
                              color="arranged_status")
            fig.show()
            self.logger.info("甘特图绘制成功")

        except Exception as e:
            self.logger.error("oops!绘制甘特图失败：" + str(e))
