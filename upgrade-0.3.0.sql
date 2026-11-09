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
