# ******************************************************************************
#  Copyright (c) 2021 University of Stuttgart
#
#  See the NOTICE file(s) distributed with this work for additional
#  information regarding copyright ownership.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# ******************************************************************************
import json
import os
import random
import string

from redbaron import RedBaron


def generate_polling_agent(inputParameters, outputParameters):
    """Generate a polling agent for the generated Qiskit Runtime program exchanging the
    required input/output with the Camunda BPMN engine"""

    # directory containing all templates required for generation
    templatesDirectory = os.path.join(os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__))),
                                      'templates')

    # generate random name for the polling agent
    pollingAgentName = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

    # RedBaron object containing the polling agent template
    with open(os.path.join(templatesDirectory, 'polling_agent_template.py'), "r") as source_code:
        pollingAgentBaron = RedBaron(source_code.read())

        # get the poll method from the template
        pollDefNode = pollingAgentBaron.find('def', name='poll')

        # get the try catch block in the method
        tryNode = pollDefNode.value.find('try')

        # create polling request with generated agent name
        pollingBody = '{"workerId": "' + pollingAgentName + '", "maxTasks": 1, "topics": [{"topicName": topic, ' \
                                                            '"lockDuration": 100000000}]}'
        pollingNode = pollDefNode.find('assign', target=lambda target: target and (target.value == 'body'))
        pollingNode.value = pollingBody

        # get the position of the input placeholders within the template
        ifNode = tryNode.value.find('ifelseblock').value[0].value.find('for').value.find('ifelseblock').find('if')
        inputNodeIndex = ifNode.index(ifNode.find('comment', recursive=True, value='##### LOAD INPUT DATA SECTION'))

        # add input parameters to the polling agent
        for inputParameter in inputParameters:
            inputRetrievalIfStatement = 'if variables.get("' + inputParameter + '").get("type") == "String":'
            inputRetrievalIfBranch = '\n    ' + inputParameter + ' = variables.get("' + inputParameter + '").get("value")'
            downloadEndpoint = 'camundaEndpoint + "/process-instance/" + externalTask.get("processInstanceId") + "/variables/' + inputParameter + '/data"'
            inputRetrievalElseBranch = '\nelse:\n    ' + inputParameter + ' = download_data(' + downloadEndpoint + ')'
            inputRetrieval = inputRetrievalIfStatement + inputRetrievalIfBranch + inputRetrievalElseBranch
            ifNode.insert(inputNodeIndex + 1, inputRetrieval)

        # remove the placeholder
        ifNode.remove(ifNode[inputNodeIndex])

        # get the position of the output placeholders within the template
        outputNodeIndex = ifNode.index(ifNode.find('comment', recursive=True, value='##### STORE OUTPUT DATA SECTION'))
        outputBodyNode = ifNode.find('assign', target=lambda target: target and (target.value == 'body'))

        # add output parameters
        outputDict = {"workerId": pollingAgentName, "variables": {}}
        for outputParameter in outputParameters:
            # encode output parameter as file to circumvent the Camunda size restrictions on strings
            encoding = 'encoded_' + outputParameter + ' = base64.b64encode(str.encode(result["' + \
                       outputParameter + '"])).decode("utf-8") '
            ifNode.insert(outputNodeIndex + 1, encoding)

            # add to final result object send to Camunda
            outputDict["variables"][outputParameter] = {"value": 'encoded_' + outputParameter, "type": "File",
                                                        "valueInfo": {
                                                            "filename": outputParameter + ".txt",
                                                            "encoding": ""
                                                        }
                                                        }

        # remove the quotes added by json.dumps for the variables in the target file
        outputJson = json.dumps(outputDict)
        for outputParameter in outputParameters:
            outputJson = outputJson.replace('"encoded_' + outputParameter + '"', 'encoded_' + outputParameter)

        # remove the placeholder
        ifNode.remove(ifNode[outputNodeIndex])

        # update the result body with the output parameters
        outputBodyNode.value = outputJson

    # workaround due to RedBaron bug which wrongly idents the exception
    pollingAgentString = pollingAgentBaron.dumps()
    pollingAgentString = pollingAgentString.replace("except Exception:", "    except Exception:")

    return pollingAgentString
