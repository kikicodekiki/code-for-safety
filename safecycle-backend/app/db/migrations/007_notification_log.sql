-- Migration 007: Notification audit log table
-- Stores every notification dispatched by the system for debugging,
-- analytics, and delivery confirmation.

CREATE TABLE IF NOT EXISTS notification_log (
    id                  BIGSERIAL PRIMARY KEY,
    device_id           TEXT        NOT NULL,
    notification_type   TEXT        NOT NULL,
    title               TEXT        NOT NULL,
    urgency             TEXT        NOT NULL,
    -- Array of channel values: 'websocket', 'local_push', 'fcm'
    channels_sent       TEXT[]      NOT NULL DEFAULT '{}',
    suppressed          BOOLEAN     NOT NULL DEFAULT FALSE,
    debounced           BOOLEAN     NOT NULL DEFAULT FALSE,
    -- Optional context
    route_id            TEXT,
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    -- Payload data stored as JSONB for queryability
    data                JSONB       NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for per-device notification history (most recent first)
CREATE INDEX IF NOT EXISTS idx_notification_log_device_id
    ON notification_log (device_id, created_at DESC);

-- Index for analytics by type
CREATE INDEX IF NOT EXISTS idx_notification_log_type
    ON notification_log (notification_type, created_at DESC);

-- Index for suppression analysis
CREATE INDEX IF NOT EXISTS idx_notification_log_suppressed
    ON notification_log (suppressed, debounced, created_at DESC)
    WHERE suppressed = TRUE OR debounced = TRUE;

-- Partial index for delivered notifications (not suppressed/debounced)
CREATE INDEX IF NOT EXISTS idx_notification_log_delivered
    ON notification_log (device_id, notification_type, created_at DESC)
    WHERE suppressed = FALSE AND debounced = FALSE;

COMMENT ON TABLE notification_log IS
    'Audit log of every notification dispatched by SafeCycle Sofia. '
    'Used for delivery confirmation, debugging, and alert fatigue analysis.';

COMMENT ON COLUMN notification_log.channels_sent IS
    'Channels through which the notification was actually delivered. '
    'Empty array means all channels failed or notification was suppressed.';

COMMENT ON COLUMN notification_log.suppressed IS
    'True if suppressed by preference, quiet hours, or navigation state check.';

COMMENT ON COLUMN notification_log.debounced IS
    'True if suppressed because the same notification was sent recently.';
