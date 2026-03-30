# sleap-rtc (SLEAP Connect)

Remote training and inference for [SLEAP](https://sleap.ai) — run `sleap-nn` on a GPU worker from your local machine.

## Quick Start

### Option 1: Dashboard

1. **Login** — Go to the [dashboard](https://talmolab.github.io/sleap-rtc/dashboard/index.html) and log in with GitHub.
2. **Create a room** — Click **Rooms** → **Create Room**.
3. **Generate an account key** — Go to **Account Keys** and create one. Copy it for the worker.
4. **Deploy a worker** — On your GPU machine, install and start a worker:

   ```bash
   # Install sleap-rtc with sleap-nn and GPU support
   uv tool install --python 3.11 sleap-rtc \
     --with "sleap-nn[torch-cuda130]" \
     --with-executables-from sleap-nn

   # Login and start the worker
   sleap-rtc login
   sleap-rtc config add-mount /path/to/your/data
   sleap-rtc worker --room <room-id>
   ```

5. **Submit a job** — In the dashboard, click **Submit Job** on your room card, select the worker, upload a config, and submit.

### Option 2: CLI

```bash
# Install on the GPU machine
uv tool install --python 3.11 sleap-rtc \
  --with "sleap-nn[torch-cuda130]" \
  --with-executables-from sleap-nn

# Login with GitHub (opens browser)
sleap-rtc login

# Configure data mounts
sleap-rtc config add-mount /path/to/your/data

# Start the worker in a room
sleap-rtc worker --room <room-id>
```

Then submit jobs from:
- The [dashboard](https://talmolab.github.io/sleap-rtc/dashboard/index.html) web UI
- The SLEAP GUI (Remote Training dialog under **Predict → Run Training**)

### Docker

```bash
# Pull and run the worker image
docker run --gpus all \
  -e SLEAP_RTC_ACCOUNT_KEY=<your-account-key> \
  -v /path/to/data:/app/shared_data \
  ghcr.io/talmolab/sleap-rtc:latest \
  worker --room <room-id>
```

## Installation

**Worker (GPU machine):**

```bash
# With CUDA GPU
uv tool install --python 3.11 sleap-rtc \
  --with "sleap-nn[torch-cuda130]" \
  --with-executables-from sleap-nn

# CPU only
uv tool install --python 3.11 sleap-rtc \
  --with "sleap-nn[torch-cpu]" \
  --with-executables-from sleap-nn

# Apple Silicon (MPS)
uv tool install --python 3.11 sleap-rtc \
  --with "sleap-nn[torch]" \
  --with-executables-from sleap-nn
```

**Pre-flight check:**

```bash
sleap-rtc doctor
```

## How It Works

1. Workers connect to a signaling server via WebSocket and join a room.
2. Clients (dashboard, SLEAP GUI, or sleap-app) connect to the same room.
3. WebRTC peer connections are established for direct communication.
4. Jobs are submitted as structured specs (training or inference) and executed on the worker's GPU.
5. Progress streams back in real-time. Results are saved to shared storage.

## Links

- [SLEAP](https://sleap.ai) — Pose estimation framework
- [sleap-nn](https://nn.sleap.ai) — Neural network backend
- [Dashboard](https://talmolab.github.io/sleap-rtc/dashboard/index.html) — Web UI for room and job management
- [sleap-app](https://app.sleap.ai) — Modern SLEAP labeling GUI
