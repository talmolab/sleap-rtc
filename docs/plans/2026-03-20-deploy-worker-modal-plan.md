# Deploy Worker Modal Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Deploy Worker" button to the room action bar that opens a modal with Docker/Cluster/Direct Install tabs for generating worker deployment commands.

**Architecture:** Port the validated prototype (`scratch/deploy-worker-prototype.html`) into the existing dashboard. Add modal HTML to `index.html`, styles to `styles.css`, and logic to `app.js`. Three tabs: Docker (command builder form), Cluster (step-by-step guide), Direct Install (uv tool install flow).

**Tech Stack:** Vanilla HTML/CSS/JS, Lucide icons, existing dashboard patterns

---

## Task 1: Add Deploy Worker button to room action bar

**Files:**
- Modify: `dashboard/app.js:963` (after View Workers button, before Invite button)

**Step 1: Insert button HTML in renderRoomCard()**

Between line 963 (end of View Workers button) and line 964 (conditional Invite button), add:

```javascript
                <button class="btn btn-ghost btn-sm" onclick="app.openDeployWorkerModal('${room.room_id}')">
                    <i data-lucide="plus"></i>
                    Deploy Worker
                </button>
```

**Step 2: Commit**

---

## Task 2: Add Deploy Worker modal HTML

**Files:**
- Modify: `dashboard/index.html:1065` (after workers-modal closing div)

**Step 1: Add modal HTML**

Insert the full deploy-worker-modal HTML after the workers-modal. Includes:
- Header with title "Deploy Worker" and subtitle
- Three tabs: Docker, Cluster, Direct Install
- Docker tab: account key dropdown, worker name, working dir, reconnect time, GPU checkbox, restart checkbox, mounts, command preview
- Cluster tab: step-by-step with image, env var, storage, command, GPU
- Direct Install tab: config form, 3-step instructions, combined copy block
- Footer with Done button

Account key dropdown starts empty — populated by JS when modal opens.

**Step 2: Commit**

---

## Task 3: Add Deploy Worker modal styles

**Files:**
- Modify: `dashboard/styles.css` (append at end)

**Step 1: Add CSS**

Port styles from prototype, prefixed with `.dw-` namespace. Includes:
- `.dw-tabs`, `.dw-tab` — tab navigation
- `.dw-tab-content` — tab panels
- `.dw-step-list`, `.dw-step-item` — numbered steps
- `.dw-step-command-wrapper`, `.dw-step-command` — code blocks with copy
- `.dw-config-table` — settings tables
- `.dw-command-preview` — Docker command output
- `.dw-info-note` — info callout
- `.dw-checkbox-row` — checkbox layout
- `.dw-mounts-container`, `.dw-mount-row`, `.dw-btn-add-mount` — mount management
- `.dw-btn-copy-inline` — small icon-only copy button
- Scrollbar styling for modal

**Step 2: Commit**

---

## Task 4: Add Deploy Worker modal logic to app.js

**Files:**
- Modify: `dashboard/app.js` (add methods to SleapDashboard class)

**Step 1: Add methods**

- `openDeployWorkerModal(roomId)` — populate account key dropdown from `this.accountKeys`, show modal
- `switchDeployTab(tabName)` — tab switching
- `updateDockerCommand()` — real-time Docker command generation
- `updateRunAIKey()` — sync cluster tab key display
- `updateDirectCommands()` — update direct install commands
- `addDeployMount()` / `removeDeployMount(id)` — Docker tab mount management
- `addDirectMount()` / `removeDirectMount(id)` — Direct Install tab mount management
- `copyDeployCommand(preId, btnId)` — copy with feedback
- `copyDeployInline(btn, text)` — inline copy with feedback

**Step 2: Wire up event listeners in `setupEventListeners()`**

**Step 3: Commit**

---

## Task 5: Test and commit

**Step 1: Open dashboard, verify all three tabs work**
**Step 2: Push to branch**
