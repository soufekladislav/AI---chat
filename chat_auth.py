"""Browser authentication and customer/admin pages for Fresh AI Chat.

Central Fresh Crackers verifies credentials. The Chat keeps only a scoped user ID,
profile display data, role and chat data; never a copy of the central password.
"""
from __future__ import annotations
import hmac
import os
import secrets
from functools import wraps
from urllib.parse import urlencode

import httpx
from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect,
                   render_template, request, session, url_for)
import chat_store as store

bp=Blueprint('account',__name__)
FRESH_URL=os.getenv('FRESH_ACCOUNT_URL','https://www.freshcrackers.cz').rstrip('/')
APP_ID=os.getenv('FRESH_ACCOUNT_APP_ID','chat').strip()
APP_SECRET=os.getenv('FRESH_ACCOUNT_SECRET','').strip()
WP_API=f'{FRESH_URL}/wp-json/fresh-account/v1'
PUBLIC_ORIGIN=os.getenv('CHAT_PUBLIC_ORIGIN','https://chat.freshcrackers.cz').rstrip('/')
PRIVACY_URL='https://www.freshcrackers.cz/ochrana-osobnich-udaju/'
WP_ACCOUNT_URL='https://www.freshcrackers.cz/muj-ucet/'


def central_configured():
    return bool(APP_SECRET and FRESH_URL.startswith('https://') and PUBLIC_ORIGIN.startswith('https://'))


def central_request(endpoint,data):
    if not central_configured():
        raise RuntimeError('Přihlašování Fresh Crackers zatím není nastavené.')
    try:
        with httpx.Client(timeout=httpx.Timeout(15.0,connect=6.0),follow_redirects=False) as client:
            resp=client.post(f'{WP_API}/{endpoint}',headers={'X-Fresh-App-Id':APP_ID,
                    'X-Fresh-App-Secret':APP_SECRET,'Accept':'application/json'},json=data)
        payload=resp.json() if 'json' in resp.headers.get('content-type','') else {}
        if resp.is_error:
            raise CentralError(str(payload.get('code','unknown')),str(payload.get('message') or 'Přihlášení se nezdařilo.'),resp.status_code)
        if not isinstance(payload,dict): raise RuntimeError('Neplatná odpověď centrálního účtu.')
        return payload
    except httpx.HTTPError:
        raise RuntimeError('Spojení s Fresh Crackers je dočasně nedostupné.') from None


class CentralError(Exception):
    def __init__(self,code,message,status):
        super().__init__(message)
        self.code=code; self.status=status


def token():
    if 'csrf' not in session: session['csrf']=secrets.token_urlsafe(32)
    return session['csrf']


def csrf_valid():
    sent=request.form.get('csrf') or request.headers.get('X-CSRF-Token') or ''
    return bool(sent and hmac.compare_digest(str(sent),str(session.get('csrf',''))))


def csrf_required(fn):
    @wraps(fn)
    def wrapper(*args,**kwargs):
        if not csrf_valid():
            if request.path.startswith('/api/'):
                return jsonify(ok=False,error='Stránka vypršela. Obnov ji a zkus to znovu.'),403
            abort(403)
        return fn(*args,**kwargs)
    return wrapper


@bp.app_context_processor
def helpers():
    return {'csrf_token':token,'privacy_url':PRIVACY_URL,'wp_account_url':WP_ACCOUNT_URL}


@bp.before_app_request
def load_user():
    g.user=None
    uid=session.get('chat_user_id')
    if uid:
        try: g.user=store.user_by_id(int(uid))
        except Exception: current_app.logger.exception('Could not load Chat account')
        if not g.user: session.pop('chat_user_id',None)


def login_required(fn):
    @wraps(fn)
    def wrapper(*args,**kwargs):
        if not g.user:
            if request.path.startswith('/api/'):
                return jsonify(ok=False,error='Přihlas se prosím znovu.'),401
            return redirect(url_for('account.login'))
        return fn(*args,**kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args,**kwargs):
        if g.user['role']!='admin': abort(403)
        return fn(*args,**kwargs)
    return wrapper


def _pending_remote(remote):
    if not isinstance(remote,dict) or not remote.get('verified') or not remote.get('user_id'):
        raise ValueError('Účet Fresh Crackers ještě není ověřený.')
    # Cookie stores only the WP identifier; other profile data are fetched afresh on confirmation.
    session.clear()
    session['pending_fresh_user_id']=int(remote['user_id'])
    token()


