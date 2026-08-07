# RealSense Camera Stability Plan

## Context

The wrist camera is currently expected to publish the image stream consumed by
Cyclo:

```text
/camera/cam_wrist/color/image_rect_raw/compressed
```

Cyclo already subscribes to this topic in:

```text
/home/user/jinsoo/omy_irasc_loren/cyclo_intelligence/shared/shared/robot_configs/omy_f3m_config.yaml
```

Relevant YAML entry:

```yaml
observation:
  images:
    cam_wrist:
      topic: /camera/cam_wrist/color/image_rect_raw/compressed
      msg_type: sensor_msgs/msg/CompressedImage
```

The camera has been physically connected, but launching the camera is unstable:
it sometimes publishes correctly and sometimes does not. The goal is to make the
camera startup path deterministic and owned by `irasc_stack`.

## Current File Layout

The RealSense driver source is currently visible inside the Docker container,
not as a normal host-side source package under `/home/user/jinsoo`.

Container paths:

```text
/root/ros2_ws/src/realsense-ros/realsense2_camera/launch/rs_launch.py
/root/ros2_ws/src/realsense-ros/realsense2_camera/src/
/root/ros2_ws/src/realsense-ros/realsense2_camera/include/
/root/ros2_ws/install/realsense2_camera/share/realsense2_camera/launch/rs_launch.py
```

Open Manipulator wrapper launch files found on the host:

```text
/home/user/jinsoo/open_manipulator/open_manipulator_bringup/launch/camera_realsense.launch.py
/home/user/jinsoo/omy_irasc_loren/open_manipulator/open_manipulator_bringup/launch/camera_realsense.launch.py
/home/user/jinsoo/personal_docker_ros2_jazzy/ros2_ws/src/open_manipulator_bringup/launch/camera_realsense.launch.py
```

The wrapper launch file imports `realsense2_camera/launch/rs_launch.py` through
ROS package discovery and then calls `rs_launch.launch_setup`.

## What The Existing Launch Does

The standard command:

```bash
ros2 launch realsense2_camera rs_launch.py camera_name:=cam_wrist
```

starts:

```text
package: realsense2_camera
executable: realsense2_camera_node
namespace: camera
node name: cam_wrist
full node name: /camera/cam_wrist
```

Expected topic prefix:

```text
/camera/cam_wrist
```

Typical topics:

```text
/camera/cam_wrist/color/camera_info
/camera/cam_wrist/color/image_raw
/camera/cam_wrist/color/metadata
/camera/cam_wrist/depth/camera_info
/camera/cam_wrist/depth/image_rect_raw
/camera/cam_wrist/depth/metadata
/camera/cam_wrist/extrinsics/depth_to_color
/tf_static
/parameter_events
/rosout
```

If depth alignment, point cloud, IMU, or compressed image transport is enabled,
additional topics can appear.

## Likely Causes Of Instability

The instability is probably not caused by Cyclo itself. Cyclo only needs a
stable image topic. The risky area is camera startup and topic publication.

Likely causes:

1. The camera is launched through different paths depending on the container or
   shell environment.
2. `camera_name`, `camera_namespace`, profile, and stream parameters are not
   centrally owned by `irasc_stack`.
3. The launch does not pin the RealSense device by `serial_no`, so device
   discovery can be nondeterministic.
4. USB enumeration or RealSense initialization timing can fail intermittently.
5. Compressed image topic availability depends on image transport/plugin setup.
6. Driver source and launch behavior are hard to audit because part of the code
   lives only inside the container.
7. Manual edits inside `/root/ros2_ws/src/realsense-ros` or `/root/ros2_ws/install`
   are not a durable solution because they can disappear when the container is
   rebuilt or replaced.

## Recommended Direction

Create a dedicated camera bringup package under `irasc_stack`.

Recommended package:

```text
irasc_stack/src/irasc_camera_bringup
```

Recommended structure:

```text
irasc_camera_bringup/
  package.xml
  CMakeLists.txt
  launch/
    cam_wrist.launch.py
  config/
    cam_wrist.yaml
```

This package should not reimplement `realsense2_camera_node`. Instead, it should
own the launch/config layer and use the official RealSense driver as a runtime
dependency.

The launch should include:

```text
FindPackageShare("realsense2_camera") / "launch" / "rs_launch.py"
```

Then pass fixed arguments for the wrist camera:

```text
camera_namespace:=camera
camera_name:=cam_wrist
serial_no:=<real camera serial number>
enable_color:=true
enable_depth:=false or true
rgb_camera.color_profile:=424,240,15
initial_reset:=true
wait_for_device_timeout:=10.0
reconnect_timeout:=6.0
```

The exact profile should be chosen after checking what the connected camera
actually supports.

## Why This Is Better

This gives us:

1. A single stable command to start the wrist camera.
2. Camera naming and topics controlled by `irasc_stack`.
3. Git-tracked launch/config files.
4. No manual dependency on hidden container-only edits.
5. Cleaner connection to Cyclo through the already expected topic name.
6. Easier future expansion for head/left/right cameras.

The target should be:

```text
RealSense hardware
  -> irasc_camera_bringup launch/config
  -> realsense2_camera_node
  -> /camera/cam_wrist/color/image_rect_raw/compressed
  -> cyclo_intelligence
```

## Things To Avoid

Avoid these unless there is a strong reason:

1. Rewriting the RealSense driver from scratch.
2. Editing `/root/ros2_ws/install/realsense2_camera/...` directly.
3. Patching container-only source without copying the fix into a host-managed
   repository.
4. Letting multiple launch files compete to define the same camera name/topic.

## Immediate Debug Checklist

Run these inside the container that owns the RealSense runtime.

Check package resolution:

```bash
source /opt/ros/jazzy/setup.bash
source /root/ros2_ws/install/setup.bash
ros2 pkg prefix realsense2_camera
```

Find the driver source and launch file:

```bash
find /root/ros2_ws -path '*realsense2_camera/launch/rs_launch.py' -print
```

Check camera hardware:

```bash
rs-enumerate-devices
```

Launch manually with explicit naming:

```bash
ros2 launch realsense2_camera rs_launch.py \
  camera_namespace:=camera \
  camera_name:=cam_wrist
```

Check node:

```bash
ros2 node list | grep cam_wrist
```

Check topics:

```bash
ros2 topic list | grep cam_wrist
```

Check image stream:

```bash
ros2 topic hz /camera/cam_wrist/color/image_raw
```

Check compressed stream:

```bash
ros2 topic hz /camera/cam_wrist/color/image_rect_raw/compressed
```

If `image_raw` exists but `compressed` does not, investigate image transport or
add an explicit republish/compression node in `irasc_camera_bringup`.

## Implementation Plan

1. Inspect Robotis/Open Manipulator RealSense launch behavior.
2. Confirm the physical camera serial number.
3. Confirm the supported color/depth profiles.
4. Create `irasc_camera_bringup`.
5. Add `cam_wrist.launch.py` with fixed namespace/name/serial/profile.
6. Add `cam_wrist.yaml` for parameters that should be version-controlled.
7. Verify that `/camera/cam_wrist/color/image_rect_raw/compressed` is stable.
8. Start Cyclo and verify that the configured observation image is received.

## Open Questions

1. Which container should become the canonical runtime for `irasc_stack`?
2. Should the wrist camera publish depth, or is color-only enough for Cyclo?
3. Should Cyclo consume `image_raw`, `image_rect_raw`, or compressed images long
   term?
4. Should `irasc_stack` own RealSense installation, or only require it as a
   dependency inside the Docker image?
