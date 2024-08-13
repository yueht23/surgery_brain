from surgery_brain.schedule2 import Schedule
from pprint import pprint

if __name__ == "__main__":
    schedule = Schedule("2024-07-10")
    print(f"排程日期：{schedule.schedule_date}，当日周{schedule.sio.get_weekday()}")
    print("最大医生工作量：", schedule.MAX_DOCTOR_WORKLOAD)
    print("最大手术室工作量：", schedule.MAX_ROOM_WORKLOAD)
    print("换台间隔：", schedule.TURNOVER_INTERVAL)
    print("开始时间：", schedule.BEGIN_TIME)

    print("现在所有未排程的申请：")
    pprint(schedule.sio.get_unarranged_applications())

    print("一阶段确定性排程：")
    schedule.schedule_first()

    print("可视化排程结果：")
    schedule.gantt_chart()

    print("一阶段排程结束后，二阶段抢单排程：")
    for app in schedule.sio.get_unarranged_applications():
        tmp = f"申请{app['id']}，手术室{app['apply_dept']},"
        tmp += f"机:{app['is_sp_robot']}, 钬{app['is_sp_holmium']}, "
        tmp += f"介{app['is_sp_intervention']}, 透{app['is_sp_perspective']},"
        tmp += f"可被安排的手术室：{schedule.sio.get_available_rooms(app)}"
        print(tmp)

    print("二阶段抢单排程：")
    schedule.schedule_sec()
