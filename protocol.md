# Pomodoro MPS BLE Protocol

本文定义 Pomodoro MPS 中 WebApp 与 mpy 之间的 BLE 控制协议，以及 mpy 侧对 `simpletouch` 单击、双击事件的处理规则。

## 设计目标

- WebApp 是配置中心：负责编辑、保存配置，并通过 BLE 下发到 PixelMug。
- mpy 是执行中心：收到配置后本地持久化，之后即使 BLE 断开，也要能独立完成专注、休息、提醒和状态流转。
- BLE 通信只传输控制命令、配置快照和状态事件，不依赖手机端维持每秒倒计时。
- 设备端物理交互优先级高于 WebApp：用户单击、双击后，mpy 立即执行并主动上报状态。

## BLE 传输层

使用 `maopaoBle` 透明传输服务：

- Service: `F150`
- Notify TX: `F151`
- Write RX: `F152`

mpy 侧在自己的主循环中调用：

```python
maopaoBle.poll()
touch.update()
```

消息使用 UTF-8 JSON 文本。单条消息建议控制在 BLE 分片实现可稳定承载的范围内；如果后续发现 MTU 或分片限制，再在 `ble_webapp.py` 层统一处理。

## 消息信封

WebApp -> mpy 命令：

```json
{
  "v": 1,
  "id": "1700000000000-1",
  "type": "cmd",
  "cmd": "sync_config",
  "payload": {}
}
```

mpy -> WebApp 应答：

```json
{
  "v": 1,
  "id": "1700000000000-1",
  "type": "ack",
  "cmd": "sync_config",
  "ok": true,
  "payload": {}
}
```

mpy -> WebApp 事件：

```json
{
  "v": 1,
  "type": "event",
  "event": "state",
  "payload": {}
}
```

字段说明：

| 字段 | 方向 | 必填 | 说明 |
| --- | --- | --- | --- |
| `v` | 双向 | 是 | 协议版本，当前固定为 `1` |
| `id` | 命令/应答 | 是 | WebApp 生成的请求 ID，mpy 应答时原样返回 |
| `type` | 双向 | 是 | `cmd` / `ack` / `event` / `error` |
| `cmd` | 命令/应答 | 是 | 命令名称 |
| `event` | 事件 | 是 | 事件名称 |
| `ok` | 应答 | 是 | 命令是否成功 |
| `payload` | 双向 | 否 | 命令、应答、事件数据 |
| `error` | 错误 | 否 | 错误码 |
| `message` | 错误 | 否 | 调试用错误说明 |

## 配置模型

WebApp 每次点击 `Show` 时，下发完整配置快照，不做增量 patch。

```json
{
  "focusMin": 25,
  "autoStartNext": false,
  "cycleCount": 4,
  "shortBreakMin": 5,
  "longBreakMin": 15,
  "soundEnabled": true,
  "endSound": "classic",
  "theme": "pulse"
}
```

配置项：

| 字段 | 类型 | 范围/枚举 | 默认值 | mpy 用途 |
| --- | --- | --- | --- | --- |
| `focusMin` | int | `1..60` | `25` | 工作专注倒计时分钟数 |
| `autoStartNext` | bool | `true/false` | `false` | 休息结束后是否自动开始下一轮工作 |
| `cycleCount` | int | `1..12` | `4` | 多少个工作周期后进入长休 |
| `shortBreakMin` | int | `1..60` | `5` | 普通短休倒计时分钟数 |
| `longBreakMin` | int | `1..60` | `15` | 长休倒计时分钟数 |
| `soundEnabled` | bool | `true/false` | `true` | DONE 提醒时是否播放声音 |
| `endSound` | string | `classic` / `gentle` | `classic` | DONE 提醒音效 |
| `theme` | string | `pulse` / `retro` | `pulse` | 设备端显示主题 |

说明：

- `cycleCount` 原型默认是 `4`。这里给 mpy 侧设置 `1..12` 的上限，避免异常输入造成过长循环；WebApp UI 可以继续按产品需求只暴露常用范围。
- WebApp 本地仍使用 LocalStorage 保存用户输入。同步失败时不回滚手机端配置。
- mpy 收到合法配置后应立即持久化到本地存储，并在之后重启时恢复配置，但运行状态重启后回到 `P1 READY`。

## 状态模型

mpy 内部状态：

| 状态 | 名称 | 说明 |
| --- | --- | --- |
| `P1` | READY | 就绪，显示当前工作时长和 `READY` |
| `P2-W` | WORK_RUNNING | 工作倒计时运行或暂停 |
| `P2-R` | REST_RUNNING | 休息倒计时运行或暂停 |
| `P3-D` | DONE | 阶段自然完成后的 5 秒提醒 |
| `P3-S` | STOP | 用户中止后的 3 秒反馈 |

