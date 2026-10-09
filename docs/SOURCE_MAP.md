# MasterChief Source Map

Generated from `docs/source_map.json` plus the live route table. Edit the JSON (or use /source-map) and regenerate with `python tools/gen_source_map.py`.

> Open a file link with VS Code installed to jump straight to the line.
> Temporary helper scripts used to apply edits are deleted after use; anything permanent lives in tools/.

## Chat

### ChatServ (IRC)

Chat server page, model controls.

**How to edit:** UI: templates/chatserv.html and static/chatserv_controls.js. Routes: blueprints/chatserv_routes.py.

- `templates/chatserv.html` - Page
- `static/chatserv_controls.js` - Controls script
- `blueprints/chatserv_routes.py` - Routes
- URLs: `/chatserv`

## Echo

### Echo Chat page (UI)

What you see on /echo-chat: layout, styles, front-end script.

**How to edit:** Layout/HTML: ECHO_CHAT_TEMPLATE in main.py. Look and feel: static/echo_chat.css. Browser behaviour: static/echo_chat.js.

- `main.py` (line 3668) - ECHO_CHAT_TEMPLATE (HTML) and the page route
- `static/echo_chat.css` - Styles
- `static/echo_chat.js` - Front-end logic
- `echo_chat_page.html` - Older standalone copy (check before editing)
- URLs: `/echo-chat`

### Echo Chat brain and API

How Echo answers: commands, memory, script library, app-change orders.

**How to edit:** Replies and commands: echo/chat_bot.py. HTTP endpoint and admin command handling (!confirmed, !cancelchange): api_echo_chat in main.py.

- `echo/chat_bot.py` (line 70) - The chat bot (reply logic, script reference index)
- `main.py` (line 14545) - /api/echo/chat endpoint
- `managers/echo_change_approvals.py` - Pending app-change proposals
- `blueprints/echo_control_routes.py` - Echo control routes
- `blueprints/echo_runtime_routes.py` - Echo runtime routes
- URLs: `/api/echo/chat`

### Echo Approvals

Review and approve changes Echo proposes.

**How to edit:** Page markup: templates/echo_approvals.html. Data/diffs: managers/echo_change_approvals.py. Routes: main.py.

- `templates/echo_approvals.html` - Page UI
- `managers/echo_change_approvals.py` (line 439) - list_pending / list_history / apply
- `main.py` (line 16554) - Routes /echo-approvals and /api/echo/approvals
- URLs: `/echo-approvals`

### Echo training and memory pages

Training and memory UIs.

**How to edit:** Edit the page templates and their routes.

- `echo_train_page.html` - Training page
- `echo_memory.html` - Memory page
- `echo_commands.html` - Commands list page
- URLs: `/echo-train`, `/echo-memory`, `/echo-commands`

## Layout

### Top navigation / drop-down menus

The header, menu groups (Operate, AI & Tools, ...) and their links.

**Warning:** The nav is defined TWICE. main.py's HTML_TEMPLATE overrides the one imported from templates/base.py, so pages show main.py's version. Change both until they are merged.

**How to edit:** Add or rename a <a href> inside the matching <details class='nav-group'> block. Group open/active state is the request.path.startswith(...) test on the <details> line.

- `main.py` (line 2517) - LIVE nav (this is what is rendered)
- `templates/base.py` (line 22) - Older copy of the layout and nav (shadowed)
- `static/navigation.js` - Nav search / behaviour

### Logo

The MasterChief logo shown in the header and on standalone pages.

**How to edit:** Replace static/masterchief-logo.svg to change the image everywhere. To change size or alt text edit the <img> tag in the files below.

- `static/masterchief-logo.svg` - The logo image
- `main.py` (line 2659) - <img> in the live layout
- `templates/base.py` (line 85) - <img> in the shadowed layout
- `core/site_branding.py` (line 9) - Injects the logo into standalone .html pages

## Operate

### Data Backups

Zip backup of data/.

**How to edit:** UI: templates/data_backups.html. Logic: managers/data_backup.py. Routes: main.py.

- `templates/data_backups.html` - Page UI
- `managers/data_backup.py` - Backup logic
- `main.py` (line 16607) - Routes /backups, /api/backups
- URLs: `/backups`

### CI/CD Center

Workflow trigger analysis, deploy target selection, triggers.

