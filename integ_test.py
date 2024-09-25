import requests
import json

if __name__ == '__main__':
    IP = 'localhost'
    PORT = '8002'
    row_data = json.dumps({'date': '2024-09-10'})

    response = requests.post(f'http://{IP}:{PORT}/surgery_brain/reset_info_port', data=row_data)
    assert response.status_code == 200

    response = requests.post(f'http://{IP}:{PORT}/surgery_brain/first_schedule', data=row_data)
    assert response.status_code == 200

    response = requests.post(f'http://{IP}:{PORT}/surgery_brain/gantt_chart', data=row_data)
    assert response.status_code == 200

    response = requests.post(f'http://{IP}:{PORT}/surgery_brain/sync_info_python_to_info', data=row_data)
    assert response.status_code == 200

    response = requests.post(f'http://{IP}:{PORT}/surgery_brain/sec_schedule', data=row_data)
    assert response.status_code == 200

    response = requests.post(f'http://{IP}:{PORT}/surgery_brain/gantt_chart', data=row_data)
    assert response.status_code == 200

    print('All tests passed.')
