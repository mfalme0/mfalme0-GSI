import math
import struct


OUTGAUGE_PACKET = struct.Struct("<I4sHBB7f2I3f16s16si")


def parse_outgauge_packet(data):
    """Return speed in km/h, RPM, and gear from a BeamNG OutGauge packet."""
    if len(data) < OUTGAUGE_PACKET.size:
        return None, None, None

    packet = OUTGAUGE_PACKET.unpack_from(data)
    gear = packet[3]
    speed_ms, rpm = packet[5], packet[6]
    if not math.isfinite(speed_ms) or not math.isfinite(rpm):
        return None, None, None
    return int(speed_ms * 3.6), int(rpm), gear
