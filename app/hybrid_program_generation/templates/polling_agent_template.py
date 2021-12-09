import threading
import base64
from qiskit import *
import requests
from urllib.request import urlopen


def poll():
    print('Polling for new external tasks at the Camunda engine with URL: ', pollingEndpoint)

    body = {
        "workerId": "$ServiceNamePlaceholder",
        "maxTasks": 1,
        "topics":
            [{"topicName": topic,
              "lockDuration": 100000000
              }]
    }

    try:
        response = requests.post(pollingEndpoint + '/fetchAndLock', json=body)

        if response.status_code == 200:
            for externalTask in response.json():
                print('External task with ID for topic ' + str(externalTask.get('topicName')) + ': '
                      + str(externalTask.get('id')))
                variables = externalTask.get('variables')
                if externalTask.get('topicName') == topic:
                    # load input data
                    ibmq_token = variables.get('ibmq_token').get('value')
                    ibmq_backend = variables.get('ibmq_backend').get('value')
                    ##### LOAD INPUT DATA SECTION

                    # callback to retrieve intermediate results
                    def interim_result_callback(job_id, interim_result):
                        print(f"interim result: {interim_result}")

                    # invoke Qiskit Runtime program
                    provider = IBMQ.enable_account(ibmq_token)
                    backend = provider.get_backend(ibmq_backend)
                    program_inputs = {}
                    options = {'backend_name': backend.name()}
                    job = provider.runtime.run(program_id=os.environ['PROGRAM_NAME'],
                                               options=options,
                                               inputs=program_inputs,
                                               callback=interim_result_callback
                                               )
                    print(f"job id: {job.job_id()}")
                    result = job.result()
                    print(result)

                    # encode parameters as files due to the string size limitation of camunda
                    ##### STORE OUTPUT DATA SECTION

                    # send response
                    body = {}
                    response = requests.post(pollingEndpoint + '/' + externalTask.get('id') + '/complete', json=body)
                    print('Status code of response message: ' + str(response.status_code))

    except Exception:
        print('Exception during polling!')

    threading.Timer(8, poll).start()


def download_data(url):
    response = urlopen(url)
    data = response.read().decode('utf-8')
    return str(data)


camundaEndpoint = os.environ['CAMUNDA_ENDPOINT']
pollingEndpoint = camundaEndpoint + '/external-task'
topic = os.environ['CAMUNDA_TOPIC']
poll()
