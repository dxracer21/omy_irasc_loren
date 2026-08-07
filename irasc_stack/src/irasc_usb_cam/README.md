# irasc_usb_cam

Camera bringup package for the iRASC stack.

This package starts the OMY wrist D405 with the ROBOTIS RealSense launch file and
starts the front Logitech camera with `usb_cam` from the same camera registry.

```bash
ros2 launch irasc_usb_cam all_cameras.launch.py
```

Camera definitions live in:

```text
config/cameras.yaml
```

## Current Setup

```text
cam_wrist -> ROBOTIS camera_realsense.launch.py -> Intel RealSense D405
cam_front -> usb_cam_node_exe                  -> Logitech/front USB camera
```

The wrist camera intentionally follows the ROBOTIS launch path instead of
creating `realsense2_camera_node` directly in this package. That keeps the D405
behavior aligned with the official OMY configuration.

The RealSense topics follow the normal `camera_namespace/camera_name` layout:

```text
/camera/cam_wrist/color/image_raw
/camera/cam_wrist/color/image_raw/compressed
/camera/cam_wrist/color/camera_info
```

Depending on the installed `realsense2_camera` version, rectified topics may also
be available under:

```text
/camera/cam_wrist/color/image_rect_raw
/camera/cam_wrist/color/image_rect_raw/compressed
```

The Logitech front camera is optional. When it is connected and a matching V4L2
MJPEG device is found, it is remapped to:

```text
/camera/cam_front/color/image_rect_raw
/camera/cam_front/color/image_rect_raw/compressed
/camera/cam_front/color/camera_info
```

If the Logitech camera is not connected, the launch file skips `cam_front` and
still starts `cam_wrist`.

## D405

The D405 entry is selected by serial number:

```yaml
serial_no: "335122273204"
```

The ROBOTIS OMY default D405 profiles are used:

```yaml
depth_module.depth_profile: "480,270,15"
depth_module.color_profile: "424,240,15"
```

Connect the OMY CAMERA ONLY port to the user PC through the ROBOTIS USB 3.0 hub
and a USB 3.0 data cable. Check the negotiated speed with:

```bash
lsusb -t
```

`5000M` is USB 3.x. `480M` is USB 2.0.

## Front Camera Device Selection

For `usb_cam`, set `video_device` to an explicit path when you want a fixed
device:

```yaml
video_device: /dev/video0
```

If `video_device` is omitted or set to `auto`, the launch file scans V4L2 devices
and keeps image-capable devices only. The selected device must support the
configured `pixel_format`; `auto_device_index` chooses among matching devices.

Check candidates inside the `irasc_stack` container with:

```bash
v4l2-ctl --list-devices
ls -l /dev/v4l/by-id/
v4l2-ctl --device /dev/video0 --list-formats-ext
```

Check RealSense status with:

```bash
rs-enumerate-devices -s
rs-enumerate-devices -c
```

## Build

From the `irasc_stack` container:

```bash
cd /root/irasc_ws
colcon build --packages-select irasc_usb_cam
source install/setup.bash
ros2 launch irasc_usb_cam all_cameras.launch.py
```

If using GUI tools from the current Windows app/X11 session, set the display if
needed:

```bash
export DISPLAY=:10
ros2 run rqt_image_view rqt_image_view
```
