#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

COMPOSE_FILE="${SCRIPT_DIR}/compose.yaml"
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

setup_x11() {
    if command -v xhost >/dev/null 2>&1; then
        xhost +local:root >/dev/null 2>&1 || true
    fi
}

container_running() {
    docker ps --format '{{.Names}}' | grep -qx "$1"
}

start_base_containers() {
    echo "[OMY iRASC] robotis_omy와 irasc_stack 컨테이너를 빌드하고 실행합니다."
    setup_x11
    compose up -d --build robotis_omy irasc_omy_stack
    compose ps
}

start_cyclo_stack() {
    local services=()

    echo "[OMY iRASC] cyclo_loren 컨테이너를 실행합니다."
    setup_x11
    prepare_cyclo_mounts

    if ! container_running robotis_omy_loren; then
        echo "[OMY iRASC] robotis_omy_loren이 꺼져 있어 함께 실행합니다."
        services+=(robotis_omy)
    fi

    if ! container_running irasc_stack; then
        echo "[OMY iRASC] irasc_stack이 꺼져 있어 함께 실행합니다."
        services+=(irasc_omy_stack)
    fi

    services+=(cyclo_loren)
    compose up -d --build "${services[@]}"
    compose ps
}

case "${1:-}" in
    start)
        case "${2:-}" in
            cyclo)
                start_cyclo_stack
                ;;
            "")
                start_base_containers
                ;;
            *)
                echo "사용법: $0 start [cyclo]"
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
        compose up -d --build robotis_omy irasc_omy_stack
        compose ps
        ;;

    build)
        compose build
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
        echo "  $0 start          robotis_omy와 irasc_stack 빌드 및 실행"
        echo "  $0 start cyclo    cyclo_loren 실행, 필요하면 robotis/irasc도 함께 실행"
        echo "  $0 cyclo          start cyclo와 동일"
        echo "  $0 stop      두 컨테이너 종료"
        echo "  $0 restart   robotis_omy와 irasc_stack 재시작"
        echo "  $0 build     이미지 빌드"
        echo "  $0 enter robotis   robotis_omy 접속"
        echo "  $0 enter irasc     irasc_stack 접속"
        echo "  $0 enter cyclo     cyclo_loren 접속"
        echo "  $0 status    컨테이너 상태 확인"
        echo "  $0 logs      로그 확인"
        exit 1
        ;;
esac
