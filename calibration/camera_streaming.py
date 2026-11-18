import threading
import socket
import struct
import sys
import os
import numpy as np
import cv2
from PIL import Image
from source.common_utilities import constants

# Add path for protobuf
pb2_path = os.path.join(os.path.dirname(__file__), '..', '..', 'neo-calibration-server-api', 'source', 'python')
sys.path.insert(0, pb2_path)

import calibration_server_api_pb2
from source.common_utilities.log_config import logger


class StreamConnection:
    """Manages a single stream connection to the server"""
    
    def __init__(self, host=constants.UVC_IP, port=constants.CAL_SERVER_PORT, stream_type='stereo'):
        self.host = host
        self.port = port
        self.stream_type = stream_type
        self.socket = None
        self.connected = False
        self.streaming = False
        self.stream_thread = None
        self.output_callback = None

    def connect(self):
        """Connect to the server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            logger.info(f"Connected to calibration server at {self.host}:{self.port} ({self.stream_type})")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to calibration server ({self.stream_type}): {e}")
            return False

    def disconnect(self):
        """Disconnect from the server"""
        self.streaming = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.connected = False
            logger.info(f"Disconnected from calibration server ({self.stream_type})")

    def send_message(self, message):
        """Send protobuf message to server"""
        if not self.connected:
            return False
        
        try:
            serialized = message.SerializeToString()
            length = struct.pack('>I', len(serialized))
            self.socket.sendall(length + serialized)
            return True
        except Exception as e:
            logger.error(f"Failed to send message ({self.stream_type}): {e}")
            self.connected = False
            return False

    def receive_message(self, timeout=2):
        """Receive protobuf message from server"""
        if not self.connected:
            return None
        
        try:
            self.socket.settimeout(timeout)
            length_data = self.socket.recv(4)
            if not length_data:
                return None
            length = struct.unpack('>I', length_data)[0]
            
            data = b''
            while len(data) < length:
                chunk = self.socket.recv(length - len(data))
                if not chunk:
                    return None
                data += chunk
            
            message = calibration_server_api_pb2.FromServer()
            message.ParseFromString(data)
            return message
        except socket.timeout:
            return None
        except Exception as e:
            logger.error(f"Failed to receive message ({self.stream_type}): {e}")
            self.connected = False
            return None


class StereoStreamConnection(StreamConnection):
    """Manages stereo camera stream"""
    
    def __init__(self, host=constants.UVC_IP, port=constants.CAL_SERVER_PORT):
        super().__init__(host, port, 'stereo')

    def start_streaming(self, output_callback=None):
        """Start stereo stream"""
        if not self.connected:
            return False
        
        try:
            request = calibration_server_api_pb2.ToServer()
            request.start_video_stream.CopyFrom(calibration_server_api_pb2.StartVideoStream())
            
            if not self.send_message(request):
                return False
            
            self.output_callback = output_callback
            self.streaming = True
            
            self.stream_thread = threading.Thread(
                target=self._receive_stereo_frames,
                daemon=True
            )
            self.stream_thread.start()
            
            logger.info("Stereo stream started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start stereo streaming: {e}")
            self.streaming = False
            return False

    def stop_streaming(self):
        """Stop stereo stream"""
        try:
            self.streaming = False
            
            if self.connected:
                request = calibration_server_api_pb2.ToServer()
                request.stop_video_stream.CopyFrom(calibration_server_api_pb2.StopVideoStream())
                self.send_message(request)
            
            logger.info("Stereo stream stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop stereo streaming: {e}")
            return False

    def _receive_stereo_frames(self):
        """Receive stereo stream frames"""
        frame_count = 0
        try:
            while self.streaming:
                message = self.receive_message(timeout=1)
                if not message:
                    continue
                
                if message.HasField('stream_frame'):
                    frame_count += 1
                    frame_data = message.stream_frame.frame
                    
                    result = {
                        'frame_number': frame_count,
                        'stream_type': 'stereo',
                        'left': {
                            'image': frame_data.left.image,
                            'source': frame_data.left.source,
                            'width': frame_data.left.width,
                            'height': frame_data.left.height,
                            'timestamp_ms': frame_data.left.timestamp_ms,
                            'format': frame_data.left.format,
                        },
                        'right': {
                            'image': frame_data.right.image,
                            'source': frame_data.right.source,
                            'width': frame_data.right.width,
                            'height': frame_data.right.height,
                            'timestamp_ms': frame_data.right.timestamp_ms,
                            'format': frame_data.right.format,
                        },
                        'is_final': message.stream_frame.is_final,
                    }
                    
                    if self.output_callback:
                        self.output_callback(result)
                    
                    logger.debug(f"Stereo frame {frame_count} received")
                    
        except Exception as e:
            if self.streaming:
                logger.error(f"Error receiving stereo frames: {e}")
        finally:
            self.streaming = False


class WideStreamConnection(StreamConnection):
    """Manages wide camera stream"""
    
    def __init__(self, host=constants.UVC_IP, port=constants.CAL_SERVER_PORT):
        super().__init__(host, port, 'wide')

    def start_streaming(self, output_callback=None):
        """Start wide stream"""
        if not self.connected:
            return False
        
        try:
            request = calibration_server_api_pb2.ToServer()
            request.get_wide_video_stream.CopyFrom(calibration_server_api_pb2.GetWideVideoStream())
            
            if not self.send_message(request):
                return False
            
            self.output_callback = output_callback
            self.streaming = True
            
            self.stream_thread = threading.Thread(
                target=self._receive_wide_frames,
                daemon=True
            )
            self.stream_thread.start()
            
            logger.info("Wide stream started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start wide streaming: {e}")
            self.streaming = False
            return False

    def stop_streaming(self):
        """Stop wide stream"""
        try:
            self.streaming = False
            
            if self.connected:
                request = calibration_server_api_pb2.ToServer()
                request.stop_wide_video_stream.CopyFrom(calibration_server_api_pb2.StopWideVideoStream())
                self.send_message(request)
            
            logger.info("Wide stream stopped")
            return True
            
        except Exception as e:
            logger.error(f"Failed to stop wide streaming: {e}")
            return False

    def _receive_wide_frames(self):
        """Receive wide stream frames"""
        frame_count = 0
        try:
            while self.streaming:
                message = self.receive_message(timeout=1)
                if not message:
                    continue
                
                if message.HasField('wide_stream_frame'):
                    frame_count += 1
                    wide_frame = message.wide_stream_frame.wide
                    
                    result = {
                        'frame_number': frame_count,
                        'stream_type': 'wide',
                        'wide': {
                            'image': wide_frame.image,
                            'source': wide_frame.source,
                            'width': wide_frame.width,
                            'height': wide_frame.height,
                            'timestamp_ms': wide_frame.timestamp_ms,
                            'format': wide_frame.format,
                        },
                        'is_final': message.wide_stream_frame.is_final,
                    }
                    
                    if self.output_callback:
                        self.output_callback(result)
                    
                    logger.debug(f"Wide frame {frame_count} received")
                    
        except Exception as e:
            if self.streaming:
                logger.error(f"Error receiving wide frames: {e}")
        finally:
            self.streaming = False


def raw_to_image(raw_data, width, height):
    """Convert raw bytes to PIL Image"""
    try:
        img_array = np.frombuffer(raw_data, dtype=np.uint8).reshape((height, width))
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
        img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(img_rgb)
    except Exception as e:
        logger.error(f"Error converting image: {e}")
        return None


def resize_image(pil_img, target_width, target_height):
    """Resize PIL image to target dimensions"""
    try:
        if target_width > 10 and target_height > 10:
            return pil_img.resize((target_width, target_height), Image.LANCZOS)
        return pil_img
    except Exception as e:
        logger.error(f"Error resizing image: {e}")
        return pil_img
