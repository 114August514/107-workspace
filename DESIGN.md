# 107 RunBox — Design Sketch (MVP)

> A beginner-friendly **local web GUI** over the cluster. No SCOW, no Slurm, no
> sbatch, no scp. Open a browser, click a few buttons, get your results.

This sketch covers only the **basic personal run-loop**. Shared / course / group
spaces from `IDEA.md` are explicitly deferred (see §9).

---

## 1. What we're actually building

We already have `hpc-helper` — a working Python CLI that runs on the student's
laptop and drives the cluster over SSH:

```
up → push → run → logs → pull → down
(get GPU) (sync) (execute) (watch) (results) (release)
```

That CLI **is the engine**. Beginners just can't use a terminal. So the MVP is:

> **A thin local web app that wraps the existing `hpc_helper` engine and turns the
> 6-step loop into 6 buttons + a live log panel.**

Nothing about the cluster interaction changes. We're building a face, not a new backend.

---

## 2. Why this shape (given the cluster)

Facts that pin the design:

| Cluster fact | Consequence for the tool |
|---|---|
| Login-node-only access; jobs via Slurm | Tool must SSH from the laptop; can't assume a service on the cluster. |
| GPU is held by a `sleep infinity` holder job, then `srun` into it | Keep the exact same "allocate a node, then run inside it" model. |
| `/public` (983 TB) is shared across all nodes and *is* `/home` | Code synced once is visible to every compute node. Simple. |
| Students already authenticate via SSH key / tunnel | Reuse `~/.ssh/config`; no new auth to build for MVP. |
| A Python engine already exists | Build the GUI in Python too — zero rewrite. |

**Form factor: local web app.** A small FastAPI server ships next to `hpc_helper`.
The student runs one command (or double-clicks a launcher), it starts on
`127.0.0.1:8760` and opens the browser. This gives us: reuse of the Python engine,
natural **live log streaming** (Server-Sent Events), and a UI that is literally the
first draft of the future "Web collaborative space" in `IDEA.md`.

---

## 3. Architecture

```
┌─────────────────────── Student's laptop ───────────────────────┐
│                                                                 │
│   Browser (localhost:8760)                                      │
│     │  HTTP + SSE (live logs)                                   │
│     ▼                                                           │
│   FastAPI app  ── thin adapter ──►  hpc_helper (existing)       │
│     - serves the single-page UI          config / session      │
│     - REST endpoints                      remote (ssh/tar)      │
│     - SSE log stream                      up/push/run/pull/...  │
│                                                    │            │
└────────────────────────────────────────────────────┼───────────┘
                                                      │ SSH
                                                      ▼
                                         Login node (tradmin-02)
                                                 │ sbatch / srun
                                                 ▼
                                       Compute node (anode01–17, GPU)
                                       code+results on /public (shared)
```

The FastAPI layer holds **no cluster logic of its own** — every endpoint is a
1:1 call into an `hpc_helper` function. If a feature isn't in the engine yet, we
add it to the engine (so the CLI benefits too), not to the web layer.

---

## 4. The beginner UI (one page, four cards)

Design principle: **a beginner should never see a path, a flag, or a Slurm word.**
One page, top-to-bottom = the natural order of doing the work.

```
┌──────────────────────────────────────────────────────────────┐
│ 107 RunBox                          ● Connected as pb24000216 │
├──────────────────────────────────────────────────────────────┤
│                                                                │
│ ①  GPU NODE                                                    │
│    ┌────────────────────────────────────────────────────┐     │
│    │  ● Running on anode07   ·  1 GPU · 4 CPU · 6h55m left│    │
│    │            [ Release node ]                          │    │
│    └────────────────────────────────────────────────────┘     │
│    (when none: "No node yet"   [ Get a GPU ▸ ] )              │
│                                                                │
│ ②  MY PROJECT                                                  │
│    Folder:  ~/Desktop/mnist-hw        [ Choose… ]              │
│    ────────────────────────────────────  32 files, 2 changed  │
│                     [ ⤒ Sync to cluster ]  ▓▓▓▓▓░░ 71%         │
│                                                                │
│ ③  RUN                                                         │
│    Script:  [ train.py ▾ ]                                     │
│    Options: --lr [0.001]  --epochs [50]   (+ add option)      │
│                     [ ▶ Run ]   [ ■ Stop ]                     │
│                                                                │
│ ④  OUTPUT                                            live ●    │
│    ┌────────────────────────────────────────────────────┐     │
│    │ epoch 12/50  loss=0.184  acc=0.947                  │     │
│    │ epoch 13/50  loss=0.171  acc=0.951 ▏                │     │
│    └────────────────────────────────────────────────────┘     │
│                     [ ⤓ Download results ]                     │
└──────────────────────────────────────────────────────────────┘
```

