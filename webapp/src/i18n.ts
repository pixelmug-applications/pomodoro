import { computed, reactive } from 'vue';

export type AppLocale = 'zh-CN' | 'en-US';

type MessageKey =
  | 'app.title'
  | 'landing.subtitle'
  | 'landing.opening'
  | 'landing.enter'
  | 'landing.retry'
  | 'landing.install'
  | 'status.browserMock'
  | 'status.loadingDevice'
  | 'status.deviceReady'
  | 'status.deviceMissing'
  | 'status.opening'
  | 'status.preparing'
  | 'status.switching'
  | 'status.launchReady'
  | 'status.connectingBle'
  | 'status.bleConnected'
  | 'status.syncingSettings'
  | 'status.syncSuccess'
  | 'status.syncFailed'
  | 'status.unknownError'
  | 'summary.breaks'
  | 'summary.cycles'
  | 'summary.restFormat'
  | 'unit.min'
  | 'settings.focusDuration'
  | 'settings.custom'
  | 'settings.minutes'
  | 'settings.options'
  | 'settings.autoStartNext'
  | 'settings.cyclesCount'
  | 'settings.shortBreak'
  | 'settings.longBreak'
  | 'settings.soundAlerts'
  | 'settings.soundMaster'
  | 'settings.classic'
  | 'settings.gentle'
  | 'action.show'
  | 'action.syncing'
  | 'ble.connected'
  | 'ble.connecting'
  | 'ble.disconnected'
  | 'ble.retry';

