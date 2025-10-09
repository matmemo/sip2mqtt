#!/usr/bin/env python

import json
import logging
import os
import paho.mqtt.client as mqtt
import signal
import time
import sys

from dotenv import load_dotenv
from pyVoIP.VoIP import VoIPPhone, InvalidStateError

class Config:
    def __init__(self):
        self.MQTT_HOST = self.check_env("MQTT_HOST")
        self.MQTT_PORT = int(self.check_env("MQTT_PORT", 1883))
        self.MQTT_BASETOPIC = self.check_env("MQTT_BASETOPIC")
        self.MQTT_USER = self.check_env("MQTT_USER", "")
        self.MQTT_PASS = self.check_env("MQTT_PASS", "")

        self.SIP_REGISTRAR_HOST = self.check_env("SIP_REGISTRAR_HOST")
        self.SIP_REGISTRAR_PORT = int(self.check_env("SIP_REGISTRAR_PORT", 5060))
        self.SIP_USER = self.check_env("SIP_USER")
        self.SIP_PASS = self.check_env("SIP_PASS")

        self.SIP_CLIENT_ADDR = self.check_env("SIP_CLIENT_ADDR")
        self.SIP_CLIENT_PORT = int(self.check_env("SIP_CLIENT_PORT", 55060))
        self.SIP_BIND_ADDR = self.check_env("SIP_BIND_ADDR", "0.0.0.0")

    def check_env(self, name, default=None):
        if os.getenv(name, default) is not None:
            return os.getenv(name, default)
        else:
            logging.error(f"{name} not set in environment")
            sys.exit(1)

    def __repr__(self):
        return (
                f"MQTT_HOST: {self.MQTT_HOST}\n" \
                f"MQTT_PORT: {self.MQTT_PORT}\n" \
                f"MQTT_BASETOPIC: {self.MQTT_BASETOPIC}\n" \
                f"MQTT_USER: {self.MQTT_USER}\n" \
                f"MQTT_PASS: {"*" * len(self.MQTT_PASS) * 2}\n" \
                f"SIP_REGISTRAR_HOST: {self.SIP_REGISTRAR_HOST}\n" \
                f"SIP_REGISTRAR_PORT: {self.SIP_REGISTRAR_PORT}\n" \
                f"SIP_USER: {self.SIP_USER}\n" \
                f"SIP_PASS: {"*" * len(self.SIP_PASS) * 2}\n" \
                f"SIP_CLIENT_ADDR: {self.SIP_CLIENT_ADDR}\n" \
                f"SIP_CLIENT_PORT: {self.SIP_CLIENT_PORT}\n" \
                f"SIP_BIND_ADDR: {self.SIP_BIND_ADDR}"
        )

class MqttClient:
    def __init__(self):
        self.online = False
        self.connection_failed = False
        self.mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.unacked_publish = set()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        logging.info(f"mqtt broker connection established with result code: {reason_code}")
        self.online = True

    def _on_connect_fail(self, client, userdata):
        logging.error("Connection to mqtt broker failed. Exiting")
        self.connection_failed = True

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        logging.info("Disconnected from mqtt broker")
        self.online = False

    def _on_publish(self, client, userdata, mid, reason_code, properties):
        try:
            userdata.remove(mid)
        except KeyError:
            logging.error("on_publish() is called with a mid not present in unacked_publish")

    def init(self, config):
        self.mqttc.on_connect = self._on_connect
        self.mqttc.on_connect_fail = self._on_connect_fail
        self.mqttc.on_disconnect = self._on_disconnect
        self.mqttc.on_publish = self._on_publish

        self.mqttc.user_data_set(self.unacked_publish)

        return self.mqttc

    def start(self, config):
        logging.info(f"Trying to connect to mqtt broker {config.MQTT_HOST}:{config.MQTT_PORT}")
        self.mqttc.will_set(config.MQTT_BASETOPIC + "/status", "offline", qos=0, retain=True)
        self.mqttc.connect(config.MQTT_HOST, config.MQTT_PORT, 60)
        self.mqttc.loop_start()

        self.publish_status(config, "online")
        self.online = True

        return self.mqttc

    def stop(self):
        self.publish_status(config, "offline")
        self.mqttc.disconnect()
        logging.info("mqtt client stopped")

    def publish(self, topic, message):
        msg_info = self.mqttc.publish(topic, message, qos=1)
        self.unacked_publish.add(msg_info.mid)

        while len(self.unacked_publish):
            time.sleep(0.1)

        msg_info.wait_for_publish()

    def publish_retained(self, topic, message):
        msg_info = self.mqttc.publish(topic, message, qos=1, retain=True)
        self.unacked_publish.add(msg_info.mid)

        while len(self.unacked_publish):
            time.sleep(0.1)

        msg_info.wait_for_publish()

    def publish_status(self, config, status):
        self.publish_retained(config.MQTT_BASETOPIC + "/status", status)


class SipClient:
    def __init__(self, publisher):
        self.online = False
        self.publisher = publisher

    def _handle_call(self, call):
        try:
            sip_message = call.request
            mqtt_message = {
                "type": "request",
                "method": sip_message.method,
                "headers": sip_message.headers
            }

            logging.info(f"sip {sip_message.method} received")
            # logging.debug(json.dumps(mqtt_message, indent=2)}")
            self.publisher(json.dumps(mqtt_message))

            time.sleep(0.5)
            call.deny()
        except InvalidStateError:
            pass
      
    def init(self, config):
        self.client = VoIPPhone(
                server = config.SIP_REGISTRAR_HOST,
                port = config.SIP_REGISTRAR_PORT,
                username = config.SIP_USER,
                password = config.SIP_PASS,
                myIP = config.SIP_CLIENT_ADDR,
                callCallback = self._handle_call,
                bindIP = config.SIP_BIND_ADDR,
                sipPort = config.SIP_CLIENT_PORT
        )

        return self.client

    def start(self, config):
        self.client.start()
        self.online = True
        logging.info("sip client started")

    def stop(self):
        self.client.stop()
        self.online = False
        logging.info("sip client stopped")

if __name__ == "__main__":
    # load config
    load_dotenv()
    config = Config()

    # setup logging
    format = "%(asctime)s: %(message)s"
    logging.basicConfig(format=format, level=logging.INFO, datefmt="%Y-%m-%d %H:%M:%S")

    logging.info("sip2mqtt initializing. Config: \n" + str(config))

    # setup signal handlers
    run_flag = True
    def stop_signals_handler(_signo, _stack_frame):
        global run_flag
        logging.info("Received termination event")
        run_flag = False

    signal.signal(signal.SIGINT, stop_signals_handler)
    signal.signal(signal.SIGTERM, stop_signals_handler)

    # setup mqtt client
    mqttc = MqttClient()

    # define publisher callback for SipClient
    def publisher(message):
        mqttc.publish(config.MQTT_BASETOPIC + "/event", message)

    # setup sip client
    sipc = SipClient(publisher)

    # start mqtt client
    mqttc.init(config)
    mqttc.start(config)
    while run_flag and not mqttc.online:
        time.sleep(0.1)

    # start sip client
    sipc.init(config)
    sipc.start(config)
    while run_flag and not sipc.online:
        time.sleep(0.1)

    # loop until stopped
    logging.info("listening...")
    while run_flag:
        time.sleep(0.5)

    # wind down
    sipc.stop()
    mqttc.stop()

    logging.info("Exiting")
