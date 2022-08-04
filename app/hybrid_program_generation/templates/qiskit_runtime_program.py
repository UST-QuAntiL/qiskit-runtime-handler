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

from typing import Any


def main(backend, user_messenger, **kwargs) -> Any:
    """Main entry point of the program.

    Args:
        backend (qiskit.providers.Backend): Backend to submit the circuits to.
        user_messenger (qiskit.providers.ibmq.runtime.UserMessenger): Used to communicate with the
            program consumer.
        kwargs: User inputs.

    Returns:
        Final result of the program.
    """
    currentIteration = 1

    return "Done"
