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
from zipfile import ZipFile

from app import app
from redbaron import RedBaron, NameNode


def create_hybrid_program(beforeLoop, afterLoop, loopCondition, taskIdProgramMap):

    # directory containing all templates required for generation
    templatesDirectory = os.path.join(os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__))), 'templates')

    # RedBaron object containing all information about the hybrid program to generate
    with open(os.path.join(templatesDirectory, 'qiskit_runtime_program.py'), "r") as source_code:
        hybridProgramBaron = RedBaron(source_code.read())

    # TODO
    print(hybridProgramBaron)
    print(len(hybridProgramBaron))
    print(taskIdProgramMap)
    print(beforeLoop)
    print(afterLoop)
    print(loopCondition)

    if beforeLoop:
        beforeLoop = beforeLoop.split(",")
        for task in beforeLoop:
            app.logger.info('Adding logic for task with ID ' + str(task) + ' before loop!')

            if task not in taskIdProgramMap:
                return {'error': 'Unable to find program related to task with ID: ' + task}
            try:
                hybridProgramBaron, methodName = handle_program(hybridProgramBaron, taskIdProgramMap[task], task)
            except Exception as error:
                return {'error': 'Failed to analyse and incorporate Python file for task with ID ' + task + '!\n'
                                 + str(error)}

    if afterLoop:
        afterLoop = afterLoop.split(",")
        for task in afterLoop:
            app.logger.info('Adding logic for task with ID ' + str(task) + ' after loop!')

            if task not in taskIdProgramMap:
                return {'error': 'Unable to find program related to task with ID: ' + task}
            hybridProgramBaron = handle_program(hybridProgramBaron, taskIdProgramMap[task])

    # write generated hybrid program code to result file
    tmp = tempfile.NamedTemporaryFile(suffix=".py", delete=False)
    with open(tmp.name, "w") as source_code:
        source_code.write(hybridProgramBaron.dumps())

    # zip generated hybrid program and meta data files
    if os.path.exists('result.zip'):
        os.remove('result.zip')
    zipObj = ZipFile('result.zip', 'w')
    zipObj.write(tmp.name, 'hybrid_program.py') # TODO: add metadata
    zipObj.close()
    zipObj = open('result.zip', "rb")
    data = zipObj.read()

    # TODO
    result = {'program': data}
    return result


def handle_program(hybridProgramBaron, path, task):
    """ Handle a program of the candidate and add the execute method,
    as well as all dependent code to the given RedBaron object"""

    # separator between code snippets from different programs
    hybridProgramBaron.append('##############################################')
    hybridProgramBaron.append('# Code snippets for file ' + basename(path))
    hybridProgramBaron.append('##############################################')

    with open(path, "r") as source_code:
        taskFile = RedBaron(source_code.read())

        # find the 'execute' method within the file
        executeNodes = taskFile.find_all('def', name='execute')

        # if not found abort the generation
        if len(executeNodes) != 1:
            raise Exception('Unable to find execute method in program: ' + basename(path))
        executeNode = executeNodes[0]

        # add the execute method and all depending methods to the RedBaron object
        methodName = add_method_recursively(hybridProgramBaron, taskFile, executeNode, task)

    return hybridProgramBaron, methodName


def add_method_recursively(hybridProgramBaron, taskFile, methodNode, prefix):
    """Add the given method node and all dependent methods, i.e., called methods to the given RedBaron object."""
    print('Recursively adding methods. Current method name: ' + methodNode.name)

    # get assignment nodes and check if they call local methods
    assignmentNodes = methodNode.find_all('assignment')

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
        addedMethodName = add_method_recursively(hybridProgramBaron, taskFile, recursiveMethodNode, prefix)
        calledMethodNameNode.value = addedMethodName

    # add prefix for corresponding file to the method name to avoid name clashes when merging multiple files
    methodNode.name = prefix + '_' + methodNode.name

    print(methodNode.help())

    # add the method to the given RedBaron object
    hybridProgramBaron.append('\n')
    hybridProgramBaron.append(methodNode)
    return methodNode.name


def is_native_reference(name):
    """Check if the given name belongs to a natively supported method of Python"""
    return name in ['int', 'str', 'len', 'filter', 'enumerate', 'float', 'list', 'dict']
