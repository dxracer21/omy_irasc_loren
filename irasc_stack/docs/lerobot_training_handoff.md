# LeRobot Training Handoff Guide

작성 기준: 2026-08-12

이 문서는 iRASC / Cyclo / LeRobot Docker 환경에서 녹화된 rosbag2 데이터를 LeRobot 학습 데이터셋으로 변환하고, ACT 또는 SmolVLA 정책을 학습시키기 위한 핸드오프 가이드이다.

다른 연구원이 AI에게 그대로 붙여넣고 현재 프로젝트 구조를 이해시키는 것을 목적으로 한다.

## 핵심 원칙

- 작업 대상 repo는 `/home/user/jinsoo/omy_irasc_loren`이다.
- `isaaclab-woojin` 컨테이너는 건드리지 않는다.
- iRASC 학습/변환/모델 경로는 Docker volume으로 호스트에 보존된다.
- 컨테이너를 껐다 켜도 `/workspace` 아래 데이터는 유지된다.
- Git push에는 학습 데이터와 모델 파일이 올라가지 않는다.
- Docker image push에는 현재 volume에 있는 학습 데이터와 모델 파일이 포함되지 않는다.

## 주요 경로

### 호스트 기준

repo 루트:

```bash
/home/user/jinsoo/omy_irasc_loren
```

Cyclo / LeRobot 공유 workspace:

```bash
/home/user/jinsoo/omy_irasc_loren/data/cyclo/workspace
```

녹화된 raw rosbag2 데이터:

```bash
/home/user/jinsoo/omy_irasc_loren/data/cyclo/workspace/rosbag2
```

LeRobot 변환 데이터셋:

```bash
/home/user/jinsoo/omy_irasc_loren/data/cyclo/workspace/lerobot
```

학습된 모델:

```bash
/home/user/jinsoo/omy_irasc_loren/data/cyclo/workspace/model/lerobot
```

Hugging Face cache:

```bash
/home/user/jinsoo/omy_irasc_loren/data/cyclo/huggingface
```

### 컨테이너 내부 기준

Cyclo / iRASC / LeRobot policy 컨테이너에서 공통으로 보이는 workspace:

```bash
/workspace
```

raw rosbag2 데이터:

```bash
/workspace/rosbag2
```

LeRobot 변환 데이터셋:

```bash
/workspace/lerobot
```

학습된 모델:

```bash
/workspace/model/lerobot
```

Hugging Face cache:

```bash
/root/.cache/huggingface
```

## 컨테이너 실행

repo 루트에서 실행한다.

```bash
cd /home/user/jinsoo/omy_irasc_loren
```

iRASC 학습 컨테이너 실행:

```bash
./irasc_stack/docker/container.sh start irasc
```

Cyclo UI / 데이터 변환 컨테이너 실행:

```bash
./irasc_stack/docker/container.sh start cyclo
```

ROBOTIS OpenManipulator 컨테이너 실행:

```bash
./irasc_stack/docker/container.sh start robotis
```

전체 종료:

```bash
./irasc_stack/docker/container.sh stop
```

실행 상태 확인:

```bash
docker ps
```

## 환경 변수 확인

iRASC 컨테이너 안에서 ROS / Zenoh 설정 확인:

```bash
docker exec -it irasc_stack bash
env | grep -E 'ROS_DOMAIN_ID|RMW_IMPLEMENTATION|ZENOH_CONFIG_OVERRIDE'
```

기대값 예시:

```bash
ROS_DOMAIN_ID=30
RMW_IMPLEMENTATION=rmw_zenoh_cpp
ZENOH_CONFIG_OVERRIDE=mode="client";connect/endpoints=["tcp/172.16.101.221:7447"]
```

OMY IP는 `.env`에서 관리한다.

```bash
OMY_IP=172.16.101.221
ZENOH_PORT=7447
ROS_DOMAIN_ID=30
RMW_IMPLEMENTATION=rmw_zenoh_cpp
```

## 녹화 데이터 확인

호스트에서 raw rosbag2 데이터 목록:

```bash
find /home/user/jinsoo/omy_irasc_loren/data/cyclo/workspace/rosbag2 -maxdepth 2 -type d | sort
```

컨테이너 내부 기준:

```bash
docker exec -it cyclo_loren bash
find /workspace/rosbag2 -maxdepth 2 -type d | sort
```

예시 raw dataset:

```bash
/workspace/rosbag2/Task_test_rec_test_rec_MCAP
```

## LeRobot 데이터셋 변환

변환은 Cyclo 컨테이너에서 실행한다.

예시: `Task_test_rec_test_rec_MCAP`을 LeRobot v3.0 데이터셋으로 변환한다.

```bash
docker exec -it cyclo_loren bash -lc '
source /opt/ros/jazzy/setup.bash
source /root/ros2_ws/install/setup.bash

/root/ros2_ws/install/cyclo_data/lib/cyclo_data/convert_rosbag_to_lerobot \
  --input-dir /workspace/rosbag2/Task_test_rec_test_rec_MCAP \
  --output /workspace/lerobot/Task_test_rec_test_rec_MCAP_lerobot_v30 \
  --repo-id local/test_rec \
  --version v3.0 \
  --fps 30 \
  --robot-type omy_f3m \
  --robot-config /orchestrator_config/omy_f3m_config.yaml
'
```

