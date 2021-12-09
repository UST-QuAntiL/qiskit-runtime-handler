[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

# qiskit-runtime-handler

This service takes a workflow fragment realizing a hybrid algorithm as input and generates a [Qiskit Runtime](https://quantum-computing.ibm.com/lab/docs/iql/runtime/) program to benefit from speedups and reduced queuing times.
Additionally, an agent is generated which handles the transfer of input/output parameters between the Qiskit Runtime program and a workflow.

## Docker Setup

* Clone the repository:
```
git clone https://github.com/UST-QuAntiL/qiskit-runtime-handler.git
```

* Start the containers using the [docker-compose file](docker-compose.yml):
```
docker-compose pull
docker-compose up
```

Now the qiskit-runtime-handler is available on http://localhost:8889/.

## Local Setup

### Start Redis

Start Redis, e.g., using Docker:

```
docker run -p 5040:5040 redis --port 5040
```

### Configure the Qiskit Runtime Handler

Before starting the Qiskit Runtime handler, define the following environment variables:

```
FLASK_RUN_PORT=8889
REDIS_URL=redis://$DOCKER_ENGINE_IP:5040
```

Thereby, please replace $DOCKER_ENGINE_IP with the actual IP of the Docker engine you started the Redis container.

### Configure the Database

* Install SQLite DB, e.g., as described [here](https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-iv-database)
* Create a `data` folder in the `app` folder
* Setup the results table with the following commands:

```
flask db migrate -m "results table"
flask db upgrade
```

### Start the Application

Start a worker for the request queue:

```
rq worker --url redis://$DOCKER_ENGINE_IP:5040 qiskit-runtime-handler
```

Finally, start the Flask application, e.g., using PyCharm or the command line.
