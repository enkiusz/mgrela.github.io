#!/usr/bin/env python

from re import I
import sys
import argparse
import logging
import structlog
import requests
from xml.dom.minidom import parseString
import base64
from struct import unpack, calcsize
from hexdump import hexdump
import fileinput
from datetime import timedelta

# Default logging configuration
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr)
)

# Reference: https://stackoverflow.com/a/49724281
LOG_LEVEL_NAMES = [logging.getLevelName(v) for v in
                   sorted(getattr(logging, '_levelToName', None) or logging._levelNames) if getattr(v, "real", 0)]


log = structlog.get_logger()

def format_eui64(b):
    b = list(b)
    b.reverse()
    return ':'.join([ f'{v:02x}' for v in b])


def consume(b, formatstring):
    datasize = calcsize(formatstring)

    try:
        unpacked = unpack(formatstring, b[0:datasize])
        b = b[datasize:]
    except Exception as e:
        log.error('cannot unpack', b=b, formatstring=formatstring, datasize=datasize)
        raise e

    return (b, *unpacked)


def parse_pkt(pkt):
    log.debug('parsing packet', pkt=pkt)

    flavor = pkt[0:2]
    payload = pkt[3:]
    kvps = None
    try:
        comma = payload.index(',')
        kvps = payload[comma+1:]
        payload = payload[:comma]
    except ValueError:
        pass

    # Last two characters of the payload are probably some kind of checksum
    checksum = payload[-2:]
    payload = payload[:-2]

    try:
        # The payload is encoded with base64
        payload = base64.urlsafe_b64decode(payload)
    except Exception as e:
        log.error('cannot decode base64', pkt=pkt)
        return None

    hexdump(payload)

    # Parse fields common to both WZ ans WS flavors
    (payload, eui64_bytes) = consume(payload, '!8s')
    eui64 = format_eui64(eui64_bytes)

    log.info('extracted fields', flavor=flavor, eui64=eui64, payload=payload, kvps=kvps, checksum=checksum)
    hexdump(payload)

    if flavor == 'WZ':

        (payload, uptime, type, static1, flag1, length) = consume(payload, '!IH3sBB')

        # The uptime unit is 500ms
        uptime = timedelta(seconds=uptime * 0.5)

        log.debug('type parsed', uptime=uptime, type=hex(type), static1=static1, flag1=flag1, length=length)

        (payload, contents) = consume(payload, f'{length}s')
        print("CONTENTS")
        hexdump(contents)
        
        if type == 0x2100: # Bootup message

            # Hypothesis for contents:
            #
            # hardware version?
            # software version?
            # country?
            # manufacturing date?
            # configuration?

            log.info('bootup packet', gw_eui64=eui64, contents=contents)

        elif type == 0x2101:  # Unknown yet
            pass
        else:
            log.warn('unknown type', pkt=pkt, type=hex(type), contents=contents)

        if len(payload) > 0:
            print("UNPARSED PAYLOAD LEFT")
            hexdump(payload)

#        (counter1, static2, counter2, static3, static1) = unpack('!IH3sB6s5s', payload)

        # static1 is always b'\x00\x9a\xc64H
        # if static1 != b'\x00\x9a\xc64H':
        #     log.warn('static1 value is not typical', pkt=pkt, static1=static1)

        # # static2 is always b'!\x01\x00\x00\x00'
        # if static2 != b'!\x01\x00\x00\x00':
        #     log.warn('static2 value is not typical', pkt=pkt, static2=static2)

        # if static3 != b'\nS\xa9\xc15w':
        #     log.warn('static3 value is not typical', pkt=pkt, static3=static3)

        # log.info('payload parsed', gw_eui64=gw_eui64, counter1=counter1, counter2=counter2, static1=static1, static2=static2, static3=static3)

    elif flavor == 'WS':
        (counter1) = unpack('!I27x', payload)
        inverter_eui64 = eui64

        log.info('payload parsed', inverter_eui64=inverter_eui64, counter1=counter1)

    else:
        log.warning('unknown packet flavor', pkt=pkt, flavor=flavor)
        return None


def zigbee_packets(config):
    log.info('polling start', url=config.url)
    while True:
        response = requests.get(config.url)
        log.debug('response', response=response)
        response.raise_for_status()

        dom = parseString(response.text)
        try:
            pkt = dom.getElementsByTagName('zigbeeData')[0].firstChild.nodeValue
            pkt = pkt.rstrip()
            log.info('packet from Zigbee module', pkt=pkt)
            yield pkt
        except AttributeError as e:
            continue

    raise RuntimeError("We shouldn't have gotten here")


def file_packets(config):
    for pkt in fileinput.input(files=config.files, encoding='ascii'):
        pkt = pkt.strip()
        if len(pkt) == 0:  # skip empty lines
            continue

        if pkt[0] == '#':  # skip comments
            continue

        yield pkt


def main(config):

    if config.url:
        packet_source = zigbee_packets(config)
    elif config.files:
        packet_source = file_packets(config)

    for pkt in packet_source:
       parse_pkt(pkt)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Poll the Enecsys Gateway for Zigbee packets')
    parser.add_argument('--loglevel', choices=LOG_LEVEL_NAMES, default='INFO', help='Change log level')
    parser.add_argument('--url', help='Poll messages from gateway URL')
    parser.add_argument('--file', dest='files', nargs='+', help='Read messages from file, use - for standard input')

    (args) = parser.parse_args()
    config = args

    # Restrict log message to be above selected level
    structlog.configure( wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, args.loglevel)) )

    log.debug('config', args=args)

    main(config)
