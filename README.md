# sip2mqtt

`sip2mqtt` is a lightweight SIP client that registers with both a SIP registrar and an MQTT broker. It listens for incoming SIP calls (INVITE events), publishes the call details to MQTT, and then hangs up (denies) the call.

## Purpose / Use Case

Many modern door communication units use the SIP protocol over Ethernet to provide audio and video communication. When a visitor presses a button on the outdoor unit, it initiates a SIP call to a configured indoor unit.

`sip2mqtt` is designed to detect these call events and forward them to an MQTT broker. This allows integration with home automation systems, enabling actions such as notifications, logging, or triggering other automation workflows when someone rings the doorbell.

## Features

- Registers with SIP and MQTT
- Listens for incoming SIP INVITE events
- Publishes call details to MQTT
- Automatically hangs up (denies the call) after publishing

## Configuration

`sip2mqtt` is configured using environment variables, typically provided in a `.env` file using [dotenv](https://github.com/theskumar/python-dotenv) format. This file should be placed in the same directory where you run the utility.

### Example `.env` File

```
# MQTT settings
MQTT_HOST=mqtt.example.com
MQTT_PORT=1883
MQTT_BASETOPIC=sip2mqtt
MQTT_USER=
MQTT_PASS=

# SIP registrar settings
SIP_REGISTRAR_HOST=sip.example.com
SIP_REGISTRAR_PORT=5060
SIP_USER=
SIP_PASS=

# SIP client network settings
SIP_CLIENT_ADDR=<external IP>        # Public IP address to advertise in SIP messages
SIP_CLIENT_PORT=55060                # Port used for incoming SIP traffic
SIP_BIND_ADDR=0.0.0.0                # Local interface to bind for SIP listening
```

### Configuration Variables

#### MQTT Settings

| Variable         | Description                            | Required | Default  |
|------------------|----------------------------------------|----------|----------|
| `MQTT_HOST`      | MQTT broker hostname or IP             | ✅ Yes   | —        |
| `MQTT_PORT`      | MQTT broker port                       | ✅ Yes   | —        |
| `MQTT_BASETOPIC` | Base topic used for MQTT messages      | ✅ Yes   | —        |
| `MQTT_USER`      | Username for MQTT authentication       | ❌ No    | *(empty)* |
| `MQTT_PASS`      | Password for MQTT authentication       | ❌ No    | *(empty)* |

#### SIP Registrar Settings

| Variable              | Description                      | Required | Default |
|------------------------|----------------------------------|----------|---------|
| `SIP_REGISTRAR_HOST`   | SIP registrar hostname or IP     | ✅ Yes   | —       |
| `SIP_REGISTRAR_PORT`   | SIP registrar port               | ✅ Yes   | —       |
| `SIP_USER`             | SIP username                     | ✅ Yes   | —       |
| `SIP_PASS`             | SIP password                     | ✅ Yes   | —       |

#### SIP Client Network Settings

| Variable           | Description                                                                 | Required | Default   |
|--------------------|-----------------------------------------------------------------------------|----------|-----------|
| `SIP_CLIENT_ADDR`  | Public IP address to include in SIP messages (for NAT traversal)            | ✅ Yes   | —         |
| `SIP_CLIENT_PORT`  | Port the client will use to receive SIP messages                            | ✅ Yes   | —         |
| `SIP_BIND_ADDR`    | Local network interface to bind the SIP listener (e.g. `0.0.0.0`)           | ✅ Yes   | `0.0.0.0` |


## Running via Podman

You can run `sip2mqtt` in a container using [Podman](https://podman.io/). Below are the steps to build and run the container locally.

### Prerequisites

- [Podman](https://podman.io/) installed on your system
- A `.env` file with all required configuration variables (see [Configuration](#configuration))

### 1. Build the Container

Run the following command in the project root directory (where the Containerfile and `.env` file are located):

```bash
podman build -t sip2mqtt:latest .
```

This will build a local container image named `sip2mqtt:latest`.

### 2. Run the Container (Foreground)

```bash
podman run -it --rm \
  -p 55060:55060/udp \
  --env-file=.env \
  sip2mqtt:latest
```

- `--env-file=.env`: Loads environment variables from the `.env` file.
- `-p 55060:55060/udp`: Exposes the SIP UDP port to the host (adjust if needed).
- `--rm`: Automatically removes the container after it exits.
- `-it`: Runs the container in interactive mode for logging/output.

> **Note:** SIP typically uses UDP, so ensure the port is published with `/udp`.


### 3. Run the Container in Background (Daemonized)

```bash
podman run -d \
  --name sip2mqtt \
  --env-file=.env \
  -p 55060:55060/udp \
  sip2mqtt:latest
```

### Persisting the Installation

To run the application persistently, you can use tools like Docker Compose or Podman Quadlets, depending on your environment.

While covering every deployment option is beyond the scope of this documentation, you can refer to the example setups provided in the `compose/` and `quadlet/` directories. These should help you get started with a persistent setup tailored to your needs.