변환 결과 확인:

```bash
find /home/user/jinsoo/omy_irasc_loren/data/cyclo/workspace/lerobot -maxdepth 2 -type d | sort
```

컨테이너 내부 학습 데이터 경로:

```bash
/workspace/lerobot/Task_test_rec_test_rec_MCAP_lerobot_v30
```

호스트 기준 학습 데이터 경로:

```bash
/home/user/jinsoo/omy_irasc_loren/data/cyclo/workspace/lerobot/Task_test_rec_test_rec_MCAP_lerobot_v30
```

## iRASC 학습 컨테이너 접속

iRASC 컨테이너에 들어간다.

```bash
docker exec -it irasc_stack bash
```

학습용 alias를 실행한다.

```bash
train
```

`train` alias는 LeRobot 학습에 필요한 Python 환경으로 들어가기 위한 편의 alias이다.

alias가 동작하지 않으면 컨테이너 안에서 다음을 먼저 확인한다.

```bash
alias | grep train
which lerobot-train
```

## ACT 학습 명령어

예시: `test_rec` 데이터셋을 ACT policy로 40000 step 학습한다.

```bash
train

lerobot-train \
  --dataset.repo_id local/test_rec \
  --dataset.root /workspace/lerobot/Task_test_rec_test_rec_MCAP_lerobot_v30 \
  --policy.type act \
  --policy.push_to_hub false \
  --output_dir /workspace/model/lerobot/test_rec_act \
  --job_name test_rec_act \
  --steps 40000 \
  --batch_size 8 \
  --num_workers 2 \
  --wandb.enable false \
  --save_checkpoint true \
  --save_freq 5000 \
  --save_checkpoint_to_hub false
```

학습된 모델 저장 위치:

```bash
/workspace/model/lerobot/test_rec_act
```

40000 step checkpoint의 inference 경로:

```bash
/workspace/model/lerobot/test_rec_act/checkpoints/040000/pretrained_model
```

호스트 기준:

```bash
/home/user/jinsoo/omy_irasc_loren/data/cyclo/workspace/model/lerobot/test_rec_act/checkpoints/040000/pretrained_model
```

## SmolVLA 학습 명령어

SmolVLA는 pretrained 모델과 tokenizer를 Hugging Face cache로 다운로드해서 사용한다.

Hugging Face cache는 volume mount되어 있으므로, 한 번 받은 파일은 컨테이너를 다시 만들어도 유지된다.

```bash
train

lerobot-train \
  --dataset.repo_id local/test_rec \
  --dataset.root /workspace/lerobot/Task_test_rec_test_rec_MCAP_lerobot_v30 \
  --policy.type smolvla \
  --policy.push_to_hub false \
  --output_dir /workspace/model/lerobot/test_rec_smolvla \
  --job_name test_rec_smolvla \
  --steps 40000 \
  --batch_size 8 \
  --num_workers 2 \
  --wandb.enable false \
  --save_checkpoint true \
  --save_freq 5000 \
  --save_checkpoint_to_hub false
```

SmolVLA 40000 step checkpoint의 inference 경로:

```bash
/workspace/model/lerobot/test_rec_smolvla/checkpoints/040000/pretrained_model
```

## 주요 학습 파라미터 의미

`--dataset.repo_id`

LeRobot 내부 dataset id이다. 로컬 데이터셋이면 `local/...` 형태로 둔다.

`--dataset.root`

실제 LeRobot 변환 데이터셋 경로이다. 이 프로젝트에서는 보통 `/workspace/lerobot/...`를 사용한다.

`--policy.type`

학습할 policy 종류이다. 현재 주로 사용하는 값은 `act`, `smolvla`이다.

`--policy.push_to_hub false`

학습된 policy를 Hugging Face Hub에 업로드하지 않는다.

`--output_dir`

학습 결과와 checkpoint가 저장되는 경로이다. 모델 이름을 사실상 여기서 정한다.

`--job_name`

학습 job 이름이다. 로그와 출력 식별용 이름이다.

`--steps`

학습 step 수이다. 예시에서는 40000을 사용한다.

`--batch_size`

한 step에 사용하는 batch 크기이다. GPU 메모리가 부족하면 줄인다.

`--num_workers`

데이터 로딩 worker 수이다.

`--wandb.enable false`

Weights & Biases 로깅을 끈다.

`--save_checkpoint true`

checkpoint 저장을 켠다.

`--save_freq 5000`

5000 step마다 checkpoint를 저장한다.

`--save_checkpoint_to_hub false`

checkpoint를 Hugging Face Hub에 업로드하지 않는다.

## 학습 후 checkpoint config 정리

LeRobot 학습 후 ROBOTIS `lerobot-zenoh` inference 컨테이너에서 다음과 비슷한 오류가 날 수 있다.

```text
TypeError: ... got an unexpected keyword argument 'pretrained_revision'
```

