# AFSer.de access route

Verified on 4 October 2026.

## Login

1. Open <https://www.afser.de/>.
2. Enter `Alexander Kluge` in **Login-Name**.
3. Fill **Passwort** using the local `.afser-password` file in the AFS workspace.
4. Click **Anmelden**.
5. Confirm that the dashboard displays **Servus Alexander!**.

The login and dashboard share the same URL. Reuse an authenticated browser tab when available; otherwise repeat the login steps.

## Local password setup

Workspace: `/Users/alexanderkluge/Documents/AFS`.

Run this in a local zsh terminal to enter or replace the password with hidden input:

```zsh
(umask 077; read -rs 'pw?afser.de password: '; printf '%s' "$pw" > /Users/alexanderkluge/Documents/AFS/.afser-password; printf '\n')
```

The file contains a plaintext password and is local only. It was verified with owner-only read/write permissions (`0600`). Load its contents directly into the password field without printing them, quoting them in chat, or including them in tool output. Never commit the password file, session cookies, or private dashboard screenshots.

## Repository

<https://github.com/alexanderh2seo4/AFS>

This document records the route and setup instructions only. The password and authenticated browser session are not stored in GitHub.
