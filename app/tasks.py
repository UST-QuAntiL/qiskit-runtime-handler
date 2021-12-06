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

from app import db
from rq import get_current_job

from app.result_model import Result
import json


def generate_hybrid_program(token, qpu_name, shots):
    """Calculate the current calibration matrix for the given QPU and save the result in db"""
    job = get_current_job()

    # TODO

    result = Result.query.get(job.get_id())
    result.error = json.dumps({'error': 'Failed to generate hybrid program'})
    result.complete = True
    db.session.commit()
