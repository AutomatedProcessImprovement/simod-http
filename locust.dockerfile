FROM locustio/locust:2.15.1

ADD tests/assets /home/locust/assets
ADD tests/locustfile.py /home/locust/locustfile.py
ADD tests/run.sh /home/locust/run.sh

WORKDIR /home/locust

ENV PYTHONUNBUFFERED=1

EXPOSE 8089
EXPOSE 5557

ENTRYPOINT ["bash", "run.sh"]
