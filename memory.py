import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class MemoryManager:
    def __init__(self, db_path: str, short_term_limit: int = 5, summarize_interval: int = 5):
        self.db_path = db_path
        self.short_term_limit = short_term_limit
        self.summarize_interval = summarize_interval
        self._init_db()

    def _init_db(self):
        """Initialize the SQLite database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Table for short-term memory (recent messages)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS short_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table for long-term memory (summarized conversations)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS long_term_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                summary TEXT NOT NULL,
                message_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Table to track message counts per user
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_message_counts (
                user_id TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        """)

        conn.commit()
        conn.close()

    def add_message(self, user_id: str, role: str, content: str) -> Tuple[List[Dict], Optional[str]]:
        """
        Add a message to short-term memory.
        Returns: (short_term_messages, summary_if_created)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Insert the new message
        cursor.execute(
            "INSERT INTO short_term_memory (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, role, content)
        )

        # Update message count for this user
        cursor.execute("""
            INSERT INTO user_message_counts (user_id, count)
            VALUES (?, 1)
            ON CONFLICT(user_id) DO UPDATE SET count = count + 1
        """, (user_id,))

        # Get current count
        cursor.execute("SELECT count FROM user_message_counts WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        current_count = result[0] if result else 0

        conn.commit()

        # Check if we need to summarize
        summary = None
        if current_count >= self.summarize_interval:
            summary = self._summarize_and_clear(user_id, cursor)
            # Reset count after summarization
            cursor.execute(
                "UPDATE user_message_counts SET count = 0 WHERE user_id = ?",
                (user_id,)
            )
            conn.commit()

        # Get current short-term memory for this user
        short_term = self._get_short_term_memory(user_id, cursor)

        conn.close()

        return short_term, summary

    def _get_short_term_memory(self, user_id: str, cursor) -> List[Dict]:
        """Get the most recent short-term messages for a user."""
        cursor.execute("""
            SELECT role, content FROM short_term_memory
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, self.short_term_limit))

        rows = cursor.fetchall()
        # Return in chronological order (oldest first)
        return [{"role": row[0], "content": row[1]} for row in reversed(rows)]

    def _summarize_and_clear(self, user_id: str, cursor) -> str:
        """Summarize messages and move to long-term memory."""
        # Get all messages for this user from short-term memory
        cursor.execute("""
            SELECT role, content FROM short_term_memory
            WHERE user_id = ?
            ORDER BY timestamp ASC
        """, (user_id,))

        messages = cursor.fetchall()

        if not messages:
            return ""

        # Create a summary from the messages
        conversation_text = "\n".join([
            f"{msg[0]}: {msg[1]}" for msg in messages
        ])

        # Simple extraction-based summary (the actual summarization
        # will be done by the LLM in the main bot)
        summary = f"Conversation summary ({len(messages)} messages)"

        # Store in long-term memory
        cursor.execute(
            "INSERT INTO long_term_memory (user_id, summary, message_count) VALUES (?, ?, ?)",
            (user_id, conversation_text, len(messages))
        )

        # Clear short-term memory for this user
        cursor.execute("DELETE FROM short_term_memory WHERE user_id = ?", (user_id,))

        return conversation_text

    def get_long_term_memory(self, user_id: str) -> List[str]:
        """Get all long-term memory summaries for a user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT summary FROM long_term_memory
            WHERE user_id = ?
            ORDER BY created_at ASC
        """, (user_id,))

        rows = cursor.fetchall()
        conn.close()

        return [row[0] for row in rows]

    def get_combined_memory(self, user_id: str) -> List[Dict]:
        """
        Get combined memory for a user: long-term summaries + recent short-term messages.
        Returns a list formatted for the LLM.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        memory = []

        # Add long-term memory as system context
        cursor.execute("""
            SELECT summary FROM long_term_memory
            WHERE user_id = ?
            ORDER BY created_at ASC
        """, (user_id,))

        long_term_summaries = cursor.fetchall()
        for summary in long_term_summaries:
            memory.append({
                "role": "system",
                "content": f"[Previous conversation memory]: {summary[0]}"
            })

        # Add recent short-term messages
        cursor.execute("""
            SELECT role, content FROM short_term_memory
            WHERE user_id = ?
            ORDER BY timestamp ASC
            LIMIT ?
        """, (user_id, self.short_term_limit))

        short_term = cursor.fetchall()
        for msg in short_term:
            memory.append({"role": msg[0], "content": msg[1]})

        conn.close()

        return memory

    def clear_user_memory(self, user_id: str):
        """Clear all memory for a specific user."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM short_term_memory WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM long_term_memory WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM user_message_counts WHERE user_id = ?", (user_id,))

        conn.commit()
        conn.close()
