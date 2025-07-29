FROM python:3-bookworm

WORKDIR /

RUN apt-get update && apt-get install wget -y

RUN wget \
    -qO- \
    https://github.com/jthomperoo/custom-pod-autoscaler/releases/download/v2.12.2/custom-pod-autoscaler.tar.gz \
    | tar xz \
    && mv dist/* /app/

RUN rm -r dist/

ADD requirements.txt .

RUN pip install -r requirements.txt

ENV configPath=/config.yaml
ADD config.yaml /

ADD scripts /scripts

CMD [ "/app/custom-pod-autoscaler" ]
