FROM python:3.7-slim

MAINTAINER Benjamin Weder "benjamin.weder@iaas.uni-stuttgart.de"

COPY ./requirements.txt /requirements.txt
WORKDIR /
RUN apt-get update
RUN apt-get install -y gcc python3-dev
RUN pip install -r requirements.txt
COPY . /

EXPOSE 8889/tcp

ENV FLASK_APP=qiskit-runtime-handler.py
ENV FLASK_ENV=development
ENV FLASK_DEBUG=0
RUN echo "python -m flask db upgrade" > /startup.sh
RUN echo "gunicorn qiskit-runtime-handler:app -b 0.0.0.0:8889 -w 4 --timeout 500 --log-level info" >> /startup.sh
CMD [ "sh", "/startup.sh" ]
