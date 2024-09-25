from surgery_brain.schedule2 import Schedule

if __name__ == "__main__":
    schedule = Schedule("2024-09-09")
    schedule.sio.reset_info_port()
    print(f"排程日期：{schedule.schedule_date}，当日周{schedule.sio.get_weekday()}")
    print("最大医生工作量：", schedule.MAX_DOCTOR_WORKLOAD)
    print("最大手术室工作量：", schedule.MAX_ROOM_WORKLOAD)
    print("换台间隔：", schedule.TURNOVER_INTERVAL)
    print("开始时间：", schedule.BEGIN_TIME)

    print("一阶段确定性排程：")
    schedule.schedule_first()
    print("可视化排程结果：")
    schedule.gantt_chart()

    schedule.sio.sync_info_python_to_info(drop_ratio=0.25)

    print("二阶段抢单排程：")
    schedule.schedule_sec()

    print("可视化排程结果：")
    schedule.gantt_chart()
