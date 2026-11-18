import io
import logging
import threading
import time
import source.common_utilities.constants as constants
from source.hbc.hbc_utils import get_hbc_instance, logger


def set_distance_sensor_settings(gain, offset, timeout=5):
    response_event = threading.Event()
    result = {}

    def handler(msg_type, from_hbc):
        logger.info("Handler received msg_type: %s", msg_type)
        result["data"] = from_hbc
        response_event.set()

    hbc = get_hbc_instance(handler)
    if not hbc:
        msg = "Cannot set distance sensor settings because HBC is unavailable."
        logger.error(msg)
        return msg

    try:
        hbc.set_distance_sensor_settings(gain, offset)
        hbc.get_device_settings()

        if not response_event.wait(timeout):
            err = f"Timed out waiting for {constants.PROTO_DISTANCE_SETTINGS_RESULT} response after {timeout} second(s)"
            logger.error(err)
            raise TimeoutError(err)

        return str(result.get("data"))

    except TimeoutError as e:
        logger.error("Timeout: %s", e)
        return str(e)

    except Exception:
        logger.exception("Failed to set distance sensor settings")
        return "distance sensor settings operation failed"


def distance_sensor_start_stop_ranging(runtime, timeout=5, on_sample=None):
    """
    Start ranging, collect streaming samples, stop after runtime.
    on_sample(elapsed_s, distance_mm) is optional and can update GUI live.
    """
    log_stream = io.StringIO()
    stream_handler = logging.StreamHandler(log_stream)
    logger.addHandler(stream_handler)

    response_event = threading.Event()
    t0 = time.time()
    result = {"samples": []}  # list of (elapsed_s, distance_mm)

    def handler(msg_type, from_hbc):
        if msg_type == constants.PROTO_DISTANCE_SETTINGS_RESULT:
            elapsed = time.time() - t0
            distance_mm = from_hbc.distance_sensor_ranging_result.distance_to_target_mm
            result["samples"].append((elapsed, distance_mm))
            logger.info("Handler received msg_type: %s", msg_type)

            if on_sample:
                try:
                    on_sample(elapsed, distance_mm)
                except Exception:
                    logger.exception("on_sample callback failed")

            response_event.set()

    hbc = get_hbc_instance(handler)
    if not hbc:
        msg = "Cannot start distance sensor ranging because HBC is unavailable."
        logger.error(msg)
        logger.removeHandler(stream_handler)
        return msg

    err_text = None
    try:
        logger.info("---- Start of distance sensor ranging")
        hbc.distance_sensor_start_ranging()

        if not response_event.wait(timeout):
            err_text = f"Timed out waiting for {constants.PROTO_DISTANCE_SETTINGS_RESULT} response after {timeout} second(s)"
            logger.error(err_text)
        else:
            time.sleep(runtime)

    except Exception:
        logger.exception("Failed to start distance sensor ranging")
        err_text = "start distance sensor ranging operation failed"

    finally:
        try:
            hbc.distance_sensor_stop_ranging()
            logger.info("End of distance sensor ranging ----")
        finally:
            logger.removeHandler(stream_handler)

    lines = []
    if err_text:
        lines.append(err_text)
        lines.append("")

    samples = result["samples"]
    lines.append(f"Samples received: {len(samples)}")
    if samples:
        vals = [d for _, d in samples]
        lines.append(f"Current: {vals[-1]:.3f} mm")
        lines.append(f"Min: {min(vals):.3f} mm | Max: {max(vals):.3f} mm | Mean: {sum(vals)/len(vals):.3f} mm")
        lines.append("")
        lines.append("Index | Time(s) | Distance(mm)")
        lines.append("--------------------------------")
        for i, (ts, d) in enumerate(samples, 1):
            lines.append(f"{i:5d} | {ts:7.3f} | {d:11.3f}")

    return "\n".join(lines)