이 경우 checkpoint의 `config.json`에 inference 컨테이너가 받지 못하는 필드가 들어간 것이다.

repo 루트에서 아래 명령어를 실행한다.

```bash
cd /home/user/jinsoo/omy_irasc_loren
./irasc_stack/docker/container.sh fix-models
```

이 명령은 `/workspace/model/lerobot` 아래의 checkpoint config를 검사하고, 필요한 경우 `pretrained_revision` 필드를 제거한다.

## Inference에 넣을 모델 경로

ACT 예시:

```bash
/workspace/model/lerobot/test_rec_act/checkpoints/040000/pretrained_model
```

SmolVLA 예시:

```bash
/workspace/model/lerobot/test_rec_smolvla/checkpoints/040000/pretrained_model
```

Cyclo UI 또는 LeRobot inference 쪽에서 모델 경로를 넣을 때는 호스트 경로가 아니라 컨테이너 내부 경로인 `/workspace/...`를 사용한다.

## 자주 나는 문제

### convert_rosbag_to_lerobot: command not found

`convert_rosbag_to_lerobot`이 PATH에 없을 수 있다. 전체 경로로 실행한다.

```bash
/root/ros2_ws/install/cyclo_data/lib/cyclo_data/convert_rosbag_to_lerobot
```

그리고 실행 전 ROS setup을 source한다.

```bash
source /opt/ros/jazzy/setup.bash
source /root/ros2_ws/install/setup.bash
```

### 학습 데이터나 모델이 Git push에 안 올라감

정상이다. 학습 데이터와 모델은 repo 내부의 `data/cyclo/...` 아래에 있지만, 일반적으로 Git에는 올리지 않는다.

백업이 필요하면 아래 호스트 경로를 별도로 백업한다.

```bash
/home/user/jinsoo/omy_irasc_loren/data/cyclo/workspace/rosbag2
/home/user/jinsoo/omy_irasc_loren/data/cyclo/workspace/lerobot
/home/user/jinsoo/omy_irasc_loren/data/cyclo/workspace/model/lerobot
/home/user/jinsoo/omy_irasc_loren/data/cyclo/huggingface
```

### Docker image push에 학습 결과가 포함되지 않음

정상이다. 학습 데이터와 모델은 Docker image 안이 아니라 volume mount된 호스트 경로에 저장된다.

Docker image에는 의존성, Python 패키지, ROS workspace 빌드 결과 같은 실행 환경이 들어간다.

학습 데이터와 모델은 별도로 관리한다.

### SmolVLA 첫 학습이 오래 걸림

pretrained model, tokenizer 등 Hugging Face 파일을 처음 다운로드할 수 있다.

이 프로젝트에서는 Hugging Face cache가 아래 경로에 mount되어 있어 재다운로드를 줄인다.

호스트:

```bash
/home/user/jinsoo/omy_irasc_loren/data/cyclo/huggingface
```

컨테이너:

```bash
/root/.cache/huggingface
```

### Inference에서 loading 또는 inferencing에서 멈춤

먼저 LeRobot server 컨테이너 로그를 본다.

```bash
docker logs --tail 200 lerobot_server
```

Cyclo 컨테이너 로그도 같이 본다.

```bash
docker logs --tail 200 cyclo_loren
```

ROS / Zenoh 환경 변수가 맞는지 확인한다.

```bash
docker exec -it lerobot_server bash -lc 'env | grep -E "ROS_DOMAIN_ID|RMW_IMPLEMENTATION|ZENOH|WORKSPACE"'
docker exec -it cyclo_loren bash -lc 'env | grep -E "ROS_DOMAIN_ID|RMW_IMPLEMENTATION|ZENOH|WORKSPACE"'
```

## 새 데이터셋으로 반복할 때 바꿀 부분

예를 들어 새 raw rosbag2 폴더가 아래와 같다면:

```bash
/workspace/rosbag2/Task_new_demo_MCAP
```

변환 output:

```bash
/workspace/lerobot/Task_new_demo_MCAP_lerobot_v30
```

repo id:

```bash
local/task_new_demo
```

ACT output_dir:

```bash
/workspace/model/lerobot/task_new_demo_act
```

SmolVLA output_dir:

```bash
/workspace/model/lerobot/task_new_demo_smolvla
```

이 네 가지 이름만 일관되게 바꾸면 된다.

## 현재 test_rec 예시 요약

raw rosbag2:

```bash
/workspace/rosbag2/Task_test_rec_test_rec_MCAP
```

LeRobot dataset:

```bash
/workspace/lerobot/Task_test_rec_test_rec_MCAP_lerobot_v30
```

ACT model:

```bash
/workspace/model/lerobot/test_rec_act
```

ACT 40000 checkpoint:

```bash
/workspace/model/lerobot/test_rec_act/checkpoints/040000/pretrained_model
```

SmolVLA model:

```bash
/workspace/model/lerobot/test_rec_smolvla
```

SmolVLA 40000 checkpoint:

```bash
/workspace/model/lerobot/test_rec_smolvla/checkpoints/040000/pretrained_model
```
