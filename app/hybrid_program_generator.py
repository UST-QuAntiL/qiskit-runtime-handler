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

from app import app


def create_hybrid_program(beforeLoop, afterLoop, loopCondition, taskIdProgramMap):
    # TODO
    print(taskIdProgramMap)
    print(beforeLoop)
    print(afterLoop)
    print(loopCondition)

    for task in beforeLoop:
        app.logger.info('Adding logic for task with ID ' + str(task) + ' before loop!')

    for task in afterLoop:
        app.logger.info('Adding logic for task with ID ' + str(task) + ' after loop!')

    result = {'error': 'TODO'}

    return result
