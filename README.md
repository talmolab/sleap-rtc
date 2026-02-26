# sleap-rtc

sleap-rtc lets you run SLEAP training and inference on a remote GPU from your local machine.

## Installation

On the worker (GPU machine):

```bash
uv tool install --python 3.11 sleap-rtc --with "sleap-nn[torch]" --with-executables-from sleap-nn --torch-backend auto
```

## Setup

### 1. Get an API key and create a room

Go to the [sleap-rtc dashboard](https://talmolab.github.io/sleap-rtc/dashboard/index.html), log in with GitHub, and:

1. Generate an API key under **Tokens**
2. Create a room under **Rooms** and note the room secret

### 2. Start the worker

```bash
sleap-rtc login --api-key <api-key>
sleap-rtc config add-mount /path/to/your/data
sleap-rtc worker --room-secret <secret>
```

### 3. Submit a job

Open SLEAP, go to the Remote Training dialog, paste the session string displayed by the worker, and submit.

## Links

- [SLEAP](https://sleap.ai)
- [sleap-nn](https://nn.sleap.ai)
- [Dashboard](https://talmolab.github.io/sleap-rtc/dashboard/index.html)
