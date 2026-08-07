#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

COMPOSE_FILE="${SCRIPT_DIR}/compose.yaml"
BUILD_COMPOSE_FILE="${SCRIPT_DIR}/compose.build.yaml"
ENV_FILE="${PROJECT_ROOT}/.env"
PROJECT_NAME="omy_irasc_loren"

# Cyclo image tags use the host architecture suffix for policy containers.
MACHINE_ARCH="$(uname -m)"
if [ "${MACHINE_ARCH}" = "aarch64" ] || [ "${MACHINE_ARCH}" = "arm64" ]; then
    export ARCH="arm64"
else
    export ARCH="amd64"
fi

ensure_dir() {
    [ -d "$1" ] || mkdir -p "$1"
}

prepare_cyclo_mounts() {
    ensure_dir "${PROJECT_ROOT}/data/cyclo/workspace"
    ensure_dir "${PROJECT_ROOT}/data/cyclo/workspace/dataset"
    ensure_dir "${PROJECT_ROOT}/data/cyclo/workspace/rosbag2"
    ensure_dir "${PROJECT_ROOT}/data/cyclo/workspace/lerobot"
    ensure_dir "${PROJECT_ROOT}/data/cyclo/workspace/model"
    ensure_dir "${PROJECT_ROOT}/data/cyclo/workspace/model/lerobot"
    ensure_dir "${PROJECT_ROOT}/data/cyclo/workspace/model/groot"
    ensure_dir "${PROJECT_ROOT}/data/cyclo/huggingface"
    ensure_dir "${PROJECT_ROOT}/data/cyclo/zenoh_cache"
    ensure_dir "${PROJECT_ROOT}/data/cyclo/agent_sockets"

    echo "[OMY iRASC] Cyclo workspace: ${PROJECT_ROOT}/data/cyclo/workspace"
    echo "[OMY iRASC] Cyclo Hugging Face cache: ${PROJECT_ROOT}/data/cyclo/huggingface"
}

compose() {
    docker compose \
        -p "${PROJECT_NAME}" \
        --env-file "${ENV_FILE}" \
        -f "${COMPOSE_FILE}" \
        "$@"
}

compose_build() {
    docker compose \
        -p "${PROJECT_NAME}" \
        --env-file "${ENV_FILE}" \
        -f "${COMPOSE_FILE}" \
        -f "${BUILD_COMPOSE_FILE}" \
        "$@"
}

setup_x11() {
    if command -v xhost >/dev/null 2>&1; then
        xhost +local:root >/dev/null 2>&1 || true
    fi
}

container_running() {
    docker ps --format '{{.Names}}' | grep -qx "$1"
}

build_irasc_workspace() {
    if ! container_running irasc_stack; then
        echo "[OMY iRASC] irasc_stack 컨테이너가 실행 중이 아닙니다."
        exit 1
    fi

    echo "[OMY iRASC] iRASC ROS 패키지를 /root/ros2_ws에서 빌드합니다."
    compose exec -T irasc_omy_stack bash -lc '
        set -e
        source /opt/ros/jazzy/setup.bash
        if [ -f /root/ros2_ws/install/setup.bash ]; then
            source /root/ros2_ws/install/setup.bash
        fi
        cd /root/ros2_ws
        colcon build --packages-select irasc_usb_cam
        source /root/ros2_ws/install/setup.bash
    '
}

start_base_containers() {
    echo "[OMY iRASC] irasc_stack 컨테이너를 실행합니다."
    setup_x11
    prepare_cyclo_mounts
    compose up -d irasc_omy_stack
    compose ps
}

start_robotis_container() {
    echo "[OMY iRASC] robotis_omy 컨테이너를 실행합니다."
    setup_x11
    compose up -d robotis_omy
    compose ps
}

start_irasc_container() {
    echo "[OMY iRASC] irasc_stack 컨테이너를 실행합니다."
    setup_x11
    prepare_cyclo_mounts
    compose up -d irasc_omy_stack
    compose ps
}

start_cyclo_stack() {
    echo "[OMY iRASC] cyclo_loren 컨테이너만 실행합니다."
    setup_x11
    prepare_cyclo_mounts
    compose up -d cyclo_loren
    compose ps
}

case "${1:-}" in
    start)
        case "${2:-}" in
            robotis)
                start_robotis_container
                ;;
            irasc|stack)
                start_irasc_container
                ;;
            cyclo)
                start_cyclo_stack
                ;;
            "")
                start_base_containers
                ;;
            *)
                echo "사용법: $0 start [robotis|irasc|cyclo]"
                exit 1
                ;;
        esac
        ;;

    cyclo)
        start_cyclo_stack
        ;;

    stop)
        echo "[OMY iRASC] 컨테이너를 종료합니다."
        compose down
        ;;

    restart)
        compose down
        compose up -d irasc_omy_stack
        compose ps
        ;;

    build)
        compose_build build irasc_omy_stack
        ;;

    build-ws)
        build_irasc_workspace
        ;;

    pull)
        compose pull
        ;;

    push)
        compose_build push irasc_omy_stack
        ;;

    publish)
        compose_build build irasc_omy_stack
        compose_build push irasc_omy_stack
        ;;

    enter)
        case "${2:-}" in
            robotis)
                compose exec robotis_omy bash
                ;;
            irasc|stack)
                compose exec irasc_omy_stack bash
                ;;
            cyclo)
                compose exec cyclo_loren bash
                ;;
            *)
                echo "사용법:"
                echo "  $0 enter robotis   robotis_omy_loren 접속"
                echo "  $0 enter irasc     irasc_stack 접속"
                echo "  $0 enter cyclo     cyclo_loren 접속"
                exit 1
                ;;
        esac
        ;;

    status)
        compose ps
        ;;

    logs)
        compose logs -f
        ;;

    *)
        echo "사용법:"
        echo "  $0 start          irasc_stack만 실행"
        echo "  $0 start robotis  robotis_omy만 실행"
        echo "  $0 start irasc    irasc_stack만 실행"
        echo "  $0 start cyclo    cyclo_loren만 실행"
        echo "  $0 cyclo          start cyclo와 동일"
        echo "  $0 stop      켜져있는 컨테이너 모두 종료"
        echo "  $0 restart   irasc_stack 재시작"
        echo "  $0 build     irasc_stack 이미지 빌드"
        echo "  $0 build-ws  실행 중인 irasc_stack에서 iRASC 패키지만 빌드"
        echo "  $0 pull      compose.yaml에 적힌 이미지 pull"
        echo "  $0 push      irasc_stack 이미지 push"
        echo "  $0 publish   irasc_stack 이미지 build 후 push"
        echo "  $0 enter robotis   robotis_omy 접속"
        echo "  $0 enter irasc     irasc_stack 접속"
        echo "  $0 enter cyclo     cyclo_loren 접속"
        echo "  $0 status    컨테이너 상태 확인"
        echo "  $0 logs      로그 확인"
        exit 1
        ;;
esac
