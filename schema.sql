-- Fresh AI Chat 0.2.1 | MariaDB / MySQL (UTF8MB4, InnoDB)
-- Create an empty database and a dedicated DB user in cPanel first, then run this file once.
-- Existing AI Engine and WordPress tables are not modified.
CREATE TABLE IF NOT EXISTS chat_users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  fresh_user_id BIGINT UNSIGNED NOT NULL,
  email VARCHAR(254) NOT NULL,
  display_name VARCHAR(160) NOT NULL DEFAULT '',
  role VARCHAR(16) NOT NULL DEFAULT 'user',
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  privacy_ack_at DATETIME NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_chat_users_fresh_user_id (fresh_user_id),
  KEY ix_chat_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_conversations (
  id CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  title VARCHAR(180) NOT NULL DEFAULT 'Nový chat',
  persona_snapshot_json TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_chat_conversations_user_updated (user_id, updated_at),
  CONSTRAINT fk_chat_conversations_user FOREIGN KEY (user_id) REFERENCES chat_users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_messages (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  conversation_id CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  role VARCHAR(12) NOT NULL,
  content LONGTEXT NOT NULL,
  metadata_json TEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_chat_messages_conversation_id (conversation_id, id),
  CONSTRAINT fk_chat_messages_conversation FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- After first account registration, grant admin manually using the Fresh Crackers user ID:
-- UPDATE chat_users SET role='admin' WHERE fresh_user_id=123 AND is_active=1;
-- To find your own Chat ID: SELECT id, fresh_user_id, email, role FROM chat_users;

CREATE TABLE IF NOT EXISTS chat_personas (
 user_id BIGINT UNSIGNED NOT NULL,
 preset VARCHAR(24) NOT NULL,
 assistant_name VARCHAR(36) NOT NULL,
 avatar_key VARCHAR(24) NOT NULL,
 tone VARCHAR(800) NOT NULL,
 greeting VARCHAR(160) NOT NULL,
 mobile_quick_button TINYINT(1) NOT NULL DEFAULT 0,
 created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 PRIMARY KEY(user_id),
 CONSTRAINT fk_chat_personas_user FOREIGN KEY(user_id) REFERENCES chat_users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chat_persona_generation_limits (
 user_id BIGINT UNSIGNED NOT NULL,
 last_generated_at DATETIME NOT NULL,
 usage_day DATE NOT NULL,
 daily_count TINYINT UNSIGNED NOT NULL DEFAULT 0,
 PRIMARY KEY (user_id),
 CONSTRAINT fk_chat_persona_generation_user FOREIGN KEY(user_id) REFERENCES chat_users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Fresh AI Chat 0.3.0, run on the EXISTING Chat database. No DELETE/TRUNCATE.
-- chat_users, chat_conversations, chat_messages and existing personas remain unchanged.
CREATE TABLE IF NOT EXISTS chat_memory (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  user_id BIGINT UNSIGNED NOT NULL,
  conversation_id CHAR(36) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  note_hash CHAR(64) CHARACTER SET ascii COLLATE ascii_general_ci NOT NULL,
  content TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY(id),
  UNIQUE KEY uq_chat_memory_user_hash (user_id,note_hash),
  KEY ix_chat_memory_user_created (user_id,created_at),
  CONSTRAINT fk_chat_memory_owner FOREIGN KEY(user_id) REFERENCES chat_users(id) ON DELETE CASCADE,
  CONSTRAINT fk_chat_memory_conversation FOREIGN KEY(conversation_id) REFERENCES chat_conversations(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
