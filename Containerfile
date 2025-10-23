### build stage
FROM docker.io/library/python:3.13-trixie AS builder
ENV PYTHONUNBUFFERED 1

RUN mkdir /app
WORKDIR /app
RUN --mount=type=bind,source=requirements.txt,target=/tmp/requirements.txt <<EOF
python -m venv .venv
. ./.venv/bin/activate
pip install -Ur /tmp/requirements.txt
EOF


### prepare runner
FROM docker.io/library/python:3.13-slim AS runner

RUN <<EOF
mkdir /app
groupadd -g 1000 sip2mqtt
useradd -M -d /app -g 1000 -u 1000 sip2mqtt
# chown 1000:1000 /app
EOF

USER 1000:1000
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY sip2mqtt.py /app/sip2mqtt.py

ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT [ "python", "sip2mqtt.py" ]
