# Nasazení Fresh AI Chat 0.3.1 (z aktuální 0.3.0)

1. V cPanelu nejprve zálohuj **celý aktuální adresář Chatu a jeho databázi**. Mimo archiv si bezpečně uchovej `.env`, `.htaccess` a funkční nastavení Python aplikace / Passengeru. Neposílej `.env` ani tajné klíče v diagnostice.
2. ZIP obsahuje úplný runtime Chatu. Rozbal jeho **obsah přímo do existujícího kořene aplikace `chat.freshcrackers.cz`**, aby tam vedle sebe zůstaly `app.py`, `chat_store.py`, `personality.py`, `passenger_wsgi.py`, `templates/` a `static/`. Nenech soubory o úroveň hlouběji v novém podsložce. Zachovej svou `.env` a `.htaccess`; `.env.example` je jen neprodukční vzor.
3. Žádné `DROP`, `CREATE`, `ALTER` ani import SQL neprováděj. Migrace schématu **0.3.0 → 0.3.1 není potřeba**. Nově se ke každé další odpovědi ukládá snapshot osobnosti do existujícího `chat_messages.metadata_json`; při prvním přepnutí v daném vlákně se do starších odpovědí doplní původní snapshot, kde dosud chyběl.
4. V cPanelu restartuj Python aplikaci Chatu. Kontrola: `https://chat.freshcrackers.cz/health` vrací `version: 0.3.1`. Při pochybnostech proveď Ctrl+Shift+R a ověř přímo health endpoint, který se nesmí vyhodnocovat podle textu generovaného AI.
5. Otevři `Osobnost Chatu`: jako první je jméno, dále styl, avatar a upřesnění komunikace. Máš-li profil ze starší verze, zvol **Obnovit ukázkový styl vybrané osobnosti** a ulož, chceš-li nové výraznější vzorové formulace. Dřívější vlastní úpravy textu stylu se automaticky nepřepisují.
6. Pokračuj ve **starém vlákně** a napiš testovací zprávu. Předchozí bubliny si mají ponechat původní jméno/avatar, nové odpovědi už mají používat aktuální osobnost a její nový styl. Nová osobnost se nastaví až od následující úspěšně uložené odpovědi, historické texty se nepřegenerovávají.
7. Změň avatar, ulož, obnov Chat. Ověř favicon v prohlížeči a `https://chat.freshcrackers.cz/app.webmanifest`, jehož `name`, `short_name` a `icons` mají odpovídat aktuální osobnosti přihlášeného uživatele. U již nainstalované PWA může systém telefonu držet původní ikonu/název; v takovém případě odeber zástupce z plochy a znovu přidej. Nemá to smazat serverové chaty.
8. Ověř v profilu tlačítka Facebook, WhatsApp, X, LinkedIn, TikTok (jen **kopírování odkazu**, žádné automatické publikování) a nativní nabídku telefonu. Sdílí se výhradně veřejný odkaz na aplikaci, nikoliv soukromá historie nebo URL s přihlašovacími tokeny.
9. Test identity: zeptej se „Jaký model používáš?“; Chat vrátí **model předchozí odpovědi v daném vlákně** z metadat a vysvětlí, že následující model volí Engine až podle zadání. Pro konkrétní právě dokončený požadavek jsou rozhodující metadata pod bublinou / záznam v Enginu.

### Návrat na 0.3.0

Vrať zálohu předchozí aplikace, restartuj Passenger. Protože tato aktualizace nemění databázové tabulky, data uložená v `metadata_json` mají být stále kompatibilní; před produkční změnou i tak vytvoř zálohu DB.

### Co není součástí 0.3.1

Automatické zpracování **celé** historie všech chatů do sdílené paměti, multimodální generování obrázků/videa z Chatu a skutečný systémový widget Android/iOS. Schopnost odpovědi z explicitních poznámek zůstává v Enginu `local / memory-v1`, nikoliv ve zkušební route `mock-local`.