对外状态 payload：

```json
{
  "state": "P2-W",
  "phase": "work",
  "paused": false,
  "durationSec": 1500,
  "timeLeftSec": 1492,
  "progress": 0.9947,
  "completedCycles": 1,
  "nextRestType": "short",
  "config": {
    "focusMin": 25,
    "autoStartNext": false,
    "cycleCount": 4,
    "shortBreakMin": 5,
    "longBreakMin": 15,
    "soundEnabled": true,
    "endSound": "classic",
    "theme": "pulse"
  }
}
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `state` | 当前状态码 |
| `phase` | `ready` / `work` / `short_break` / `long_break` / `done` / `stop` |
| `paused` | 仅 `P2-W` / `P2-R` 有意义 |
| `durationSec` | 当前阶段总秒数 |
| `timeLeftSec` | 当前阶段剩余秒数 |
| `progress` | `timeLeftSec / durationSec`，用于 WebApp 展示 |
| `completedCycles` | 已完成工作周期数，达到 `cycleCount` 后下一次休息为长休 |
| `nextRestType` | `short` / `long` / `null` |
| `config` | mpy 当前生效配置 |

## WebApp -> mpy 命令

### `hello`

连接建立后 WebApp 发送，用于握手和读取当前状态。

请求：

```json
{"v":1,"id":"1","type":"cmd","cmd":"hello","payload":{"app":"pomodoro","client":"webapp"}}
```

成功应答 payload：

```json
{"app":"pomodoro","protocol":1,"state":{}}
```

### `open`

启动页点击 `Open on Device` 后发送。mpy 应进入 `P1 READY`，停止任何当前提示音或旧状态反馈。

请求：

```json
{"v":1,"id":"2","type":"cmd","cmd":"open","payload":{}}
```

行为：

- 停止 DONE/STOP 提醒。
- 不清除已保存配置。
- 当前状态强制切到 `P1`。
- 返回最新状态。

### `sync_config`

配置页点击 `Show` 后发送。mpy 校验、保存并应用完整配置。

请求：

```json
{
  "v": 1,
  "id": "3",
  "type": "cmd",
  "cmd": "sync_config",
  "payload": {
    "config": {
      "focusMin": 25,
      "autoStartNext": false,
      "cycleCount": 4,
      "shortBreakMin": 5,
      "longBreakMin": 15,
      "soundEnabled": true,
      "endSound": "classic",
      "theme": "pulse"
    },
    "applyMode": "ready"
  }
}
```

`applyMode`：

| 值 | 行为 |
| --- | --- |
| `ready` | 推荐。保存配置并切到 `P1 READY`，显示新时长 |
| `defer` | 保存配置，但如果正在倒计时，不打断当前阶段；下个阶段开始时生效 |

本项目首版采用 `ready`，与原型 `Show` 的含义一致：把配置展示到设备上并准备开始。

失败应答错误码：

| error | 说明 |
| --- | --- |
| `invalid_config` | 配置字段缺失或范围非法 |
| `persist_failed` | mpy 本地保存失败 |

### `get_state`

WebApp 主动拉取当前状态。

```json
{"v":1,"id":"4","type":"cmd","cmd":"get_state","payload":{}}
```

### `control`

WebApp 调试或后续增强用控制命令。正式 UI 首版可以只使用 `open`、`sync_config`、`get_state`，不必须暴露这些按钮。

请求：

```json
{"v":1,"id":"5","type":"cmd","cmd":"control","payload":{"action":"toggle_pause"}}
```

动作：

| action | 允许状态 | 行为 |
| --- | --- | --- |
| `start` | `P1` | 开始工作倒计时，进入 `P2-W` |
| `toggle_pause` | `P2-W` / `P2-R` | 暂停/继续 |
| `stop` | `P2-W` / `P2-R` | 中止，进入 `P3-S` |
| `reset_ready` | 任意 | 停止提醒和倒计时，进入 `P1` |
| `next_duration` | `P1` | 按 `25 -> 45 -> 15 -> 25` 切换工作时长 |

## mpy -> WebApp 事件

### `state`

状态变化时立即发送。包括 `open`、`sync_config`、物理按键、倒计时归零、DONE/STOP 结束。

```json
{"v":1,"type":"event","event":"state","payload":{"state":"P1","phase":"ready"}}
```

### `tick`

倒计时运行中低频发送，建议每 5 秒一次；连接存在时用于 WebApp 轻量同步显示，BLE 断开时不影响设备运行。

```json
{"v":1,"type":"event","event":"tick","payload":{"state":"P2-W","timeLeftSec":1490,"durationSec":1500,"progress":0.9933}}
```

### `touch`

物理按键触发后发送，便于 WebApp 做日志或即时刷新。

```json
{"v":1,"type":"event","event":"touch","payload":{"action":"click","stateBefore":"P2-W","stateAfter":"P2-W"}}
```

### `config_changed`

设备端自己改变配置时发送。首版只有 `P1` 双击切换时长会触发。

```json
{"v":1,"type":"event","event":"config_changed","payload":{"config":{"focusMin":45},"source":"touch"}}
```

### `error`

设备端遇到可恢复错误时发送。

```json
{"v":1,"type":"event","event":"error","payload":{"error":"timer_overrun","message":"timer loop delayed"}}
```

## simpletouch 事件处理

`SimpleTouch` 建议参数：

```python
touch = SimpleTouch(pin_no=13, active_high=True, debounce_ms=20, dbl_ms=350)
```

事件矩阵：

| 当前状态 | 单击 `click` | 双击 `double` |
| --- | --- | --- |
| `P1 READY` | 开始工作倒计时，进入 `P2-W` | 切换工作时长 `25 -> 45 -> 15 -> 25`，保持 `P1` |
| `P2-W` 工作中 | 暂停/继续，`paused` 取反 | 中止工作，进入 `P3-S STOP`，3 秒后回 `P1` |
| `P2-R` 休息中 | 暂停/继续，`paused` 取反 | 中止休息，进入 `P3-S STOP`，3 秒后回 `P1` |
| `P3-D DONE` | 立即停止提醒，进入下一阶段 | 立即停止提醒，进入下一阶段 |
| `P3-S STOP` | 立即结束 STOP 反馈，进入 `P1` | 立即结束 STOP 反馈，进入 `P1` |

双击切换时长规则：

- 只在 `P1 READY` 生效。
- 如果当前 `focusMin` 是 `25`，切到 `45`。
- 如果当前 `focusMin` 是 `45`，切到 `15`。
- 其他值，包括 WebApp 下发的自定义值，双击后切到 `25`。
- 切换后应持久化 `focusMin`，并发送 `config_changed` 与 `state` 事件。

DONE 阶段提前中断后的流转：

| DONE 来源 | 中断或 5 秒结束后 |
| --- | --- |
| 工作阶段 `P2-W` 归零 | 根据 `completedCycles` 判断进入短休或长休，进入 `P2-R` 并自动开始 |
| 休息阶段 `P2-R` 归零，`autoStartNext=true` | 进入下一轮 `P2-W` 并自动开始 |
| 休息阶段 `P2-R` 归零，`autoStartNext=false` | 回到 `P1 READY` |

## mpy 本地控制项

mpy 需要维护以下运行时变量：

| 变量 | 说明 |
| --- | --- |
| `config` | 当前生效配置 |
| `state` | `P1` / `P2-W` / `P2-R` / `P3-D` / `P3-S` |
| `paused` | 当前计时是否暂停 |
| `phase` | 当前阶段类型 |
| `duration_sec` | 当前阶段总秒数 |
| `time_left_sec` | 当前阶段剩余秒数 |
| `completed_cycles` | 已完成工作周期数 |
| `done_from_phase` | DONE 来源，用于反馈结束后决定下一阶段 |
| `feedback_until_ms` | DONE/STOP 反馈结束时间 |
| `last_tick_event_ms` | BLE tick 限频时间戳 |

## 校验规则

mpy 收到 `sync_config` 时必须校验：

- `focusMin`、`shortBreakMin`、`longBreakMin` 必须是 `1..60` 整数。
- `cycleCount` 必须是正整数，首版接受 `1..12`。
- `soundEnabled`、`autoStartNext` 必须是布尔值。
- `endSound` 只能是 `classic` 或 `gentle`。
- `theme` 只能是 `pulse` 或 `retro`。

校验失败时：

- 不修改当前 mpy 配置。
- 返回 `ok:false`、`error:"invalid_config"`。
- WebApp 显示同步失败，但保留手机端 LocalStorage 中的用户输入。

## 首版实现边界

- WebApp 首版只需要调用 `open`、`sync_config`、`get_state`。
- `control` 命令保留给调试和后续版本，不作为首版主交互入口。
- `tick` 事件不是倒计时正确性的依赖；mpy 倒计时必须完全由本地时间驱动。
- 加速度摇晃启动属于硬件 PRD 范围，但本协议当前只定义 `simpletouch` 单击和双击。后续加入摇晃时，可复用 `touch` 事件结构，把 `action` 扩展为 `shake`。
