# qiskit-runtime-handler

TODO

## Docker Setup

TODO

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
