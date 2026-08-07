#!/usr/bin/env python3

from pathlib import Path
import subprocess

import yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

CAPTURE_FORMATS = ('MJPG', 'YUYV', 'UYVY', 'GREY')
NON_IMAGE_FORMATS = ('Z16',)


def _run(command):
    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ''


def _video_devices_from_by_id():
    by_id = Path('/dev/v4l/by-id')
    devices = []
    if by_id.exists():
        for path in sorted(by_id.glob('*video-index*')):
            target = path.resolve()
            if target.name.startswith('video'):
                devices.append(str(target))
    for path in sorted(Path('/dev').glob('video*')):
        devices.append(str(path))
    return list(dict.fromkeys(devices))


def _formats_for(device):
    output = _run(['v4l2-ctl', '--device', device, '--list-formats-ext'])
    formats = []
    for line in output.splitlines():
        line = line.strip()
        if line.startswith('[') and "'" in line:
            parts = line.split("'")
            if len(parts) >= 2:
                formats.append(parts[1].strip())
    return formats


def _is_image_capture(formats):
    if not formats:
        return False
    if any(fmt in NON_IMAGE_FORMATS for fmt in formats):
        return False
    return any(fmt in CAPTURE_FORMATS for fmt in formats)


def _image_candidates():
    candidates = []
    for device in _video_devices_from_by_id():
        formats = _formats_for(device)
        if _is_image_capture(formats):
            candidates.append({'device': device, 'formats': formats})
    return candidates


def _required_v4l2_format(camera_config):
    
    if camera_config.get('backend', 'usb_cam') == 'v4l2_camera':
        pixel_format = str(camera_config.get('v4l2_camera', {}).get('pixel_format', '')).lower()
    else:
        pixel_format = str(camera_config.get('usb_cam', {}).get('pixel_format', '')).lower()
    if pixel_format.startswith('mjpeg') or pixel_format.startswith('mjpg'):
        return 'MJPG'
    if pixel_format.startswith('yuyv'):
        return 'YUYV'
    if pixel_format.startswith('uyvy'):
        return 'UYVY'
    if pixel_format.startswith('mono'):
        return 'GREY'
    return None


def _resolve_video_device(camera_name, camera_config, candidates):
    explicit_device = camera_config.get('video_device')
    if explicit_device and explicit_device != 'auto':
        return explicit_device

    required_format = _required_v4l2_format(camera_config)
    matching_candidates = [
        item for item in candidates
        if required_format is None or required_format in item['formats']
    ]

    index = int(camera_config.get('auto_device_index', camera_config.get('auto_color_index', 0)))
    if index >= len(matching_candidates):
        candidate_text = ', '.join(
            f"{idx}:{item['device']}({','.join(item['formats'])})"
            for idx, item in enumerate(matching_candidates)
        ) or 'none'
        format_text = required_format or 'any color format'
        if not camera_config.get('required', True):
            return None
        raise RuntimeError(
            f"Camera '{camera_name}' requested auto_device_index={index} with {format_text}, "
            f"but only {len(matching_candidates)} matching candidates were found: {candidate_text}"
        )
    return matching_candidates[index]['device']


def _usb_cam_node(camera_name, camera_config, video_device):
    topic_base = camera_config.get('topic_base', f'/camera/{camera_name}/color')
    params = dict(camera_config.get('usb_cam', {}))
    params['video_device'] = video_device
    params['frame_id'] = camera_config.get('frame_id', f'{camera_name}_frame')
    params.setdefault('camera_name', camera_name)

    return Node(
        package='usb_cam',
        executable='usb_cam_node_exe',
        name=camera_name,
        namespace='irasc_usb_cam',
        output='both',
        parameters=[params],
        remappings=[
            ('image_raw', f'{topic_base}/image_rect_raw'),
            ('image_raw/compressed', f'{topic_base}/image_rect_raw/compressed'),
            ('image_raw/compressedDepth', f'{topic_base}/image_rect_raw/compressedDepth'),
            ('image_raw/theora', f'{topic_base}/image_rect_raw/theora'),
            ('camera_info', f'{topic_base}/camera_info'),
        ],
    )