const messages: Record<AppLocale, Record<MessageKey, string>> = {
  'zh-CN': {
    'app.title': "\u756a\u8304\u65f6\u949f",
    'landing.subtitle': "\u7528\u4e13\u6ce8\u548c\u4f11\u606f\u5faa\u73af\u4fdd\u6301\u8282\u594f\uff0c\u5e76\u5c06\u8ba1\u65f6\u914d\u7f6e\u540c\u6b65\u5230 PixelMug\u3002",
    'landing.opening': "\u6b63\u5728\u6253\u5f00...",
    'landing.enter': "\u8fdb\u5165\u8bbe\u7f6e",
    'landing.retry': "\u91cd\u8bd5",
    'landing.install': "\u5728 PixelMug \u4e0a\u6253\u5f00",
    'status.browserMock': "\u6d4f\u89c8\u5668\u6a21\u62df\u6a21\u5f0f\u3002",
    'status.loadingDevice': "\u6b63\u5728\u67e5\u627e PixelMug...",
    'status.deviceReady': "PixelMug \u5df2\u5c31\u7eea\u3002",
    'status.deviceMissing': "\u8fd8\u6ca1\u6709\u7ed1\u5b9a PixelMug\u3002",
    'status.opening': "\u6b63\u5728\u6253\u5f00 PixelMug...",
    'status.preparing': "\u6b63\u5728\u51c6\u5907\u5e94\u7528...",
    'status.switching': "\u6b63\u5728\u5207\u6362\u5e94\u7528...",
    'status.launchReady': "PixelMug \u5df2\u51c6\u5907\u597d\u3002",
    'status.connectingBle': "\u6b63\u5728\u8fde\u63a5 BLE...",
    'status.bleConnected': "BLE \u5df2\u8fde\u63a5\u3002",
    'status.syncingSettings': "\u6b63\u5728\u540c\u6b65\u8bbe\u7f6e...",
    'status.syncSuccess': "\u8bbe\u7f6e\u5df2\u540c\u6b65\u5230 PixelMug\u3002\u8bf7\u5355\u51fb\u8bbe\u5907\u5f00\u59cb\u3002",
    'status.syncFailed': "\u540c\u6b65\u5931\u8d25\u3002",
    'status.unknownError': "\u672a\u77e5\u9519\u8bef",
    'summary.breaks': "\u4f11\u606f",
    'summary.cycles': "\u5faa\u73af",
    'summary.restFormat': "\u77ed\u4f11\u606f {short} \u5206\u949f / \u957f\u4f11\u606f {long} \u5206\u949f",
    'unit.min': "\u5206\u949f",
    'settings.focusDuration': "\u4e13\u6ce8\u65f6\u957f",
    'settings.custom': "\u81ea\u5b9a\u4e49",
    'settings.minutes': "\u5206\u949f",
    'settings.options': "\u756a\u8304\u9009\u9879",
    'settings.autoStartNext': "\u81ea\u52a8\u5f00\u59cb\u4e0b\u4e00\u4e2a\u756a\u8304",
    'settings.cyclesCount': "\u5faa\u73af\u6b21\u6570",
    'settings.shortBreak': "\u77ed\u4f11\u606f\uff08\u5206\u949f\uff09",
    'settings.longBreak': "\u957f\u4f11\u606f\uff08\u5206\u949f\uff09",
    'settings.soundAlerts': "\u58f0\u97f3\u4e0e\u63d0\u9192",
    'settings.soundMaster': "\u58f0\u97f3\u603b\u5f00\u5173",
    'settings.classic': "\u7ecf\u5178",
    'settings.gentle': "\u8f7b\u67d4",
    'action.show': "\u540c\u6b65",
    'action.syncing': "\u540c\u6b65\u4e2d...",
    'ble.connected': "BLE \u5df2\u8fde\u63a5",
    'ble.connecting': "\u6b63\u5728\u8fde\u63a5 BLE ({seconds}s)",
    'ble.disconnected': "BLE \u672a\u8fde\u63a5",
    'ble.retry': "\u91cd\u8bd5",
  },
  'en-US': {
    'app.title': 'Pomodoro Timer',
    'landing.subtitle': 'A Pomodoro timer that keeps you focused with balanced work and rest cycles.',
    'landing.opening': 'Opening...',
    'landing.enter': 'Click to Enter',
    'landing.retry': 'Try Again',
    'landing.install': 'Open on PixelMug',
    'status.browserMock': 'Browser mock mode.',
    'status.loadingDevice': 'Loading PixelMug...',
    'status.deviceReady': 'PixelMug ready.',
    'status.deviceMissing': 'No PixelMug is bound.',
    'status.opening': 'Opening on PixelMug...',
    'status.preparing': 'Preparing app...',
    'status.switching': 'Switching app...',
    'status.launchReady': 'Ready on PixelMug.',
    'status.connectingBle': 'Connecting BLE...',
    'status.bleConnected': 'BLE connected.',
    'status.syncingSettings': 'Syncing settings...',
    'status.syncSuccess': 'Settings synced to PixelMug. Tap the device to start.',
    'status.syncFailed': 'Sync failed.',
    'status.unknownError': 'Unknown error',
    'summary.breaks': 'Breaks',
    'summary.cycles': 'Cycles',
    'summary.restFormat': '{short}m short / {long}m long',
    'unit.min': 'min',
    'settings.focusDuration': 'Focus Duration',
    'settings.custom': 'Custom',
    'settings.minutes': 'Minutes',
    'settings.options': 'Pomodoro Options',
    'settings.autoStartNext': 'Auto-start next tomato',
    'settings.cyclesCount': 'Cycles count',
    'settings.shortBreak': 'Short Break (min)',
    'settings.longBreak': 'Long Break (min)',
    'settings.soundAlerts': 'Sound & Alerts',
    'settings.soundMaster': 'Sound Master Switch',
    'settings.classic': 'Classic',
    'settings.gentle': 'Gentle',
    'action.show': 'Show',
    'action.syncing': 'Syncing...',
    'ble.connected': 'BLE connected',
    'ble.connecting': 'Connecting BLE ({seconds}s)',
    'ble.disconnected': 'BLE disconnected',
    'ble.retry': 'Retry',
  },
};

const state = reactive({
  locale: detectLocale(),
});

export const currentLocale = computed(() => state.locale);

export function setLocale(locale: string | null | undefined) {
  state.locale = normalizeLocale(locale);
}

export function t(key: MessageKey, params: Record<string, string | number> = {}) {
  const template = messages[state.locale][key] || messages['en-US'][key] || key;
  return Object.entries(params).reduce(
    (text, [name, value]) => text.split(`{${name}}`).join(String(value)),
    template,
  );
}

function detectLocale(): AppLocale {
  const query = new URLSearchParams(globalThis.location?.search || '');
  return normalizeLocale(
    query.get('lang') ||
      query.get('language') ||
      query.get('locale') ||
      globalThis.navigator?.language,
  );
}

function normalizeLocale(value: string | null | undefined): AppLocale {
  const text = String(value || '').toLowerCase();
  if (text.startsWith('zh')) return 'zh-CN';
  return 'en-US';
}