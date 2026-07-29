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
    mesa-utils \
    x11-apps \
    python3-pip \
    python3-colcon-common-extensions \
    ros-jazzy-rqt \
    ros-jazzy-rqt-image-view \
    ros-jazzy-image-transport-plugins \
    ros-jazzy-cv-bridge \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /root/irasc_ws

RUN mkdir -p /root/irasc_ws/src

COPY src/ /root/irasc_ws/src/

RUN echo "source /opt/ros/jazzy/setup.bash" >> /root/.bashrc && \
    echo 'if [ -f /root/irasc_ws/install/setup.bash ]; then source /root/irasc_ws/install/setup.bash; fi' >> /root/.bashrc

CMD ["bash"]