def _v4l2_camera_node(camera_name, camera_config, video_device):
    topic_base = camera_config.get('topic_base', f'/camera/{camera_name}/color')
    v4l2_config = dict(camera_config.get('v4l2_camera', {}))
    image_width = int(v4l2_config.pop('image_width'))
    image_height = int(v4l2_config.pop('image_height'))
    params = {
        'video_device': video_device,
        'image_size': [image_width, image_height],
        'camera_frame_id': camera_config.get('frame_id', f'{camera_name}_frame'),
        **v4l2_config,
    }

    return Node(
        package='v4l2_camera',
        executable='v4l2_camera_node',
        name=camera_name,
        namespace='irasc_usb_cam',
        output='both',
        parameters=[params],
        remappings=[
            ('image_raw', f'{topic_base}/image_rect_raw'),
            ('image_raw/compressed', f'{topic_base}/image_rect_raw/compressed'),
            ('image_raw/compressedDepth', f'{topic_base}/image_rect_raw/compressedDepth'),
            ('image_raw/theora', f'{topic_base}/image_rect_raw/theora'),
            ('camera_info', f'{topic_base}/camera_info'),
        ],
    )


def _realsense2_camera_node(camera_name, camera_config):
    params = dict(camera_config.get('realsense2_camera', {}))
    params.setdefault('camera_name', camera_name)
    params.setdefault('camera_namespace', 'camera')

    serial_no = camera_config.get('serial_no')
    if serial_no:
        params.setdefault('serial_no', str(serial_no))

    robotis_launch = (
        Path(get_package_share_directory('open_manipulator_bringup'))
        / 'launch'
        / 'camera_realsense.launch.py'
    )
    launch_arguments = {}
    for key, value in params.items():
        argument_name = key if key.endswith('1') else f'{key}1'
        if isinstance(value, bool):
            argument_value = str(value).lower()
        else:
            argument_value = str(value)
        if key in ('serial_no', 'serial_no1') and argument_value.isdigit():
            argument_value = f'_{argument_value}'
        launch_arguments[argument_name] = argument_value

    return IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(robotis_launch)),
        launch_arguments=launch_arguments.items(),
    )


def _camera_node(camera_name, camera_config, video_device=None):
    backend = camera_config.get('backend', 'usb_cam')
    if backend == 'usb_cam':
        return _usb_cam_node(camera_name, camera_config, video_device)
    if backend == 'v4l2_camera':
        return _v4l2_camera_node(camera_name, camera_config, video_device)
    if backend == 'realsense2_camera':
        return _realsense2_camera_node(camera_name, camera_config)
    raise RuntimeError(f"Unsupported camera backend '{backend}' for camera '{camera_name}'")


def _launch_setup(context, *args, **kwargs):
    config_path = Path(LaunchConfiguration('config').perform(context))
    with config_path.open('r') as stream:
        config = yaml.safe_load(stream) or {}

    cameras = config.get('cameras', {})
    candidates = _image_candidates()
    nodes = []
    used_devices = set()

    for camera_name, camera_config in cameras.items():
        if not camera_config.get('enabled', True):
            continue
        if camera_config.get('backend', 'usb_cam') == 'realsense2_camera':
            nodes.append(_camera_node(camera_name, camera_config))
        else:
            video_device = _resolve_video_device(camera_name, camera_config, candidates)
            if video_device is None:
                nodes.append(LogInfo(msg=f"Skipping optional camera '{camera_name}': no matching video device found"))
                continue
            if video_device in used_devices:
                raise RuntimeError(f"Video device '{video_device}' is assigned more than once")
            used_devices.add(video_device)
            nodes.append(_camera_node(camera_name, camera_config, video_device))

    return nodes


def generate_launch_description():
    default_config = str(
        Path(get_package_share_directory('irasc_usb_cam')) / 'config' / 'cameras.yaml'
    )
    return LaunchDescription([
        DeclareLaunchArgument(
            'config',
            default_value=default_config,
            description='Path to the irasc_usb_cam camera registry YAML file.',
        ),
        OpaqueFunction(function=_launch_setup),
    ])
