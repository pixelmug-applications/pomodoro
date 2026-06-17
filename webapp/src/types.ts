export type DeviceInfo = {
  name?: string;
  talId?: string;
  slot?: string | number;
  slotId?: string;
  deviceId?: string;
  online?: boolean;
  raw?: unknown;
};

export type AppStatus =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'installing'
  | 'connecting'
  | 'connected'
  | 'syncing'
  | 'error';

export type EndSound = 'classic' | 'gentle';
export type ScreenTheme = 'pulse' | 'retro';

export type PomodoroConfig = {
  focusMin: number;
  autoStartNext: boolean;
  cycleCount: number;
  shortBreakMin: number;
  longBreakMin: number;
  soundEnabled: boolean;
  endSound: EndSound;
  theme: ScreenTheme;
};

export type PomodoroRuntimeState = {
  state: string;
  phase: string;
  paused: boolean;
  durationSec: number;
  timeLeftSec: number;
  progress: number;
  completedCycles?: number;
  nextRestType?: 'short' | 'long' | null;
  config?: PomodoroConfig;
};
