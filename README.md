# qiskit-runtime-handler

TODO

## Docker Setup

TODO

## Local Setup

TODO

### Database
* Install SQLite DB, e.g., as described [here](https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-iv-database)
* Create a `data` folder in the `app` folder
* Setup the results table with the following commands:
```
flask db migrate -m "results table"
flask db upgrade
```
