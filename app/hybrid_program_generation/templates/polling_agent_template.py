import threading
import base64
import zipfile
from tempfile import mkdtemp

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
                    ibmq_backend = variables.get('ibmq_backend').get('value')
                    ##### LOAD INPUT DATA SECTION

                    # callback to retrieve intermediate results
                    def interim_result_callback(job_id, interim_result):
                        print(f"interim result: {interim_result}")

                    # invoke Qiskit Runtime program
                    backend = provider.get_backend(ibmq_backend)
                    program_inputs = {}
                    options = {'backend_name': backend.name()}
                    job = provider.runtime.run(program_id=program_id,
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


# deploy the related Qiskit Runtime program on service startup
provider = IBMQ.enable_account(os.environ['IBMQ_TOKEN'])
directory_to_extract_to = mkdtemp()
with zipfile.ZipFile('hybrid_program.zip', 'r') as zip_ref:
    zip_ref.extractall(directory_to_extract_to)
hybrid_program_data = os.path.join(os.getcwd(), os.path.join(directory_to_extract_to, "hybrid_program.py"))
hybrid_program_json = os.path.join(os.getcwd(), os.path.join(directory_to_extract_to, "hybrid_program.json"))
program_id = provider.runtime.upload_program(
    data=hybrid_program_data,
    metadata=hybrid_program_json
)
print('Uploaded Qiskit Runtime program with ID: ', program_id)

# start polling for requests
camundaEndpoint = os.environ['CAMUNDA_ENDPOINT']
pollingEndpoint = camundaEndpoint + '/external-task'
topic = os.environ['CAMUNDA_TOPIC']
poll()
