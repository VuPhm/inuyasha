FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY \
    server/emulator.py \
    server/private_server.py \
    server/private_auth.py \
    server/economy_audit.py \
    server/combat_effects.py \
    server/combat_sim.py \
    server/event_runtime.py \
    server/event_handlers.py \
    server/r79_event_handlers.py \
    server/bdd_handlers.py \
    server/teambattle_handlers.py \
    server/nightmare_handlers.py \
    server/reborn_handlers.py \
    server/ggzj_handlers.py \
    server/gddh_handlers.py \
    server/social_handlers.py \
    server/guild_handlers.py \
    server/pvpinter_handlers.py \
    server/pet_handlers.py \
    server/warfare_handlers.py \
    server/game_data.json \
    server/bdd_data.json \
    server/pet_data.json \
    server/warfare_data.json \
    /app/server/

RUN mkdir -p /data

EXPOSE 8080

VOLUME ["/data"]

CMD ["python3", "/app/server/private_server.py", "--host", "0.0.0.0", "--port", "8080", "--data-dir", "/data"]
