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
import json


@app.route('/qiskit-runtime-handler/api/v1.0/generate-hybrid-program', methods=['POST'])
def generate_hybrid_program():
    """Put hybrid program generation job in queue. Return location of the later result."""
    logging.info('Received request: ', request)
    if not request.json or not 'qpu-name' in request.json or not 'token' in request.json:
        abort(400)
    qpu_name = request.json['qpu-name']
    token = request.json['token']
    shots = request.json.get('shots', 8192)

    # TODO: params

    job = app.execute_queue.enqueue('app.tasks.generate_hybrid_program', qpu_name=qpu_name, token=token,
                                    shots=shots, job_timeout=18000)
    result = Result(id=job.get_id())
    db.session.add(result)
    db.session.commit()

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