def _accept_remote(remote):
    if not remote.get('verified'): raise ValueError('Účet Fresh Crackers není ověřený.')
    old=store.user_by_fresh_id(int(remote['user_id']))
    if old and not old['is_active']:
        raise ValueError('Účet Chatu je deaktivovaný. Kontaktuj podporu.')
    if not old:
        _pending_remote(remote)
        return redirect(url_for('account.confirm'))
    store.update_identity(old['id'],remote)
    session.clear(); session['chat_user_id']=int(old['id']); session.permanent=True
    token()
    return redirect('/')


def _check_password(request_data):
    return central_request('auth/password',{'email':request_data.get('email','').strip(),
                                            'password':request_data.get('password','')})


@bp.route('/account/login',methods=['GET','POST'])
def login():
    if g.user: return redirect('/')
    error=None; unverified=False; email=''
    if request.method=='POST':
        if not csrf_valid(): abort(403)
        email=request.form.get('email','').strip().lower()
        try:
            remote=_check_password(request.form)
            return _accept_remote(remote)
        except CentralError as exc:
            error='Tento účet ještě není ověřený. Pošli si nový ověřovací e-mail.' if exc.code=='unverified' else 'E-mail nebo heslo nesouhlasí.' if exc.status==401 else str(exc)
            unverified=exc.code=='unverified'
        except (RuntimeError,ValueError) as exc: error=str(exc)
    return render_template('login.html',error=error,unverified=unverified,email=email)


@bp.route('/account/register',methods=['GET','POST'])
def register():
    if g.user: return redirect('/')
    error=None; email=''
    if request.method=='POST':
        if not csrf_valid(): abort(403)
        email=request.form.get('email','').strip().lower()
        password=request.form.get('password',''); again=request.form.get('password_confirm','')
        if password!=again: error='Hesla se neshodují.'
        elif len(password)<10: error='Heslo musí obsahovat alespoň 10 znaků.'
        elif request.form.get('privacy')!='1': error='Potvrď prosím seznámení se zásadami ochrany osobních údajů.'
        elif not request.form.get('email','').strip() or '@' not in email: error='Zadej platný e-mail.'
        else:
            try:
                remote=central_request('account/register',{'email':email,'password':password,
                    'privacy_ack':True,'return_url':f'{PUBLIC_ORIGIN}/account/login?verified=1'})
                if remote.get('existing_account') and remote.get('verified') and remote.get('user'):
                    return _accept_remote(remote['user'])
                return render_template('register_done.html',email=email)
            except CentralError as exc:
                error='Na Fresh Crackers už máš účet. Přihlas se jeho heslem nebo využij obnovení hesla.' if exc.code=='account_exists' else str(exc)
            except (RuntimeError,ValueError) as exc: error=str(exc)
    return render_template('register.html',error=error,email=email)


@bp.post('/account/verification/resend')
@csrf_required
def resend():
    email=request.form.get('email','').strip().lower()
    try:
        central_request('account/verification/resend',{'email':email,'return_url':f'{PUBLIC_ORIGIN}/account/login?verified=1'})
    except Exception: current_app.logger.warning('Unable to resend verification for Chat',exc_info=True)
    flash('Pokud účet čeká na ověření, na e-mail jsme poslali nový odkaz.','success')
    return redirect(url_for('account.login'))


@bp.route('/account/forgot',methods=['GET','POST'])
def forgot():
    sent=False
    if request.method=='POST':
        if not csrf_valid(): abort(403)
        try: central_request('account/password/forgot',{'email':request.form.get('email','').strip()})
        except Exception: current_app.logger.warning('Could not request password reset',exc_info=True)
        sent=True
    return render_template('forgot.html',sent=sent)


@bp.get('/account/fresh/start')
def sso_start():
    if not central_configured(): return redirect(url_for('account.login'))
    state=secrets.token_urlsafe(32)
    session['sso_state']=state
    ret=f'{PUBLIC_ORIGIN}/account/fresh/callback'
    qs=urlencode({'fac_sso_start':'1','app_id':APP_ID,'return_url':ret,'state':state})
    return redirect(f'{FRESH_URL}/?{qs}')


