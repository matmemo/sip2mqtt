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

run_flag = True
mqtt_online_flag = False
sip_online_flag = False

mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_unacked_publish = set()

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
                f"SIP_CLIENT_ADDR: {self.SIP_CLIENT_ADDR}\n"
                f"SIP_CLIENT_PORT: {self.SIP_CLIENT_PORT}"
        )

# mqtt client callbacks
def mqtt_on_connect(client, userdata, flags, reason_code, properties):
    global mqtt_online_flag
    logging.info(f"mqtt broker connection established with result code: {reason_code}")
    mqtt_online_flag = True

def mqtt_on_connect_fail(client, userdata):
    global run_flag
    logging.error("Connection to mqtt broker failed. Exiting")
    run_flag = False

def mqtt_on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    global mqtt_online_flag
    logging.info("Disconnected from mqtt broker")
    mqtt_online_flag = False

def mqtt_on_publish(client, userdata, mid, reason_code, properties):
    try:
        userdata.remove(mid)
    except KeyError:
        print("on_publish() is called with a mid not present in unacked_publish")

def mqtt_init(config):
    global mqttc, mqtt_unacked_publish
    mqttc.on_connect = mqtt_on_connect
    mqttc.on_connect_fail = mqtt_on_connect_fail
    mqttc.on_disconnect = mqtt_on_disconnect
    mqttc.on_publish = mqtt_on_publish

    mqttc.user_data_set(mqtt_unacked_publish)

    logging.info(f"Trying to connect to mqtt broker {config.MQTT_HOST}:{config.MQTT_PORT}")
    mqttc.will_set(config.MQTT_BASETOPIC + "/status", "offline", qos=0, retain=True)
    mqttc.connect(config.MQTT_HOST, config.MQTT_PORT, 60)
    mqttc.loop_start()

    mqtt_publish_status(config, "online")

    return mqttc

def mqtt_publish(topic, message):
    global mqttc, mqtt_unacked_publish
    msg_info = mqttc.publish(config.MQTT_BASETOPIC, message, qos=1)
    mqtt_unacked_publish.add(msg_info.mid)

    while len(mqtt_unacked_publish):
        time.sleep(0.1)

    msg_info.wait_for_publish()

def mqtt_publish_retained(topic, message):
    global mqttc, mqtt_unacked_publish
    msg_info = mqttc.publish(config.MQTT_BASETOPIC, message, qos=1, retain=True)
    mqtt_unacked_publish.add(msg_info.mid)

    while len(mqtt_unacked_publish):
        time.sleep(0.1)

    msg_info.wait_for_publish()

def mqtt_publish_status(config, status):
    mqtt_publish_retained(config.MQTT_BASETOPIC + "/status", status)

# sip client callbacks
def sip_handle_call(call):
    try:
        sip_message = call.request
        mqtt_message = {
            "type": "request",
            "method": sip_message.method,
            "headers": sip_message.headers
        }

        # print(f"Method: {sip_message.method}")
        # print(f"Headers: {json.dumps(sip_message.headers, indent=4)}")

        mqtt_publish(config.MQTT_BASETOPIC + "/event", json.dumps(mqtt_message))

        time.sleep(0.5)
        call.deny()
    except InvalidStateError:
        pass
  
def sip_init(config):
    sip_client = VoIPPhone(
            server = config.SIP_REGISTRAR_HOST,
            port = config.SIP_REGISTRAR_PORT,
            username = config.SIP_USER,
            password = config.SIP_PASS,
            myIP = config.SIP_CLIENT_ADDR,
            callCallback = sip_handle_call,
            sipPort = config.SIP_CLIENT_PORT
    )

    sip_client.start()

    return sip_client

if __name__ == "__main__":
    load_dotenv()
    config = Config()

    format = "%(asctime)s: %(message)s"
    logging.basicConfig(format=format, level=logging.INFO,
                        datefmt="%Y-%m-%d %H:%M:%S")

    logging.info("sip2mqtt started. Config: \n" + str(config))

    def stop_signals_handler(_signo, _stack_frame):
        global run_flag
        logging.info("Received termination event")
        run_flag = False

    signal.signal(signal.SIGINT, stop_signals_handler)
    signal.signal(signal.SIGTERM, stop_signals_handler)

    mqttc = mqtt_init(config)
    while run_flag and not mqtt_online_flag:
        time.sleep(0.1)

    sip_client = sip_init(config)
    logging.info("sip client started")
    logging.info("listening")

    while run_flag:
        time.sleep(0.1)

    sip_client.stop()
    logging.info("sip client stopped")

    mqtt_publish_status(config, "offline")
    mqttc.disconnect()
    mqttc.loop_stop()
    logging.info("mqtt client stopped")

    logging.info("Exiting")
