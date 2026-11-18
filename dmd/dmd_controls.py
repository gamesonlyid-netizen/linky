import socket
import struct
from pathlib import Path
from typing import Tuple


def _prepend_message_length(payload: bytes) -> bytes:
    return struct.pack("!I", len(payload)) + payload


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    chunks = []
    got = 0
    while got < n:
        chunk = sock.recv(n - got)
        if not chunk:
            raise ConnectionError("Socket closed while receiving data")
        chunks.append(chunk)
        got += len(chunk)
    return b"".join(chunks)


def send_dmd_bmp_via_cal_server(
    bmp_path: Path,
    host: str,
    port: int,
    calibration_pb2_module,
    socket_timeout: float = 6.0,
) -> Tuple[bool, str]:
    if not bmp_path.exists():
        return False, f"BMP not found: {bmp_path}"

    raw = bmp_path.read_bytes()
    if not raw:
        return False, f"BMP is empty: {bmp_path}"

    ToServer = calibration_pb2_module.ToServer
    FromServer = calibration_pb2_module.FromServer

    req = ToServer()
    req.calibrate_dmd.image = raw

    payload = req.SerializeToString()
    framed = _prepend_message_length(payload)

    with socket.create_connection((host, port), timeout=socket_timeout) as s:
        s.settimeout(socket_timeout)
        s.sendall(framed)

        header = _recv_exact(s, 4)
        (msg_len,) = struct.unpack("!I", header)
        response_data = _recv_exact(s, msg_len)

    resp = FromServer()
    if not resp.ParseFromString(response_data):
        return False, "Could not decode DMD response packet"

    if resp.HasField("dmd_calibrated"):
        ok = resp.dmd_calibrated.success
        return ok, f"DMD calibrated success={ok}"

    return False, "Response did not include dmd_calibrated"

# import socket
# import struct
# from pathlib import Path
# from typing import Tuple


# def _prepend_message_length(payload: bytes) -> bytes:
#     # match ncs::prependMessageLength() behavior: 4-byte network-order length + payload
#     return struct.pack("!I", len(payload)) + payload


# def _recv_exact(sock: socket.socket, n: int) -> bytes:
#     chunks = []
#     got = 0
#     while got < n:
#         chunk = sock.recv(n - got)
#         if not chunk:
#             raise ConnectionError("Socket closed while receiving data")
#         chunks.append(chunk)
#         got += len(chunk)
#     return b"".join(chunks)


# def send_dmd_bmp_via_cal_server(
#     bmp_path: Path,
#     host: str,
#     port: int,
#     calibration_pb2_module
# ) -> Tuple[bool, str]:
#     """
#     Sends CalibrateDmd(image=<bmp bytes>) to calibration server and returns (ok, message).

#     calibration_pb2_module should be imported generated module (e.g. calibration_server_api_pb2).
#     """
#     if not bmp_path.exists():
#         return False, f"BMP not found: {bmp_path}"

#     raw = bmp_path.read_bytes()
#     if not raw:
#         return False, f"BMP is empty: {bmp_path}"

#     ToServer = calibration_pb2_module.ToServer
#     FromServer = calibration_pb2_module.FromServer

#     req = ToServer()
#     req.calibrate_dmd.image = raw

#     payload = req.SerializeToString()
#     framed = _prepend_message_length(payload)

#     with socket.create_connection((host, port), timeout=5) as s:
#         s.sendall(framed)

#         # read framed response
#         header = _recv_exact(s, 4)
#         (msg_len,) = struct.unpack("!I", header)
#         response_data = _recv_exact(s, msg_len)

#     resp = FromServer()
#     if not resp.ParseFromString(response_data):
#         return False, "Could not decode DMD response packet"

#     # Expect dmd_calibrated from your C++ route
#     if resp.HasField("dmd_calibrated"):
#         ok = resp.dmd_calibrated.success
#         return ok, f"DMD calibrated success={ok}"
#     return False, "Response did not include dmd_calibrated"