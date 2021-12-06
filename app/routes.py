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

from app import app, db
from app.result_model import Result
from flask import jsonify, abort, request
import logging
import tempfile
import os
import json


@app.route('/qiskit-runtime-handler/api/v1.0/generate-hybrid-program', methods=['POST'])
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
    app.logger.info('Received request for hybrid program generation...')

    # TODO
    print(requiredPrograms)
    new_file, filename = tempfile.mkstemp()
    requiredPrograms.save(os.path.join(filename))
    print(filename)

    # execute job asynchronously
    job = app.queue.enqueue('app.tasks.generate_hybrid_program', beforeLoop=beforeLoop, afterLoop=afterLoop,
                            loopCondition=loopCondition, requiredProgramsPath=filename, job_timeout=18000)
    app.logger.info('Added job for hybrid program generation to the queue...')
    result = Result(id=job.get_id())
    db.session.add(result)
    db.session.commit()

    # return location of task object to retrieve final result
    logging.info('Returning HTTP response to client...')
    content_location = '/qiskit-runtime-handler/api/v1.0/results/' + result.id
    response = jsonify({'Location': content_location})
    response.status_code = 202
    response.headers['Location'] = content_location
    return response


@app.route('/qiskit-runtime-handler/api/v1.0/results/<result_id>', methods=['GET'])
def get_result(result_id):
    """Return result when it is available."""
    result = Result.query.get(result_id)
    if result.complete:
        result_dict = json.loads(result.result)
        return jsonify({'id': result.id, 'complete': result.complete, 'result': result_dict}), 200
    else:
        return jsonify({'id': result.id, 'complete': result.complete}), 200


@app.route('/qiskit-runtime-handler/api/v1.0/version', methods=['GET'])
def version():
    return jsonify({'version': '1.0'})
