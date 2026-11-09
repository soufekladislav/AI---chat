"""Fresh AI Chat database access. All queries are scoped to a logged-in Chat user."""
from contextlib import contextmanager
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
import pymysql
from pymysql.cursors import DictCursor


def connection():
    params = dict(
        host=os.getenv('CHAT_DB_HOST',''),
        port=int(os.getenv('CHAT_DB_PORT','3306')),
        user=os.getenv('CHAT_DB_USER',''),
        password=os.getenv('CHAT_DB_PASSWORD',''),
        database=os.getenv('CHAT_DB_NAME',''),
        charset='utf8mb4', cursorclass=DictCursor,
        connect_timeout=8, read_timeout=15, write_timeout=15, autocommit=False,
    )
    if not all(params[k] for k in ('host','user','database')):
        raise RuntimeError('Databáze Chatu není nakonfigurovaná.')
    return pymysql.connect(**params)


@contextmanager
def transaction():
    db=connection()
    try:
        with db.cursor() as cur:
            yield cur
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def fetchone(sql, args=()):
    with transaction() as cur:
        cur.execute(sql,args)
        return cur.fetchone()


def fetchall(sql, args=()):
    with transaction() as cur:
        cur.execute(sql,args)
        return cur.fetchall()


def user_by_id(user_id):
    return fetchone('SELECT * FROM chat_users WHERE id=%s AND is_active=1',(user_id,))


def user_by_fresh_id(fresh_id):
    return fetchone('SELECT * FROM chat_users WHERE fresh_user_id=%s',(fresh_id,))


def create_user(remote):
    # The only call-site is after confirmed central identity + explicit Chat consent.
    fresh_id=int(remote['user_id'])
    if fresh_id <= 0 or not remote.get('verified'):
        raise ValueError('Centrální účet není ověřený.')
    email=str(remote['email']).strip().lower()[:254]
    billing=remote.get('billing') or {}
    name=str(billing.get('name') or remote.get('display_name') or email.split('@')[0])[:160]
    with transaction() as cur:
        cur.execute('SELECT id,is_active FROM chat_users WHERE fresh_user_id=%s FOR UPDATE',(fresh_id,))
        old=cur.fetchone()
        if old:
            if not old['is_active']:
                raise ValueError('Tento účet Chatu je deaktivovaný. Kontaktuj podporu.')
            return old['id']
        cur.execute('''INSERT INTO chat_users (fresh_user_id,email,display_name,role,is_active,privacy_ack_at)
                       VALUES (%s,%s,%s,'user',1,UTC_TIMESTAMP())''',(fresh_id,email,name))
        return cur.lastrowid


def update_identity(user_id, remote):
    # E-mail is central; the Chat display name is a local user preference.
    email=str(remote.get('email') or '').lower()[:254]
    with transaction() as cur:
        cur.execute('UPDATE chat_users SET email=%s WHERE id=%s AND is_active=1',(email,user_id))


def list_conversations(user_id, limit=80):
    return fetchall('''SELECT id,title,created_at,updated_at FROM chat_conversations
                       WHERE user_id=%s ORDER BY updated_at DESC LIMIT %s''',(user_id,min(limit,100)))


def owned_conversation(user_id, conversation_id):
    return fetchone('SELECT id,title FROM chat_conversations WHERE id=%s AND user_id=%s',(conversation_id,user_id))


def new_conversation(user_id, persona):
    conversation_id=str(uuid.uuid4())
    with transaction() as cur:
        cur.execute('INSERT INTO chat_conversations (id,user_id,persona_snapshot_json) VALUES (%s,%s,%s)',
                    (conversation_id,user_id,json.dumps(persona,ensure_ascii=False)))
    return conversation_id


def get_messages(user_id, conversation_id):
    if not owned_conversation(user_id,conversation_id):
        return None
    rows=fetchall('''SELECT role,content,metadata_json,created_at FROM chat_messages
                     WHERE conversation_id=%s ORDER BY id DESC LIMIT 300''',(conversation_id,))
    rows.reverse()  # show the latest messages in chronological order
    for row in rows:
        try: row['meta']=json.loads(row.pop('metadata_json') or 'null')
        except (ValueError,TypeError): row['meta']=None
    return rows


def history_for_engine(user_id, conversation_id):
    if not owned_conversation(user_id,conversation_id):
        return None
    rows=fetchall('''SELECT role,content FROM chat_messages WHERE conversation_id=%s
                     ORDER BY id DESC LIMIT 14''',(conversation_id,))
    return list(reversed(rows))


