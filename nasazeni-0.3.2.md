# Fresh AI Chat 0.3.2 – provozní reporting pro Engine 0.5.3

Zálohuj Chat a databázi, nahraj kompletní balíček do stávajícího kořene Chatu, zachovej produkční `.env`, `.htaccess` a funkční Passenger start. Restartuj Chat v cPanelu. `/health` musí vracet 0.3.2. Chat nevyžaduje žádné SQL.

Ověř, že `FRESH_ENGINE_API_KEY` Chatu odpovídá vyhrazenému `FRESH_CHAT_ENGINE_KEY` na Enginu. Teprve ověřený kanál umožňuje zasílat identifikaci uživatele pro statistiky. Pro úplný seznam aktivních uživatelů v `.env` Chatu nastav ještě **druhý, samostatný** náhodný klíč `CHAT_REPORTING_SECRET` (min. 32 znaků) a tutéž hodnotu v `.env` Enginu jako `FRESH_CHAT_REPORTING_SECRET`. Interní HTTPS endpoint vrací pouze identifikátory, jména a e-maily aktivních uživatelů, žádné zprávy, a bez tohoto druhého klíče vrátí 401. Obsah konverzací není součástí exportu. Kreditní a platební chování Chatu se nemění. Podrobný společný postup je v balíčku Enginu `NASAZENI-0.5.3.md`.
