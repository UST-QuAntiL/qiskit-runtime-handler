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

from flask_smorest import Blueprint
from flask import current_app as app
from flask import jsonify, abort, request, send_from_directory, url_for
import logging
import os
import string
import random

blp = Blueprint(
    "qiskit_runtime",
    __name__,
    url_prefix="/qiskit_runtime",
    description="Generate Qiskit Runtime programs",
)


@blp.route('/qiskit-runtime-handler/api/v1.0/generate-hybrid-program', methods=['POST'])
def generate_hybrid_program():
    """Put hybrid program generation job in queue. Return location of the later result."""

    # extract required input data
    if not request.form.get('beforeLoop') or not request.form.get('afterLoop') \
            or not request.form.get('loopCondition') \
            or not request.files['requiredPrograms']:
        print('Not all required parameters available in request: ')
        if not request.form.get('beforeLoop'):
            print('beforeLoop parameter is missing!')
        if not request.form.get('afterLoop'):
            print('afterLoop parameter is missing!')
        if not request.form.get('loopCondition'):
            print('loopCondition parameter is missing!')
        if not request.files['requiredPrograms']:
            print('requiredPrograms parameter is missing!')
        abort(400)
    beforeLoop = request.form.get('beforeLoop')
    afterLoop = request.form.get('afterLoop')
    loopCondition = request.form.get('loopCondition')
    requiredPrograms = request.files['requiredPrograms']
    print('Received request for hybrid program generation...')

    # retrieve provenance collection boolean from request
    if request.form.get('provenanceCollection'):
        provenanceCollection = request.form.get('provenanceCollection').lower() == 'true'
    else:
        provenanceCollection = False
    print('Provenance collection intended for hybrid program: ' + str(provenanceCollection))

    # store file with required programs in local file and forward path to the workers
    directory = app.config["UPLOAD_FOLDER"]
    print('Storing file comprising required programs at folder: ' + str(directory))
    if not os.path.exists(directory):
        os.makedirs(directory)
    randomString = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
    fileName = 'required-programs' + randomString + '.zip'
    requiredPrograms.save(os.path.join(directory, fileName))
    url = url_for('download_uploaded_file', name=os.path.basename(fileName))
    print('File available via URL: ' + str(url))

    # execute job asynchronously
    job = app.queue.enqueue('app.tasks.generate_hybrid_program', beforeLoop=beforeLoop, afterLoop=afterLoop,
                            loopCondition=loopCondition, requiredProgramsUrl=url,
                            provenanceCollection=provenanceCollection, job_timeout=18000)
    print('Added job for hybrid program generation to the queue...')
    result = app.model.result_model.Result(id=job.get_id())
    db.session.add(result)
    db.session.commit()

    # return location of task object to retrieve final result
    logging.info('Returning HTTP response to client...')
    content_location = '/qiskit-runtime-handler/api/v1.0/results/' + result.id
    response = jsonify({'Location': content_location})
    response.status_code = 202
    response.headers['Location'] = content_location
    return response


@blp.route('/qiskit-runtime-handler/api/v1.0/results/<result_id>', methods=['GET'])
def get_result(result_id):
    """Return result when it is available."""
    result = Result.query.get(result_id)
    if result.complete:
        if result.error:
            return jsonify({'id': result.id, 'complete': result.complete, 'error': result.error}), 200
        else:
            # create result directory if not existing
            directory = app.config["RESULT_FOLDER"]
            if not os.path.exists(directory):
                os.makedirs(directory)

            # create files and serve as URL
            programName = os.path.join(directory, result.id + '-program.zip')
            with open(programName, 'wb') as file:
                file.write(result.program)
            agentName = os.path.join(directory, result.id + '-agent.zip')
            with open(agentName, 'wb') as file:
                file.write(result.agent)

            return jsonify({'id': result.id, 'complete': result.complete,
                            'programUrl': url_for('download_generated_file', name=result.id + '-program.zip'),
                            'agentUrl': url_for('download_generated_file', name=result.id + '-agent.zip')}), 200
    else:
        return jsonify({'id': result.id, 'complete': result.complete}), 200


@blp.route('/qiskit-runtime-handler/api/v1.0/uploads/<name>')
def download_uploaded_file(name):
    return send_from_directory(app.config["UPLOAD_FOLDER"], name)


@blp.route('/qiskit-runtime-handler/api/v1.0/hybrid-programs/<name>')
def download_generated_file(name):
    return send_from_directory(app.config["RESULT_FOLDER"], name)


@blp.route('/qiskit-runtime-handler/api/v1.0/version', methods=['GET'])
def version():
    return jsonify({'version': '1.0'})
