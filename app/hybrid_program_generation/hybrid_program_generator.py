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
import tempfile
from os.path import basename
from zipfile import ZipFile

from app import app
from redbaron import RedBaron

from app.hybrid_program_generation.method_handler import get_output_parameters_of_execute, add_method_recursively


def create_hybrid_program(beforeLoop, afterLoop, loopCondition, taskIdProgramMap):

    # directory containing all templates required for generation
    templatesDirectory = os.path.join(os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__))),
                                      'templates')

    # RedBaron object containing all information about the hybrid program to generate
    with open(os.path.join(templatesDirectory, 'qiskit_runtime_program.py'), "r") as source_code:
        hybridProgramBaron = RedBaron(source_code.read())

    # retrieve all task names related to programs that have to be merged into the hybrid program
    taskNames = []
    if beforeLoop:
        beforeLoop = beforeLoop.split(",")
        taskNames.extend(beforeLoop)
    if afterLoop:
        afterLoop = afterLoop.split(",")
        taskNames.extend(afterLoop)

    # add methods from the given programs to the hybrid program
    programMetaData = {}
    for task in taskNames:
        if task not in taskIdProgramMap:
            return {'error': 'Unable to find program related to task with ID: ' + task}
        try:
            hybridProgramBaron, methodName, inputParameterList, outputParameterList = handle_program(hybridProgramBaron,
                                                                                                     taskIdProgramMap[
                                                                                                         task], task)
            app.logger.info('Added methods for task with ID ' + task + '. Method name to call from root: ' + methodName)
            app.logger.info('Call requires input parameters: ' + str(inputParameterList))
            programMetaData[task] = {'methodName': methodName,
                                     'inputParameters': tuple(inputParameterList),
                                     'outputParameters': tuple(outputParameterList)}
        except Exception as error:
            app.logger.error(error)
            return {'error': 'Failed to analyse and incorporate Python file for task with ID ' + task + '!\n'
                             + str(error)}

    # generate the main method of the Qiskit Runtime program
    try:
        hybridProgramBaron, inputParameters, outputParameters = generate_main_method(hybridProgramBaron, beforeLoop,
                                                                                     afterLoop, loopCondition,
                                                                                     programMetaData)
    except Exception as error:
        app.logger.error(error)
        return {'error': str(error)}

    # write generated hybrid program code to result file
    hybridProgramTemp = tempfile.NamedTemporaryFile(suffix=".py", delete=False)
    with open(hybridProgramTemp.name, "w") as source_code:
        source_code.write(hybridProgramBaron.dumps())

    # generate meta data and write to file
    metaDataTemp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    with open(metaDataTemp.name, "w") as source_code:
        source_code.write(generate_program_metadata(inputParameters, outputParameters))

    # zip generated hybrid program and meta data files
    if os.path.exists('../result.zip'):
        os.remove('../result.zip')
    zipObj = ZipFile('../result.zip', 'w')
    zipObj.write(hybridProgramTemp.name, 'hybrid_program.py')
    zipObj.write(metaDataTemp.name, 'hybrid_program.json')
    zipObj.close()
    zipObj = open('../result.zip', "rb")
    data = zipObj.read()

    # TODO: generate invocation stub
    result = {'program': data}
    return result


def generate_main_method(hybridProgramBaron, beforeLoop, afterLoop, loopCondition, programMetaData):
    """Generate the main method executing the hybrid loop"""
    app.logger.info('Generating main method for Qiskit Runtime program!')

    # find the main method stub
    mainMethodNodes = hybridProgramBaron.find_all('def', name='main')
    if len(mainMethodNodes) != 1:
        raise Exception('Unable to find main method in Qiskit Runtime template!')
    mainMethodNode = mainMethodNodes[0]

    # get the position of the return node within the template to insert the logic directly before
    returnPosition = mainMethodNode.index(mainMethodNode.find('return'))
    mainMethodNode.remove(mainMethodNode[returnPosition])
    startPosition = returnPosition - 1

    # add while loop which is terminated if the loop condition is met in between the before and after tasks
    mainMethodNode[startPosition:startPosition] = "while True:\n    pass"
    whileNode = mainMethodNode.find('while')

    # lists of already assigned variables and required overall inputs
    assignedVariables = []
    requiredInputs = []

    # add tasks before the loop
    if beforeLoop:
        for task in beforeLoop:
            whileNode, requiredInputs, assignedVariables = add_program_invocation(whileNode, requiredInputs,
                                                                                  assignedVariables, task,
                                                                                  programMetaData)

    # add loop condition and break loop if meet
    loopCondition = loopCondition.replace('${', '').replace('}', '')  # remove Camunda specific evaluation
    whileNode.value.append('\n')
    whileNode.value.append('if not ' + loopCondition + ':\n    break')

    # add tasks after the loop
    if afterLoop:
        for task in afterLoop:
            whileNode, requiredInputs, assignedVariables = add_program_invocation(whileNode, requiredInputs,
                                                                                  assignedVariables, task,
                                                                                  programMetaData)

    # get values from required external input parameters
    for requiredInput in requiredInputs:
        if requiredInput.startswith('backend'):
            # map the Qiskit Runtime backend to all backend parameters
            mainMethodNode.insert(startPosition, requiredInput + ' = backend')
        else:
            # retrieve from input args
            mainMethodNode.insert(startPosition, requiredInput + ' = kwargs["' + requiredInput + '"]')
    mainMethodNode.insert(startPosition, '# loading input parameters')
    mainMethodNode.insert(startPosition, '\n')

    # get output variables
    output = 'serialized_result = {'
    for assignedVariable in assignedVariables:
        output += '"' + assignedVariable + '":' + assignedVariable + ',\n'
    output += '}'
    mainMethodNode.append('# serialize and return output')
    mainMethodNode.append(output)
    mainMethodNode.append('user_messenger.publish(serialized_result, final=True)')
    mainMethodNode.append('\n')
    mainMethodNode.append('\n')

    return hybridProgramBaron, requiredInputs, assignedVariables


