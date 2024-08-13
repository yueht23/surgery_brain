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

    print("儿科现在可用的手术室：")
    pprint(schedule.sio.get_available_rooms_for_dept("儿科"))
    print("产科现在可用的手术室：")
    pprint(schedule.sio.get_available_rooms_for_dept("妇科"))

    print("一阶段确定性排程：")
    schedule.schedule_first()

    print("可视化排程结果：")
    schedule.gantt_chart()

    print("二阶段抢单排程：")
    schedule.schedule_sec()
