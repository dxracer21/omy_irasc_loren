#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

COMPOSE_FILE="${SCRIPT_DIR}/compose.yaml"
ENV_FILE="${PROJECT_ROOT}/.env"
PROJECT_NAME="omy_irasc_loren"

compose() {
    docker compose \
        -p "${PROJECT_NAME}" \
        --env-file "${ENV_FILE}" \
        -f "${COMPOSE_FILE}" \
        "$@"
}

case "${1:-}" in
    start)
        echo "[OMY iRASC] 컨테이너를 빌드하고 실행합니다."

        if command -v xhost >/dev/null 2>&1; then
            xhost +local:root >/dev/null 2>&1 || true
        fi

        compose up -d --build
        compose ps
        ;;

    stop)
        echo "[OMY iRASC] 컨테이너를 종료합니다."
        compose down
        ;;

    restart)
        compose down
        compose up -d --build
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
            *)
                echo "사용법:"
                echo "  $0 enter robotis   robotis_omy_loren 접속"
                echo "  $0 enter irasc     irasc_stack 접속"
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
        echo "  $0 start     두 컨테이너 빌드 및 실행"
        echo "  $0 stop      두 컨테이너 종료"
        echo "  $0 restart   두 컨테이너 재시작"
        echo "  $0 build     이미지 빌드"
        echo "  $0 robotis   robotis_omy 접속"
        echo "  $0 app       irasc_app 접속"
        echo "  $0 status    컨테이너 상태 확인"
        echo "  $0 logs      로그 확인"
        exit 1
        ;;
esac
