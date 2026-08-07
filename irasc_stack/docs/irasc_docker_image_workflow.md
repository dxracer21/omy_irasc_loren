# iRASC Docker Image Workflow

This repository is organized so normal runtime uses prebuilt images, while image build/push is explicit.

## Files

- `irasc_stack/docker/compose.yaml`: runtime compose file. `irasc_omy_stack` uses `IRASC_STACK_IMAGE` and does not build locally.
- `irasc_stack/docker/compose.build.yaml`: build overlay used only by `container.sh build`, `push`, and `publish`.
- `irasc_stack/docker/Dockerfile`: recipe for producing the iRASC image. It can still use `robotis/open-manipulator:5.0.0` as the base image.
- `.env.example`: copy to `.env` after a fresh clone and set machine-specific values.

## Build and publish on the development machine

```bash
cp .env.example .env
# edit IRASC_STACK_IMAGE to your registry path, for example:
# IRASC_STACK_IMAGE=<dockerhub-id>/omy-irasc-stack:2026-08-07-smolvla

./irasc_stack/docker/container.sh build
docker login
./irasc_stack/docker/container.sh push

# or build and push in one command
./irasc_stack/docker/container.sh publish
```

## Run after a fresh clone

```bash
cp .env.example .env
# confirm OMY_IP=172.16.101.221 and edit IRASC_STACK_IMAGE
./irasc_stack/docker/container.sh pull
./irasc_stack/docker/container.sh start
./irasc_stack/docker/container.sh start cyclo
```

## Notes

- `start` no longer passes `--build`; it starts the images defined in `compose.yaml`.
- Host source/config/scripts are still mounted into `irasc_stack`, so ROS workspace changes are rebuilt inside the running container by `container.sh`.
- Hugging Face cache is mounted at `data/cyclo/huggingface`, so downloaded model files survive container replacement.
- If you install packages manually inside a running container, those changes are not in the image until you rebuild the Dockerfile or commit/tag/push the container intentionally.
