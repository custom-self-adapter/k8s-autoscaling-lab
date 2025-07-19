FROM registry.k8s.lab/custom-self-adapter:python-3-12-latest

COPY requirements.txt .

RUN pip install -r requirements.txt

ADD config.yaml /

COPY scripts /scripts
