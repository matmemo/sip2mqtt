FROM docker.io/library/python:3.13-trixie

RUN <<EOF
mkdir /app
groupadd -g 1000 sip2mqtt
useradd -M -d /app -g 1000 -u 1000 sip2mqtt
chown 1000:1000 /app
EOF

COPY docker/run.sh /
RUN chown 1000:1000 /run.sh && chmod +x /run.sh

COPY sip2mqtt.py /app/
RUN chown 1000:1000 /app/sip2mqtt.py

USER 1000:1000

RUN --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt <<EOF
cd /app
pip install -r /tmp/requirements.txt
EOF

ENTRYPOINT /run.sh
