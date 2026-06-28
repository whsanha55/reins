# deploy/ — reins 보드 배포 (host agent)

reins UI/API 에서 "Deploy" 버튼 → jjong host agent 가 각 repo 의 `deploy.sh` 실행.
controller/agent 분리: reins API(container)=큐, 본 agent(host)=실행.

## 파일

- `agent.sh` — 폴링 루프. claim → `git fetch + reset --hard origin/<ref> + bash deploy.sh` → result 회신.
- `reins-deploy-agent.service` — systemd 유닛.

## 동작 원리

1. UI `POST /api/projects/{pid}/deploy` → `deploy_jobs` pending row.
2. agent 폴링 `POST /api/deploy/claim` → row running 으로 클레임.
3. agent: `cd <host_path> && git fetch --prune origin && git reset --hard origin/<ref> && bash deploy.sh`.
4. agent `POST /api/deploy/{id}/result` `{status, exit_code, log_tail}`.
5. UI 이력에서 status + log tail 확인.

**책임 분리(model 2)**: agent=공통 git 동기화, 각 repo `deploy.sh`=빌드(`docker compose up -d --build` 등). 호스트 `~/*.sh` 래퍼 불필요.

**자기 배포(reins→reins)**: agent 는 호스트 프로세스라 api 컨테이너 재기동 중에도 실행 계속. result 는 `--retry-connrefused` 로 api 복귀 후 재전송.

## 설치 (jjong)

1. 의존: `sudo apt-get install -y jq` (curl/git 읔 보통 있음).
2. env 파일:
   ```bash
   sudo install -d /etc/reins
   sudo tee /etc/reins/deploy-agent.env >/dev/null <<'EOF'
   REINS_API_URL=http://127.0.0.1:21001
   REINS_TOKEN=<reins API 토큰>
   POLL_INTERVAL=5
   EOF
   ```
3. 유닛 설치/기동:
   ```bash
   sudo cp ~/reins/deploy/reins-deploy-agent.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now reins-deploy-agent
   journalctl -u reins-deploy-agent -f
   ```
4. reins project 의 `host_path` 세팅(`/home/ubuntu/reins`) — UI 편집 또는
   `PATCH /api/projects/1 {"host_path":"/home/ubuntu/reins"}`.

## 새 프로젝트 추가

1. 해당 repo 루트에 `deploy.sh` commit (빌드/serve 스텝).
2. reins 에 프로젝트 등록 + `host_path` 세팅(host 체크아웃 경로).
3. 끝. agent 가 자동 잡음.