def generate_program_metadata(inputParameters, outputParameters):
    meta_data = {'name': "generated-qiskit-runtime-program",
                 'description': "Hybrid program generated based on a workflow fragment.",
                 'max_execution_time': 18000,
                 "spec": {"parameters": {"properties": {}, "required": []},
                          "return_values": {"properties": {}}}}

    for inputParameter in inputParameters:
        if not inputParameter.startswith('backend'):
            meta_data['spec']['parameters']['properties'][inputParameter] = {"type": "string"}
            meta_data['spec']['parameters']['required'].append(inputParameter)

    for outputParameter in outputParameters:
        meta_data['spec']['return_values']['properties'][outputParameter] = {"type": "string"}

    return json.dumps(meta_data)


def add_program_invocation(whileNode, requiredInputs, assignedVariables, task, programMetaData):
    """Add the invocation for the program representing the given tasks under the given while node"""
    app.logger.info('Adding logic for task with ID ' + str(task))
    metaData = programMetaData[task]
    outputParameters = ', '.join(metaData['outputParameters'])
    inputParameters = ', '.join(metaData['inputParameters'])

    # generate invocation
    invocation = outputParameters + ' = ' + metaData['methodName'] + '(' + inputParameters + ')'
    whileNode.value.append(invocation)

    # check if invocation used not set variables and request them as input
    for inputParameter in metaData['inputParameters']:
        if inputParameter not in assignedVariables and inputParameter not in requiredInputs:
            requiredInputs.append(inputParameter)
    assignedVariables.extend(metaData['outputParameters'])

    return whileNode, requiredInputs, assignedVariables


def handle_program(hybridProgramBaron, path, task):
    """ Handle a program of the candidate and add the execute method,
    as well as all dependent code to the given RedBaron object"""

    # separator between code snippets from different programs
    hybridProgramBaron.append('##############################################')
    hybridProgramBaron.append('# Code snippets for file ' + basename(path))
    hybridProgramBaron.append('##############################################')

    with open(path, "r") as source_code:
        taskFile = RedBaron(source_code.read())

        # get all imports from the file
        importListFile = taskFile.find_all('import')
        importListFile.extend(taskFile.find_all('FromImportNode'))

        # get last import node of the current RedBaron object
        importListHybridProgram = hybridProgramBaron.find_all('import')
        importListHybridProgram.extend(hybridProgramBaron.find_all('FromImportNode'))
        index = 0
        for i in importListHybridProgram:
            index = max(index, hybridProgramBaron.index(i))

        # for now all imports are added independent of their occurrence
        hybridProgramBaron[index:index] = importListFile

        # find the 'execute' method within the file
        executeNodes = taskFile.find_all('def', name='execute')

        # if not found abort the generation
        if len(executeNodes) != 1:
            raise Exception('Unable to find execute method in program: ' + basename(path))
        executeNode = executeNodes[0]

        # get the output parameters for the given program
        outputParameterList = get_output_parameters_of_execute(taskFile)
        if outputParameterList is None:
            raise Exception('Unable to retrieve output parameters of execute method in program: ' + basename(path))

        # add the execute method and all depending methods to the RedBaron object
        methodName, inputParameterList, signatureExtendedWithBackend = add_method_recursively(hybridProgramBaron,
                                                                                              taskFile,
                                                                                              executeNode,
                                                                                              task)

    return hybridProgramBaron, methodName, inputParameterList, outputParameterList