def save_turn(user_id, conversation_id, prompt, result, persona=None):
    reply=str(result.get('output') or '')
    meta={k:result.get(k) for k in ('provider','model','latency_ms','estimated_cost_usd','job_id')}
    if persona is not None: meta['persona']=persona
    with transaction() as cur:
        cur.execute('SELECT id,title,persona_snapshot_json FROM chat_conversations WHERE id=%s AND user_id=%s FOR UPDATE',
                    (conversation_id,user_id))
        convo=cur.fetchone()
        if not convo: raise ValueError('Konverzace neexistuje.')
        if persona is not None:
            try: previous = json.loads(convo['persona_snapshot_json'] or '{}')
            except (TypeError, ValueError): previous = {}
            # Existing assistant messages retain the persona under which they were
            # generated. Backfill pre-upgrade messages once, before switching.
            if previous and previous != persona:
                cur.execute('''SELECT id,metadata_json FROM chat_messages
                               WHERE conversation_id=%s AND role='assistant' FOR UPDATE''', (conversation_id,))
                for item in cur.fetchall():
                    try: old_meta=json.loads(item['metadata_json'] or '{}')
                    except (TypeError, ValueError): old_meta={}
                    if not isinstance(old_meta,dict): old_meta={}
                    if 'persona' not in old_meta:
                        old_meta['persona']=previous
                        cur.execute('UPDATE chat_messages SET metadata_json=%s WHERE id=%s',
                                    (json.dumps(old_meta,ensure_ascii=False),item['id']))
                cur.execute('UPDATE chat_conversations SET persona_snapshot_json=%s WHERE id=%s',
                            (json.dumps(persona,ensure_ascii=False),conversation_id))
        cur.execute('INSERT INTO chat_messages (conversation_id,role,content) VALUES (%s,%s,%s)',
                    (conversation_id,'user',prompt))
        cur.execute('INSERT INTO chat_messages (conversation_id,role,content,metadata_json) VALUES (%s,%s,%s,%s)',
                    (conversation_id,'assistant',reply,json.dumps(meta,ensure_ascii=False)))
        if convo['title']=='Nový chat':
            cur.execute('UPDATE chat_conversations SET title=%s,updated_at=UTC_TIMESTAMP() WHERE id=%s',
                        (prompt[:90].replace('\n',' '),conversation_id))
        else:
            cur.execute('UPDATE chat_conversations SET updated_at=UTC_TIMESTAMP() WHERE id=%s',(conversation_id,))



def last_model_for_conversation(user_id, conversation_id):
    if not owned_conversation(user_id, conversation_id):
        return None
    rows=fetchall('''SELECT metadata_json FROM chat_messages WHERE conversation_id=%s
                     AND role='assistant' ORDER BY id DESC LIMIT 30''', (conversation_id,))
    for row in rows:
        try: meta=json.loads(row.get('metadata_json') or '{}')
        except (TypeError, ValueError): continue
        if isinstance(meta,dict) and meta.get('provider') and meta.get('model') and meta['provider'] not in ('chat','local-info'):
            return {'provider':str(meta['provider']), 'model':str(meta['model'])}
    return None

def recent_user_requests(user_id,minutes=10):
    row=fetchone('''SELECT COUNT(*) AS n FROM chat_messages m
                    INNER JOIN chat_conversations c ON c.id=m.conversation_id
                    WHERE c.user_id=%s AND m.role='user' AND m.created_at>=UTC_TIMESTAMP()-INTERVAL %s MINUTE''',
                    (user_id,minutes))
    return row['n'] if row else 0


def delete_conversation(user_id, conversation_id):
    with transaction() as cur:
        cur.execute('DELETE FROM chat_conversations WHERE id=%s AND user_id=%s',(conversation_id,user_id))
        return cur.rowcount


def get_persona(user_id):
    return fetchone('''SELECT preset,assistant_name,avatar_key,tone,greeting,mobile_quick_button
                       FROM chat_personas WHERE user_id=%s''',(user_id,))