Plus a **first-run setup screen** (replaces `hpc init`): SSH alias, username,
default conda env, and a **[ Test connection ]** button that must go green before
the main page unlocks. Sensible defaults pre-filled for this cluster
(`account=stu`, `partition=Students`, `qos=qos_stu_small`, `1 GPU / 4 CPU / 7h`).

### Beginner-friendly touches (cheap, high value)
- **Get a GPU** shows a spinner + "waiting for a free node…" instead of hanging.
- **Sync** shows a plain count ("2 files changed"), never rsync/tar jargon; warns
  gently if a huge folder (dataset) is about to upload.
- **Script dropdown** is auto-populated from `.py` files in the chosen folder — no typing paths.
- **Options** are just labeled text boxes appended as `--flag value`.
- Errors are translated: `Permission denied (publickey)` → "Couldn't log in — your
  SSH key isn't set up. [How to fix]".

---

## 5. Endpoints ↔ engine (the entire API surface)

| UI action | HTTP | hpc_helper call |
|---|---|---|
| Test / status banner | `GET /api/session` | `session.load()` + `remote.squeue()` |
| Get a GPU | `POST /api/node/up` | `up()` (polls to running) |
| Release node | `POST /api/node/down` | `down()` |
| Choose folder / scan | `GET /api/project/scan` | list `.py`, diff vs manifest |
| Sync to cluster | `POST /api/project/push` | `push()` (stream progress) |
| Run | `POST /api/run` | `run(script, args)` |
| Live output | `GET /api/run/stream` (SSE) | tail of the running `srun` |
| Stop | `POST /api/run/stop` | signal the run |
| Download results | `POST /api/pull` | `pull()` |

That's **~9 endpoints**. Everything the beginner needs, nothing they don't.

---

## 6. Live logs

The one genuinely interactive piece. `run()` streams stdout over the SSH channel;
FastAPI relays it to the browser via **Server-Sent Events** (`text/event-stream`).
The browser appends lines to card ④ and auto-scrolls. Stop button closes the stream
and signals the remote process. No WebSocket complexity needed for one-way output.

---

## 7. State & config

Reuse what the engine already persists — no new store:
- `~/.hpc-helper/config.toml` — connection + defaults (written by the setup screen).
- `~/.hpc-helper/session.json` — active `job_id` / `node`, so the banner is correct
  even after the browser is closed and reopened.
- `~/.hpc-helper/manifests/` — incremental-sync manifest (drives the "2 changed" count).

The web app is **stateless**; refreshing the page just re-reads these.

---

## 8. Tech stack (deliberately small)

- **Backend:** Python + FastAPI + Uvicorn, importing `hpc_helper` directly.
- **Frontend:** one `index.html` + vanilla JS (or Alpine.js) + a little CSS. No
  build step, no npm. Served by FastAPI as a static file.
- **Launch:** `runbox` console-script → starts Uvicorn on `127.0.0.1:8760` and
  opens the browser (`webbrowser.open`).
- **Packaging:** `pip install -e .` for now; a PyInstaller one-file build later if
  we want double-click-to-run.

Dependencies added over the existing CLI: just `fastapi` + `uvicorn`. That's it.

---

## 9. Explicitly OUT of scope for the MVP

Deferred so we ship the thing beginners actually struggle with first:
- Shared / group / course / project spaces, roles & permissions, audit log.
- Shared datasets & the "reference instead of copy" model.
- Templates / template gallery, batch sweeps GUI (`hpc batch` stays CLI-only).
- Multi-user server, accounts, leaderboards, submission collection.

These are the `IDEA.md` roadmap; the local web app is intentionally the seed that
grows toward them (§2), but none are needed for v1.

---

## 10. Build plan (small, in order)

1. **Scaffold** — FastAPI app that imports `hpc_helper`, serves a static page,
   `GET /api/session` returns real status. *(proves the wiring)*
2. **Setup screen** — form → `config.toml`, `[Test connection]` → green/red.
3. **Node card** — Get a GPU / Release, live banner with node + time left.
4. **Project card** — folder pick, `.py` scan, Sync with a progress bar.
5. **Run + live logs** — script dropdown, option boxes, Run, SSE output panel, Stop.
6. **Results** — Download results button.
7. **Polish** — friendly error translation, empty/loading states, one launcher command.

Each step is independently demoable. After step 6 a beginner can go from
"open browser" to "results on my laptop" without touching a terminal — that's the MVP.
```

