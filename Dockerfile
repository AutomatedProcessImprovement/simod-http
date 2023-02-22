FROM nokal/simod:v3.2.1

WORKDIR /usr/src/Simod/
ADD run.sh .

ENV DISPLAY=:99
ENV SIMOD_HTTP_DEBUG=false

CMD ["/bin/bash", "run.sh"]
