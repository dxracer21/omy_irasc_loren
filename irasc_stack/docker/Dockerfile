FROM robotis/open-manipulator:5.0.0

SHELL ["/bin/bash", "-c"]

ENV DEBIAN_FRONTEND=noninteractive
ENV ROS_DISTRO=jazzy

RUN apt-get update && apt-get install -y \
    git \
    nano \
    vim \
    curl \
    wget \
    usbutils \
    v4l-utils \
    mesa-utils \
    x11-apps \
    python3-pip \
    python3.12-venv \
    python3-colcon-common-extensions \
    ros-jazzy-rqt \
    ros-jazzy-rqt-image-view \
    ros-jazzy-usb-cam \
    ros-jazzy-v4l2-camera \
    ros-jazzy-realsense2-camera \
    ros-jazzy-realsense2-camera-msgs \
    ros-jazzy-image-transport \
    ros-jazzy-image-transport-plugins \
    ros-jazzy-compressed-image-transport \
    ros-jazzy-cv-bridge \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /root/ros2_ws

ARG LEROBOT_REPO=https://github.com/huggingface/lerobot.git
ARG LEROBOT_REF=main
ENV LEROBOT_VENV=/opt/venvs/lerobot

RUN python3 -m venv "${LEROBOT_VENV}" && \
    git clone --depth 1 --branch "${LEROBOT_REF}" "${LEROBOT_REPO}" /root/lerobot && \
    source "${LEROBOT_VENV}/bin/activate" && \
    python -m pip install --upgrade pip && \
    python -m pip install -e '/root/lerobot[training,smolvla]' typeguard

RUN mkdir -p /root/ros2_ws/src/irasc

COPY src/ /root/ros2_ws/src/irasc/

RUN source /opt/ros/jazzy/setup.bash && \
    if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi && \
    cd /root/ros2_ws && \
    colcon build --packages-select irasc_usb_cam

RUN echo 'source /opt/ros/jazzy/setup.bash' >> /root/.bashrc && \
    echo 'if [ -f /root/ros2_ws/install/setup.bash ]; then source /root/ros2_ws/install/setup.bash; fi' >> /root/.bashrc && \
    echo 'alias train="source /opt/venvs/lerobot/bin/activate"' >> /root/.bashrc

CMD ["bash"]