def set_persona(user_id, values):
    with transaction() as cur:
        cur.execute('''INSERT INTO chat_personas (user_id,preset,assistant_name,avatar_key,tone,greeting,mobile_quick_button)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)
                       ON DUPLICATE KEY UPDATE preset=VALUES(preset),assistant_name=VALUES(assistant_name),
                       avatar_key=VALUES(avatar_key),tone=VALUES(tone),greeting=VALUES(greeting),
                       mobile_quick_button=VALUES(mobile_quick_button)''',
                    (user_id,values['preset'],values['assistant_name'],values['avatar_key'],
                     values['tone'],values['greeting'],int(values['mobile_quick_button'])))


def claim_persona_generation(user_id):
    """Atomic per-customer limit: 1 per minute and 10 per UTC calendar day."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    with transaction() as cur:
        # INSERT IGNORE + SELECT FOR UPDATE is safe for simultaneous Passenger workers.
        cur.execute('''INSERT IGNORE INTO chat_persona_generation_limits
                       (user_id,last_generated_at,usage_day,daily_count)
                       VALUES (%s,DATE_SUB(UTC_TIMESTAMP(),INTERVAL 2 DAY),UTC_DATE(),0)''',(user_id,))
        cur.execute('''SELECT last_generated_at,usage_day,daily_count
                       FROM chat_persona_generation_limits WHERE user_id=%s FOR UPDATE''',(user_id,))
        row=cur.fetchone()
        if not row: return False
        if row['last_generated_at'] and now-row['last_generated_at'] < timedelta(seconds=60):
            return False
        count=int(row['daily_count']) if row['usage_day']==now.date() else 0
        if count>=10: return False
        cur.execute('''UPDATE chat_persona_generation_limits SET
                       last_generated_at=UTC_TIMESTAMP(),usage_day=UTC_DATE(),daily_count=%s
                       WHERE user_id=%s''',(count+1,user_id))
        return True


def conversation_persona(user_id, conversation_id):
    return fetchone('''SELECT c.persona_snapshot_json FROM chat_conversations c
                       WHERE c.id=%s AND c.user_id=%s''',(conversation_id,user_id))


# Explicit notes, scoped to the authenticated Chat user. No global indexes or raw
# conversation scraping; the entire original chat remains in chat_messages.
def store_explicit_note(user_id, conversation_id, text):
    import hashlib
    text = str(text or '').strip()[:1800]
    if not text or not owned_conversation(user_id, conversation_id):
        raise ValueError('Poznámku nelze uložit.')
    digest = hashlib.sha256(text.casefold().encode('utf-8')).hexdigest()
    with transaction() as cur:
        cur.execute("""INSERT INTO chat_memory (user_id,conversation_id,note_hash,content)
                       VALUES (%s,%s,%s,%s)
                       ON DUPLICATE KEY UPDATE conversation_id=VALUES(conversation_id), id=LAST_INSERT_ID(id)""",
                    (user_id, conversation_id, digest, text))
        return cur.lastrowid


def relevant_notes(user_id, prompt, limit=5):
    """Return only explicit notes whose topic overlaps the current user message."""
    import re
    import unicodedata
    def norm(s):
        return ''.join(c for c in unicodedata.normalize('NFKD', str(s)).casefold()
                       if not unicodedata.combining(c))
    stop={'jsem','jsme','jsi','mame','bylo','byla','bude','jake','jaky','jakou','tento','tomto','prosim',
          'zapamatuj','pamatujes','pripomen','ulozene','informace','moje','muj','nase','ktere','ktery','tebe','tobe'}
    query={word for word in re.findall(r'[a-z0-9]{4,}',norm(prompt)) if word not in stop}
    if not query: return []
    rows=fetchall("""SELECT id,content,conversation_id FROM chat_memory
                     WHERE user_id=%s ORDER BY id DESC LIMIT 250""",(user_id,))
    found=[]
    for row in rows:
        overlap=query & set(re.findall(r'[a-z0-9]{4,}',norm(row['content'])))
        if overlap: found.append((len(overlap),row))
    found.sort(key=lambda item:item[0],reverse=True)
    return [{'id':r['id'],'kind':'explicit_user_note','text':r['content'],
             'source_conversation_id':r['conversation_id']} for _,r in found[:min(int(limit),5)]]


def list_explicit_notes(user_id):
    return fetchall("""SELECT id,content,created_at FROM chat_memory
                     WHERE user_id=%s ORDER BY id DESC LIMIT 200""",(user_id,))


def delete_explicit_note(user_id, note_id):
    with transaction() as cur:
        cur.execute('DELETE FROM chat_memory WHERE user_id=%s AND id=%s',(user_id,note_id))
        return cur.rowcount
