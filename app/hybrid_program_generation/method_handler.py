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

import random

from app import app


def add_method_recursively(hybridProgramBaron, taskFile, methodNode, prefix):
    """Add the given method node and all dependent methods, i.e., called methods to the given RedBaron object."""
    app.logger.info('Recursively adding methods. Current method name: ' + methodNode.name)

    # get assignment nodes and check if they call local methods
    assignmentNodes = methodNode.find_all('assignment', recursive=True)

    # replace all calls of qiskit.execute in this method to use the Qiskit Runtime backend
    signatureExtendedWithBackend, parameterName, backendSignaturePositions = replace_qiskit_execute(assignmentNodes,
                                                                                                    methodNode)

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
        app.logger.info('Found new method invocation of local method: ' + calledMethodNameNode.value)
        addedMethodName, inputParameterList, signatureExtended, backendSignaturePositionsNew = add_method_recursively(
            hybridProgramBaron,
            taskFile,
            recursiveMethodNode,
            prefix)
        calledMethodNameNode.value = addedMethodName

        # handle backend objects in called method
        if backendSignaturePositionsNew:
            app.logger.info('Added method defined backend as parameter at positions: ' + str(backendSignaturePositionsNew))
            for backendSignaturePosition in backendSignaturePositionsNew:
                parameter = assignmentValues.value[1].value[backendSignaturePosition]
                extended, indices, parameterName = check_qiskit_backend_assignment(methodNode, assignmentNodes,
                                                                                   parameterName,
                                                                                   backendSignaturePositions,
                                                                                   parameter.value.value)
                for index in indices:
                    if index not in backendSignaturePositions:
                        backendSignaturePositions.append(index)

        # check if the signature of the invoked method was extended by the Qiskit Runtime backend
        if signatureExtended:
            app.logger.info('Extending method invocation due to extended method signature!')

            # generate parameter name for the current method if not already done
            if not parameterName:
                parameterName = get_unused_method_parameter('backend', methodNode)
                app.logger.info('Qiskit Runtime backend not yet available as variable in this method. '
                                'Adding with name: ' + parameterName)

                # append to method signature
                methodNode.arguments.append(parameterName)

            # extend the method invocation with the new parameter
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
    return methodNode.name, inputParameterList, signatureExtendedWithBackend, backendSignaturePositions


def replace_qiskit_execute(assignmentNodes, methodNode):
    """Search for a qiskit.execute() command which has to be replaced by backend.run() for Qiskit Runtime"""
    app.logger.info('Checking for qiskit.execute call in method: ' + methodNode.name)

    name = None
    signatureExtensionRequired = False
    backendSignaturePositions = []
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
        circuitArgumentName = assignmentNode.value[2].value.find('call_argument',
                                                                 target=lambda target: target and (
                                                                         target.value == 'experiments'))

        # otherwise the circuit is the first positional argument
        if circuitArgumentName:
            circuitArgumentName = circuitArgumentName.value
        else:
            circuitArgumentName = assignmentNode.value[2].value[0].value

        # check if backend to use is explicitly defined under the 'backend' parameters
        backendArgumentName = assignmentNode.value[2].value.find('call_argument',
                                                                 target=lambda target: target and (
                                                                         target.value == 'backend'))

        # otherwise the backend is the second positional argument
        if backendArgumentName:
            backendArgumentName = backendArgumentName.value
        else:
            backendArgumentName = assignmentNode.value[2].value[1].value
        app.logger.info('Backend variable name for qiskit.execute(): ' + backendArgumentName.value)

        # check if backend is assigned locally
        signatureExtension, backendSignaturePositions, name = check_qiskit_backend_assignment(methodNode,
                                                                                              assignmentNodes,
                                                                                              name,
                                                                                              backendSignaturePositions,
                                                                                              backendArgumentName.value)
        if signatureExtension:
            # signature must be extended to pass the backend
            signatureExtensionRequired = True

        # replace the call with the qiskit runtime backend call
        app.logger.info('Replacing qiskit.execute with call to Qiskit Runtime backend in method: ' + methodNode.name)
        assignmentNode.value = backendArgumentName.value + ".run(" + circuitArgumentName.value + ")"

    return signatureExtensionRequired, name, backendSignaturePositions


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


def check_qiskit_backend_assignment(methodNode, assignmentNodes, backendName, backendSignaturePositions, variableName):
    """Check if the Qiskit backend for a circuit execution is assigned locally or in the method signature"""

    backendAssignment = find_element_with_name(assignmentNodes, 'assign', variableName)
    if backendAssignment:

        if not backendName:
            backendName = get_unused_method_parameter('backend', methodNode)
            app.logger.info('Qiskit Runtime backend not yet available as variable in this method. '
                            'Adding with name: ' + backendName)

            # append to method signature
            methodNode.arguments.append(backendName)

        # instead pass Qiskit Runtime backend as parameter
        backendAssignment.value = backendName

        # signature must be extended to pass the backend
        return True, backendSignaturePositions, backendName
    else:
        app.logger.info('Searching for parameter ' + variableName + ' within method signature')

        # check if backend is passed through the signature
        backendSignatureParam = find_element_with_name(methodNode.arguments, 'def_argument', variableName)
        if backendSignatureParam:
            # get position within the signature
            backendSignaturePosition = methodNode.arguments.find_all('def_argument').index(backendSignatureParam)
            if backendSignaturePosition not in backendSignaturePositions:
                backendSignaturePositions.append(backendSignaturePosition)
        else:
            app.logger.error(
                'Backend used for qiskit.execute neither defined as method parameter nor as local variable!')
        return False, backendSignaturePositions, None


def find_element_with_name(assignmentNodes, type, name):
    """Get the RedBaron object with the given type and name out of the set of given RedBaron objects if available"""
    return assignmentNodes.find(type, target=lambda target: target.type == 'name' and (target.value == name))


def is_native_reference(name):
    """Check if the given name belongs to a natively supported method of Python"""
    return name in ['int', 'str', 'len', 'filter', 'enumerate', 'float', 'list', 'dict', 'pow', 'sum']
