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

from sqlalchemy import LargeBinary
from flask import current_app as app


class Result(app.db.Model):
    id = app.db.Column(app.db.String(36), primary_key=True)
    program = app.db.Column('program', LargeBinary)
    agent = app.db.Column('agent', LargeBinary)
    error = app.db.Column(app.db.String(1200), default="")
    complete = app.db.Column(app.db.Boolean, default=False)

    def __repr__(self):
        return 'Result {}'.format(self.complete)
