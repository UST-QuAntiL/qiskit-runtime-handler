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

from app import db, app
from app.hybrid_program_generation import hybrid_program_generator
from rq import get_current_job

from app.hybrid_program_generation.zip_handler import search_python_file
from app.result_model import Result
import zipfile
import os
import urllib.request


def generate_hybrid_program(beforeLoop, afterLoop, loopCondition, requiredProgramsUrl):
    """Generate the hybrid program for the given candidate and save the result in db"""
    job = get_current_job()

    # get URL to the ZIP file with the required programs
    url = 'http://' + os.environ.get('FLASK_RUN_HOST') + ':' + os.environ.get('FLASK_RUN_PORT') + requiredProgramsUrl

    # download the ZIP file
    app.logger.info('Downloading required programs from: ' + str(url))
    downloadPath, response = urllib.request.urlretrieve(url, "requiredPrograms.zip")

    # dict to store task IDs and the paths to the related programs
    taskIdProgramMap = {}

    # extract the zip file
    with zipfile.ZipFile(downloadPath, "r") as zip_ref:
        directory = mkdtemp()
        app.logger.info('Extracting to directory: ' + str(directory))
        zip_ref.extractall(directory)

        # zip contains one folder per task within the candidate
        zipContents = [f for f in listdir(directory)]
        for zipContent in zipContents:
            app.logger.info('Searching for program related to task with ID: ' + str(zipContent))

            # search for Python file and store with ID if found
            pythonFile = search_python_file(os.path.join(directory, zipContent))
            if pythonFile is not None:
                taskIdProgramMap[zipContent] = pythonFile

    # create the hybrid program and a corresponding invoking agent
    programCreationResult = hybrid_program_generator.create_hybrid_program(beforeLoop, afterLoop, loopCondition,
                                                                           taskIdProgramMap)

    # insert results into job object
    result = Result.query.get(job.get_id())
    if 'error' not in programCreationResult:
        app.logger.info('Program generation successful!')
        result.program = programCreationResult.program
        result.agent = programCreationResult.agent
    else:
        app.logger.info('Program generation failed!')
        result.error = programCreationResult['error']

    # update database
    result.complete = True
    db.session.commit()
