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

from os import listdir
from tempfile import mkdtemp

from app import app
import zipfile
import os


def search_python_file(directory):
    # only .py are supported, also nested in zip files
    containedPythonFiles = [f for f in listdir(os.path.join(directory)) if f.endswith('app.py')]
    if len(containedPythonFiles) >= 1:
        app.logger.info('Found Python file with name: ' + str(containedPythonFiles[0]))

        # we only support one file, in case there are multiple files, try the first one
        return os.path.join(directory, containedPythonFiles[0])

    # check if there are nested Python files
    containedZipFiles = [f for f in listdir(os.path.join(directory)) if f.endswith('.zip')]
    for zip in containedZipFiles:

        # extract the zip file
        with zipfile.ZipFile(os.path.join(directory, zip), "r") as zip_ref:
            folder = mkdtemp()
            app.logger.info('Extracting to directory: ' + str(folder))
            zip_ref.extractall(folder)

            # recursively search within zip
            result = search_python_file(folder)

            # return if we found the first Python file
            if result is not None:
                return os.path.join(folder, result)

    return None


def zip_runtime_program(hybridProgramTemp, metaDataTemp):
    if os.path.exists('../hybrid_program.zip'):
        os.remove('../hybrid_program.zip')
    zipObj = zipfile.ZipFile('../hybrid_program.zip', 'w')
    zipObj.write(hybridProgramTemp.name, 'hybrid_program.py')
    zipObj.write(metaDataTemp.name, 'hybrid_program.json')
    zipObj.close()
    zipObj = open('../hybrid_program.zip', "rb")
    return zipObj.read(), '../hybrid_program.zip'


def zip_polling_agent(templatesDirectory, pollingAgentTemp, hybridProgram):
    # zip generated polling agent, afterwards zip resulting file with required Dockerfile
    if os.path.exists('../polling_agent.zip'):
        os.remove('../polling_agent.zip')
    if os.path.exists('../polling_agent_wrapper.zip'):
        os.remove('../polling_agent_wrapper.zip')
    zipObj = zipfile.ZipFile('../polling_agent.zip', 'w')
    zipObj.write(pollingAgentTemp.name, 'polling_agent.py')
    zipObj.write(hybridProgram, 'hybrid_program.zip')
    zipObj.close()
    zipObj = zipfile.ZipFile('../polling_agent_wrapper.zip', 'w')
    zipObj.write('../polling_agent.zip', 'service.zip')
    zipObj.write(os.path.join(templatesDirectory, 'Dockerfile'), 'Dockerfile')
    zipObj = open('../polling_agent_wrapper.zip', "rb")
    return zipObj.read()
