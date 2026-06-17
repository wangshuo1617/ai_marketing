import sqlite3
import pandas as pd
from datetime import datetime
from typing import Any, List, Dict, Optional
import os

DB_PATH = "ai_marketing.db"

class DBManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # 0. AI News Candidates Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ai_news_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    content TEXT,
                    url TEXT,
                    source TEXT,
                    type TEXT,
                    tags TEXT,
                    published_at TEXT,
                    relevance_score REAL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT
                )
            ''')
            existing_candidate_columns = {
                row[1] for row in cursor.execute("PRAGMA table_info(ai_news_candidates)").fetchall()
            }
            candidate_columns = {
                "type": "TEXT",
                "tags": "TEXT",
                "published_at": "TEXT",
                "relevance_score": "REAL",
            }
            for column, column_type in candidate_columns.items():
                if column not in existing_candidate_columns:
                    cursor.execute(f"ALTER TABLE ai_news_candidates ADD COLUMN {column} {column_type}")

            # 1. Inspirations Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS inspirations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    content TEXT,
                    url TEXT,
                    source TEXT,
                    type TEXT,
                    tags TEXT,
                    created_at TEXT
                )
            ''')

            # 2. Topic Facts Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS topic_facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact TEXT,
                    discussion_score REAL,
                    reason TEXT,
                    run_id TEXT,
                    created_at TEXT
                )
            ''')

            # 3. Fact-Inspiration Mapping (Many-to-Many)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fact_sources (
                    fact_id INTEGER,
                    inspiration_id INTEGER,
                    FOREIGN KEY (fact_id) REFERENCES topic_facts (id),
                    FOREIGN KEY (inspiration_id) REFERENCES inspirations (id)
                )
            ''')

            # 4. Topic Outlines Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS topic_outlines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fact_id INTEGER,
                    title_hook TEXT,
                    anxiety_background TEXT,
                    technical_breakdown TEXT,
                    practical_solution TEXT,
                    private_domain_hook TEXT,
                    content_angle TEXT,
                    created_at TEXT,
                    FOREIGN KEY (fact_id) REFERENCES topic_facts (id)
                )
            ''')

            # 5. Platform Drafts Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS platform_drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    outline_id INTEGER,
                    platform TEXT,
                    title TEXT,
                    body TEXT,
                    word_count INTEGER,
                    score REAL,
                    passed BOOLEAN,
                    issues TEXT,
                    created_at TEXT,
                    FOREIGN KEY (outline_id) REFERENCES topic_outlines (id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS complete_drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    draft_id INTEGER,
                    title TEXT,
                    markdown TEXT,
                    version INTEGER,
                    created_at TEXT,
                    updated_at TEXT,
                    FOREIGN KEY (draft_id) REFERENCES platform_drafts (id)
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS draft_images (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    draft_id INTEGER,
                    complete_draft_id INTEGER,
                    image_index INTEGER,
                    alt_text TEXT,
                    prompt TEXT,
                    local_path TEXT,
                    public_url TEXT,
                    markdown_position TEXT,
                    created_at TEXT,
                    FOREIGN KEY (draft_id) REFERENCES platform_drafts (id),
                    FOREIGN KEY (complete_draft_id) REFERENCES complete_drafts (id)
                )
            ''')
            conn.commit()

    # --- Generic Helpers ---
    def execute_query(self, query: str, params: tuple = ()):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor

    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def save_dataframe(self, df: pd.DataFrame, table_name: str, if_exists: str = 'append'):
        """Save a pandas DataFrame to a SQLite table. 
        Strictly forbid 'replace' to prevent accidental data loss.
        """
        if if_exists == 'replace':
            raise RuntimeError(
                f"Dangerous operation: 'replace' is forbidden in save_dataframe for table '{table_name}'. "
                "Use a specific DELETE query if you need to clear data, or use 'append'."
            )
        with self._get_connection() as conn:
            df.to_sql(table_name, conn, if_exists=if_exists, index=False)

    # --- Specific Business Methods ---
    def add_inspiration(self, data: Dict[str, Any]):
        query = '''
            INSERT INTO inspirations (title, content, url, source, type, tags, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            data.get('title'), data.get('content'), data.get('url'),
            data.get('source'), data.get('type'), data.get('tags'),
            data.get('created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid

    def replace_ai_news_candidates(self, df: pd.DataFrame):
        columns = [
            "title", "content", "url", "source", "type", "tags",
            "published_at", "created_at", "relevance_score", "status",
        ]
        candidate_df = df.copy()
        for column in columns:
            if column not in candidate_df.columns:
                candidate_df[column] = ""
        candidate_df = candidate_df[columns]
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ai_news_candidates")
            candidate_df.to_sql("ai_news_candidates", conn, if_exists="append", index=False)
            conn.commit()

    def add_topic_fact(self, fact_data: Dict[str, Any], source_ids: List[int]):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Insert Fact
            cursor.execute('''
                INSERT INTO topic_facts (fact, discussion_score, reason, run_id, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                fact_data.get('fact'), fact_data.get('discussion_score'),
                fact_data.get('reason'), fact_data.get('run_id'),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            fact_id = cursor.lastrowid
            
            # Insert Mappings
            for s_id in source_ids:
                cursor.execute('INSERT INTO fact_sources (fact_id, inspiration_id) VALUES (?, ?)', (fact_id, s_id))
            
            conn.commit()
            return fact_id

    def add_topic_outline(self, outline_data: Dict[str, Any]):
        query = '''
            INSERT INTO topic_outlines (fact_id, title_hook, anxiety_background, technical_breakdown, 
                                        practical_solution, private_domain_hook, content_angle, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            outline_data.get('fact_id'), outline_data.get('title_hook'),
            outline_data.get('anxiety_background'), outline_data.get('technical_breakdown'),
            outline_data.get('practical_solution'), outline_data.get('private_domain_hook'),
            outline_data.get('content_angle'), datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid

    def add_platform_draft(self, draft_data: Dict[str, Any]):
        query = '''
            INSERT INTO platform_drafts (outline_id, platform, title, body, word_count, score, passed, issues, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            draft_data.get('outline_id'), draft_data.get('platform'),
            draft_data.get('title'), draft_data.get('body'),
            draft_data.get('word_count'), draft_data.get('score'),
            draft_data.get('passed'), draft_data.get('issues'),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.lastrowid

    def save_complete_draft(self, draft_id: int, title: str, markdown: str) -> int:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = self.fetch_all("SELECT MAX(version) AS version FROM complete_drafts WHERE draft_id = ?", (draft_id,))
        next_version = int((rows[0].get("version") if rows else 0) or 0) + 1
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO complete_drafts (draft_id, title, markdown, version, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (draft_id, title, markdown, next_version, now, now),
            )
            conn.commit()
            return cursor.lastrowid

    def add_draft_image(self, image_data: Dict[str, Any]) -> int:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO draft_images (
                    draft_id, complete_draft_id, image_index, alt_text, prompt,
                    local_path, public_url, markdown_position, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    image_data.get("draft_id"),
                    image_data.get("complete_draft_id"),
                    image_data.get("image_index"),
                    image_data.get("alt_text"),
                    image_data.get("prompt"),
                    image_data.get("local_path"),
                    image_data.get("public_url"),
                    image_data.get("markdown_position"),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
            conn.commit()
            return cursor.lastrowid
