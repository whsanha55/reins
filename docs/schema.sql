-- reins 스키마 단일진실 (v1). CREATE TABLE + INSERT(init data) + CREATE INDEX 만.
-- 런타임 행 갱신은 앱 코드(server/app) 에서. 본 파일엔 DDL + 초기데이터만.
-- 마이그레이터(server/migrate.py)가 본 파일을 그대로 실행.

-- ============================================================ projects
CREATE TABLE IF NOT EXISTS projects (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    color       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================ tickets
-- parent_id self-ref = 에픽(D-DR2). status 풀 단어(D-DR8). updated_at 정렬용(D-DR8).
CREATE TABLE IF NOT EXISTS tickets (
    id           BIGSERIAL PRIMARY KEY,
    project_id   BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title        TEXT NOT NULL,
    description  TEXT,
    type         TEXT NOT NULL DEFAULT 'task',        -- task | epic
    parent_id    BIGINT REFERENCES tickets(id) ON DELETE SET NULL,  -- 에픽 self-ref
    priority     INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'todo',        -- todo|progressing|qa|done|cancel
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT tickets_status_chk CHECK (status IN ('todo','progressing','qa','done','cancel')),
    CONSTRAINT tickets_type_chk  CHECK (type IN ('task','epic'))
);
CREATE INDEX IF NOT EXISTS idx_tickets_project   ON tickets(project_id);
CREATE INDEX IF NOT EXISTS idx_tickets_parent     ON tickets(parent_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status     ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_updated    ON tickets(updated_at);
CREATE INDEX IF NOT EXISTS idx_tickets_created    ON tickets(created_at);
CREATE INDEX IF NOT EXISTS idx_tickets_claim      ON tickets(created_at) WHERE status='todo';

-- ============================================================ ticket_events (append-only, 커서)
CREATE TABLE IF NOT EXISTS ticket_events (
    id          BIGSERIAL PRIMARY KEY,
    ticket_id   BIGINT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    payload     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_events_ticket_created ON ticket_events(ticket_id, id);

-- ============================================================ ticket_comments (D-DR2/D-DR6)
CREATE TABLE IF NOT EXISTS ticket_comments (
    id          BIGSERIAL PRIMARY KEY,
    ticket_id   BIGINT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    author      TEXT NOT NULL,
    body        TEXT NOT NULL,
    read_at     TIMESTAMPTZ,                          -- agent-read ✓ 인디케이터
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_comments_ticket ON ticket_comments(ticket_id, created_at);

-- ============================================================ decisions (결정 큐, idempotent)
CREATE TABLE IF NOT EXISTS decisions (
    id              BIGSERIAL PRIMARY KEY,
    ticket_id       BIGINT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    gate            TEXT NOT NULL,                    -- pr_open|merge|deploy|spec_ambiguous
    summary         TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending|approved|rejected|changes
    resolution_note TEXT,
    agent_run_id    BIGINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at     TIMESTAMPTZ,
    CONSTRAINT decisions_status_chk CHECK (status IN ('pending','approved','rejected','changes')),
    CONSTRAINT decisions_gate_chk   CHECK (gate IN ('pr_open','merge','deploy','spec_ambiguous'))
);
-- idempotent: (ticket_id,gate) 당 pending 1개만. 중복 resolve 는 앱측 WHERE status='pending' 로 차단.
CREATE UNIQUE INDEX IF NOT EXISTS uq_decisions_pending ON decisions(ticket_id, gate) WHERE status='pending';
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status, created_at);

-- ============================================================ agent_runs (heartbeat, lifecycle)
CREATE TABLE IF NOT EXISTS agent_runs (
    id           BIGSERIAL PRIMARY KEY,
    ticket_id    BIGINT NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    status       TEXT NOT NULL DEFAULT 'running',     -- running|succeeded|failed|stalled
    heartbeat_at TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ,
    result       JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT runs_status_chk CHECK (status IN ('running','succeeded','failed','stalled'))
);
CREATE INDEX IF NOT EXISTS idx_runs_status_heartbeat ON agent_runs(status, heartbeat_at);
CREATE INDEX IF NOT EXISTS idx_runs_ticket ON agent_runs(ticket_id);

-- ============================================================ workflow_actions (T8 확장점, Phase2 drop-in)
CREATE TABLE IF NOT EXISTS workflow_actions (
    id           BIGSERIAL PRIMARY KEY,
    trigger_from TEXT,
    trigger_to   TEXT,
    action_type  TEXT NOT NULL,                       -- agent_run|telegram|decision|ci|deploy
    enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================ notify_routes (scoophub 패턴)
-- category = 이벤트 topic(decision|stalled|digest|info). topic_id NULL+topic_name → 첫 발신시 createForumTopic.
CREATE TABLE IF NOT EXISTS notify_routes (
    id          BIGSERIAL PRIMARY KEY,
    category    TEXT NOT NULL DEFAULT '',             -- ''=wildcard
    channel     TEXT NOT NULL DEFAULT 'telegram',
    chat_id     TEXT,
    topic_id    INTEGER,
    topic_name  TEXT,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT routes_category_chk CHECK (category IN ('','decision','stalled','digest','info'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_routes_category_channel ON notify_routes(category, channel);

-- ============================================================ notify_log (중복방지)
CREATE TABLE IF NOT EXISTS notify_log (
    id          BIGSERIAL PRIMARY KEY,
    route_id    BIGINT NOT NULL REFERENCES notify_routes(id) ON DELETE CASCADE,
    payload_key TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL,                        -- success|error
    error       TEXT,
    sent_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT notifylog_status_chk CHECK (status IN ('success','error'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_notifylog_route_payload ON notify_log(route_id, payload_key);

-- ============================================================ audit_log (append-only, TRUST)
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    entity      TEXT NOT NULL,
    entity_id   BIGINT,
    action      TEXT NOT NULL,
    actor       TEXT,
    payload     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================ init data
-- 워크플로우 기본 액션(v1 하드코딩과 동일). Phase2 drop-in 확장점.
INSERT INTO workflow_actions (trigger_from, trigger_to, action_type) VALUES
    ('todo', 'progressing', 'agent_run'),
    ('progressing', 'qa', 'telegram'),
    ('qa', 'done', 'telegram'),
    ('qa', 'progressing', 'telegram')
ON CONFLICT DO NOTHING;
