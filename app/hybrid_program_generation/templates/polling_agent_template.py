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
                    print('Received execution request for process instance ID: ' + externalTask['processInstanceId'])

                    # URL to update variables at Camunda
                    hybridJobPrefix = '$hybridJobId'
                    updateUrl = camundaEndpoint + '/process-instance/' + externalTask['processInstanceId'] \
                                + '/variables/'

                    # load input data
                    ibmq_backend = variables.get('ibmq_backend').get('value')

                    ##### LOAD INPUT DATA SECTION

                    # callback to retrieve intermediate results
                    def interim_result_callback(job_id, interim_result):
                        print('Received new intermediate result...')

                        # handle dict results
                        if isinstance(interim_result, dict):
                            print('Handling dict as intermediate result...')

                            # iterate through all received intermediate results
                            for key in interim_result.keys():
                                print('Intermediate result contains key: ' + key)

                                # skip too large results for now, which could only be stored as files
                                if len(interim_result[key]) > 4000:
                                    print('Skipping result as it exceeds the Camunda variable size...')
                                    continue

                                # send the intermediate result to Camunda
                                updateIntermediateBody = {"value": interim_result[key], "type": "String"}
                                updateIntermediateResponse = requests.put(updateUrl + hybridJobPrefix + '-' + key,
                                                                          json=updateIntermediateBody)
                                print('Status code for updating variables with job ID: '
                                      + str(updateIntermediateResponse.status_code))

                        # handle string results
                        elif ':' in interim_result:
                            print('Handling String as intermediate result...')
                            intermediateParts = interim_result.split(':')
                            if len(intermediateParts) == 2:
                                variableName = intermediateParts[0].strip()
                                variableValue = intermediateParts[1].strip()
                                print('Received variable with name: ', variableName)

                                # skip too large results for now, which could only be stored as files
                                if len(variableValue) > 4000:
                                    print('Skipping result as it exceeds the Camunda variable size...')
                                else:
                                    updateIntermediateBody = {"value": variableValue, "type": "String"}
                                    updateIntermediateResponse = requests.put(updateUrl + hybridJobPrefix + '-'
                                                                              + variableName,
                                                                              json=updateIntermediateBody)
                                    print('Status code for updating variables with job ID: '
                                          + str(updateIntermediateResponse.status_code))

                    # invoke Qiskit Runtime program
                    backend = provider.get_backend(ibmq_backend)
                    program_inputs = {}
                    options = {'backend_name': backend.name()}
                    print('Executing on device: ' + backend.name())
                    job = provider.runtime.run(program_id=program_id,
                                               options=options,
                                               inputs=program_inputs,
                                               callback=interim_result_callback
                                               )
                    print(f"job id: {job.job_id()}")

                    # send ID of running job to Camunda
                    updateBody = {"value" : str(job.job_id()), "type": "String"}
                    print('Setting ID of Qiskit Runtime job under URL: ' + updateUrl)
                    updateResponse = requests.put(updateUrl + hybridJobPrefix, json=updateBody)
                    print('Status code for updating variables with job ID: ' + str(updateResponse.status_code))

                    # wait for result
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
ibmq_url = os.getenv('IBMQ_URL', "https://auth.quantum-computing.ibm.com/api")
ibmq_hub = os.getenv('IBMQ_HUB', "ibm-q")
ibmq_group = os.getenv('IBMQ_GROUP', "open")
ibmq_project = os.getenv('IBMQ_PROJECT', "main")
provider = IBMQ.enable_account(os.environ['IBMQ_TOKEN'], url=ibmq_url, hub=ibmq_hub, group=ibmq_group,
                               project=ibmq_project)
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
