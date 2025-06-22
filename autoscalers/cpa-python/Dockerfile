FROM custompodautoscaler/python:latest

ADD requirements.txt .

RUN pip install -r requirements.txt

ADD config.yaml /

ADD scripts /scripts