@bp.get('/account/fresh/callback')
def sso_callback():
    state=request.args.get('state',''); expected=session.pop('sso_state',None)
    if not expected or not hmac.compare_digest(expected,state) or not request.args.get('code'):
        return render_template('login.html',error='Přihlášení vypršelo. Zkus to znovu.',unverified=False,email=''),400
    try: return _accept_remote(central_request('auth/exchange',{'code':request.args['code']}))
    except (CentralError,RuntimeError,ValueError) as exc:
        return render_template('login.html',error=str(exc),unverified=False,email=''),400


@bp.route('/account/confirm',methods=['GET','POST'])
def confirm():
    uid=session.get('pending_fresh_user_id')
    if not uid: return redirect(url_for('account.login'))
    if request.method=='POST':
        if not csrf_valid(): abort(403)
        if request.form.get('consent')!='1':
            return render_template('confirm.html',error='Potvrď prosím vytvoření účtu Chatu.'),400
        try:
            # WordPress profile endpoint is a GET. Keep the app secret server-side.
            with httpx.Client(timeout=12.0,follow_redirects=False) as client:
                res=client.get(f'{WP_API}/account/profile',params={'user_id':uid},
                    headers={'X-Fresh-App-Id':APP_ID,'X-Fresh-App-Secret':APP_SECRET})
            res.raise_for_status(); remote=res.json()
            if int(remote.get('user_id',0))!=uid or not remote.get('verified'):
                raise ValueError('Centrální účet není ověřený.')
            local_id=store.create_user(remote)
            session.clear(); session['chat_user_id']=int(local_id); session.permanent=True
            token(); return redirect('/account/personality')
        except Exception:
            current_app.logger.exception('Chat account provisioning failed')
            return render_template('confirm.html',error='Účet Chatu nyní nejde vytvořit. Zkus to prosím znovu.'),503
    return render_template('confirm.html',error=None)


@bp.post('/account/logout')
@login_required
@csrf_required
def logout():
    session.clear()
    return redirect(url_for('account.login'))


@bp.route('/account/profile',methods=['GET','POST'])
@login_required
def profile():
    error=None
    if request.method=='POST':
        if not csrf_valid(): abort(403)
        name=request.form.get('display_name','').strip()[:160]
        if len(name)<2: error='Vyplň prosím jméno.'
        else:
            # Local display preference only. Central identity/email/password stay in WordPress.
            with store.transaction() as cur:
                cur.execute('UPDATE chat_users SET display_name=%s WHERE id=%s',(name,g.user['id']))
            return redirect(url_for('account.profile'))
    return render_template('profile.html',error=error)


@bp.get('/admin')
@admin_required
def admin_index():
    users=store.fetchall('''SELECT u.*, (SELECT COUNT(*) FROM chat_conversations c WHERE c.user_id=u.id) AS conversation_count
                             FROM chat_users u ORDER BY created_at DESC LIMIT 500''')
    return render_template('admin.html',users=users)


@bp.route('/admin/users/<int:user_id>',methods=['GET','POST'])
@admin_required
def admin_user(user_id):
    user=store.fetchone('SELECT * FROM chat_users WHERE id=%s',(user_id,))
    if not user: abort(404)
    error=None
    if request.method=='POST':
        if not csrf_valid(): abort(403)
        action=request.form.get('action','save')
        if action=='delete':
            if int(user_id)==int(g.user['id']): error='Svůj vlastní administrátorský účet zde nelze smazat.'
            elif request.form.get('confirm')!='SMAZAT': error='Pro smazání napiš SMAZAT.'
            else:
                with store.transaction() as cur:
                    cur.execute('DELETE FROM chat_users WHERE id=%s',(user_id,))
                return redirect(url_for('account.admin_index'))
        else:
            role=request.form.get('role','user')
            name=request.form.get('display_name','').strip()[:160]
            active=1 if request.form.get('is_active')=='1' else 0
            if role not in ('admin','user') or not name: error='Zkontroluj jméno a roli.'
            elif user_id==g.user['id'] and (role!='admin' or active==0):
                error='Nemůžeš odebrat svou vlastní administrátorskou roli ani deaktivovat svůj účet.'
            else:
                with store.transaction() as cur:
                    cur.execute('''UPDATE chat_users SET display_name=%s,role=%s,is_active=%s WHERE id=%s''',
                                (name,role,active,user_id))
                return redirect(url_for('account.admin_user',user_id=user_id))
    count=store.fetchone('SELECT COUNT(*) AS n FROM chat_conversations WHERE user_id=%s',(user_id,))
    return render_template('admin_user.html',account=user,error=error,conversation_count=count['n'])
