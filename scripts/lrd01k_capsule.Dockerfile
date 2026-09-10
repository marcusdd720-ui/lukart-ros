FROM python:3.11-slim
WORKDIR /capsule
COPY core/cross_environment_replay_verifier_v1.py /capsule/verifier.py
ENTRYPOINT ["python", "/capsule/verifier.py"]
