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
import os
import tempfile
from os.path import basename
import random
from zipfile import ZipFile

from app import app
from redbaron import RedBaron


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
    tmp = tempfile.NamedTemporaryFile(suffix=".py", delete=False)
    with open(tmp.name, "w") as source_code:
        source_code.write(hybridProgramBaron.dumps())

    # zip generated hybrid program and meta data files
    if os.path.exists('result.zip'):
        os.remove('result.zip')
    zipObj = ZipFile('result.zip', 'w')
    zipObj.write(tmp.name, 'hybrid_program.py')  # TODO: add metadata
    zipObj.close()
    zipObj = open('result.zip', "rb")
    data = zipObj.read()

    # TODO
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
        if inputParameter not in assignedVariables:
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


def add_method_recursively(hybridProgramBaron, taskFile, methodNode, prefix):
    """Add the given method node and all dependent methods, i.e., called methods to the given RedBaron object."""
    app.logger.info('Recursively adding methods. Current method name: ' + methodNode.name)

    # get assignment nodes and check if they call local methods
    assignmentNodes = methodNode.find_all('assignment', recursive=True)

    # replace all calls of qiskit.execute in this method to use the Qiskit Runtime backend
    signatureExtendedWithBackend, parameterName = replace_qiskit_execute(assignmentNodes, methodNode)

    # iterate over all assignment nodes and check if they rely on a local method call
    for assignmentNode in assignmentNodes:

        # we assume local calls always provide only one name node
        assignmentValues = assignmentNode.value
        if len(assignmentValues) < 2 or str(assignmentValues.value[1].type) != 'call':
            continue

        # extract the name of the local method that is called
        calledMethodNameNode = assignmentValues.value[0]

        # check if the method was already added to the RedBaron object
        if len(hybridProgramBaron.find_all('def', name=prefix + '_' + calledMethodNameNode.value)):
            calledMethodNameNode.value = prefix + '_' + calledMethodNameNode.value
            continue

        # filter native primitives that are referenced
        if is_native_reference(calledMethodNameNode.value):
            continue

        # check if the method was imported explicitly
        imported = False
        for importNode in taskFile.find_all('FromImportNode'):
            if len(importNode.targets.find_all('name_as_name', value=calledMethodNameNode.value)) > 0:
                imported = True
        if imported:
            continue

        # find method node in the current file
        recursiveMethodNode = taskFile.find('def', name=calledMethodNameNode.value)
        if not recursiveMethodNode:
            raise Exception('Unable to find method in program that is referenced: ' + calledMethodNameNode.value)

        # update invocation with new method name
        addedMethodName, inputParameterList, signatureExtended = add_method_recursively(hybridProgramBaron,
                                                                                        taskFile,
                                                                                        recursiveMethodNode,
                                                                                        prefix)
        calledMethodNameNode.value = addedMethodName

        # check if the signature of the invoked method was extended by the Qiskit Runtime backend
        if signatureExtended:

            # generate parameter name for the current method if not already done
            if not parameterName:
                parameterName = get_unused_method_parameter('backend', methodNode)

                # append to method signature
                methodNode.arguments.append(parameterName)

            # extend the method invokation with the new parameter
            assignmentValues.value[1].append(parameterName)
            signatureExtendedWithBackend = True

    # add prefix for corresponding file to the method name to avoid name clashes when merging multiple files
    methodNode.name = prefix + '_' + methodNode.name

    # determine input parameters of the method
    inputParameterList = []
    inputParameterNodes = methodNode.arguments.find_all('def_argument')
    for inputParameterNode in inputParameterNodes:
        inputParameterList.append(inputParameterNode.target.value)

    # add the method to the given RedBaron object
    hybridProgramBaron.append('\n')
    hybridProgramBaron.append(methodNode)
    return methodNode.name, inputParameterList, signatureExtendedWithBackend


def replace_qiskit_execute(assignmentNodes, methodNode):
    """Search for a qiskit.execute() command which has to be replaced by backend.run() for Qiskit Runtime"""

    # get a name for the qiskit runtime backend that is not already occupied
    name = get_unused_method_parameter('backend', methodNode)

    qiskitExecuteFound = False
    for assignmentNode in assignmentNodes:

        # assignment requires a value
        if not assignmentNode.value:
            continue

        # call to qiskit.execute is represented as AtomtrailersNode
        # (see https://redbaron.readthedocs.io/en/latest/nodes_reference.html#atomtrailersnode)
        if assignmentNode.value.type != 'atomtrailers':
            continue

        # contains at least two name nodes (qiskit, execute) and one call node
        if len(assignmentNode.value) < 3:
            continue

        # first node must be a name node with value qiskit
        if assignmentNode.value[0].value != 'qiskit':
            continue

        # second node must be a name node with value execute
        if assignmentNode.value[1].value != 'execute':
            continue

        # third node must be a call node
        if assignmentNode.value[2].type != 'call':
            continue

        # check if circuit to execute is explicitly defined under the 'experiments' parameters
        argumentName = assignmentNode.value[2].value.find('call_argument',
                                                          target=lambda target: target and (
                                                                  target.value == 'experiments'))

        # otherwise the circuit is the first positional argument
        if argumentName:
            argumentName = argumentName.value
        else:
            argumentName = assignmentNode.value[2].value[0]

        # replace the call with the qiskit runtime backend call
        assignmentNode.value = name + ".run(" + argumentName.value + ")"
        qiskitExecuteFound = True

    # adapt the method signature with the new argument
    if qiskitExecuteFound:
        methodNode.arguments.append(name)
        return qiskitExecuteFound, name
    return qiskitExecuteFound, None


def get_unused_method_parameter(prefix, methodNode):
    """Get a variable name that was not already used in the given method using the given prefix"""
    name = prefix
    while True:
        if methodNode.arguments.find('def_argument', target=lambda target: target and (target.value == name)) \
                or check_if_variable_used(methodNode, name):
            name = name + str(random.randint(0, 9))
        else:
            return name


def check_if_variable_used(methodNode, name):
    """Check if a variable with the given name is assigned in the given method"""
    for assignment in methodNode.find_all('assignment'):

        # if assignment has name node on the left side, compare the name of the variable with the given name
        if assignment.target.type == 'name' and assignment.target.value == name:
            return True

        # if assignment has tuple node on the left, check each entry
        if assignment.target.type == 'tuple' and assignment.target.find('name', value=name):
            return True

    return False


def get_output_parameters_of_execute(taskFile):
    """Get the set of output parameters of an execute method within a program"""

    # get the invocation of the execute method to extract the output parameters
    invokeExecuteNode = taskFile.find('assign', recursive=True,
                                      value=lambda value: value.type == 'atomtrailers'
                                                          and len(value.value) == 2
                                                          and value.value[0].value == 'execute')

    # generation has to be aborted if retrieval of output parameters fails
    if not invokeExecuteNode:
        return None

    # only one output parameter
    if invokeExecuteNode.target.type == 'name':
        return [invokeExecuteNode.target.value]
    else:
        # set of output parameters
        return [parameter.value for parameter in invokeExecuteNode.target.value]


def is_native_reference(name):
    """Check if the given name belongs to a natively supported method of Python"""
    return name in ['int', 'str', 'len', 'filter', 'enumerate', 'float', 'list', 'dict']