**How to edit:** UI: templates/cicd.html. Logic and providers: managers/cicd_center.py. Routes: main.py. Pipelines themselves: .github/workflows/*.yml. Saved settings go to data/cicd_config.json (created on first save).

- `templates/cicd.html` - Page UI
- `managers/cicd_center.py` - Logic: workflow parsing, GitHub/GitLab/TFE/Render triggers
- `main.py` (line 16673) - Routes /cicd, /api/cicd/*
- `.github/workflows/ci.yml` - Tests on push/PR to main
- `.github/workflows/pypi-publish.yml` - PyPI publish on release/tag
- URLs: `/cicd`

### Source Control page (git buttons)

Commit / push / pull from the UI.

**How to edit:** Routes call git via subprocess. main.py has a duplicate copy of these routes.

- `blueprints/scm_routes.py` (line 32) - Blueprint copy
- `main.py` (line 20217) - Duplicate copy
- `templates/scm.py` - Page HTML
- URLs: `/sys/scm`

### Idea Basket and Chaos Monkey

Idea basket panel inside /chaos-monkey.

**How to edit:** Panel HTML: templates/core_scripts.html (#ideas-panel). API and storage: blueprints/core_scripts.py.

- `templates/core_scripts.html` (line 22) - Page and ideas panel
- `blueprints/core_scripts.py` - Routes /chaos-monkey and /api/core-scripts/ideas
- URLs: `/chaos-monkey`

### Page Editor

Pick a page, see every file/block behind it, edit with diff, backup and restore.

**How to edit:** UI: templates/page_editor.html. Logic and safety rules (allowed folders/types, backups): managers/page_editor.py. Routes: main.py. Backups go to data/page_editor_backups/.

- `templates/page_editor.html` - Page UI
- `managers/page_editor.py` - Finds segments, validates and saves edits
- `main.py` (line 16823) - Routes /page-editor and /api/page-editor/*
- URLs: `/page-editor`

## Pages

### About page

The About page content.

**How to edit:** Edit about.html (plain HTML in the project root).

- `about.html` - Page content
- `main.py` (line 17472) - Route that serves it
- URLs: `/about`

### System diagnostics

Diagnostics page and scan APIs.

**How to edit:** Edit the route logic in the blueprint and the HTML in templates/diagnostics.py.

- `blueprints/diagnostics_routes.py` (line 23) - Routes /sys/diagnostics and /sys/api/scan
- `templates/diagnostics.py` (line 3) - HTML template string
- URLs: `/sys/diagnostics`

## Release

### App version

The version number for packaging, PyPI, and the About page.

**How to edit:** Change version= in setup.py for the package/PyPI version. The About page shows the latest version from GitHub (GITHUB_REPO env var), not setup.py.

- `setup.py` (line 107) - Package / PyPI version
- `core/github_version.py` - Fetches the GitHub version for About
- `main.py` (line 17478) - /api/about/version route
- URLs: `/about`, `/api/about/version`

### Python dependencies

What pip installs.

**How to edit:** requirements.txt is required; requirements-optional.txt holds heavy AI/audio packages (torch, diffusers).

- `requirements.txt` - Core dependencies
- `requirements-optional.txt` - Optional heavy dependencies

## Scripts

### Code UI (script library)

masterchief_code_ui: browse and manage scripts.

**How to edit:** Page served by ui_pages; script indexing lives in the Echo bot and the script index modules.

- `blueprints/ui_pages.py` (line 152) - Route /masterchief_code_ui
- `main.py` (line 13699) - Main route /masterchief_code_ui
- URLs: `/masterchief_code_ui`

## Security

### Login and roles

Users, passwords, permissions.

**How to edit:** Runtime user data is data/rbac.json (hashed passwords - do not hand-edit or commit). Admin UI: rbac.html.

- `rbac.html` - Roles UI
- `data/rbac.json` - User/session data (runtime state)
- URLs: `/login`, `/rbac`

## All routes

| URL | Methods | File | Line |
|---|---|---|---|
| `/` | GET | `main.py` | 6694 |
| `/about` | GET | `blueprints/ui_pages.py` | 169 |
| `/about` | GET | `main.py` | 17470 |
| `/addons` | GET | `main.py` | 9613 |
| `/addons/build/<filename>` | GET | `main.py` | 10274 |
| `/addons/create_blank_module` | POST | `main.py` | 9686 |
| `/addons/delete/<filename>` | GET | `main.py` | 10319 |
| `/addons/install/<filename>` | GET,POST | `main.py` | 10143 |
| `/addons/load/<addon_name>` | GET | `main.py` | 10337 |
| `/addons/modules` | GET | `main.py` | 10555 |
| `/addons/modules/<module_name>/` | GET | `main.py` | 11388 |
| `/addons/modules/<module_name>/api/file` | DELETE,GET,POST,PUT | `main.py` | 12627 |
| `/addons/modules/<module_name>/api/files` | GET | `main.py` | 12579 |
| `/addons/modules/<module_name>/api/ui_integration` | GET,POST | `main.py` | 12730 |
| `/addons/modules/<module_name>/api/upload` | POST | `main.py` | 12696 |
| `/addons/modules/<module_name>/app/` | GET | `main.py` | 12260 |
| `/addons/modules/<module_name>/app/<path:subpath>` | GET | `main.py` | 12260 |
| `/addons/modules/<module_name>/build` | POST | `main.py` | 11261 |
| `/addons/modules/<module_name>/config/<path:config_file>` | GET | `main.py` | 10743 |
| `/addons/modules/<module_name>/config/<path:config_file>` | POST | `main.py` | 10763 |
| `/addons/modules/<module_name>/delete` | POST | `main.py` | 12457 |
| `/addons/modules/<module_name>/install_deps` | POST | `main.py` | 10785 |
| `/addons/modules/<module_name>/manager` | GET | `main.py` | 10678 |
| `/addons/modules/<module_name>/run_setup/<path:setup_script>` | POST | `main.py` | 11153 |
| `/addons/modules/<module_name>/start` | POST | `main.py` | 12160 |
| `/addons/modules/<module_name>/status` | GET | `main.py` | 12392 |
| `/addons/modules/<module_name>/stop` | POST | `main.py` | 12419 |
| `/addons/modules/<module_name>/web/<path:filepath>` | GET | `main.py` | 11531 |
| `/addons/modules/delete_all` | POST | `main.py` | 12519 |
| `/addons/register_features/<addon_name>` | GET | `main.py` | 10481 |
| `/addons/upload` | POST | `main.py` | 9632 |
| `/api/about/version` | GET | `main.py` | 17477 |
| `/api/ado/hooks` | DELETE,GET,POST | `main.py` | 1249 |
| `/api/ado/hooks` | DELETE,GET,POST | `blueprints/azure.py` | 32 |
| `/api/akamai/cps/acknowledge` | POST | `main.py` | 18565 |
| `/api/akamai/cps/changes` | POST | `main.py` | 18291 |
| `/api/akamai/cps/deploy` | POST | `main.py` | 18305 |
| `/api/akamai/cps/details` | POST | `main.py` | 18275 |
| `/api/akamai/cps/dv-challenges` | POST | `main.py` | 18332 |
| `/api/akamai/cps/list` | POST | `main.py` | 18239 |
| `/api/akamai/cps/renew` | POST | `main.py` | 18809 |
| `/api/akamai/cps/sprint-scan` | POST | `main.py` | 18627 |
| `/api/akamai/cps/upload-cert` | POST | `main.py` | 18528 |
| `/api/akamai/creds/save` | POST | `main.py` | 18191 |
| `/api/akamai/creds/test` | POST | `main.py` | 18208 |
| `/api/akamai/origins/check-ssl` | POST | `main.py` | 18452 |
| `/api/akamai/origins/sync-to-kv` | POST | `main.py` | 18481 |
| `/api/akamai/r53/add-record` | POST | `main.py` | 18359 |
| `/api/akamai/r53/check-record` | POST | `main.py` | 18396 |
| `/api/akamai/r53/list-records` | POST | `main.py` | 18425 |
| `/api/architecture/visio` | POST | `blueprints/iac_routes.py` | 15 |
| `/api/azure/create_rg` | POST | `main.py` | 1173 |
| `/api/azure/create_rg` | POST | `blueprints/azure.py` | 156 |
| `/api/azure/groups` | GET | `main.py` | 997 |
| `/api/azure/groups` | GET | `blueprints/azure.py` | 60 |
| `/api/azure/resources` | GET | `main.py` | 1029 |
| `/api/azure/resources` | GET | `blueprints/azure.py` | 77 |
| `/api/azure/storage/accounts` | GET | `main.py` | 1075 |
| `/api/azure/storage/accounts` | GET | `blueprints/azure.py` | 99 |
| `/api/azure/storage/containers` | POST | `main.py` | 1107 |
| `/api/azure/storage/containers` | POST | `blueprints/azure.py` | 116 |
| `/api/backups` | GET | `main.py` | 16615 |
| `/api/backups` | POST | `main.py` | 16623 |
| `/api/backups/<name>/download` | GET | `main.py` | 16641 |
| `/api/blueprint/main/extract` | POST | `blueprints/wizard.py` | 103 |
| `/api/blueprint/main/summary` | GET | `blueprints/wizard.py` | 78 |
| `/api/catalog/analysis` | GET | `blueprints/manager.py` | 510 |
| `/api/catalog/files` | GET | `blueprints/manager.py` | 504 |
| `/api/catalog/routes` | GET | `blueprints/manager.py` | 490 |
| `/api/certs/appgw` | POST | `main.py` | 17910 |
| `/api/certs/appservices` | POST | `main.py` | 17870 |
| `/api/certs/audit` | GET | `main.py` | 18080 |
| `/api/certs/audit/clear` | POST | `main.py` | 18096 |
| `/api/certs/chain` | POST | `main.py` | 18107 |
| `/api/certs/delete` | POST | `main.py` | 17851 |
| `/api/certs/details` | POST | `main.py` | 17622 |
| `/api/certs/expiring` | POST | `main.py` | 17638 |
| `/api/certs/keyvault/list` | POST | `main.py` | 17988 |
| `/api/certs/keyvault/sync` | POST | `main.py` | 18038 |
| `/api/certs/keyvault/versions` | POST | `main.py` | 18018 |
| `/api/certs/list` | POST | `main.py` | 17606 |
| `/api/certs/summary` | GET | `main.py` | 17586 |
| `/api/certs/wizard` | POST | `main.py` | 17663 |
| `/api/chatserv/message` | POST | `blueprints/chatserv_routes.py` | 371 |
| `/api/chatserv/motd` | POST | `blueprints/chatserv_routes.py` | 423 |
| `/api/chatserv/state` | GET | `blueprints/chatserv_routes.py` | 336 |
| `/api/chatserv/transfers/consume` | POST | `blueprints/chatserv_routes.py` | 400 |
| `/api/cicd/config` | POST | `main.py` | 16708 |
| `/api/cicd/explain` | GET | `main.py` | 16689 |
| `/api/cicd/gitlab-template` | GET,POST | `main.py` | 16747 |
| `/api/cicd/overview` | GET | `main.py` | 16681 |
| `/api/cicd/run` | POST | `main.py` | 16725 |
| `/api/cicd/runs` | GET | `main.py` | 16700 |
| `/api/cicd/test/<provider>` | POST | `main.py` | 16717 |
| `/api/cloud/accounts` | GET | `managers/cloud.py` | 150 |
| `/api/cloud/accounts` | POST | `managers/cloud.py` | 157 |
| `/api/cloud/accounts/<aid>` | DELETE | `managers/cloud.py` | 172 |
| `/api/cloud/costs` | GET | `managers/cloud.py` | 211 |
| `/api/cloud/refresh` | POST | `managers/cloud.py` | 218 |
| `/api/cloud/resources` | GET | `managers/cloud.py` | 180 |
| `/api/cloud/resources/<rid>` | GET | `managers/cloud.py` | 190 |
| `/api/cloud/resources/<rid>/start` | POST | `managers/cloud.py` | 197 |
| `/api/cloud/resources/<rid>/stop` | POST | `managers/cloud.py` | 204 |
| `/api/code-archetypes` | GET,POST | `main.py` | 7961 |
| `/api/core-scripts` | GET | `blueprints/core_scripts.py` | 72 |
| `/api/core-scripts/dry-check` | POST | `blueprints/core_scripts.py` | 138 |
| `/api/core-scripts/ideas` | DELETE | `blueprints/core_scripts.py` | 120 |
| `/api/core-scripts/ideas` | GET | `blueprints/core_scripts.py` | 84 |
| `/api/core-scripts/ideas` | POST | `blueprints/core_scripts.py` | 96 |
| `/api/core-scripts/run` | POST | `blueprints/core_scripts.py` | 152 |
| `/api/deployments/capabilities` | GET | `blueprints/deploy_routes.py` | 165 |
| `/api/deployments/execute` | POST | `blueprints/deploy_routes.py` | 229 |
| `/api/deployments/preview` | POST | `blueprints/deploy_routes.py` | 181 |
| `/api/echo/action_handlers` | GET | `main.py` | 15530 |
| `/api/echo/approvals` | GET | `main.py` | 16562 |
| `/api/echo/approvals/<path:session_id>/<action>` | POST | `main.py` | 16576 |
| `/api/echo/chat` | POST | `main.py` | 14543 |
| `/api/echo/commands` | GET,POST | `main.py` | 14356 |
| `/api/echo/commands/<name>` | DELETE,PUT | `main.py` | 14432 |
| `/api/echo/debug_image_provider` | GET | `main.py` | 16123 |
| `/api/echo/generate_image` | POST | `main.py` | 15790 |
| `/api/echo/generate_image_async` | POST | `main.py` | 15989 |
| `/api/echo/history` | GET | `main.py` | 15651 |
| `/api/echo/image_status` | GET | `main.py` | 16063 |
| `/api/echo/memories` | GET | `managers/memory.py` | 139 |
| `/api/echo/memories` | POST | `managers/memory.py` | 149 |
| `/api/echo/memories/<mid>` | DELETE | `managers/memory.py` | 188 |
| `/api/echo/memories/<mid>` | GET | `managers/memory.py` | 169 |
| `/api/echo/memories/<mid>` | PUT | `managers/memory.py` | 179 |
| `/api/echo/memories/<mid>/pin` | POST | `managers/memory.py` | 196 |
| `/api/echo/memories/context` | POST | `managers/memory.py` | 219 |
| `/api/echo/memories/search` | GET | `managers/memory.py` | 204 |
| `/api/echo/memories/topics` | GET | `managers/memory.py` | 212 |
| `/api/echo/model` | GET | `main.py` | 15677 |
| `/api/echo/models` | GET | `main.py` | 16916 |
| `/api/echo/outputs` | GET | `main.py` | 15300 |
| `/api/echo/outputs/delete` | POST | `main.py` | 15364 |
| `/api/echo/preload_model` | GET,POST | `main.py` | 15690 |
| `/api/echo/remote/twilio` | POST | `main.py` | 14488 |
| `/api/echo/search` | GET | `main.py` | 17102 |
| `/api/echo/select_model` | POST | `main.py` | 16945 |
| `/api/echo/session/<session_id>` | DELETE,GET | `main.py` | 17188 |
| `/api/echo/session/create` | POST | `main.py` | 17294 |
| `/api/echo/session/favorite` | POST | `main.py` | 17248 |
| `/api/echo/session_prefs` | GET,POST | `main.py` | 15535 |
| `/api/echo/sessions` | GET | `main.py` | 17128 |
| `/api/echo/stats` | GET | `main.py` | 15635 |
| `/api/echo/train` | POST | `main.py` | 15597 |
| `/api/echo/train_cancel` | POST | `main.py` | 16397 |
| `/api/echo/train_list` | GET | `main.py` | 16381 |
| `/api/echo/train_model` | POST | `main.py` | 16179 |
| `/api/echo/train_status` | GET | `main.py` | 16337 |
| `/api/echo/training_files` | GET | `main.py` | 16151 |
| `/api/echo/upload_ingest` | POST | `main.py` | 17010 |
| `/api/echo/voice_commands` | GET | `main.py` | 15430 |
| `/api/echo/voice_commands` | POST | `main.py` | 15434 |
| `/api/echo/voice_commands/<cmd_id>` | DELETE | `main.py` | 15452 |
| `/api/echo/voice_commands/<cmd_id>` | PUT | `main.py` | 15461 |
| `/api/echo/youtube_search` | GET | `main.py` | 15479 |
| `/api/features` | GET | `features/manager.py` | 171 |
| `/api/features/<feature_name>/toggle` | POST | `features/manager.py` | 236 |
| `/api/features/create` | POST | `features/manager.py` | 180 |
| `/api/features/enabled` | GET | `blueprints/feature_routes.py` | 40 |
| `/api/features/enabled` | GET | `main.py` | 19965 |
| `/api/features/github` | POST | `features/manager.py` | 260 |
| `/api/features/github/clone` | POST | `features/handlers/github_integration.py` | 68 |
| `/api/features/github/create-repo` | POST | `features/handlers/github_integration.py` | 121 |
| `/api/features/github/file-content/<path:repo_name>` | GET | `features/handlers/github_integration.py` | 93 |
| `/api/features/github/files/<path:repo_name>` | GET | `features/handlers/github_integration.py` | 84 |
| `/api/features/github/load` | POST | `features/manager.py` | 319 |
| `/api/features/github/repo-scripts` | POST | `features/manager.py` | 495 |
| `/api/features/github/repos` | GET | `features/handlers/github_integration.py` | 47 |
| `/api/features/github/repos/<owner>/<repo>` | GET | `features/handlers/github_integration.py` | 56 |
| `/api/features/github/repos/<owner>/<repo>/contents` | GET | `features/handlers/github_integration.py` | 138 |
| `/api/features/github/repos/<owner>/<repo>/file-content` | GET | `features/handlers/github_integration.py` | 152 |
| `/api/features/github/save-file` | POST | `features/handlers/github_integration.py` | 108 |
| `/api/features/github/search` | GET | `features/manager.py` | 388 |
| `/api/features/github/user/<username>/repos` | GET | `features/manager.py` | 377 |
| `/api/features/load-github` | POST | `features/manager.py` | 426 |
| `/api/features/script` | POST | `features/manager.py` | 553 |
| `/api/features/settings` | GET,POST | `blueprints/feature_routes.py` | 79 |
| `/api/features/settings` | GET,POST | `main.py` | 19999 |
| `/api/features/test` | GET | `features/manager.py` | 147 |
| `/api/gallery/admin/login` | POST | `main.py` | 19425 |
| `/api/gallery/admin/logout` | POST | `main.py` | 19447 |
| `/api/gallery/admin/settings` | GET,POST | `main.py` | 19454 |
| `/api/gallery/admin/verify` | POST | `main.py` | 19436 |
| `/api/gallery/delete/<art_id>` | DELETE | `main.py` | 19410 |
| `/api/gallery/image/<filename>` | GET | `main.py` | 19385 |
| `/api/gallery/list` | GET | `main.py` | 19324 |
| `/api/gallery/orders` | GET | `main.py` | 19510 |
| `/api/gallery/purchase` | POST | `main.py` | 19472 |
| `/api/gallery/update/<art_id>` | POST | `main.py` | 19396 |
| `/api/gallery/upload` | POST | `main.py` | 19329 |
| `/api/gguf/models` | GET | `main.py` | 16085 |
| `/api/gguf/select` | POST | `main.py` | 16102 |
| `/api/iac/generate` | POST | `blueprints/iac_routes.py` | 86 |
| `/api/ide/exec_async` | POST | `main.py` | 1765 |
| `/api/ide/exec_status` | GET | `main.py` | 1823 |
| `/api/ide/execute` | POST | `main.py` | 1357 |
| `/api/ide/execute` | POST | `blueprints/ide.py` | 29 |
| `/api/ide/load` | POST | `main.py` | 1293 |
| `/api/ide/log` | POST | `main.py` | 1602 |
| `/api/ide/remote/creds` | GET | `main.py` | 1574 |
| `/api/ide/remote/creds` | POST | `main.py` | 1528 |
| `/api/ide/save` | POST | `main.py` | 1327 |
| `/api/ide/scripts` | GET | `managers/script.py` | 344 |
| `/api/ide/scripts` | GET | `blueprints/ide.py` | 11 |
| `/api/ide/search` | GET | `main.py` | 1704 |
| `/api/ide/tree` | GET | `main.py` | 1644 |
| `/api/manager/feature_flags` | GET,PUT | `blueprints/manager.py` | 642 |
| `/api/manager/models` | GET | `blueprints/manager.py` | 666 |
| `/api/manager/models` | GET | `main.py` | 19786 |
| `/api/manager/models/preload` | POST | `blueprints/manager.py` | 692 |
| `/api/manager/models/preload` | POST | `main.py` | 19834 |
| `/api/manager/run_tests` | POST | `blueprints/manager.py` | 746 |
| `/api/manager/run_tests` | POST | `main.py` | 19910 |
| `/api/manager/run_tests/status` | GET | `blueprints/manager.py` | 757 |
| `/api/manager/run_tests/status` | GET | `main.py` | 19934 |
| `/api/manager/tasks` | DELETE,GET,POST,PUT | `blueprints/manager.py` | 562 |
| `/api/manager/tasks` | DELETE,GET,POST,PUT | `main.py` | 19686 |
| `/api/marketplace/installed` | GET | `managers/marketplace.py` | 195 |
| `/api/marketplace/plugins` | GET | `managers/marketplace.py` | 126 |
| `/api/marketplace/plugins/<pid>` | GET | `managers/marketplace.py` | 136 |
| `/api/marketplace/plugins/<pid>/config` | GET | `managers/marketplace.py` | 164 |
| `/api/marketplace/plugins/<pid>/config` | PUT | `managers/marketplace.py` | 171 |
| `/api/marketplace/plugins/<pid>/install` | POST | `managers/marketplace.py` | 143 |
| `/api/marketplace/plugins/<pid>/reviews` | GET | `managers/marketplace.py` | 179 |
| `/api/marketplace/plugins/<pid>/reviews` | POST | `managers/marketplace.py` | 186 |
| `/api/marketplace/plugins/<pid>/uninstall` | POST | `managers/marketplace.py` | 150 |
| `/api/marketplace/plugins/<pid>/update` | POST | `managers/marketplace.py` | 157 |
| `/api/marketplace/refresh` | POST | `managers/marketplace.py` | 202 |
| `/api/mock/generate` | POST | `blueprints/mock.py` | 9 |
| `/api/mock/start` | POST | `blueprints/mock.py` | 44 |
| `/api/mock/stop` | POST | `blueprints/mock.py` | 88 |
| `/api/modules/toggle` | POST | `blueprints/feature_routes.py` | 178 |
| `/api/modules/toggle` | POST | `main.py` | 8887 |
| `/api/notifications` | GET | `managers/notification.py` | 186 |
| `/api/notifications/<nid>` | DELETE | `managers/notification.py` | 218 |
| `/api/notifications/<nid>/read` | POST | `managers/notification.py` | 202 |
| `/api/notifications/channels` | GET | `managers/notification.py` | 226 |
| `/api/notifications/channels` | POST | `managers/notification.py` | 233 |
| `/api/notifications/channels/<cid>` | DELETE | `managers/notification.py` | 251 |
| `/api/notifications/channels/<cid>` | PUT | `managers/notification.py` | 242 |
| `/api/notifications/channels/<cid>/test` | POST | `managers/notification.py` | 259 |
| `/api/notifications/count` | GET | `managers/notification.py` | 195 |
| `/api/notifications/read_all` | POST | `managers/notification.py` | 210 |
| `/api/notifications/rules` | GET | `managers/notification.py` | 267 |
| `/api/notifications/rules` | POST | `managers/notification.py` | 274 |
| `/api/notifications/rules/<rid>` | DELETE | `managers/notification.py` | 292 |
| `/api/notifications/rules/<rid>` | PUT | `managers/notification.py` | 283 |
| `/api/observability/loki/query` | POST | `blueprints/observability_routes.py` | 220 |
| `/api/observability/prometheus/query` | POST | `blueprints/observability_routes.py` | 188 |
| `/api/observability/status` | GET | `blueprints/observability_routes.py` | 159 |
| `/api/okta/apps` | POST | `main.py` | 8848 |
| `/api/okta/mfa` | POST | `main.py` | 8798 |
| `/api/okta/signin` | POST | `main.py` | 8723 |
| `/api/page-editor/backups` | GET | `main.py` | 16891 |
| `/api/page-editor/find` | GET | `main.py` | 16847 |
| `/api/page-editor/page` | GET | `main.py` | 16839 |
| `/api/page-editor/pages` | GET | `main.py` | 16831 |
| `/api/page-editor/preview` | POST | `main.py` | 16864 |
| `/api/page-editor/restore` | POST | `main.py` | 16899 |
| `/api/page-editor/save` | POST | `main.py` | 16874 |
| `/api/page-editor/segment` | GET | `main.py` | 16855 |
| `/api/personality/apply` | POST | `main.py` | 13548 |
| `/api/personality/delete` | POST | `main.py` | 13622 |
| `/api/personality/list` | GET | `main.py` | 13498 |
| `/api/personality/status` | GET | `main.py` | 13474 |
| `/api/personality/toggle` | POST | `main.py` | 13677 |
| `/api/pipelines` | GET | `managers/pipeline.py` | 367 |
| `/api/pipelines` | POST | `managers/pipeline.py` | 374 |
| `/api/pipelines/<pid>` | DELETE | `managers/pipeline.py` | 399 |
| `/api/pipelines/<pid>` | GET | `managers/pipeline.py` | 383 |
| `/api/pipelines/<pid>` | PUT | `managers/pipeline.py` | 390 |
| `/api/pipelines/<pid>/execute` | POST | `managers/pipeline.py` | 407 |
| `/api/pipelines/<pid>/export` | GET | `managers/pipeline.py` | 475 |
| `/api/pipelines/<pid>/export.yaml` | GET | `managers/pipeline.py` | 482 |
| `/api/pipelines/import` | POST | `managers/pipeline.py` | 451 |
| `/api/pipelines/import-yaml` | POST | `managers/pipeline.py` | 460 |
| `/api/pipelines/runs` | GET | `managers/pipeline.py` | 415 |
| `/api/pipelines/runs/<rid>` | GET | `managers/pipeline.py` | 423 |
| `/api/pipelines/runs/<rid>/approval` | POST | `managers/pipeline.py` | 438 |
| `/api/pipelines/runs/<rid>/cancel` | POST | `managers/pipeline.py` | 430 |
| `/api/rbac/api_keys` | POST | `managers/rbac.py` | 303 |
| `/api/rbac/api_keys/<key_id>` | DELETE | `managers/rbac.py` | 312 |
| `/api/rbac/audit` | GET | `managers/rbac.py` | 295 |
| `/api/rbac/login` | POST | `managers/rbac.py` | 320 |
| `/api/rbac/roles` | GET | `managers/rbac.py` | 236 |
| `/api/rbac/roles` | POST | `managers/rbac.py` | 243 |
| `/api/rbac/roles/<role_name>` | DELETE | `managers/rbac.py` | 261 |
| `/api/rbac/roles/<role_name>` | PUT | `managers/rbac.py` | 252 |
| `/api/rbac/sessions` | GET | `managers/rbac.py` | 269 |
| `/api/rbac/sessions/<session_id>` | DELETE | `managers/rbac.py` | 276 |
| `/api/rbac/sessions/all` | DELETE | `managers/rbac.py` | 284 |
| `/api/rbac/users` | GET | `managers/rbac.py` | 203 |
| `/api/rbac/users` | POST | `managers/rbac.py` | 210 |
| `/api/rbac/users/<user_id>` | DELETE | `managers/rbac.py` | 228 |
| `/api/rbac/users/<user_id>` | PUT | `managers/rbac.py` | 219 |
| `/api/resources/convert_to_training` | POST | `main.py` | 13414 |
| `/api/resources/delete` | POST | `main.py` | 13140 |
| `/api/resources/enqueue_ingest` | POST | `main.py` | 13190 |
| `/api/resources/ingest_status` | GET | `main.py` | 13238 |
| `/api/resources/list` | GET | `main.py` | 12926 |
| `/api/resources/load` | POST | `main.py` | 13270 |
| `/api/resources/upload` | POST | `main.py` | 12946 |
| `/api/roku/build` | POST | `main.py` | 19170 |
| `/api/roku/deploy` | POST | `blueprints/roku_routes.py` | 130 |
| `/api/roku/download/<slug>` | GET | `blueprints/roku_routes.py` | 63 |
| `/api/roku/guide/<token>` | GET | `blueprints/roku_routes.py` | 77 |
| `/api/roku/settings` | GET,POST | `blueprints/roku_routes.py` | 40 |
| `/api/roku/validate` | POST | `main.py` | 19118 |
| `/api/source-map` | GET | `main.py` | 16774 |
| `/api/source-map/lookup` | GET | `main.py` | 16782 |
| `/api/source-map/markdown` | GET | `main.py` | 16795 |
| `/api/stats` | GET | `main.py` | 8902 |
| `/api/teams/calendar` | POST | `main.py` | 8055 |
| `/api/teams/chat/messages` | POST | `main.py` | 8146 |
| `/api/teams/chat/send` | POST | `main.py` | 8177 |
| `/api/teams/chats` | POST | `main.py` | 8118 |
| `/api/teams/connect` | POST | `main.py` | 7983 |
| `/api/teams/device_poll` | POST | `main.py` | 8240 |
| `/api/teams/device_start` | POST | `main.py` | 8209 |
| `/api/teams/ps_connect` | POST | `main.py` | 8328 |
| `/api/teams/ps_status` | POST | `main.py` | 8291 |
| `/api/teams/ps_teams` | POST | `main.py` | 8365 |
| `/api/terraform/ci-validate` | POST | `blueprints/terraform.py` | 127 |
| `/api/terraform/enterprise/deploy_to_project` | POST | `main.py` | 975 |
| `/api/terraform/enterprise/download/<job_id>` | GET | `main.py` | 962 |
| `/api/terraform/enterprise/generate` | POST | `main.py` | 943 |
| `/api/terraform/enterprise/validate` | POST | `main.py` | 953 |
| `/api/terraform/generate` | POST | `blueprints/terraform.py` | 38 |
| `/api/terraform/install` | POST | `blueprints/iac_routes.py` | 140 |
| `/api/terraform/run` | POST | `blueprints/terraform.py` | 89 |
| `/api/terraform/status` | GET | `blueprints/iac_routes.py` | 109 |
| `/api/terraform/validate-design` | POST | `blueprints/terraform.py` | 74 |
| `/api/test` | GET | `blueprints/feature_routes.py` | 194 |
| `/api/test` | GET | `main.py` | 8898 |
| `/api/tf/apply` | POST | `main.py` | 847 |
| `/api/tf/apply` | POST | `blueprints/terraform.py` | 186 |
| `/api/tf/backup` | GET | `main.py` | 923 |
| `/api/tf/backup` | GET | `blueprints/terraform.py` | 258 |
| `/api/tf/destroy` | POST | `blueprints/terraform.py` | 211 |
| `/api/tf/import` | POST | `main.py` | 888 |
| `/api/tf/import` | POST | `blueprints/terraform.py` | 231 |
| `/api/tf/plan` | POST | `blueprints/terraform.py` | 161 |
| `/api/tf/refresh` | GET | `blueprints/terraform.py` | 222 |
| `/api/tf/state` | GET | `main.py` | 910 |
| `/api/tf/state` | GET | `blueprints/terraform.py` | 249 |
| `/api/tf/validate` | POST | `blueprints/terraform.py` | 157 |
| `/api/vault/audit` | GET | `managers/vault.py` | 244 |
| `/api/vault/rotation` | GET | `managers/vault.py` | 252 |
| `/api/vault/secrets` | GET | `managers/vault.py` | 197 |
| `/api/vault/secrets` | POST | `managers/vault.py` | 204 |
| `/api/vault/secrets/<sid>` | DELETE | `managers/vault.py` | 229 |
| `/api/vault/secrets/<sid>` | GET | `managers/vault.py` | 213 |
| `/api/vault/secrets/<sid>` | PUT | `managers/vault.py` | 220 |
| `/api/vault/secrets/<sid>/versions` | GET | `managers/vault.py` | 237 |
| `/archetypes` | GET | `main.py` | 7956 |
| `/arm_creator` | GET | `blueprints/ui_pages.py` | 31 |
| `/arm_creator` | GET | `main.py` | 19515 |
| `/auth/azure/callback` | GET | `auth_module.py` | 235 |
| `/auth/azure/login` | GET | `auth_module.py` | 226 |
| `/auth/github/callback` | GET | `auth_module.py` | 303 |
| `/auth/github/login` | GET | `auth_module.py` | 294 |
| `/auth/logout` | POST | `auth_module.py` | 337 |
| `/auth/okta/callback` | GET | `auth_module.py` | 269 |
| `/auth/okta/login` | GET | `auth_module.py` | 260 |
| `/auth/status` | GET | `auth_module.py` | 126 |
| `/backups` | GET | `main.py` | 16607 |
| `/blueprint-wizard` | GET | `blueprints/wizard.py` | 68 |
| `/caf_generator` | GET | `blueprints/ui_pages.py` | 63 |
| `/catalog/file` | GET | `blueprints/manager.py` | 515 |
| `/chaos-monkey` | GET | `blueprints/core_scripts.py` | 47 |
| `/chatserv` | GET | `blueprints/chatserv_routes.py` | 331 |
| `/cicd` | GET | `main.py` | 16673 |
| `/cloud` | GET | `blueprints/ui_pages.py` | 111 |
| `/cloud` | GET | `main.py` | 17499 |
| `/core-scripts` | GET | `blueprints/core_scripts.py` | 47 |
| `/data/echo_chat_outputs/<path:fname>` | GET | `main.py` | 15336 |
| `/data/echo_images/<path:fname>` | GET | `main.py` | 15962 |
| `/debug/fetch_model` | GET | `main.py` | 17318 |
| `/deploy-center` | GET | `blueprints/deploy_routes.py` | 157 |
| `/echo-approvals` | GET | `main.py` | 16554 |
| `/echo-chat` | GET | `main.py` | 13714 |
| `/echo-commands` | GET | `main.py` | 14348 |
| `/echo-memory` | GET | `blueprints/ui_pages.py` | 125 |
| `/echo-memory` | GET | `main.py` | 18894 |
| `/echo-train` | GET | `main.py` | 16934 |
| `/favicon.ico` | GET | `blueprints/ui_pages.py` | 176 |
| `/feature/run/<path:feature_key>` | POST | `blueprints/feature_routes.py` | 138 |
| `/feature/run/<path:feature_key>` | POST | `main.py` | 20063 |
| `/features` | GET | `blueprints/feature_routes.py` | 28 |
| `/features` | GET | `main.py` | 19953 |
| `/gallery` | GET | `main.py` | 19008 |
| `/github` | GET | `features/handlers/github_integration.py` | 33 |
| `/google-services` | GET | `main.py` | 7950 |
| `/hello` | GET | `blueprints/ui_pages.py` | 191 |
| `/iac_manager` | GET | `blueprints/ui_pages.py` | 77 |
| `/iac_manager` | GET | `main.py` | 19558 |
| `/login` | GET,POST | `auth_module.py` | 141 |
| `/manager` | GET | `blueprints/manager.py` | 555 |
| `/manager` | GET | `main.py` | 19632 |
| `/marketplace` | GET | `blueprints/ui_pages.py` | 132 |
| `/marketplace` | GET | `main.py` | 18904 |
| `/master-menu` | GET | `blueprints/manager.py` | 631 |
| `/masterchief_code_ui` | GET | `blueprints/ui_pages.py` | 152 |
| `/masterchief_code_ui` | GET | `main.py` | 13699 |
| `/media/roku` | GET | `main.py` | 19020 |
| `/metrics` | GET | `blueprints/observability_routes.py` | 131 |
| `/modules` | GET | `main.py` | 7940 |
| `/notifications` | GET | `blueprints/ui_pages.py` | 139 |
| `/notifications` | GET | `main.py` | 18914 |
| `/observability` | GET | `blueprints/observability_routes.py` | 154 |
| `/okta` | GET | `main.py` | 8705 |
| `/page-editor` | GET | `main.py` | 16823 |
| `/personality` | GET | `main.py` | 17364 |
| `/personality/edit` | GET | `main.py` | 17388 |
| `/personality/save` | POST | `main.py` | 17436 |
| `/pipelines` | GET | `blueprints/ui_pages.py` | 104 |
| `/pipelines` | GET | `main.py` | 17489 |
| `/processes` | GET | `main.py` | 9509 |
| `/processes/kill/<int:pid>` | GET | `main.py` | 9518 |
| `/rbac` | GET | `blueprints/ui_pages.py` | 146 |
| `/rbac` | GET | `main.py` | 18924 |
| `/resources` | GET | `main.py` | 12809 |
| `/resources/load_options` | GET | `main.py` | 12858 |
| `/resources/preview` | GET | `main.py` | 12822 |
| `/roku` | GET | `auth_module.py` | 221 |
| `/scripts` | GET | `managers/script.py` | 297 |
| `/scripts/add` | POST | `managers/script.py` | 333 |
| `/scripts/backup/<b64path>` | POST | `main.py` | 9027 |
| `/scripts/diff/<b64path>` | POST | `main.py` | 9421 |
| `/scripts/edit/<b64path>` | GET | `main.py` | 8939 |
| `/scripts/exec_path/<b64path>` | GET,POST | `main.py` | 9462 |
| `/scripts/execute/<filename>` | GET | `managers/script.py` | 357 |
| `/scripts/refresh_index` | POST | `managers/script.py` | 316 |
| `/scripts/run/<filename>` | POST | `managers/script.py` | 364 |
| `/scripts/save/<b64path>` | POST | `main.py` | 8970 |
| `/scripts/suggest_commit/<b64path>` | GET | `main.py` | 9364 |
| `/secrets` | GET | `blueprints/ui_pages.py` | 118 |
| `/secrets` | GET | `main.py` | 18884 |
| `/services` | GET | `main.py` | 9544 |
| `/services/restart/<service_name>` | GET | `main.py` | 9591 |
| `/services/start/<service_name>` | GET | `main.py` | 9555 |
| `/services/stop/<service_name>` | GET | `main.py` | 9573 |
| `/setup/` | GET | `setup_wizard/__init__.py` | 65 |
| `/setup/configure` | POST | `setup_wizard/__init__.py` | 70 |
| `/setup/status` | GET | `setup_wizard/__init__.py` | 97 |
| `/site-map` | GET | `blueprints/manager.py` | 358 |
| `/source-map` | GET | `main.py` | 16766 |
| `/sys/api/export-active` | GET | `main.py` | 20188 |
| `/sys/api/file` | GET | `blueprints/diagnostics_routes.py` | 54 |
| `/sys/api/modules/from-idea` | POST | `blueprints/ops_routes.py` | 408 |
| `/sys/api/ops-action` | POST | `blueprints/ops_routes.py` | 357 |
| `/sys/api/ops-summary` | GET | `blueprints/ops_routes.py` | 200 |
| `/sys/api/orphan-sweep/abort` | POST | `main.py` | 20180 |
| `/sys/api/orphan-sweep/start` | POST | `main.py` | 20137 |
| `/sys/api/orphan-sweep/stream` | GET | `main.py` | 20160 |
| `/sys/api/scan` | GET | `blueprints/diagnostics_routes.py` | 35 |
| `/sys/api/scm/commit` | POST | `blueprints/scm_routes.py` | 74 |
| `/sys/api/scm/commit` | POST | `main.py` | 20260 |
| `/sys/api/scm/pull` | POST | `blueprints/scm_routes.py` | 122 |
| `/sys/api/scm/pull` | POST | `main.py` | 20309 |
| `/sys/api/scm/push` | POST | `blueprints/scm_routes.py` | 110 |
| `/sys/api/scm/push` | POST | `main.py` | 20296 |
| `/sys/api/scm/status` | GET | `blueprints/scm_routes.py` | 44 |
| `/sys/api/scm/status` | GET | `main.py` | 20227 |
| `/sys/api/services` | GET | `blueprints/ops_routes.py` | 151 |
| `/sys/api/services` | GET | `main.py` | 20102 |
| `/sys/diagnostics` | GET | `blueprints/diagnostics_routes.py` | 23 |
| `/sys/ops` | GET | `blueprints/ops_routes.py` | 190 |
| `/sys/scm` | GET | `blueprints/scm_routes.py` | 32 |
| `/sys/scm` | GET | `main.py` | 20217 |
| `/teams` | GET | `main.py` | 7945 |
| `/tf_wizard` | GET | `main.py` | 18936 |
| `/tf_wizard/generate` | POST | `main.py` | 18947 |
| `/tf_wizard/schema/apply` | POST | `main.py` | 18961 |
| `/tf_wizard/static/<path:filename>` | GET | `main.py` | 351 |
| `/web_ide` | GET | `blueprints/ui_pages.py` | 45 |
| `/web_ide` | GET | `main.py` | 19526 |
| `/web_tf_wizard` | GET | `blueprints/feature_routes.py` | 166 |
| `/web_tf_wizard` | GET | `main.py` | 20090 |
